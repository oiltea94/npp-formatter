#include "bridge_process.hpp"
#include "json.hpp"
#include "i18n.hpp"
#include "parser_selection.hpp"
#include <filesystem>
#include <iostream>

void check(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
int wmain(int argc, wchar_t** argv) {
    try {
        using namespace formatter::i18n;
        check(fromNativeFileName("CHINESESIMPLIFIED.XML") == Language::SimplifiedChinese, "Simplified Chinese selection failed");
        check(fromNativeFileName("localization/taiwaneseMandarin.xml") == Language::TraditionalChinese, "Traditional Chinese selection failed");
        check(fromNativeFileName("hongKongCantonese.xml") == Language::TraditionalChinese, "Hong Kong Chinese selection failed");
        for (auto filename : {"", "english.xml", "english_customizable.xml", "french.xml", "unknown.xml"})
            check(fromNativeFileName(filename) == Language::English, "English fallback failed");
        for (size_t key = 1; key < static_cast<size_t>(Text::Count); ++key)
            for (auto language : {Language::English, Language::SimplifiedChinese, Language::TraditionalChinese})
                check(*get(static_cast<Text>(key), language) != L'\0', "Missing translation");
        std::cout << "PASS host locale selection, English fallback and translation coverage\n";
        for (auto [language, parser] : {std::pair{L_JAVASCRIPT, "babel"}, {L_JS_EMBEDDED, "babel"},
             {L_TYPESCRIPT, "typescript"}, {L_JAVA, "java"}, {L_JSON, "json"}, {L_JSON5, "json5"},
             {L_HTML, "html"}, {L_XML, "xml"}, {L_CSS, "css"}, {L_YAML, "yaml"},
             {L_PHP, "php"}, {L_SQL, "sql"}, {L_PROPS, "dot-properties"}, {L_TOML, "toml"}, {L_BASH, "sh"}})
            check(std::string(formatter::parserForLanguage(language)) == parser, "Host parser mapping failed");
        for (int language : {L_TEXT, L_PYTHON, L_USER, L_EXTERNAL})
            check(formatter::parserForLanguage(language) == nullptr, "Unsupported language was guessed");
        std::cout << "PASS document-language parser mapping and unsupported-language fallback\n";
        check(formatter::sqlDialectIndex(L"missing") == 0, "Invalid SQL dialect must fall back to SQL");
        check(formatter::shellDialectIndex(999) == 0, "Invalid Shell dialect must fall back to Bash");
        for (size_t i = 0; i < std::size(formatter::shellDialects); ++i)
            check(formatter::shellDialectIndex(formatter::shellDialects[i].value) == i, "Shell dialect round trip failed");
        for (size_t i = 0; i < std::size(formatter::sqlDialects); ++i)
            check(formatter::sqlDialectIndex(formatter::sqlDialects[i].value) == i, "SQL dialect setting round trip failed");
        if (argc != 3) throw std::runtime_error("Usage: process_test.exe node.exe fixture.cjs");
        std::atomic<bool> cancel{false};
        const auto cwd = std::filesystem::temp_directory_path().wstring();
        std::vector<std::wstring> arguments{argv[2], L"space here", L"quote\"here", L"trailing\\", L"", L"中文😀", L"& no shell"};
        auto raw = formatter::runProcess(argv[1], arguments, R"({"mode":"arguments","text":"stdin"})", 5000, cancel, cwd);
        auto details = nlohmann::json::parse(raw.output);
        check(raw.exitCode == 0 && details.at("text") == "stdin", "Generic process stdin failed");
        check(std::filesystem::equivalent(formatter::wide(details.at("cwd").get<std::string>()), cwd), "Working directory failed");
        for (size_t i = 1; i < arguments.size(); ++i)
            check(details.at("args").at(i - 1) == formatter::utf8(arguments[i]), "Argument quoting failed");
        std::cout << "PASS generic process arguments, Unicode, working directory and stdin\n";
        auto invoke = [&](const nlohmann::json& request, DWORD timeout = 5000) {
            return formatter::runBridge(argv[1], argv[2], request.dump(), timeout, cancel);
        };
        std::string unicode = u8"中文😀";
        check(formatter::utf8(formatter::wide(unicode)) == unicode, "Unicode round trip failed");
        check(formatter::wide(unicode).size() == 4, "UTF-16 positions are incorrect");
        std::string large;
        for (int i = 0; i < 100000; ++i) large += unicode;
        auto echoed = invoke({{"text", large}});
        check(echoed.exitCode == 0 && echoed.output == large, "Large input/output transfer failed");
        std::cout << "PASS Unicode and large bidirectional pipes\n";
        auto noisy = invoke({{"mode", "stderr"}, {"text", unicode}});
        check(noisy.output == unicode && noisy.error.size() == 256 * 1024, "Concurrent stderr draining failed");
        std::cout << "PASS stderr saturation\n";
        bool timedOut = false;
        try { invoke({{"mode", "hang"}}, 150); }
        catch (const std::exception& e) { timedOut = std::string(e.what()).find("timed out") != std::string::npos; }
        check(timedOut, "Timeout did not terminate Node");
        std::cout << "PASS timeout termination\n";
        cancel = true;
        bool wasCancelled = false;
        try { invoke({{"mode", "hang"}}); }
        catch (const std::exception& e) { wasCancelled = std::string(e.what()).find("cancelled") != std::string::npos; }
        check(wasCancelled, "Cancellation failed");
        cancel = false;
        std::cout << "PASS cancellation\n";
        auto descendant = invoke({{"mode", "descendant"}});
        check(descendant.output == "parent-exited", "Descendant pipe cleanup failed");
        std::cout << "PASS descendant cleanup\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << "FAIL " << error.what() << '\n'; return 1; }
}
