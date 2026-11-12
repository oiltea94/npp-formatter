#include "bridge_process.hpp"
#include "json.hpp"
#include <filesystem>
#include <iostream>

void check(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
int wmain(int argc, wchar_t** argv) {
    try {
        if (argc != 3) throw std::runtime_error("Usage: process_test.exe node.exe fixture.cjs");
        std::atomic<bool> cancel{false};
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
