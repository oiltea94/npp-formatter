#pragma once
#include <functional>
#include <windows.h>
#include <atomic>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace formatter {
struct Handle {
    HANDLE value = nullptr;
    explicit Handle(HANDLE h = nullptr) : value(h) {}
    ~Handle() { reset(); }
    Handle(const Handle&) = delete;
    Handle& operator=(const Handle&) = delete;
    void reset() { if (value && value != INVALID_HANDLE_VALUE) CloseHandle(value); value = nullptr; }
};

inline std::wstring wide(const std::string& input) {
    if (input.empty()) return {};
    int size = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, input.data(), static_cast<int>(input.size()), nullptr, 0);
    if (!size) throw std::runtime_error("Invalid UTF-8 text.");
    std::wstring result(size, L'\0');
    MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, input.data(), static_cast<int>(input.size()), result.data(), size);
    return result;
}

inline std::string utf8(const std::wstring& input) {
    if (input.empty()) return {};
    int size = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, input.data(), static_cast<int>(input.size()), nullptr, 0, nullptr, nullptr);
    if (!size) throw std::runtime_error("Invalid UTF-16 text.");
    std::string result(size, '\0');
    WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, input.data(), static_cast<int>(input.size()), result.data(), size, nullptr, nullptr);
    return result;
}

inline std::wstring quote(const std::wstring& arg) {
    std::wstring result = L"\"";
    size_t slashes = 0;
    for (wchar_t ch : arg) {
        if (ch == L'\\') { ++slashes; continue; }
        result.append(ch == L'"' ? slashes * 2 + 1 : slashes, L'\\');
        slashes = 0;
        result += ch;
    }
    result.append(slashes * 2, L'\\');
    return result + L'"';
}

struct ProcessResult { DWORD exitCode = 0; std::string output, error; };

inline ProcessResult runProcess(const std::wstring& executable, const std::vector<std::wstring>& arguments,
                               const std::string& input, DWORD timeoutMs,
                               const std::atomic<bool>& cancelled, const std::wstring& directory = {}) {
    SECURITY_ATTRIBUTES security{sizeof(SECURITY_ATTRIBUTES), nullptr, TRUE};
    Handle childIn, parentIn, parentOut, childOut, parentErr, childErr;
    if (!CreatePipe(&childIn.value, &parentIn.value, &security, 0) ||
        !CreatePipe(&parentOut.value, &childOut.value, &security, 0) ||
        !CreatePipe(&parentErr.value, &childErr.value, &security, 0))
        throw std::runtime_error("Could not create formatter pipes.");
    for (HANDLE handle : {parentIn.value, parentOut.value, parentErr.value})
        if (!SetHandleInformation(handle, HANDLE_FLAG_INHERIT, 0))
            throw std::runtime_error("Could not configure formatter pipes.");

    SIZE_T bytes = 0;
    InitializeProcThreadAttributeList(nullptr, 1, 0, &bytes);
    std::vector<unsigned char> storage(bytes);
    auto attributes = reinterpret_cast<LPPROC_THREAD_ATTRIBUTE_LIST>(storage.data());
    if (!InitializeProcThreadAttributeList(attributes, 1, 0, &bytes))
        throw std::runtime_error("Could not initialize process attributes.");
    struct AttributesCleanup {
        LPPROC_THREAD_ATTRIBUTE_LIST ptr;
        ~AttributesCleanup() { DeleteProcThreadAttributeList(ptr); }
    } cleanup{attributes};
    HANDLE inherited[]{childIn.value, childOut.value, childErr.value};
    if (!UpdateProcThreadAttribute(attributes, 0, PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
                                  inherited, sizeof(inherited), nullptr, nullptr))
        throw std::runtime_error("Could not restrict inherited handles.");

    Handle job(CreateJobObjectW(nullptr, nullptr));
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    if (!job.value || !SetInformationJobObject(job.value, JobObjectExtendedLimitInformation, &limits, sizeof(limits)))
        throw std::runtime_error("Could not initialize the formatter process job.");
    STARTUPINFOEXW startup{};
    startup.StartupInfo.cb = sizeof(startup);
    startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES;
    startup.StartupInfo.hStdInput = childIn.value;
    startup.StartupInfo.hStdOutput = childOut.value;
    startup.StartupInfo.hStdError = childErr.value;
    startup.lpAttributeList = attributes;
    PROCESS_INFORMATION process{};
    std::wstring command = quote(executable);
    for (const auto& argument : arguments) command += L" " + quote(argument);
    if (!CreateProcessW(executable.c_str(), command.data(), nullptr, nullptr, TRUE,
                        CREATE_NO_WINDOW | CREATE_SUSPENDED | EXTENDED_STARTUPINFO_PRESENT,
                        nullptr, directory.empty() ? nullptr : directory.c_str(), &startup.StartupInfo, &process))
        throw std::runtime_error("Could not start formatter (Windows error " + std::to_string(GetLastError()) + "). Check Settings.");
    Handle processHandle(process.hProcess), threadHandle(process.hThread);
    if (!AssignProcessToJobObject(job.value, processHandle.value)) {
        TerminateProcess(processHandle.value, 1);
        throw std::runtime_error("Could not assign formatter to its process job.");
    }
    childIn.reset(); childOut.reset(); childErr.reset();
    ProcessResult result;
    std::atomic<bool> overflow{false};
    std::atomic<bool> writeFailed{false};
    auto read = [&](HANDLE pipe, std::string& destination) {
        char buffer[8192]; DWORD count = 0;
        while (ReadFile(pipe, buffer, sizeof(buffer), &count, nullptr) && count) {
            if (destination.size() + count > 64 * 1024 * 1024) { overflow = true; break; }
            destination.append(buffer, count);
        }
    };
    // All pipe directions run concurrently: large requests and stderr cannot deadlock.
    std::thread writer, outReader, errReader;
    try {
        writer = std::thread([&] {
            size_t offset = 0;
            while (offset < input.size()) {
                DWORD count = 0;
                DWORD chunk = static_cast<DWORD>((input.size() - offset > 8192) ? 8192 : input.size() - offset);
                if (!WriteFile(parentIn.value, input.data() + offset, chunk, &count, nullptr) || !count) {
                    writeFailed = true; break;
                }
                offset += count;
            }
            parentIn.reset();
        });
        outReader = std::thread(read, parentOut.value, std::ref(result.output));
        errReader = std::thread(read, parentErr.value, std::ref(result.error));
    } catch (...) {
        TerminateJobObject(job.value, 1);
        if (writer.joinable()) writer.join();
        if (outReader.joinable()) outReader.join();
        if (errReader.joinable()) errReader.join();
        throw;
    }
    bool timedOut = false, failedWait = false;
    ULONGLONG started = GetTickCount64();
    if (ResumeThread(threadHandle.value) == static_cast<DWORD>(-1)) failedWait = true;
    while (!failedWait) {
        DWORD wait = WaitForSingleObject(processHandle.value, 25);
        if (wait == WAIT_OBJECT_0) break;
        if (wait == WAIT_FAILED) { failedWait = true; break; }
        if (cancelled || overflow) break;
        if (GetTickCount64() - started >= timeoutMs) { timedOut = true; break; }
    }
    // Also close descendants that may have inherited a pipe after the tool exits.
    TerminateJobObject(job.value, 1);
    WaitForSingleObject(processHandle.value, INFINITE);
    GetExitCodeProcess(processHandle.value, &result.exitCode);
    writer.join(); outReader.join(); errReader.join();
    if (cancelled) throw std::runtime_error("Formatting cancelled.");
    if (timedOut) throw std::runtime_error("Formatting timed out. Increase the timeout in Settings if necessary.");
    if (overflow) throw std::runtime_error("Formatter response exceeded 64 MiB.");
    if (failedWait) throw std::runtime_error("Failed to wait for formatter.");
    if (writeFailed && result.output.empty()) throw std::runtime_error("Formatter closed its input unexpectedly. " + result.error);
    return result;
}
inline ProcessResult runBridge(const std::wstring& node, const std::wstring& bridge,
                               const std::string& input, DWORD timeoutMs,
                               const std::atomic<bool>& cancelled) {
    return runProcess(node, {bridge}, input, timeoutMs, cancelled);
}
} // namespace formatter
