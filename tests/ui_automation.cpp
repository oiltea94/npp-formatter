// Build-only UIA client. Match the editor's architecture, including native ARM64.
// https://learn.microsoft.com/windows/win32/winauto/uiauto-threading
#include "bridge_process.hpp"
#include <uiautomation.h>
#include <wrl/client.h>
#include <iostream>
#include <limits>
#include <sstream>

using Microsoft::WRL::ComPtr;

void check(HRESULT result, const char* operation) {
    if (FAILED(result)) {
        std::ostringstream message;
        message << operation << " failed (HRESULT 0x" << std::hex
                << static_cast<unsigned long>(result) << ')';
        throw std::runtime_error(message.str());
    }
}

struct Apartment {
    Apartment() { check(CoInitializeEx(nullptr, COINIT_MULTITHREADED), "CoInitializeEx(MTA)"); }
    ~Apartment() { CoUninitialize(); }
};

int wmain(int argc, wchar_t** argv) {
    try {
        if (argc < 3 || !((std::wstring(argv[1]) == L"text" && argc == 3) ||
                          (std::wstring(argv[1]) == L"invoke" && argc == 4)))
            throw std::runtime_error("Usage: ui_automation.exe text HWND | invoke HWND NAME");
        size_t consumed = 0;
        auto value = std::stoull(argv[2], &consumed);
        if (consumed != wcslen(argv[2]) || value > std::numeric_limits<UINT_PTR>::max())
            throw std::runtime_error("Invalid window handle");
        auto window = reinterpret_cast<HWND>(static_cast<UINT_PTR>(value));
        if (!IsWindow(window)) throw std::runtime_error("Target window no longer exists");

        // This process owns no windows; every COM call and Release stays in this MTA.
        Apartment apartment;
        ComPtr<IUIAutomation2> automation;
        std::cerr << "UIA: creating native client\n";
        check(CoCreateInstance(__uuidof(CUIAutomation8), nullptr, CLSCTX_INPROC_SERVER,
                               IID_PPV_ARGS(automation.GetAddressOf())), "CoCreateInstance");
        check(automation->put_ConnectionTimeout(5000), "ConnectionTimeout");
        check(automation->put_TransactionTimeout(5000), "TransactionTimeout");
        ComPtr<IUIAutomationElement> root;
        std::cerr << "UIA: locating dialog\n";
        check(automation->ElementFromHandle(window, root.GetAddressOf()), "ElementFromHandle");
        if (!root) throw std::runtime_error("Dialog has no automation element");

        if (std::wstring(argv[1]) == L"text") {
            ComPtr<IUIAutomationCondition> all;
            check(automation->CreateTrueCondition(all.GetAddressOf()), "CreateTrueCondition");
            ComPtr<IUIAutomationCacheRequest> cache;
            check(automation->CreateCacheRequest(cache.GetAddressOf()), "CreateCacheRequest");
            check(cache->AddProperty(UIA_NamePropertyId), "Cache Name property");
            check(cache->put_TreeScope(TreeScope_Element), "Cache TreeScope");
            ComPtr<IUIAutomationElementArray> elements;
            std::cerr << "UIA: enumerating descendants and caching names\n";
            check(root->FindAllBuildCache(TreeScope_Descendants, all.Get(), cache.Get(),
                                         elements.GetAddressOf()), "FindAllBuildCache");
            int count = 0;
            check(elements->get_Length(&count), "Element count");
            for (int i = 0; i < count; ++i) {
                ComPtr<IUIAutomationElement> element;
                check(elements->GetElement(i, element.GetAddressOf()), "GetElement");
                BSTR name = nullptr;
                check(element->get_CachedName(&name), "CachedName");
                std::wstring text(name ? name : L"", SysStringLen(name));
                SysFreeString(name);
                std::cout << formatter::utf8(text) << '\n';
            }
        } else {
            VARIANT name{};
            name.vt = VT_BSTR;
            name.bstrVal = SysAllocString(argv[3]);
            if (!name.bstrVal) throw std::runtime_error("Could not allocate control name");
            ComPtr<IUIAutomationCondition> condition;
            auto result = automation->CreatePropertyCondition(UIA_NamePropertyId, name, condition.GetAddressOf());
            VariantClear(&name);
            check(result, "CreatePropertyCondition");
            ComPtr<IUIAutomationElement> target;
            std::cerr << "UIA: locating control\n";
            check(root->FindFirst(TreeScope_Descendants, condition.Get(), target.GetAddressOf()), "FindFirst");
            if (!target) throw std::runtime_error("Named control was not found");
            ComPtr<IUIAutomationInvokePattern> pattern;
            check(target->GetCurrentPatternAs(UIA_InvokePatternId, IID_PPV_ARGS(pattern.GetAddressOf())), "InvokePattern");
            std::cerr << "UIA: invoking control\n";
            check(pattern->Invoke(), "Invoke");
        }
        std::cerr << "UIA: complete\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "UIA: " << error.what() << '\n';
        return 1;
    }
}
