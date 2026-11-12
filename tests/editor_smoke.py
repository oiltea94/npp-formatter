"""Exercise the built plugin in a separate, hidden portable Notepad++ instance."""
import ctypes as C
import argparse
import configparser
from ctypes import wintypes as W
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from verify_package import MACHINES, PE, verify_dll

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = {
    'en': {'file': None, 'format': 'Format document', 'settings': 'Settings...', 'about': 'About',
           'title': 'NppFormatter settings', 'browse': 'Browse...', 'detect': 'Auto-detect',
           'save': 'Save', 'cancel': 'Cancel', 'detecting': 'Detecting ', 'detected': 'Detected.',
           'node_first': 'Node.js first', 'unchanged': 'already formatted',
           'formatting': 'NppFormatter: formatting...', 'discarded': 'result discarded',
           'about_title': 'About NppFormatter', 'about_body': 'Requires user-installed Node.js 18+'},
    'zh-CN': {'file': 'chineseSimplified.xml', 'format': '格式化文档', 'settings': '配置...', 'about': '关于',
              'title': 'NppFormatter 配置', 'browse': '浏览...', 'detect': '自动检测',
              'save': '保存', 'cancel': '取消', 'detecting': '正在检测', 'detected': '检测成功',
              'node_first': '先检测或浏览选择 Node.js', 'unchanged': '无需格式化',
              'formatting': 'NppFormatter：正在格式化...', 'discarded': '已丢弃结果',
              'about_title': '关于 NppFormatter', 'about_body': '需要自行安装 Node.js 18+'},
    'zh-TW': {'file': 'taiwaneseMandarin.xml', 'format': '格式化文件', 'settings': '設定...', 'about': '關於',
              'title': 'NppFormatter 設定', 'browse': '瀏覽...', 'detect': '自動偵測',
              'save': '儲存', 'cancel': '取消', 'detecting': '正在偵測', 'detected': '偵測成功',
              'node_first': '先偵測或瀏覽選擇 Node.js', 'unchanged': '無需格式化',
              'formatting': 'NppFormatter：正在格式化...', 'discarded': '已捨棄結果',
              'about_title': '關於 NppFormatter', 'about_body': '需要自行安裝 Node.js 18+'},
}
SETTING_ERRORS = {
    'en': ('NppFormatter error', 'Timeout must be between 1000 and 120000 milliseconds.'),
    'zh-CN': ('NppFormatter 错误', '超时时间必须为 1000 至 120000 毫秒。'),
    'zh-TW': ('NppFormatter 錯誤', '逾時時間必須為 1000 至 120000 毫秒。'),
}
USER32 = C.WinDLL('user32', use_last_error=True)
KERNEL32 = C.WinDLL('kernel32', use_last_error=True)
CALLBACK = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
USER32.SendMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
USER32.SendMessageW.restype = C.c_ssize_t
USER32.PostMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
USER32.EnumWindows.argtypes = [CALLBACK, W.LPARAM]
USER32.EnumChildWindows.argtypes = [W.HWND, CALLBACK, W.LPARAM]
USER32.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
USER32.GetClassNameW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
USER32.GetMenu.argtypes = [W.HWND]
USER32.GetMenu.restype = W.HMENU
USER32.GetSubMenu.argtypes = [W.HMENU, C.c_int]
USER32.GetSubMenu.restype = W.HMENU
USER32.GetMenuItemCount.argtypes = [W.HMENU]
USER32.GetMenuItemID.argtypes = [W.HMENU, C.c_int]
USER32.GetMenuItemID.restype = W.UINT
USER32.GetMenuStringW.argtypes = [W.HMENU, W.UINT, W.LPWSTR, C.c_int, W.UINT]
KERNEL32.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
KERNEL32.OpenProcess.restype = W.HANDLE
KERNEL32.VirtualAllocEx.argtypes = [W.HANDLE, C.c_void_p, C.c_size_t, W.DWORD, W.DWORD]
KERNEL32.VirtualAllocEx.restype = C.c_void_p
KERNEL32.VirtualFreeEx.argtypes = [W.HANDLE, C.c_void_p, C.c_size_t, W.DWORD]
KERNEL32.WriteProcessMemory.argtypes = [W.HANDLE, C.c_void_p, C.c_void_p, C.c_size_t, C.c_void_p]
KERNEL32.ReadProcessMemory.argtypes = [W.HANDLE, C.c_void_p, C.c_void_p, C.c_size_t, C.c_void_p]
KERNEL32.CloseHandle.argtypes = [W.HANDLE]
USER32.GetDlgItem.argtypes = [W.HWND, C.c_int]
USER32.GetDlgItem.restype = W.HWND
USER32.GetWindowRect.argtypes = [W.HWND, C.POINTER(W.RECT)]
USER32.IsWindowEnabled.argtypes = [W.HWND]
USER32.IsWindow.argtypes = [W.HWND]
USER32.GetDlgCtrlID.argtypes = [W.HWND]
USER32.GetParent.argtypes = [W.HWND]
USER32.GetParent.restype = W.HWND


def window_class(window):
    name = C.create_unicode_buffer(256)
    USER32.GetClassNameW(window, name, len(name))
    return name.value


def window_title(window):
    title = C.create_unicode_buffer(256)
    USER32.SendMessageW(window, 13, len(title), C.addressof(title))
    return title.value


def accessible_text(window):
    # Task Dialog draws its body with DirectUI, which does not expose WM_GETTEXT.
    script = f'''
        $ErrorActionPreference = 'Stop'
        [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
        Add-Type -AssemblyName UIAutomationClient
        $root = [Windows.Automation.AutomationElement]::FromHandle([IntPtr]{window})
        $elements = $root.FindAll([Windows.Automation.TreeScope]::Descendants,
                                 [Windows.Automation.Condition]::TrueCondition)
        foreach ($element in $elements) {{ $element.Current.Name }}
    '''
    return subprocess.check_output(['powershell', '-NoProfile', '-Command', script],
                                   encoding='utf-8', timeout=15)


def windows(pid):
    found = []
    @CALLBACK
    def visit(window, _):
        owner = W.DWORD()
        USER32.GetWindowThreadProcessId(window, C.byref(owner))
        if owner.value == pid:
            found.append(window)
        return True
    USER32.EnumWindows(visit, 0)
    return found


def children(parent):
    found = []
    @CALLBACK
    def visit(window, _):
        found.append(window)
        return True
    USER32.EnumChildWindows(parent, visit, 0)
    return found


def menu_command(menu, label):
    for index in range(USER32.GetMenuItemCount(menu)):
        text = C.create_unicode_buffer(256)
        USER32.GetMenuStringW(menu, index, text, len(text), 0x400)
        if text.value.replace('&', '').split('\t')[0] == label:
            return USER32.GetMenuItemID(menu, index)
        submenu = USER32.GetSubMenu(menu, index)
        if submenu:
            result = menu_command(submenu, label)
            if result is not None:
                return result
    return None


def until(predicate, timeout=10):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = predicate()
        if value:
            return value
        time.sleep(0.03)
    raise AssertionError('Timed out waiting for the editor')


def run(sandbox, architecture, language='en'):
    labels = LANGUAGES[language]
    configured = os.environ.get('NPP_EXE') or shutil.which('notepad++')
    if configured:
        source = Path(configured)
    elif os.environ.get('ProgramFiles'):
        source = Path(os.environ['ProgramFiles']) / 'Notepad++' / 'notepad++.exe'
    else:
        raise RuntimeError('Set NPP_EXE to a matching Notepad++ executable.')
    if not source.is_file():
        raise RuntimeError('Notepad++ was not found. Set NPP_EXE to its executable.')
    if PE(source.read_bytes()).machine != MACHINES[architecture]:
        raise RuntimeError('Notepad++ architecture differs from --arch; set NPP_EXE to a matching editor.')
    stage = ROOT / 'dist' / architecture / 'NppFormatter'
    verify_dll((stage / 'NppFormatter.dll').read_bytes(), architecture)
    if C.sizeof(C.c_void_p) < 8 and architecture != 'x86':
        raise RuntimeError('Use 64-bit Python to test a 64-bit editor.')
    shutil.copy2(source, sandbox / 'notepad++.exe')
    for name in ('langs.model.xml', 'stylers.model.xml'):
        shutil.copy2(source.parent / name, sandbox / name)
    (sandbox / 'doLocalConf.xml').write_text('', encoding='utf-8')
    (sandbox / 'localization').mkdir()
    for filename in ('english.xml', 'chineseSimplified.xml', 'taiwaneseMandarin.xml'):
        shutil.copy2(source.parent / 'localization' / filename, sandbox / 'localization' / filename)
    if labels['file']:
        shutil.copy2(source.parent / 'localization' / labels['file'], sandbox / 'nativeLang.xml')
    destination = sandbox / 'plugins' / 'NppFormatter'
    shutil.copytree(stage, destination, dirs_exist_ok=True)
    config_dir = sandbox / 'plugins' / 'Config'
    config_dir.mkdir(exist_ok=True)
    node = subprocess.check_output(['node', '-p', 'process.execPath'], text=True).strip()
    ini = f'[Formatter]\nNodePath={node}\nPrettierPath={ROOT / "node_modules" / "prettier"}\nUntitledParser=json\nTimeoutMs=10000\n'
    (config_dir / 'NppFormatter.ini').write_text(ini, encoding='utf-16')
    original = 'const emoji="😀";const answer=42; // 中文\n'
    expected = 'const emoji = "😀";\nconst answer = 42; // 中文\n'
    document = sandbox / 'input.js'
    document.write_text(original, encoding='utf-8', newline='\n')
    project_prettier = sandbox / 'node_modules' / 'prettier'
    shutil.copytree(ROOT / 'node_modules' / 'prettier', project_prettier)
    startup = subprocess.STARTUPINFO()
    startup.dwFlags = subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    environment = os.environ.copy()
    environment['PATH'] = str(Path(node).parent) + os.pathsep + environment.get('PATH', '')
    process = subprocess.Popen([str(sandbox / 'notepad++.exe'), '-multiInst', '-nosession', '-noUpdater', str(document)], startupinfo=startup, env=environment)
    handle = memory = main_window = editor = None
    try:
        main_window = until(lambda: next((w for w in windows(process.pid) if window_class(w) == 'Notepad++'), None))
        command = until(lambda: menu_command(USER32.GetMenu(main_window), labels['format']))
        controls = until(lambda: [w for w in children(main_window) if window_class(w) == 'Scintilla'])
        statusbar = until(lambda: next((w for w in children(main_window) if window_class(w) == 'msctls_statusbar32'), None))
        handle = KERNEL32.OpenProcess(0x438, False, process.pid)
        assert handle, C.get_last_error()
        memory = KERNEL32.VirtualAllocEx(handle, None, 2 * 1024 * 1024, 0x3000, 0x04)
        assert memory, C.get_last_error()
        send = USER32.SendMessageW

        def read_bytes(size):
            result = C.create_string_buffer(size)
            assert KERNEL32.ReadProcessMemory(handle, memory, result, size, None)
            return result.raw

        def text(window):
            size = send(window, 2006, 0, 0)
            send(window, 2182, size + 1, memory)
            return read_bytes(size + 1)[:size].decode('utf-8')

        editor = until(lambda: next((w for w in controls if text(w) == original), None))

        def get_control(dialog, identifier):
            return USER32.GetDlgItem(dialog, identifier)

        def control_text(dialog, identifier):
            control = get_control(dialog, identifier)
            buffer = C.create_unicode_buffer(send(control, 14, 0, 0) + 1)
            send(control, 13, len(buffer), C.addressof(buffer))
            return buffer.value

        def set_control(dialog, identifier, value):
            buffer = C.create_unicode_buffer(value)
            send(get_control(dialog, identifier), 12, 0, C.addressof(buffer))

        def open_settings():
            setting_command = menu_command(USER32.GetMenu(main_window), labels['settings'])
            assert setting_command is not None
            USER32.PostMessageW(main_window, 0x111, setting_command, 0)
            return until(lambda: next((w for w in windows(process.pid) if window_class(w) == 'NppFormatterSettings'), None))

        def detect(dialog, identifier):
            USER32.PostMessageW(dialog, 0x111, identifier, 0)
            until(lambda: labels['detecting'] in control_text(dialog, 105))
            assert not USER32.IsWindowEnabled(get_control(dialog, 1)), 'Save stayed enabled during detection'
            until(lambda: USER32.IsWindowEnabled(get_control(dialog, identifier)), timeout=15)
            assert control_text(dialog, 105).startswith(labels['detected']), control_text(dialog, 105)

        ini_path = config_dir / 'NppFormatter.ini'
        before = ini_path.read_bytes()
        dialog = open_settings()
        title = C.create_unicode_buffer(256)
        send(dialog, 13, len(title), C.addressof(title))
        assert title.value == labels['title'], title.value
        for identifier, key in ((201, 'browse'), (202, 'browse'), (203, 'detect'), (204, 'detect'), (1, 'save'), (2, 'cancel')):
            assert control_text(dialog, identifier) == labels[key]
        for identifier in (301, 302, 303, 304):
            label = control_text(dialog, identifier)
            assert label
            if language != 'en':
                assert any('\u4e00' <= ch <= '\u9fff' for ch in label), label
        set_control(dialog, 104, '')
        USER32.PostMessageW(dialog, 0x111, 1, 0)
        error_title, error_body = SETTING_ERRORS[language]
        error_dialog = until(lambda: next((w for w in windows(process.pid)
                                          if window_class(w) == '#32770' and window_title(w) == error_title), None))
        assert any(error_body in window_title(c) for c in children(error_dialog))
        USER32.PostMessageW(error_dialog, 0x10, 0, 0)
        until(lambda: not USER32.IsWindow(error_dialog))
        set_control(dialog, 104, '10000')
        for browse_id, detect_id in ((201, 203), (202, 204)):
            browse_rect, detect_rect = W.RECT(), W.RECT()
            assert get_control(dialog, detect_id), 'Auto-detect button is missing'
            USER32.GetWindowRect(get_control(dialog, browse_id), C.byref(browse_rect))
            USER32.GetWindowRect(get_control(dialog, detect_id), C.byref(detect_rect))
            assert detect_rect.left > browse_rect.right, 'Auto-detect is not after Browse'
        set_control(dialog, 101, '')
        set_control(dialog, 102, 'keep this value')
        USER32.PostMessageW(dialog, 0x111, 204, 0)
        until(lambda: labels['node_first'] in control_text(dialog, 105))
        assert control_text(dialog, 102) == 'keep this value'
        detect(dialog, 203)
        assert os.path.samefile(control_text(dialog, 101), node)
        detect(dialog, 204)
        assert os.path.samefile(control_text(dialog, 102), project_prettier)
        assert ini_path.read_bytes() == before, 'Detection saved settings without Save'
        USER32.PostMessageW(dialog, 0x111, 2, 0)
        until(lambda: not USER32.IsWindow(dialog))
        dialog = open_settings()
        assert control_text(dialog, 102) == str(ROOT / 'node_modules' / 'prettier')
        USER32.PostMessageW(dialog, 0x111, 203, 0)
        until(lambda: labels['detecting'] in control_text(dialog, 105))
        started = time.monotonic()
        USER32.PostMessageW(dialog, 0x111, 2, 0)
        until(lambda: not USER32.IsWindow(dialog))
        assert time.monotonic() - started < 2, 'Cancel blocked during detection'
        assert ini_path.read_bytes() == before
        dialog = open_settings()
        detect(dialog, 204)
        USER32.PostMessageW(dialog, 0x111, 1, 0)
        until(lambda: not USER32.IsWindow(dialog))
        saved = configparser.ConfigParser(interpolation=None)
        saved.read(ini_path, encoding='utf-16')
        assert os.path.samefile(saved['Formatter']['PrettierPath'], project_prettier), 'Saved Prettier path differs from detected package'
        assert os.path.samefile(saved['Formatter']['NodePath'], node), 'Saved Node path differs from detected executable'
        assert ini_path.with_suffix('.ini.bak').read_bytes() == before
        print('PASS settings: detection buttons, Node/project discovery, preserve on failure, Cancel and explicit Save', flush=True)

        if language == 'en':
            dialog = open_settings()
            set_control(dialog, 101, '')
            set_control(dialog, 102, 'unsaved path')
            set_control(dialog, 103, 'typescript')
            USER32.PostMessageW(dialog, 0x111, 204, 0)
            until(lambda: labels['node_first'] in control_text(dialog, 105))
            USER32.PostMessageW(main_window, 0x111, 48011, 0)  # Notepad++ Preferences
            combo = until(lambda: next((c for w in windows(process.pid) for c in children(w)
                                        if USER32.GetDlgCtrlID(c) == 6124), None))
            bridge_file = destination / 'bridge.cjs'
            original_bridge = bridge_file.read_bytes()
            bridge_file.write_bytes(original_bridge.replace(
                b"'use strict';", b"'use strict';\nAtomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 800);", 1))
            USER32.PostMessageW(dialog, 0x111, 203, 0)
            until(lambda: labels['detecting'] in control_text(dialog, 105))
            assert not USER32.IsWindowEnabled(get_control(dialog, 203))
            for target, display in (('zh-CN', '中文简体'), ('zh-TW', '台灣繁體'), ('en', 'English')):
                wanted = C.create_unicode_buffer(display)
                index = send(combo, 0x158, -1, C.addressof(wanted))  # CB_FINDSTRINGEXACT
                if index < 0:
                    available = []
                    for item in range(send(combo, 0x146, 0, 0)):
                        value = C.create_unicode_buffer(send(combo, 0x149, item, 0) + 1)
                        send(combo, 0x148, item, C.addressof(value))
                        available.append(value.value)
                    raise AssertionError(f'Host language missing: {display}; available={available}')
                send(combo, 0x14E, index, 0)  # CB_SETCURSEL
                USER32.PostMessageW(USER32.GetParent(combo), 0x111, (1 << 16) | 6124, combo)
                translated = LANGUAGES[target]
                until(lambda: control_text(dialog, 201) == translated['browse'])
                assert menu_command(USER32.GetMenu(main_window), translated['format']) == command
                assert menu_command(USER32.GetMenu(main_window), translated['settings']) is not None
                assert menu_command(USER32.GetMenu(main_window), translated['about']) is not None
                if target == 'zh-CN':
                    until(lambda: USER32.IsWindowEnabled(get_control(dialog, 203)), timeout=15)
                    assert os.path.samefile(control_text(dialog, 101), node)
                    bridge_file.write_bytes(original_bridge)
                assert control_text(dialog, 105).startswith(translated['detected'])
                assert control_text(dialog, 102) == 'unsaved path'
                assert control_text(dialog, 103) == 'typescript'
            # The General page containing the combo is a child of Preferences.
            preferences = USER32.GetParent(USER32.GetParent(combo))
            USER32.PostMessageW(preferences, 0x10, 0, 0)
            USER32.PostMessageW(dialog, 0x111, 2, 0)
            until(lambda: not USER32.IsWindow(dialog))
            print('PASS live language changes: en -> zh-CN -> zh-TW -> en; unsaved fields and active detection preserved', flush=True)

        about_command = menu_command(USER32.GetMenu(main_window), labels['about'])
        assert about_command is not None
        USER32.PostMessageW(main_window, 0x111, about_command, 0)
        about_dialog = until(lambda: next((w for w in windows(process.pid)
                                          if window_class(w) == '#32770' and window_title(w) == labels['about_title']), None))
        send(about_dialog, 13, len(title), C.addressof(title))
        assert title.value == labels['about_title'], title.value
        body = []
        for control in children(about_dialog):
            buffer = C.create_unicode_buffer(send(control, 14, 0, 0) + 1)
            send(control, 13, len(buffer), C.addressof(buffer))
            body.append(buffer.value)
        about_text = accessible_text(about_dialog)
        assert labels['about_body'] in about_text, about_text
        homepage = 'https://github.com/oiltea94/npp-formatter'
        links = [w for w in children(about_dialog) if window_class(w) == 'SysLink']
        assert any(f'<a href="{homepage}">{homepage}</a>' in window_title(w) for w in links), body
        USER32.PostMessageW(about_dialog, 0x10, 0, 0)
        until(lambda: not USER32.IsWindow(about_dialog))
        print(f'PASS localization: {language} menu, settings, detection messages and About', flush=True)

        def set_text(value):
            raw = value.encode('utf-8') + b'\0'
            assert KERNEL32.WriteProcessMemory(handle, memory, C.c_char_p(raw), len(raw), None)
            send(editor, 2181, 0, memory)

        def status():
            size = send(statusbar, 1036, 0, 0) & 0xFFFF
            send(statusbar, 1037, 0, memory)
            return read_bytes((size + 1) * 2).decode('utf-16-le').rstrip('\0')

        send(editor, 2037, 65001, 0)
        cursor = original.encode('utf-8').index(b'answer')
        send(editor, 2160, cursor, cursor)
        send(editor, 2175, 0, 0)
        USER32.PostMessageW(main_window, 0x111, command, 0)
        until(lambda: text(editor) == expected)
        assert send(editor, 2008, 0, 0) == expected.encode('utf-8').index(b'answer')
        print('PASS real editor: plugin loaded, Unicode formatting and caret mapping', flush=True)
        send(editor, 2176, 0, 0)
        assert text(editor) == original, 'One undo did not restore the document'
        print('PASS real editor: one-step undo', flush=True)
        set_text(expected)
        send(editor, 2175, 0, 0)
        USER32.PostMessageW(main_window, 0x111, command, 0)
        until(lambda: labels['unchanged'] in status())
        assert not send(editor, 2174, 0, 0), 'No-op added an undo record'
        print('PASS real editor: no-op preserves undo history', flush=True)

        # Delay user config to make the edit-during-format race deterministic.
        project_config = sandbox / 'prettier.config.cjs'
        project_config.write_text('Atomics.wait(new Int32Array(new SharedArrayBuffer(4)),0,0,800);module.exports={};', encoding='utf-8')
        set_text(original)
        USER32.PostMessageW(main_window, 0x111, command, 0)
        until(lambda: status() == labels['formatting'])
        changed = original + '// typed while formatting\n'
        started = time.monotonic()
        set_text(changed)
        assert time.monotonic() - started < 0.5, 'Editor blocked during formatting'
        until(lambda: labels['discarded'] in status())
        assert text(editor) == changed, 'Stale result overwrote the edit'
        print('PASS real editor: responsive during formatting; stale result discarded', flush=True)
        project_config.unlink()
        report = {'architecture': architecture, 'language': language, 'checks': 8,
                  'live_language_switch': language == 'en', 'result': 'PASS'}
        (ROOT / 'build' / architecture / f'editor-smoke-{language}.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    finally:
        if editor:
            USER32.SendMessageW(editor, 2014, 0, 0)
        if memory:
            KERNEL32.VirtualFreeEx(handle, memory, 0, 0x8000)
        if handle:
            KERNEL32.CloseHandle(handle)
        if main_window:
            USER32.PostMessageW(main_window, 0x10, 0, 0)
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=3)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=MACHINES, default='x64')
    parser.add_argument('--language', choices=[*LANGUAGES, 'all'], default='all')
    args = parser.parse_args()
    for language in LANGUAGES if args.language == 'all' else [args.language]:
        with tempfile.TemporaryDirectory(prefix='npp-formatter-test-\u4e2d\u6587 ') as directory:
            run(Path(directory), args.arch, language)
