#pragma once
#include "dependency_discovery.hpp"
#include <algorithm>

namespace formatter {
inline bool pythonFile(const std::wstring& file) {
    auto extension = std::filesystem::path(file).extension().wstring();
    CharLowerBuffW(extension.data(), static_cast<DWORD>(extension.size()));
    return extension == L".py" || extension == L".pyi" || extension == L".pyw";
}

// Ruff has no cursor-map API. Retain positions in unchanged prefixes/suffixes;
// inside changed text, preserve line and UTF-16 column, clamped to a code point.
inline size_t pythonCursor(const std::wstring& before, const std::wstring& after, size_t cursor) {
    cursor = std::min(cursor, before.size());
    size_t prefix = 0, suffix = 0;
    while (prefix < before.size() && prefix < after.size() && before[prefix] == after[prefix]) ++prefix;
    while (suffix < before.size() - prefix && suffix < after.size() - prefix &&
           before[before.size() - suffix - 1] == after[after.size() - suffix - 1]) ++suffix;
    size_t mapped = cursor;
    if (cursor > prefix) {
        if (cursor >= before.size() - suffix) mapped = after.size() - (before.size() - cursor);
        else {
            size_t line = 0, start = 0;
            for (size_t i = 0; i < cursor; ++i) if (before[i] == L'\n') { ++line; start = i + 1; }
            size_t target = 0;
            while (line && target < after.size()) if (after[target++] == L'\n') --line;
            auto end = after.find_first_of(L"\r\n", target);
            if (end == std::wstring::npos) end = after.size();
            mapped = std::min(target + cursor - start, end);
        }
    }
    mapped = std::min(mapped, after.size());
    if (mapped && mapped < after.size() && after[mapped] >= 0xdc00 && after[mapped] <= 0xdfff) --mapped;
    return mapped;
}

inline std::string ruffVersion(const std::wstring& executable, const std::atomic<bool>& cancelled) {
    auto result = runProcess(executable, {L"--version"}, "", 1500, cancelled);
    if (result.exitCode || result.output.rfind("ruff ", 0) != 0)
        throw std::runtime_error("The selected executable did not report a Ruff version. " + result.error);
    while (!result.output.empty() && (result.output.back() == '\r' || result.output.back() == '\n')) result.output.pop_back();
    return result.output;
}

inline std::wstring detectRuff(const std::wstring& current, const std::wstring& file,
                               const std::atomic<bool>& cancelled) {
    namespace fs = std::filesystem;
    std::vector<fs::path> candidates;
    if (fs::path(file).is_absolute()) {
        auto directory = fs::path(file).parent_path();
        while (true) {
            candidates.push_back(directory / L".venv/Scripts/ruff.exe");
            if (directory == directory.parent_path()) break;
            directory = directory.parent_path();
        }
    }
    if (!current.empty()) candidates.push_back(current);
    auto paths = environment(L"PATH");
    for (size_t begin = 0; begin <= paths.size();) {
        auto end = paths.find(L';', begin);
        auto directory = paths.substr(begin, end == std::wstring::npos ? end : end - begin);
        if (directory.size() >= 2 && directory.front() == L'"' && directory.back() == L'"')
            directory = directory.substr(1, directory.size() - 2);
        if (!directory.empty()) candidates.push_back(fs::path(directory) / L"ruff.exe");
        if (end == std::wstring::npos) break;
        begin = end + 1;
    }
    auto profile = environment(L"USERPROFILE");
    if (!profile.empty()) candidates.push_back(fs::path(profile) / L".local/bin/ruff.exe");
    std::set<fs::path> seen;
    auto started = GetTickCount64();
    for (const auto& candidate : candidates) {
        if (cancelled || GetTickCount64() - started >= 10000) break;
        std::error_code ec;
        if (!candidate.is_absolute() || !fs::is_regular_file(candidate, ec) || !seen.insert(candidate).second) continue;
        try { ruffVersion(candidate.wstring(), cancelled); return candidate.wstring(); }
        catch (const std::exception&) { /* Check the next installed candidate. */ }
    }
    throw std::runtime_error("No working Ruff executable found. Install Ruff, restart Notepad++, or use Browse.");
}

inline nlohmann::json formatPython(const std::wstring& executable, const std::string& text,
                                  const std::wstring& file, size_t cursor, const std::string& eol,
                                  DWORD timeout, const std::atomic<bool>& cancelled) {
    namespace fs = std::filesystem;
    std::error_code ec;
    if (!fs::path(executable).is_absolute() || !fs::is_regular_file(executable, ec))
        return {{"ok", false}, {"code", "MISSING_RUFF"}};
    bool saved = fs::path(file).is_absolute();
    std::vector<std::wstring> args{L"format", L"--no-cache", L"--force-exclude", L"--color", L"never"};
    auto name = saved ? file : L"untitled.py";
    if (!saved) {
        args.insert(args.end(), {L"--isolated", L"--config", eol == "crlf" ? L"format.line-ending = 'cr-lf'" : L"format.line-ending = 'lf'"});
    } else if (fs::path(name).extension() != L".py" && fs::path(name).extension() != L".pyi") {
        auto extension = fs::path(name).extension().wstring();
        if (extension.empty()) name += L".py";
        else {
            auto lower = extension;
            CharLowerBuffW(lower.data(), static_cast<DWORD>(lower.size()));
            args.insert(args.end(), {L"--extension", extension.substr(1) + (lower == L".pyi" ? L":pyi" : L":python")});
        }
    }
    args.insert(args.end(), {L"--stdin-filename", name, L"-"});
    auto result = runProcess(executable, args, text, timeout, cancelled, saved ? fs::path(file).parent_path().wstring() : L"");
    if (result.exitCode) {
        return {{"ok", false}, {"error", result.error.empty() ? "Ruff failed (exit " + std::to_string(result.exitCode) + ")." : result.error},
                {"canChooseParser", result.error.find("Failed to parse ") != std::string::npos &&
                    result.error.find("Failed to parse " + utf8(fs::path(name).filename().wstring()) + ":") != std::string::npos}};
    }
    return {{"ok", true}, {"formatted", result.output},
            {"cursorOffset", pythonCursor(wide(text), wide(result.output), cursor)}};
}

inline nlohmann::json checkRuff(const std::wstring& executable, const std::wstring& file,
                              const std::atomic<bool>& cancelled) {
    nlohmann::json report{{"name", "Ruff (Python)"}, {"status", "error"}, {"path", utf8(executable)}};
    std::error_code ec;
    if (executable.empty() || !std::filesystem::is_regular_file(executable, ec)) {
        report["status"] = "missing"; return report;
    }
    try {
        report["version"] = ruffVersion(executable, cancelled);
        // Use a Python probe in the document's directory, preserving config discovery.
        auto probe = std::filesystem::path(file).is_absolute() ? (std::filesystem::path(file).parent_path() / L"__npp_formatter_probe__.py").wstring() : L"";
        auto result = formatPython(executable, "probe=1\n", probe, 0, "lf", 5000, cancelled);
        if (!result.value("ok", false)) throw std::runtime_error(result.value("error", "Ruff sample failed."));
        if (result.at("formatted") == "probe=1\n") throw std::runtime_error("Ruff sample was excluded by project settings; formatting was not verified.");
        report["status"] = "available";
    } catch (const std::exception& error) { report["error"] = error.what(); }
    return report;
}
} // namespace formatter
