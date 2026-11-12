#include <windows.h>
#include <commdlg.h>
#include <commctrl.h>
#include <shellapi.h>
#include <filesystem>
#include <fstream>
#include <memory>
#include <unordered_map>
#include "PluginInterface.h"
#include "json.hpp"
#include "bridge_process.hpp"
#include "dependency_discovery.hpp"
#include "i18n.hpp"
#include "parser_selection.hpp"

namespace fs = std::filesystem;
using nlohmann::json;
using formatter::utf8;
using formatter::wide;
using formatter::i18n::Text;
using formatter::i18n::Language;
namespace {
HINSTANCE instance;
NppData host;
HWND timerWindow = nullptr, settingsWindow = nullptr;
fs::path pluginDirectory, configPath;
std::thread worker;
std::atomic<bool> cancelled{false}, finished{false};
uint64_t generation = 0;
bool shuttingDown = false;
struct Settings { std::wstring node, prettier; DWORD timeoutMs = 10000; };
Settings settings;
struct DocumentParser { std::string parser; LRESULT document; };
std::unordered_map<UINT_PTR, DocumentParser> documentParsers;
LRESULT applyingDocument = 0;
bool choosingParser = false;
struct Request {
    HWND editor;
    UINT_PTR bufferId;
    LRESULT document;
    uint64_t generation;
    LRESULT cursor, anchor;
    std::string text, payload;
    bool rememberChoice = false;
};
struct Completion { Request request; json response; std::string error; };
std::unique_ptr<Completion> completion;
FuncItem commands[4];
std::thread detectionWorker;
std::atomic<bool> detectionCancelled{false}, detectionFinished{false};
struct DetectionResult { int field; std::wstring path, error; };
DetectionResult detectionResult;
Language uiLanguage = Language::English;
Text lastStatus = Text::Empty, detectionStatus = Text::Empty;
std::wstring detectionDetails;
const wchar_t* tr(Text key) { return formatter::i18n::get(key, uiLanguage); }

LRESULT sci(HWND editor, UINT message, WPARAM w = 0, LPARAM l = 0) {
    return SendMessageW(editor, message, w, l);
}
void status(Text key) {
    lastStatus = key;
    SendMessageW(host._nppHandle, NPPM_SETSTATUSBAR, STATUSBAR_DOC_TYPE, reinterpret_cast<LPARAM>(tr(key)));
}
void showError(const std::string& text) {
    std::wstring message;
    try { message = wide(text); }
    catch (...) { message = L"The operation failed; its diagnostic text is not valid UTF-8."; }
    MessageBoxW(settingsWindow ? settingsWindow : host._nppHandle, message.c_str(), tr(Text::ErrorTitle), MB_OK | MB_ICONERROR);
}
std::wstring controlText(HWND window, int id) {
    HWND control = GetDlgItem(window, id);
    std::wstring text(GetWindowTextLengthW(control) + 1, L'\0');
    GetWindowTextW(control, text.data(), static_cast<int>(text.size()));
    text.resize(wcslen(text.c_str()));
    return text;
}
std::wstring readSetting(const wchar_t* key, const wchar_t* fallback) {
    std::vector<wchar_t> value(32768);
    GetPrivateProfileStringW(L"Formatter", key, fallback, value.data(), static_cast<DWORD>(value.size()), configPath.c_str());
    return value.data();
}
void loadSettings() {
    settings.node = readSetting(L"NodePath", L"");
    settings.prettier = readSetting(L"PrettierPath", L"");
    settings.timeoutMs = GetPrivateProfileIntW(L"Formatter", L"TimeoutMs", 10000, configPath.c_str());
    if (settings.timeoutMs < 1000 || settings.timeoutMs > 120000) settings.timeoutMs = 10000;
}
void saveSettings(const Settings& next) {
    fs::create_directories(configPath.parent_path());
    fs::path temporary = configPath; temporary += L".tmp";
    { std::ofstream file(temporary, std::ios::binary | std::ios::trunc);
      file.write("\xff\xfe", 2);
      if (!file) throw std::runtime_error(utf8(tr(Text::CreateSettingsError))); }
    auto write = [&](const wchar_t* key, const std::wstring& value) {
        if (!WritePrivateProfileStringW(L"Formatter", key, value.c_str(), temporary.c_str()))
            throw std::runtime_error(utf8(tr(Text::WriteSettingsError)));
    };
    write(L"NodePath", next.node); write(L"PrettierPath", next.prettier);
    write(L"TimeoutMs", std::to_wstring(next.timeoutMs));
    WritePrivateProfileStringW(nullptr, nullptr, nullptr, temporary.c_str());
    if (fs::exists(configPath)) {
        fs::path backup = configPath; backup += L".bak";
        fs::copy_file(configPath, backup, fs::copy_options::overwrite_existing);
    }
    if (!MoveFileExW(temporary.c_str(), configPath.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH))
        throw std::runtime_error(utf8(tr(Text::ReplaceSettingsError)));
    settings = next;
}
void addControl(HWND parent, const wchar_t* kind, const wchar_t* text,
                DWORD style, int x, int y, int width, int height, int id) {
    HWND control = CreateWindowExW(wcscmp(kind, L"EDIT") == 0 ? WS_EX_CLIENTEDGE : 0,
        kind, text, WS_CHILD | WS_VISIBLE | style, x, y, width, height,
        parent, reinterpret_cast<HMENU>(static_cast<INT_PTR>(id)), instance, nullptr);
    SendMessageW(control, WM_SETFONT, reinterpret_cast<WPARAM>(GetStockObject(DEFAULT_GUI_FONT)), TRUE);
}
void browse(HWND window, bool node) {
    wchar_t path[32768]{};
    OPENFILENAMEW dialog{};
    dialog.lStructSize = sizeof(dialog); dialog.hwndOwner = window;
    dialog.lpstrFile = path; dialog.nMaxFile = 32768;
    dialog.lpstrFilter = tr(node ? Text::NodeFilter : Text::PrettierFilter);
    dialog.Flags = OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST | OFN_NOCHANGEDIR;
    if (GetOpenFileNameW(&dialog)) {
        std::wstring selected = node ? std::wstring(path) : fs::path(path).parent_path().wstring();
        SetDlgItemTextW(window, node ? 101 : 102, selected.c_str());
    }
}
void setDetectionStatus(HWND window, Text key, const std::wstring& details = {}) {
    detectionStatus = key;
    detectionDetails = details;
    std::wstring message = tr(key);
    if (!details.empty()) message += L"\r\n" + details;
    SetDlgItemTextW(window, 105, message.c_str());
}
void updateSettingsLanguage(HWND window) {
    SetWindowTextW(window, tr(Text::SettingsTitle));
    const std::pair<int, Text> controls[] = {
        {301, Text::NodeLabel}, {302, Text::PrettierLabel}, {304, Text::TimeoutLabel},
        {201, Text::Browse}, {202, Text::Browse}, {203, Text::Detect}, {204, Text::Detect},
        {IDOK, Text::Save}, {IDCANCEL, Text::Cancel}
    };
    for (auto [id, key] : controls) SetDlgItemTextW(window, id, tr(key));
    setDetectionStatus(window, detectionStatus, detectionDetails);
}
bool updateMenuLabel(HMENU menu, UINT command, const wchar_t* label) {
    for (int i = 0; i < GetMenuItemCount(menu); ++i) {
        if (GetMenuItemID(menu, i) == command) {
            // Keep Shortcut Mapper's displayed key combination and all item state.
            wchar_t existing[256]{};
            GetMenuStringW(menu, i, existing, 256, MF_BYPOSITION);
            std::wstring text(label);
            if (auto shortcut = wcschr(existing, L'\t')) text += shortcut;
            MENUITEMINFOW item{}; item.cbSize = sizeof(item); item.fMask = MIIM_STRING;
            item.dwTypeData = text.data();
            return SetMenuItemInfoW(menu, i, TRUE, &item) != FALSE;
        }
        auto submenu = GetSubMenu(menu, i);
        if (submenu && updateMenuLabel(submenu, command, label)) return true;
    }
    return false;
}
void refreshLanguage() {
    char filename[256]{};
    SendMessageW(host._nppHandle, NPPM_GETNATIVELANGFILENAME, sizeof(filename), reinterpret_cast<LPARAM>(filename));
    uiLanguage = formatter::i18n::fromNativeFileName(filename);
    const Text labels[]{Text::Format, Text::Settings, Text::About, Text::FormatAs};
    auto menu = reinterpret_cast<HMENU>(SendMessageW(host._nppHandle, NPPM_GETMENUHANDLE, NPPPLUGINMENU, 0));
    for (size_t i = 0; i < std::size(commands); ++i) {
        wcscpy_s(commands[i]._itemName, tr(labels[i]));
        if (menu && commands[i]._cmdID) updateMenuLabel(menu, commands[i]._cmdID, tr(labels[i]));
    }
    DrawMenuBar(host._nppHandle);
    if (settingsWindow) updateSettingsLanguage(settingsWindow);
    if (lastStatus != Text::Empty) status(lastStatus);
}
void detectionControls(HWND window, bool enabled) {
    for (int id : {101, 102, 201, 202, 203, 204, IDOK})
        EnableWindow(GetDlgItem(window, id), enabled);
}
void stopDetection() {
    detectionCancelled = true;
    if (detectionWorker.joinable()) detectionWorker.join();
    detectionFinished = false;
}
void startDetection(HWND window, bool node) {
    if (detectionWorker.joinable()) return;
    auto selectedNode = controlText(window, 101);
    auto selectedPrettier = controlText(window, 102);
    if (!node && (selectedNode.empty() || !fs::path(selectedNode).is_absolute() || !fs::is_regular_file(selectedNode))) {
        setDetectionStatus(window, Text::NodeFirst);
        return;
    }
    wchar_t filename[32768]{};
    SendMessageW(host._nppHandle, NPPM_GETFULLCURRENTPATH, 32768, reinterpret_cast<LPARAM>(filename));
    std::wstring filePath = fs::path(filename).is_absolute() ? filename : L"";
    auto bridge = (pluginDirectory / L"bridge.cjs").wstring();
    detectionCancelled = false; detectionFinished = false;
    if (!SetTimer(window, 2, 50, nullptr)) throw std::runtime_error(utf8(tr(Text::DetectionTimerError)));
    try {
        detectionWorker = std::thread([node, selectedNode, selectedPrettier, filePath, bridge] {
            DetectionResult result{node ? 101 : 102, {}, {}};
            try {
                if (node) result.path = formatter::detectNode(selectedNode, bridge, detectionCancelled);
                else {
                    json request{{"operation", "detectPrettier"}, {"prettierPath", utf8(selectedPrettier)}};
                    if (!filePath.empty()) request["filePath"] = utf8(filePath);
                    auto process = formatter::runBridge(selectedNode, bridge, request.dump(), 10000, detectionCancelled);
                    auto response = json::parse(process.output);
                    if (process.exitCode != 0 || !response.value("ok", false))
                        throw std::runtime_error(response.value("error", "Prettier detection failed."));
                    result.path = wide(response.at("prettierPath").get<std::string>());
                }
            } catch (const std::exception& error) {
                try { result.error = wide(error.what()); }
                catch (...) { result.error = L"Invalid diagnostic encoding."; }
            }
            detectionResult = std::move(result);
            detectionFinished.store(true, std::memory_order_release);
        });
    } catch (...) { KillTimer(window, 2); throw; }
    detectionControls(window, false);
    setDetectionStatus(window, node ? Text::DetectNode : Text::DetectPrettier);
}
LRESULT CALLBACK settingsProc(HWND window, UINT message, WPARAM w, LPARAM l) {
    try {
        if (message == WM_CREATE) {
            addControl(window, L"STATIC", tr(Text::NodeLabel), 0, 16, 16, 550, 20, 301);
            addControl(window, L"EDIT", settings.node.c_str(), WS_TABSTOP | ES_AUTOHSCROLL, 16, 40, 480, 26, 101);
            addControl(window, L"BUTTON", tr(Text::Browse), WS_TABSTOP, 504, 40, 96, 26, 201);
            addControl(window, L"BUTTON", tr(Text::Detect), WS_TABSTOP, 608, 40, 100, 26, 203);
            addControl(window, L"STATIC", tr(Text::PrettierLabel), 0, 16, 80, 692, 20, 302);
            addControl(window, L"EDIT", settings.prettier.c_str(), WS_TABSTOP | ES_AUTOHSCROLL, 16, 104, 480, 26, 102);
            addControl(window, L"BUTTON", tr(Text::Browse), WS_TABSTOP, 504, 104, 96, 26, 202);
            addControl(window, L"BUTTON", tr(Text::Detect), WS_TABSTOP, 608, 104, 100, 26, 204);
            addControl(window, L"STATIC", tr(Text::TimeoutLabel), 0, 16, 144, 420, 20, 304);
            addControl(window, L"EDIT", std::to_wstring(settings.timeoutMs).c_str(), WS_TABSTOP | ES_NUMBER, 450, 140, 150, 26, 104);
            addControl(window, L"STATIC", L"", 0, 16, 180, 692, 44, 105);
            addControl(window, L"BUTTON", tr(Text::Save), WS_TABSTOP | BS_DEFPUSHBUTTON, 496, 236, 100, 30, IDOK);
            addControl(window, L"BUTTON", tr(Text::Cancel), WS_TABSTOP, 608, 236, 100, 30, IDCANCEL);
            setDetectionStatus(window, Text::Empty);
            SendMessageW(host._nppHandle, NPPM_MODELESSDIALOG, MODELESSDIALOGADD, reinterpret_cast<LPARAM>(window));
            return 0;
        }
        if (message == WM_TIMER && w == 2 && detectionFinished.load(std::memory_order_acquire)) {
            detectionWorker.join();
            detectionFinished = false;
            KillTimer(window, 2);
            if (!detectionResult.path.empty()) SetDlgItemTextW(window, detectionResult.field, detectionResult.path.c_str());
            setDetectionStatus(window, detectionResult.error.empty() ? Text::Detected : Text::DetectionFailed, detectionResult.error);
            detectionControls(window, true);
            if (GetActiveWindow() == window)
                SetFocus(GetDlgItem(window, detectionResult.field == 101 ? 203 : 204));
            return 0;
        }
        if (message == WM_COMMAND) {
            int id = LOWORD(w);
            if (detectionWorker.joinable() && (id == IDOK || (id >= 201 && id <= 204))) return 0;
            if (id == 201 || id == 202) { browse(window, id == 201); return 0; }
            if (id == 203 || id == 204) { startDetection(window, id == 203); return 0; }
            if (id == IDOK) {
                Settings next;
                next.node = controlText(window, 101); next.prettier = controlText(window, 102);
                std::wstring timeout = controlText(window, 104);
                size_t end = 0;
                unsigned long value;
                try { value = std::stoul(timeout, &end); }
                catch (const std::exception&) { throw std::runtime_error(utf8(tr(Text::TimeoutError))); }
                if (end != timeout.size() || value < 1000 || value > 120000)
                    throw std::runtime_error(utf8(tr(Text::TimeoutError)));
                next.timeoutMs = value;
                if (!fs::path(next.node).is_absolute() || !fs::is_regular_file(next.node))
                    throw std::runtime_error(utf8(tr(Text::NodePathError)));
                if (!fs::path(next.prettier).is_absolute() || !fs::is_regular_file(fs::path(next.prettier) / L"package.json"))
                    throw std::runtime_error(utf8(tr(Text::PrettierPathError)));
                saveSettings(next);
                DestroyWindow(window); return 0;
            }
            if (id == IDCANCEL) { DestroyWindow(window); return 0; }
        }
        if (message == WM_CLOSE) { DestroyWindow(window); return 0; }
        if (message == WM_DESTROY) {
            KillTimer(window, 2);
            stopDetection();
            SendMessageW(host._nppHandle, NPPM_MODELESSDIALOG, MODELESSDIALOGREMOVE, reinterpret_cast<LPARAM>(window));
            settingsWindow = nullptr; return 0;
        }
    } catch (const std::exception& error) { showError(error.what()); return 0; }
    return DefWindowProcW(window, message, w, l);
}
void centerOnHost(HWND target) {
    RECT owner{}, window{};
    if (GetWindowRect(host._nppHandle, &owner) && GetWindowRect(target, &window)) {
        LONG width = window.right - window.left, height = window.bottom - window.top;
        LONG x = owner.left + (owner.right - owner.left - width) / 2;
        LONG y = owner.top + (owner.bottom - owner.top - height) / 2;
        MONITORINFO monitor{};
        monitor.cbSize = sizeof(monitor);
        if (GetMonitorInfoW(MonitorFromWindow(host._nppHandle, MONITOR_DEFAULTTONEAREST), &monitor)) {
            const auto& work = monitor.rcWork;
            x = std::clamp(x, work.left, std::max(work.left, work.right - width));
            y = std::clamp(y, work.top, std::max(work.top, work.bottom - height));
        }
        SetWindowPos(target, nullptr, x, y, 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE);
    }
}
void openSettings() {
    if (settingsWindow) { SetForegroundWindow(settingsWindow); return; }
    settingsWindow = CreateWindowExW(WS_EX_CONTROLPARENT, L"NppFormatterSettings", tr(Text::SettingsTitle),
        WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU,
        CW_USEDEFAULT, CW_USEDEFAULT, 740, 316, host._nppHandle, nullptr, instance, nullptr);
    if (!settingsWindow) return;
    centerOnHost(settingsWindow);
    ShowWindow(settingsWindow, SW_SHOW);
}
INT_PTR CALLBACK parserDialogProc(HWND window, UINT message, WPARAM w, LPARAM l) {
    if (message == WM_INITDIALOG) {
        SetWindowTextW(window, tr(Text::ParserTitle));
        SetWindowPos(window, nullptr, 0, 0, 550, 205, SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE);
        addControl(window, L"STATIC", tr(l ? Text::ParserOncePrompt : Text::ParserPrompt), 0, 16, 16, 510, 44, 402);
        addControl(window, L"COMBOBOX", L"", WS_TABSTOP | WS_VSCROLL | CBS_DROPDOWNLIST,
                   16, 64, 510, 280, 401);
        for (const auto& choice : formatter::parserChoices)
            SendDlgItemMessageW(window, 401, CB_ADDSTRING, 0, reinterpret_cast<LPARAM>(choice.label));
        addControl(window, L"BUTTON", tr(Text::Format), WS_TABSTOP | BS_DEFPUSHBUTTON, 280, 120, 130, 30, IDOK);
        addControl(window, L"BUTTON", tr(Text::Cancel), WS_TABSTOP, 422, 120, 104, 30, IDCANCEL);
        EnableWindow(GetDlgItem(window, IDOK), FALSE);
        centerOnHost(window);
        return TRUE;
    }
    if (message == WM_COMMAND) {
        if (LOWORD(w) == 401 && HIWORD(w) == CBN_SELCHANGE) {
            EnableWindow(GetDlgItem(window, IDOK), TRUE);
            return TRUE;
        }
        if (LOWORD(w) == IDOK) {
            auto selected = SendDlgItemMessageW(window, 401, CB_GETCURSEL, 0, 0);
            if (selected != CB_ERR) EndDialog(window, selected + 1);
            return TRUE;
        }
        if (LOWORD(w) == IDCANCEL) { EndDialog(window, 0); return TRUE; }
    }
    if (message == WM_CLOSE) { EndDialog(window, 0); return TRUE; }
    return FALSE;
}
std::string chooseParser(bool temporary = false) {
    struct alignas(DWORD) EmptyDialog {
        DLGTEMPLATE dialog{};
        WORD menu = 0, windowClass = 0, title = 0;
    } layout;
    layout.dialog.style = WS_POPUP | WS_CAPTION | WS_SYSMENU | DS_MODALFRAME;
    layout.dialog.cx = 280; layout.dialog.cy = 105;
    choosingParser = true;
    auto selected = DialogBoxIndirectParamW(instance, &layout.dialog, host._nppHandle, parserDialogProc, temporary);
    choosingParser = false;
    if (selected == -1) throw std::runtime_error(utf8(tr(Text::ParserDialogError)));
    if (selected <= 0 || static_cast<size_t>(selected) > std::size(formatter::parserChoices)) return {};
    return formatter::parserChoices[selected - 1].parser;
}
bool offerParserRetry(const std::string& error) {
    auto details = wide(error);
    TASKDIALOG_BUTTON retry{100, tr(Text::ChooseAgain)};
    TASKDIALOGCONFIG dialog{};
    dialog.cbSize = sizeof(dialog);
    dialog.hwndParent = host._nppHandle;
    dialog.dwFlags = TDF_ALLOW_DIALOG_CANCELLATION | TDF_POSITION_RELATIVE_TO_WINDOW;
    dialog.pszWindowTitle = tr(Text::ParseErrorTitle);
    dialog.pszContent = tr(Text::ParseErrorPrompt);
    dialog.pszExpandedInformation = details.c_str();
    dialog.pszCollapsedControlText = tr(Text::ErrorDetails);
    dialog.pszMainIcon = TD_WARNING_ICON;
    dialog.dwCommonButtons = TDCBF_CLOSE_BUTTON;
    dialog.cButtons = 1; dialog.pButtons = &retry;
    dialog.nDefaultButton = IDCLOSE;
    int selected = 0;
    choosingParser = true;
    auto result = TaskDialogIndirect(&dialog, &selected, nullptr, nullptr);
    choosingParser = false;
    if (FAILED(result)) { showError(error); return false; }
    return selected == retry.nButtonID;
}
HWND currentEditor() {
    int view = 0;
    SendMessageW(host._nppHandle, NPPM_GETCURRENTSCINTILLA, 0, reinterpret_cast<LPARAM>(&view));
    return view == 0 ? host._scintillaMainHandle : host._scintillaSecondHandle;
}
std::string readText(HWND editor) {
    LRESULT length = sci(editor, SCI_GETLENGTH);
    if (length < 0 || length > 8 * 1024 * 1024) throw std::runtime_error("The prototype formats documents up to 8 MiB.");
    std::string text(static_cast<size_t>(length) + 1, '\0');
    sci(editor, SCI_GETTEXT, text.size(), reinterpret_cast<LPARAM>(text.data()));
    text.resize(static_cast<size_t>(length));
    return text;
}
bool requestIsCurrent(const Request& request) {
    HWND editor = currentEditor();
    return !shuttingDown && request.generation == generation && editor == request.editor &&
        request.bufferId == static_cast<UINT_PTR>(SendMessageW(host._nppHandle, NPPM_GETCURRENTBUFFERID, 0, 0)) &&
        request.document == sci(editor, SCI_GETDOCPOINTER) && !sci(editor, SCI_GETREADONLY) &&
        sci(editor, SCI_GETCODEPAGE) == SC_CP_UTF8 && sci(editor, SCI_GETSELECTIONS) == 1 &&
        sci(editor, SCI_GETSELECTIONMODE) == SC_SEL_STREAM &&
        request.cursor == sci(editor, SCI_GETCURRENTPOS) && request.anchor == sci(editor, SCI_GETANCHOR) &&
        request.text == readText(editor);
}
void formatCurrentDocument(std::string overrideParser = {}, bool promptForParser = false, bool rememberChoice = false) {
    try {
        if (shuttingDown) return;
        if (worker.joinable() || choosingParser) { status(Text::Busy); return; }
        loadSettings();
        if (settings.node.empty() || settings.prettier.empty()) { openSettings(); return; }
        HWND editor = currentEditor();
        if (sci(editor, SCI_GETREADONLY)) throw std::runtime_error("This document is read-only.");
        if (sci(editor, SCI_GETCODEPAGE) != SC_CP_UTF8)
            throw std::runtime_error("Convert this document to UTF-8 before formatting with this prototype.");
        if (sci(editor, SCI_GETSELECTIONS) != 1 || sci(editor, SCI_GETSELECTIONMODE) != SC_SEL_STREAM)
            throw std::runtime_error("Use a single normal caret or selection before formatting.");
        Request request{editor, static_cast<UINT_PTR>(SendMessageW(host._nppHandle, NPPM_GETCURRENTBUFFERID, 0, 0)),
            sci(editor, SCI_GETDOCPOINTER), generation, sci(editor, SCI_GETCURRENTPOS), sci(editor, SCI_GETANCHOR), readText(editor), {}, rememberChoice};
        if (promptForParser) {
            overrideParser = chooseParser(true);
            if (overrideParser.empty()) { status(Text::FormatCancelled); return; }
            if (!requestIsCurrent(request)) { status(Text::Discarded); return; }
        }
        auto length = SendMessageW(host._nppHandle, NPPM_GETFULLPATHFROMBUFFERID, request.bufferId, 0);
        if (length < 0) throw std::runtime_error("The document was closed.");
        std::wstring filename(static_cast<size_t>(length) + 1, L'\0');
        SendMessageW(host._nppHandle, NPPM_GETFULLPATHFROMBUFFERID, request.bufferId, reinterpret_cast<LPARAM>(filename.data()));
        filename.resize(wcslen(filename.c_str()));
        json payload{{"text", request.text}, {"cursorOffset", wide(request.text.substr(0, request.cursor)).size()},
            {"prettierPath", utf8(settings.prettier)}, {"endOfLine", sci(editor, SCI_GETEOLMODE) == SC_EOL_CRLF ? "crlf" : "lf"}};
        if (fs::path(filename).is_absolute()) payload["filePath"] = utf8(filename);
        if (!overrideParser.empty()) payload["parser"] = overrideParser;
        else if (!payload.contains("filePath")) {
            int language = L_TEXT;
            SendMessageW(host._nppHandle, NPPM_GETCURRENTLANGTYPE, 0, reinterpret_cast<LPARAM>(&language));
            if (auto parser = formatter::parserForLanguage(language)) payload["parser"] = parser;
            else {
                request.rememberChoice = true;
                if (auto selected = documentParsers.find(request.bufferId); selected != documentParsers.end())
                    payload["parser"] = selected->second.parser;
                else payload["detectParser"] = language == L_TEXT;
            }
        }
        request.payload = payload.dump();
        completion.reset(); cancelled = false; finished = false;
        Settings chosen = settings;
        std::wstring bridge = (pluginDirectory / L"bridge.cjs").wstring();
        worker = std::thread([request = std::move(request), chosen, bridge]() mutable {
            auto result = std::make_unique<Completion>(); result->request = std::move(request);
            try {
                auto process = formatter::runBridge(chosen.node, bridge, result->request.payload, chosen.timeoutMs, cancelled);
                if (process.output.empty()) throw std::runtime_error("Node.js returned no result. " + process.error);
                result->response = json::parse(process.output);
                if (process.exitCode != 0 && result->response.value("ok", false))
                    throw std::runtime_error("Node.js exited unsuccessfully. " + process.error);
            } catch (const std::exception& error) { result->error = error.what(); }
            completion = std::move(result);
            finished.store(true, std::memory_order_release);
        });
        status(Text::Formatting);
    } catch (const std::exception& error) { showError(error.what()); }
}
void formatDocument() { formatCurrentDocument(); }
void formatWithLanguage() { formatCurrentDocument({}, true); }
void applyCompletion() {
    worker.join();
    auto result = std::move(completion);
    finished = false;
    auto& request = result->request;
    HWND editor = currentEditor();
    if (!requestIsCurrent(request)) {
        status(Text::Discarded); return;
    }
    if (!result->error.empty()) throw std::runtime_error(result->error);
    bool retry = false;
    if (!result->response.value("ok", false)) {
        auto error = result->response.value("error", "Invalid bridge response.");
        if (!result->response.value("canChooseParser", false)) throw std::runtime_error(error);
        status(Text::FormatFailed);
        if (!offerParserRetry(error)) return;
        if (!requestIsCurrent(request)) { status(Text::Discarded); return; }
        retry = true;
    }
    if (retry || result->response.value("needsParser", false)) {
        status(Text::ChooseLanguage);
        auto parser = chooseParser(!request.rememberChoice);
        if (parser.empty()) { status(Text::FormatCancelled); return; }
        if (!requestIsCurrent(request)) {
            status(Text::Discarded); return;
        }
        if (request.rememberChoice) documentParsers[request.bufferId] = {parser, request.document};
        formatCurrentDocument(std::move(parser), false, request.rememberChoice);
        return;
    }
    if (result->response.value("ignored", false)) { status(Text::Ignored); return; }
    auto formatted = result->response.at("formatted").get<std::string>();
    auto textWide = wide(formatted);
    auto cursor = result->response.at("cursorOffset").get<int64_t>();
    if (cursor < 0 || static_cast<size_t>(cursor) > textWide.size()) throw std::runtime_error("Invalid cursor in bridge response.");
    size_t byteCursor = utf8(textWide.substr(0, static_cast<size_t>(cursor))).size();
    if (formatted == request.text) { status(Text::Unchanged); return; }
    LRESULT firstLine = sci(editor, SCI_GETFIRSTVISIBLELINE), xOffset = sci(editor, SCI_GETXOFFSET);
    sci(editor, SCI_BEGINUNDOACTION);
    sci(editor, SCI_SETTARGETRANGE, 0, static_cast<LPARAM>(request.text.size()));
    applyingDocument = request.document;
    sci(editor, SCI_REPLACETARGET, formatted.size(), reinterpret_cast<LPARAM>(formatted.data()));
    applyingDocument = 0;
    sci(editor, SCI_ENDUNDOACTION);
    sci(editor, SCI_SETSEL, byteCursor, byteCursor);
    sci(editor, SCI_SETFIRSTVISIBLELINE, firstLine); sci(editor, SCI_SETXOFFSET, xOffset);
    status(Text::Formatted);
}
LRESULT CALLBACK timerProc(HWND window, UINT message, WPARAM w, LPARAM l) {
    if (message == WM_TIMER && finished.load(std::memory_order_acquire)) {
        try { applyCompletion(); }
        catch (const std::exception& error) { status(Text::FormatFailed); showError(error.what()); }
        return 0;
    }
    return DefWindowProcW(window, message, w, l);
}
constexpr wchar_t projectHomepage[] = L"https://github.com/oiltea94/npp-formatter";
HRESULT CALLBACK aboutCallback(HWND dialog, UINT notification, WPARAM, LPARAM link, LONG_PTR) {
    if (notification == TDN_HYPERLINK_CLICKED && link &&
        wcscmp(reinterpret_cast<const wchar_t*>(link), projectHomepage) == 0) {
        auto result = ShellExecuteW(dialog, L"open", projectHomepage, nullptr, nullptr, SW_SHOWNORMAL);
        if (reinterpret_cast<INT_PTR>(result) <= 32)
            MessageBoxW(dialog, tr(Text::OpenHomepageError), tr(Text::ErrorTitle), MB_OK | MB_ICONERROR);
    }
    return S_OK;
}
void about() {
    std::wstring content = std::wstring(tr(Text::AboutBody)) + L"\n\n" +
        tr(Text::ProjectHomepage) + L" <a href=\"" + projectHomepage + L"\">" + projectHomepage + L"</a>";
    TASKDIALOGCONFIG dialog{};
    dialog.cbSize = sizeof(dialog);
    dialog.hwndParent = host._nppHandle;
    dialog.dwFlags = TDF_ENABLE_HYPERLINKS | TDF_ALLOW_DIALOG_CANCELLATION | TDF_POSITION_RELATIVE_TO_WINDOW;
    dialog.dwCommonButtons = TDCBF_OK_BUTTON;
    dialog.pszWindowTitle = tr(Text::AboutTitle);
    dialog.pszContent = content.c_str();
    dialog.cxWidth = 360;
    dialog.pfCallback = aboutCallback;
    if (FAILED(TaskDialogIndirect(&dialog, nullptr, nullptr, nullptr)))
        MessageBoxW(host._nppHandle, tr(Text::AboutDialogError), tr(Text::ErrorTitle), MB_OK | MB_ICONERROR);
}
void shutdown() {
    shuttingDown = true; cancelled = true;
    if (worker.joinable()) worker.join();
    completion.reset();
    if (settingsWindow) DestroyWindow(settingsWindow);
    if (timerWindow) { KillTimer(timerWindow, 1); DestroyWindow(timerWindow); timerWindow = nullptr; }
    UnregisterClassW(L"NppFormatterTimer", instance);
    UnregisterClassW(L"NppFormatterSettings", instance);
}
} // namespace

BOOL WINAPI DllMain(HINSTANCE module, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) { instance = module; DisableThreadLibraryCalls(module); }
    return TRUE;
}
extern "C" __declspec(dllexport) BOOL isUnicode() { return TRUE; }
extern "C" __declspec(dllexport) const wchar_t* getName() { return L"NppFormatter"; }
extern "C" __declspec(dllexport) FuncItem* getFuncsArray(int* count) {
    // Append new commands to preserve existing Shortcut Mapper indices.
    const wchar_t* names[]{tr(Text::Format), tr(Text::Settings), tr(Text::About), tr(Text::FormatAs)};
    PFUNCPLUGINCMD callbacks[]{formatDocument, openSettings, about, formatWithLanguage};
    for (size_t i = 0; i < std::size(commands); ++i) { wcscpy_s(commands[i]._itemName, names[i]); commands[i]._pFunc = callbacks[i]; }
    *count = static_cast<int>(std::size(commands)); return commands;
}
extern "C" __declspec(dllexport) void setInfo(NppData data) {
    host = data;
    try {
        std::vector<wchar_t> filename(32768);
        if (!GetModuleFileNameW(instance, filename.data(), static_cast<DWORD>(filename.size())))
            throw std::runtime_error("Could not locate the plugin directory.");
        pluginDirectory = fs::path(filename.data()).parent_path();
        LRESULT length = SendMessageW(host._nppHandle, NPPM_GETPLUGINSCONFIGDIR, 0, 0);
        std::vector<wchar_t> config(static_cast<size_t>(length) + 1);
        if (length <= 0 || !SendMessageW(host._nppHandle, NPPM_GETPLUGINSCONFIGDIR, config.size(), reinterpret_cast<LPARAM>(config.data())))
            throw std::runtime_error("Could not locate the Notepad++ plugin settings directory.");
        configPath = fs::path(config.data()) / L"NppFormatter.ini";
        loadSettings();
        WNDCLASSW timerClass{}; timerClass.hInstance = instance;
        timerClass.lpszClassName = L"NppFormatterTimer"; timerClass.lpfnWndProc = timerProc;
        RegisterClassW(&timerClass);
        timerWindow = CreateWindowExW(0, timerClass.lpszClassName, L"", 0, 0, 0, 0, 0, HWND_MESSAGE, nullptr, instance, nullptr);
        if (!timerWindow || !SetTimer(timerWindow, 1, 50, nullptr)) throw std::runtime_error("Could not initialize result dispatch.");
        WNDCLASSW settingsClass{}; settingsClass.hInstance = instance;
        settingsClass.lpszClassName = L"NppFormatterSettings"; settingsClass.lpfnWndProc = settingsProc;
        settingsClass.hbrBackground = reinterpret_cast<HBRUSH>(COLOR_BTNFACE + 1);
        settingsClass.hCursor = LoadCursorW(nullptr, IDC_ARROW);
        RegisterClassW(&settingsClass);
    } catch (const std::exception& error) { shuttingDown = true; showError(error.what()); }
}
extern "C" __declspec(dllexport) void beNotified(SCNotification* notification) {
    switch (notification->nmhdr.code) {
    case NPPN_READY: case NPPN_NATIVELANGCHANGED: refreshLanguage(); break;
    case NPPN_FILECLOSED: case NPPN_FILESAVED: case NPPN_LANGCHANGED:
        documentParsers.erase(notification->nmhdr.idFrom);
        ++generation;
        break;
    case SCN_MODIFIED:
        if (notification->modificationType & (SC_MOD_INSERTTEXT | SC_MOD_DELETETEXT)) ++generation;
        if ((notification->modificationType & SC_MOD_DELETETEXT) && notification->position == 0 &&
            notification->length > 0 && !documentParsers.empty()) {
            auto source = static_cast<HWND>(notification->nmhdr.hwndFrom);
            if ((source == host._scintillaMainHandle || source == host._scintillaSecondHandle) &&
                sci(source, SCI_GETLENGTH) == 0) {
                auto document = sci(source, SCI_GETDOCPOINTER);
                if (document != applyingDocument) {
                    for (auto it = documentParsers.begin(); it != documentParsers.end();) {
                        if (it->second.document == document) it = documentParsers.erase(it);
                        else ++it;
                    }
                }
            }
        }
        break;
    case NPPN_BUFFERACTIVATED: case NPPN_FILEBEFORECLOSE: case NPPN_GLOBALMODIFIED:
    case NPPN_FILEBEFORESAVE: case NPPN_FILERENAMED: ++generation; break;
    case NPPN_SHUTDOWN: shutdown(); break;
    }
}
extern "C" __declspec(dllexport) LRESULT messageProc(UINT, WPARAM, LPARAM) { return TRUE; }
