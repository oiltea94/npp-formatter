#pragma once
#include <filesystem>
#include <set>
#include "bridge_process.hpp"
#include "json.hpp"

namespace formatter {
inline std::wstring environment(const wchar_t* name) {
    DWORD size = GetEnvironmentVariableW(name, nullptr, 0);
    if (!size) return {};
    std::wstring value(size, L'\0');
    DWORD written = GetEnvironmentVariableW(name, value.data(), size);
    if (!written || written >= size) return {};
    value.resize(written);
    return value;
}

inline std::vector<std::wstring> nodeCandidates(const std::wstring& current) {
    namespace fs = std::filesystem;
    std::vector<std::wstring> result;
    std::set<std::wstring> seen;
    auto add = [&](const fs::path& executable) {
        std::error_code error;
        if (!executable.is_absolute() || !fs::is_regular_file(executable, error)) return;
        auto name = executable.lexically_normal().wstring();
        auto key = name;
        CharLowerBuffW(key.data(), static_cast<DWORD>(key.size()));
        if (seen.insert(key).second) result.push_back(name);
    };
    auto paths = environment(L"PATH");
    size_t begin = 0;
    while (begin <= paths.size()) {
        auto end = paths.find(L';', begin);
        auto directory = paths.substr(begin, end == std::wstring::npos ? end : end - begin);
        if (directory.size() >= 2 && directory.front() == L'"' && directory.back() == L'"')
            directory = directory.substr(1, directory.size() - 2);
        if (!directory.empty()) add(fs::path(directory) / L"node.exe");
        if (end == std::wstring::npos) break;
        begin = end + 1;
    }
    for (auto name : {L"NVM_SYMLINK", L"VOLTA_HOME", L"ProgramW6432", L"ProgramFiles", L"ProgramFiles(x86)", L"LOCALAPPDATA"}) {
        auto base = environment(name);
        if (base.empty()) continue;
        fs::path directory(base);
        if (wcscmp(name, L"VOLTA_HOME") == 0) directory /= L"bin";
        else if (wcscmp(name, L"LOCALAPPDATA") == 0) directory /= L"Programs/nodejs";
        else if (wcscmp(name, L"NVM_SYMLINK") != 0) directory /= L"nodejs";
        add(directory / L"node.exe");
    }
    if (!current.empty()) add(current);
    return result;
}

inline std::wstring detectNode(const std::wstring& current, const std::wstring& bridge,
                               const std::atomic<bool>& cancelled) {
    namespace fs = std::filesystem;
    auto started = GetTickCount64();
    for (const auto& candidate : nodeCandidates(current)) {
        if (cancelled || GetTickCount64() - started >= 10000) break;
        try {
            auto process = runBridge(candidate, bridge, R"({"operation":"detectNode"})", 1500, cancelled);
            auto response = nlohmann::json::parse(process.output);
            if (process.exitCode != 0 || !response.value("ok", false)) continue;
            auto actual = wide(response.at("nodePath").get<std::string>());
            if (fs::path(actual).is_absolute() && fs::is_regular_file(actual)) return actual;
        } catch (const std::exception&) { /* Try the next installed executable. */ }
    }
    throw std::runtime_error("No working Node.js 18+ installation found. Install Node.js, restart Notepad++, or use Browse.");
}
} // namespace formatter
