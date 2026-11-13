#include "clang_format_adapter.hpp"
#include <fstream>
#include <iostream>

void check(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
int wmain(int argc, wchar_t** argv) {
    namespace fs = std::filesystem;
    try {
        if (argc != 2) throw std::runtime_error("Usage: clang_format_test.exe clang-format.exe");
        auto project = fs::temp_directory_path() / (L"npp-clang-中文 " + std::to_wstring(GetCurrentProcessId()));
        fs::create_directories(project / L"nested");
        struct Cleanup { fs::path path; ~Cleanup() { std::error_code ec; fs::remove_all(path, ec); } } cleanup{project};
        auto write = [&](const fs::path& name, const std::string& data) { std::ofstream(project / name, std::ios::binary) << data; };
        std::atomic<bool> cancel{false};
        auto format = [&](const std::string& text, const std::wstring& file = L"", const std::wstring& style = L"LLVM", size_t cursor = 0) {
            return formatter::formatCpp(argv[1], text, file, cursor, style, 5000, cancel);
        };
        check(formatter::clangFormatVersion(argv[1], cancel).find("clang-format version ") != std::string::npos, "Version validation failed");
        std::string source = u8"// 中文😀\nint main(){return 42;}\n";
        std::string expected = u8"// 中文😀\nint main() { return 42; }\n";
        auto result = format(source, L"", L"LLVM", formatter::wide(source.substr(0, source.find("42"))).size());
        check(result.at("ok") && result.at("formatted") == expected, "C++ Unicode formatting failed");
        check(formatter::utf8(formatter::wide(expected).substr(result.at("cursorOffset").get<size_t>())).find("42") == 0, "Native cursor mapping failed");
        check(format(expected).at("formatted") == expected, "Idempotence failed");
        check(format("").at("formatted") == "", "Empty input failed");
        check(format("int x=1;\r\n").at("formatted") == "int x = 1;\r\n", "CRLF failed");
        check(format("int x=1;\n", L"", L"Microsoft").at("ok"), "Microsoft fallback failed");
        std::cout << "PASS clang-format Unicode, native cursor, empty input, no-op and CRLF\n";
        write(L".clang-format", "BasedOnStyle: LLVM\nIndentWidth: 6\nAllowShortFunctionsOnASingleLine: None\n");
        auto file = (project / L"nested/source.cpp").wstring();
        write(L"nested/source.cpp", "disk unchanged\n");
        auto configured = format("int main(){return 42;}\n", file, L"Google");
        check(configured.at("formatted") == "int main() {\n      return 42;\n}\n", "Ancestor project configuration did not override fallback");
        std::ifstream disk(fs::path(file), std::ios::binary);
        check(std::string(std::istreambuf_iterator<char>(disk), {}) == "disk unchanged\n", "Source file was written");
        const auto oldCwd = fs::current_path();
        fs::current_path(project);
        auto isolated = format("int main(){return 42;}\n");
        fs::current_path(oldCwd);
        check(isolated.at("formatted") == "int main() { return 42; }\n", "Untitled input inherited working-directory config");
        check(format("int main(){return 42;}\n", (project / L"override.java").wstring()).at("formatted") == configured.at("formatted"), "Explicit C++ override inferred Java");
        for (auto name : {L"app.c", L"app.cpp", L"app.cc", L"app.cxx", L"types.h", L"types.hpp", L"types.hh", L"types.hxx", L"APP.CPP"})
            check(formatter::cppFile(name), "C/C++ extension routing failed");
        check(!formatter::cppFile(L"Main.java") && !formatter::cppFile(L"app.cs"), "Other language hijacked");
        std::cout << "PASS clang-format project precedence, disk preservation, isolation, overrides and routing\n";
        auto invalid = format("int main( {\n");
        check(!invalid.at("ok") && invalid.at("canChooseParser") && !invalid.contains("formatted"), "Incomplete formatting accepted");
        check(invalid.at("error").get<std::string>().find("line 1") != std::string::npos, "Incomplete formatting line diagnostic lost");
        write(L".clang-format", "InvalidSetting: true\n");
        check(!format(source, file).at("ok"), "Invalid config accepted");
        check(formatter::checkClangFormat(argv[1], file, L"LLVM", cancel).at("status") == "error", "Environment ignored bad project config");
        check(formatter::formatCpp(L"", source, L"", 0, L"LLVM", 5000, cancel).at("code") == "MISSING_CLANG_FORMAT", "Missing executable guidance failed");
        check(formatter::checkClangFormat(argv[1], L"", L"LLVM", cancel).at("status") == "available", "Environment sample failed");
        check(fs::equivalent(formatter::detectClangFormat(argv[1], cancel), argv[1]), "Current executable detection failed");
        // Keep the executable beside its DLLs; test a quoted PATH entry without
        // making an invalid partial copy of the installed toolchain.
        auto toolDirectory = fs::absolute(argv[1]).parent_path();
        const auto originalPath = formatter::environment(L"PATH");
        struct RestorePath { std::wstring value; ~RestorePath() { SetEnvironmentVariableW(L"PATH", value.c_str()); } } restorePath{originalPath};
        SetEnvironmentVariableW(L"PATH", (L"\"" + toolDirectory.wstring() + L"\"").c_str());
        check(fs::equivalent(formatter::detectClangFormat(L"", cancel), toolDirectory / L"clang-format.exe"), "Quoted PATH discovery failed");
        check(fs::equivalent(formatter::detectClangFormat((project / L"missing.exe").wstring(), cancel), toolDirectory / L"clang-format.exe"), "Detection failed to recover from stale field");
        write(L".clang-format", "DisableFormat: true\n");
        check(formatter::checkClangFormat(argv[1], file, L"LLVM", cancel).at("status") == "error", "Disabled formatting falsely reported available");
        std::cout << "PASS clang-format diagnostics, missing tool, detection and environment probe\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << "FAIL " << error.what() << '\n'; return 1; }
}
