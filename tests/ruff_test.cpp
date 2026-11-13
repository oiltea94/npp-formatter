#include "ruff_adapter.hpp"
#include <fstream>
#include <iostream>

void check(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
int wmain(int argc, wchar_t** argv) {
    namespace fs = std::filesystem;
    fs::path project;
    try {
        if (argc != 2) throw std::runtime_error("Usage: ruff_test.exe ruff.exe");
        project = fs::temp_directory_path() / (L"npp-ruff-中文 " + std::to_wstring(GetCurrentProcessId()));
        fs::create_directories(project);
        struct Cleanup { fs::path path; ~Cleanup() { std::error_code ec; fs::remove_all(path, ec); } } cleanup{project};
        auto write = [&](const fs::path& name, const std::string& data) { std::ofstream(project / name, std::ios::binary) << data; };
        std::atomic<bool> cancel{false};
        auto format = [&](const std::string& text, const std::wstring& file = L"", const std::string& eol = "lf", size_t cursor = 0) {
            auto response = formatter::formatPython(argv[1], text, file, cursor, eol, 5000, cancel);
            return response;
        };
        auto version = formatter::ruffVersion(argv[1], cancel);
        check(version.find("ruff ") == 0, "Ruff version validation failed");
        auto source = std::string(u8"emoji='中文😀'\nanswer=42\n");
        auto expected = std::string(u8"emoji = \"中文😀\"\nanswer = 42\n");
        auto result = format(source, L"", "lf", formatter::wide(source.substr(0, source.find("answer"))).size());
        check(result.at("ok") && result.at("formatted") == expected, "Python Unicode formatting failed");
        auto mapped = result.at("cursorOffset").get<size_t>();
        check(formatter::utf8(formatter::wide(expected).substr(mapped)).find("answer") == 0, "Caret line mapping failed");
        check(format(expected).at("formatted") == expected, "Python formatting is not idempotent");
        check(format("").at("formatted") == "", "Empty input failed");
        check(format("x=1\r\n", L"", "crlf").at("formatted") == "x = 1\r\n", "CRLF failed");
        std::cout << "PASS Ruff Unicode, caret fallback, empty input, no-op and CRLF\n";
        write(L"ruff.toml", "line-length = 80\nexclude = [\"skip.py\"]\n[format]\nquote-style = \"single\"\nline-ending = \"cr-lf\"\n");
        write(L"source.py", "disk must stay unchanged\n");
        auto saved = format("name=\"value\"\n", (project / L"source.py").wstring());
        check(saved.at("formatted") == "name = 'value'\r\n", "Project configuration failed");
        std::ifstream disk(project / L"source.py", std::ios::binary);
        check(std::string(std::istreambuf_iterator<char>(disk), {}) == "disk must stay unchanged\n", "Formatter changed saved file");
        check(format("x=1\n", (project / L"skip.py").wstring()).at("formatted") == "x=1\n", "Exclude failed");
        check(format("name='value'\n").at("formatted") == "name = \"value\"\n", "Untitled input inherited project config");
        check(format("x=1\n", (project / L"override.txt").wstring()).at("formatted") == "x = 1\r\n", "Explicit Python override failed");
        check(format("x:int=1\n", (project / L"types.pyi").wstring()).at("ok"), "Python stubs failed");
        for (auto name : {L"SCRIPT.PY", L"GUI.PYW", L"types.PYI"})
            check(format("x=1\n", (project / name).wstring()).at("formatted") == "x = 1\r\n", "Case-insensitive extension failed");
        std::cout << "PASS Ruff project configuration, excludes, disk preservation, override and stubs\n";
        auto invalid = format("def broken(:\n");
        check(!invalid.at("ok") && invalid.at("canChooseParser") && !invalid.contains("formatted"), "Syntax failure was accepted");
        check(invalid.at("error").get<std::string>().find("Failed to parse") != std::string::npos, "Original diagnostic lost");
        write(L"ruff.toml", "invalid = [\n");
        auto badConfig = format("x=1\n", (project / L"source.py").wstring());
        check(!badConfig.at("ok") && !badConfig.at("canChooseParser"), "Bad config reported as syntax error");
        check(formatter::formatPython(L"", "x=1", L"", 0, "lf", 5000, cancel).at("code") == "MISSING_RUFF", "Missing executable guidance failed");
        auto report = formatter::checkRuff(argv[1], (project / L"source.py").wstring(), cancel);
        check(report.at("status") == "error" && report.contains("version"), "Environment check missed broken configuration");
        fs::remove(project / L"ruff.toml");
        write(L"pyproject.toml", "[tool.ruff.format]\nquote-style = 'single'\n");
        check(format("s=\"text\"\n", (project / L"source.py").wstring()).at("formatted") == "s = 'text'\n", "pyproject.toml discovery failed");
        write(L".ruff.toml", "[format]\nquote-style = 'double'\n");
        check(format("s='text'\n", (project / L"source.py").wstring()).at("formatted") == "s = \"text\"\n", ".ruff.toml precedence failed");
        check(formatter::checkRuff(argv[1], L"", cancel).at("status") == "available", "Ruff environment sample failed");
        auto local = project / L".venv/Scripts";
        fs::create_directories(local);
        fs::copy_file(argv[1], local / L"ruff.exe");
        check(fs::equivalent(formatter::detectRuff(L"", (project / L"source.py").wstring(), cancel), local / L"ruff.exe"), "Project .venv discovery failed");
        check(formatter::pythonFile(L"SAMPLE.PY") && formatter::pythonFile(L"types.pyi") && formatter::pythonFile(L"app.pyw") &&
              !formatter::pythonFile(L"notebook.ipynb"), "Python extension routing failed");
        std::cout << "PASS Ruff diagnostics, missing tool, environment and project discovery\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << "FAIL " << error.what() << '\n'; return 1; }
}
