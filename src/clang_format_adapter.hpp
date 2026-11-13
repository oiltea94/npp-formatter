#pragma once
#include "dependency_discovery.hpp"

namespace formatter {
inline bool cppFile(const std::wstring& file) {
    auto extension = std::filesystem::path(file).extension().wstring();
    CharLowerBuffW(extension.data(), static_cast<DWORD>(extension.size()));
    return extension == L".c" || extension == L".cpp" || extension == L".cc" || extension == L".cxx" ||
           extension == L".h" || extension == L".hpp" || extension == L".hh" || extension == L".hxx";
}
inline std::wstring clangStyle(const std::wstring& value) {
    return value == L"Google" || value == L"Microsoft" ? value : L"LLVM";
}
inline std::string clangFormatVersion(const std::wstring& executable, const std::atomic<bool>& cancelled) {
    auto result = runProcess(executable, {L"--version"}, "", 1500, cancelled);
    if (result.exitCode || result.output.find("clang-format version ") == std::string::npos)
        throw std::runtime_error("The selected executable did not report a clang-format version. " + result.error);
    while (!result.output.empty() && (result.output.back() == '\r' || result.output.back() == '\n')) result.output.pop_back();
    return result.output;
}
inline std::wstring detectClangFormat(const std::wstring& current, const std::atomic<bool>& cancelled) {
    namespace fs = std::filesystem;
    std::vector<fs::path> candidates;
    if (!current.empty()) candidates.push_back(current);
    auto paths = environment(L"PATH");
    for (size_t begin = 0; begin <= paths.size();) {
        auto end = paths.find(L';', begin);
        auto directory = paths.substr(begin, end == std::wstring::npos ? end : end - begin);
        if (directory.size() >= 2 && directory.front() == L'"' && directory.back() == L'"')
            directory = directory.substr(1, directory.size() - 2);
        if (!directory.empty()) candidates.push_back(fs::path(directory) / L"clang-format.exe");
        if (end == std::wstring::npos) break;
        begin = end + 1;
    }
    for (auto key : {L"ProgramW6432", L"ProgramFiles", L"ProgramFiles(x86)"}) {
        auto folder = environment(key);
        if (!folder.empty()) candidates.push_back(fs::path(folder) / L"LLVM/bin/clang-format.exe");
    }
    std::set<fs::path> seen;
    auto started = GetTickCount64();
    for (const auto& candidate : candidates) {
        if (cancelled || GetTickCount64() - started >= 10000) break;
        std::error_code ec;
        if (!candidate.is_absolute() || !fs::is_regular_file(candidate, ec) || !seen.insert(candidate).second) continue;
        try { clangFormatVersion(candidate.wstring(), cancelled); return candidate.wstring(); }
        catch (const std::exception&) { /* Check the next installed candidate. */ }
    }
    throw std::runtime_error("No working clang-format executable found. Install LLVM, restart Notepad++, or use Browse.");
}
inline nlohmann::json formatCpp(const std::wstring& executable, const std::string& text,
                               const std::wstring& file, size_t cursor, const std::wstring& fallback,
                               DWORD timeout, const std::atomic<bool>& cancelled) {
    namespace fs = std::filesystem;
    std::error_code ec;
    if (!fs::path(executable).is_absolute() || !fs::is_regular_file(executable, ec))
        return {{"ok", false}, {"code", "MISSING_CLANG_FORMAT"}};
    if (text.empty()) return {{"ok", true}, {"formatted", ""}, {"cursorOffset", 0}};
    bool saved = fs::path(file).is_absolute();
    // Use a C++ suffix even for explicit overrides of Java/JSON/etc.; retain the
    // parent directory so clang-format still discovers the project's settings.
    auto name = saved ? file : L"untitled.cpp";
    if (!cppFile(name)) name += L".cpp";
    auto byteCursor = utf8(wide(text).substr(0, cursor)).size();
    std::vector<std::wstring> args{
        L"--assume-filename=" + name, L"--cursor=" + std::to_wstring(byteCursor),
        L"--style=" + (saved ? std::wstring(L"file") : clangStyle(fallback)),
        L"--fallback-style=" + clangStyle(fallback), L"--fail-on-incomplete-format"};
    auto result = runProcess(executable, args, text, timeout, cancelled, saved ? fs::path(file).parent_path().wstring() : L"");
    // --cursor prepends one JSON line; clang-format counts UTF-8 bytes, whereas
    // the shared plugin completion protocol counts UTF-16 code units.
    auto end = result.output.find('\n');
    if (result.exitCode && (end == std::string::npos || !result.error.empty()))
        return {{"ok", false}, {"error", result.error.empty() ? "clang-format failed (exit " + std::to_string(result.exitCode) + ")." : result.error}};
    if (end == std::string::npos) throw std::runtime_error("clang-format returned no cursor metadata.");
    auto metadata = nlohmann::json::parse(result.output.substr(0, end));
    if (metadata.value("IncompleteFormat", false))
        return {{"ok", false}, {"canChooseParser", true},
                {"error", "clang-format: incomplete formatting at line " + std::to_string(metadata.value("Line", 0)) + ". Check the syntax or selected language; the original text is unchanged."}};
    if (result.exitCode) return {{"ok", false}, {"error", "clang-format failed (exit " + std::to_string(result.exitCode) + ")."}};
    auto formatted = result.output.substr(end + 1);
    auto position = metadata.at("Cursor").get<int64_t>();
    if (position < 0 || static_cast<size_t>(position) > formatted.size())
        throw std::runtime_error("clang-format returned an invalid cursor position.");
    // Strict decoding also rejects a cursor inside a multibyte character.
    auto mapped = wide(formatted.substr(0, static_cast<size_t>(position))).size();
    return {{"ok", true}, {"formatted", formatted}, {"cursorOffset", mapped}};
}
inline nlohmann::json checkClangFormat(const std::wstring& executable, const std::wstring& file,
                                     const std::wstring& fallback, const std::atomic<bool>& cancelled) {
    nlohmann::json report{{"name", "clang-format (C/C++)"}, {"status", "error"}, {"path", utf8(executable)}};
    std::error_code ec;
    if (executable.empty() || !std::filesystem::is_regular_file(executable, ec)) {
        report["status"] = "missing"; return report;
    }
    try {
        report["version"] = clangFormatVersion(executable, cancelled);
        auto probe = std::filesystem::path(file).is_absolute() ?
            (std::filesystem::path(file).parent_path() / L"__npp_formatter_probe__.cpp").wstring() : L"";
        auto result = formatCpp(executable, "int probe=1;\n", probe, 0, fallback, 5000, cancelled);
        if (!result.value("ok", false)) throw std::runtime_error(result.value("error", "clang-format sample failed."));
        if (result.at("formatted") == "int probe=1;\n") throw std::runtime_error("clang-format sample was unchanged; formatting may be disabled by project settings and was not verified.");
        report["status"] = "available";
    } catch (const std::exception& error) { report["error"] = error.what(); }
    return report;
}
} // namespace formatter
