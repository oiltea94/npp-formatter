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
    'en': {'file': None, 'format': 'Format document', 'format_as': 'Format with language...', 'settings': 'Settings...', 'about': 'About',
           'title': 'NppFormatter settings', 'browse': 'Browse...', 'detect': 'Auto-detect',
           'save': 'Save', 'cancel': 'Cancel', 'detecting': 'Detecting ', 'detected': 'Detected.',
           'node_first': 'Node.js first', 'unchanged': 'already formatted',
           'formatting': 'NppFormatter: formatting...', 'discarded': 'result discarded',
           'about_title': 'About NppFormatter', 'about_body': 'Requires user-installed Node.js 18+'},
    'zh-CN': {'file': 'chineseSimplified.xml', 'format': '格式化文档', 'format_as': '按指定语言格式化...', 'settings': '配置...', 'about': '关于',
              'title': 'NppFormatter 配置', 'browse': '浏览...', 'detect': '自动检测',
              'save': '保存', 'cancel': '取消', 'detecting': '正在检测', 'detected': '检测成功',
              'node_first': '先检测或浏览选择 Node.js', 'unchanged': '无需格式化',
              'formatting': 'NppFormatter：正在格式化...', 'discarded': '已丢弃结果',
              'about_title': '关于 NppFormatter', 'about_body': '需要自行安装 Node.js 18+'},
    'zh-TW': {'file': 'taiwaneseMandarin.xml', 'format': '格式化文件', 'format_as': '依指定語言格式化...', 'settings': '設定...', 'about': '關於',
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
PARSER_TITLES = {'en': 'Choose document language', 'zh-CN': '选择文档语言', 'zh-TW': '選擇文件語言'}
PARSE_ERRORS = {
    'en': ('Formatting could not parse this document', 'Show error details', 'Choose another language...'),
    'zh-CN': ('格式化时未能解析文档', '查看错误详情', '重新选择语言...'),
    'zh-TW': ('格式化時未能解析文件', '查看錯誤詳情', '重新選擇語言...'),
}
JAVA_MISSING = {
    'en': 'Java formatting requires prettier-plugin-java.',
    'zh-CN': 'Java 格式化需要 prettier-plugin-java。',
    'zh-TW': 'Java 格式化需要 prettier-plugin-java。',
}
XML_MISSING = {
    'en': 'XML formatting requires @prettier/plugin-xml.',
    'zh-CN': 'XML 格式化需要 @prettier/plugin-xml。',
    'zh-TW': 'XML 格式化需要 @prettier/plugin-xml。',
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
USER32.IsWindowVisible.argtypes = [W.HWND]
USER32.SetWindowPos.argtypes = [W.HWND, W.HWND, C.c_int, C.c_int, C.c_int, C.c_int, W.UINT]
USER32.MonitorFromWindow.argtypes = [W.HWND, W.DWORD]
USER32.MonitorFromWindow.restype = W.HANDLE


class MonitorInfo(C.Structure):
    _fields_ = [('size', W.DWORD), ('monitor', W.RECT), ('work', W.RECT), ('flags', W.DWORD)]


USER32.GetMonitorInfoW.argtypes = [W.HANDLE, C.POINTER(MonitorInfo)]


def window_class(window):
    name = C.create_unicode_buffer(256)
    USER32.GetClassNameW(window, name, len(name))
    return name.value


def window_title(window):
    title = C.create_unicode_buffer(256)
    USER32.SendMessageW(window, 13, len(title), C.addressof(title))
    return title.value


class UIAutomation:
    def __init__(self, architecture):
        self.helper = ROOT / 'build' / architecture / 'ui_automation.exe'
        if not self.helper.is_file():
            raise RuntimeError('Build the UI Automation helper with scripts/build.ps1 before testing.')
        if PE(self.helper.read_bytes()).machine != MACHINES[architecture]:
            raise RuntimeError('UI Automation helper architecture differs from the editor.')

    def run(self, operation, window, *arguments):
        command = [str(self.helper), operation, str(window), *arguments]
        try:
            return subprocess.run(command, check=True, capture_output=True,
                                  encoding='utf-8', timeout=15,
                                  creationflags=subprocess.CREATE_NO_WINDOW).stdout
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as error:
            diagnostic = error.stderr or ''
            if isinstance(diagnostic, bytes):
                diagnostic = diagnostic.decode('utf-8', errors='replace')
            reason = 'timed out after 15s' if isinstance(error, subprocess.TimeoutExpired) else f'exited {error.returncode}'
            raise RuntimeError(f'UI Automation helper {reason}: {diagnostic.strip()}') from error

    def text(self, window):
        # Task Dialog's DirectUI content is not exposed through WM_GETTEXT.
        return self.run('text', window)

    def invoke(self, window, name):
        self.run('invoke', window, name)


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
    automation = UIAutomation(architecture)
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
            dialog = until(lambda: next((w for w in windows(process.pid)
                                        if window_class(w) == 'NppFormatterSettings' and USER32.IsWindowVisible(w)), None))
            owner, bounds = W.RECT(), W.RECT()
            assert USER32.GetWindowRect(main_window, C.byref(owner))
            assert USER32.GetWindowRect(dialog, C.byref(bounds))
            monitor = MonitorInfo()
            monitor.size = C.sizeof(monitor)
            assert USER32.GetMonitorInfoW(USER32.MonitorFromWindow(main_window, 2), C.byref(monitor))
            width, height = bounds.right - bounds.left, bounds.bottom - bounds.top
            x = owner.left + int((owner.right - owner.left - width) / 2)
            y = owner.top + int((owner.bottom - owner.top - height) / 2)
            work = monitor.work
            x = max(work.left, min(x, max(work.left, work.right - width)))
            y = max(work.top, min(y, max(work.top, work.bottom - height)))
            assert abs(bounds.left - x) <= 1 and abs(bounds.top - y) <= 1, 'Settings is not centered on its owner'
            return dialog

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
        assert not get_control(dialog, 103), 'Global untitled parser setting should be removed'
        assert control_text(dialog, 106) == 'SQL', 'Old settings must default to standard SQL'
        assert control_text(dialog, 107) == 'Bash', 'Old settings must default to Bash'
        send(get_control(dialog, 107), 0x14E, 1, 0)
        send(get_control(dialog, 106), 0x14E, 1, 0)  # MySQL, not saved until Save.
        for identifier in (301, 302, 304, 306, 307):
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
        # Reopening follows the moved owner and stays inside the monitor work area.
        original_bounds = W.RECT()
        assert USER32.GetWindowRect(main_window, C.byref(original_bounds))
        monitor = MonitorInfo()
        monitor.size = C.sizeof(monitor)
        assert USER32.GetMonitorInfoW(USER32.MonitorFromWindow(main_window, 2), C.byref(monitor))
        assert USER32.SetWindowPos(main_window, None, monitor.work.left - 200, monitor.work.top + 40, 820, 600, 0x14)
        dialog = open_settings()
        assert control_text(dialog, 102) == str(ROOT / 'node_modules' / 'prettier')
        assert control_text(dialog, 106) == 'SQL', 'Cancel persisted the SQL dialect'
        assert control_text(dialog, 107) == 'Bash', 'Cancel persisted the Shell dialect'
        USER32.PostMessageW(dialog, 0x111, 203, 0)
        until(lambda: labels['detecting'] in control_text(dialog, 105))
        started = time.monotonic()
        USER32.PostMessageW(dialog, 0x111, 2, 0)
        until(lambda: not USER32.IsWindow(dialog))
        assert time.monotonic() - started < 2, 'Cancel blocked during detection'
        assert ini_path.read_bytes() == before
        assert USER32.SetWindowPos(main_window, None, original_bounds.left, original_bounds.top,
                                  original_bounds.right - original_bounds.left,
                                  original_bounds.bottom - original_bounds.top, 0x14)
        dialog = open_settings()
        detect(dialog, 204)
        send(get_control(dialog, 106), 0x14E, 1, 0)
        send(get_control(dialog, 107), 0x14E, 1, 0)
        USER32.PostMessageW(dialog, 0x111, 1, 0)
        until(lambda: not USER32.IsWindow(dialog))
        saved = configparser.ConfigParser(interpolation=None)
        saved.read(ini_path, encoding='utf-16')
        assert 'UntitledParser' not in saved['Formatter'], 'Legacy global parser was written back'
        assert saved['Formatter']['SqlDialect'] == 'mysql'
        assert saved['Formatter']['ShellDialect'] == '2'
        assert os.path.samefile(saved['Formatter']['PrettierPath'], project_prettier), 'Saved Prettier path differs from detected package'
        assert os.path.samefile(saved['Formatter']['NodePath'], node), 'Saved Node path differs from detected executable'
        assert ini_path.with_suffix('.ini.bak').read_bytes() == before
        print('PASS settings: detection buttons, Node/project discovery, preserve on failure, Cancel and explicit Save', flush=True)
        print('PASS settings placement: owner centering, moved owner and screen-edge clamping', flush=True)

        def check_environment(dialog):
            USER32.PostMessageW(dialog, 0x111, 205, 0)
            until(lambda: not USER32.IsWindowEnabled(get_control(dialog, 205)))
            assert not USER32.IsWindowEnabled(get_control(dialog, 1))
            until(lambda: USER32.IsWindowEnabled(get_control(dialog, 205)), timeout=35)
            report_text = control_text(dialog, 108)
            assert 'Node.js:' in report_text and 'Prettier:' in report_text, control_text(dialog, 105)
            return report_text

        environment_before = ini_path.read_bytes()
        dialog = open_settings()
        assert control_text(dialog, 205) == {
            'en': 'Check formatting environment', 'zh-CN': '检查格式化环境', 'zh-TW': '檢查格式化環境',
        }[language]
        report_text = check_environment(dialog)
        missing_label = {'en': 'Not installed', 'zh-CN': '未安装', 'zh-TW': '未安裝'}[language]
        assert f'prettier-plugin-toml: {missing_label}' in report_text
        assert f'prettier-plugin-sh: {missing_label}' in report_text
        set_control(dialog, 102, str(sandbox / 'missing-prettier'))
        assert control_text(dialog, 108) == '', 'Changing paths left stale environment results'
        invalid_report = check_environment(dialog)
        assert 'package.json' in invalid_report
        assert 'prettier-plugin-toml:' not in invalid_report
        assert ini_path.read_bytes() == environment_before, 'Environment check saved settings'
        USER32.PostMessageW(dialog, 0x111, 2, 0)
        until(lambda: not USER32.IsWindow(dialog))
        dialog = open_settings()
        USER32.PostMessageW(dialog, 0x111, 205, 0)
        until(lambda: not USER32.IsWindowEnabled(get_control(dialog, 205)))
        started = time.monotonic()
        USER32.PostMessageW(dialog, 0x111, 2, 0)
        until(lambda: not USER32.IsWindow(dialog))
        assert time.monotonic() - started < 2, 'Cancel blocked during environment check'
        print('PASS environment: localized check, missing packages, unsaved paths, invalid package, stale report and Cancel', flush=True)

        if language == 'en':
            dialog = open_settings()
            assert control_text(dialog, 106) == 'MySQL'
            assert control_text(dialog, 107) == 'POSIX sh'
            send(get_control(dialog, 107), 0x14E, 2, 0)
            send(get_control(dialog, 106), 0x14E, 5, 0)  # SQL Server, unsaved.
            set_control(dialog, 101, '')
            set_control(dialog, 102, 'unsaved path')
            set_control(dialog, 104, '15000')
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
                assert menu_command(USER32.GetMenu(main_window), translated['format_as']) is not None
                if target == 'zh-CN':
                    until(lambda: USER32.IsWindowEnabled(get_control(dialog, 203)), timeout=15)
                    assert os.path.samefile(control_text(dialog, 101), node)
                    bridge_file.write_bytes(original_bridge)
                if target == 'zh-CN':
                    assert control_text(dialog, 105).startswith(translated['detected'])
                else:
                    assert control_text(dialog, 105).startswith({
                        'en': 'Check finished.', 'zh-TW': '檢查完成',
                    }[target])
                    assert 'Node.js:' in control_text(dialog, 108)
                    assert {'en': 'Check failed', 'zh-TW': '檢查失敗'}[target] in control_text(dialog, 108)
                assert control_text(dialog, 102) == 'unsaved path'
                assert control_text(dialog, 104) == '15000'
                assert control_text(dialog, 106) == 'SQL Server (T-SQL)'
                assert control_text(dialog, 107) == 'mksh'
                assert control_text(dialog, 306) == {
                    'en': 'SQL dialect (project config takes priority)',
                    'zh-CN': 'SQL 方言（项目配置优先）',
                    'zh-TW': 'SQL 方言（專案設定優先）',
                }[target]
                if target == 'zh-CN':
                    check_environment(dialog)  # Results must retranslate without losing unsaved paths.
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
        about_controls = children(about_dialog)
        for control in about_controls:
            buffer = C.create_unicode_buffer(send(control, 14, 0, 0) + 1)
            send(control, 13, len(buffer), C.addressof(buffer))
            body.append(buffer.value)
        about_text = automation.text(about_dialog)
        # Exercise repeated client creation/teardown against the same live provider.
        for _ in range(2):
            assert automation.text(about_dialog) == about_text, 'Repeated UIA reads changed About text'
        print(f'PASS native UI Automation: {architecture} helper, repeated About reads', flush=True)
        assert labels['about_body'] in about_text, about_text
        assert 'prettier-plugin-java' in about_text, 'About must explain the optional Java dependency'
        assert '@prettier/plugin-xml' in about_text, 'About must explain the optional XML dependency'
        for package in ('@prettier/plugin-php', 'prettier-plugin-sql', 'prettier-plugin-properties', 'prettier-plugin-toml', 'prettier-plugin-sh'):
            assert package in about_text, f'About must explain {package}'
        for name in ('JSONC', 'MDX', 'Handlebars'):
            assert name in about_text, f'About must include {name}'
        homepage = 'https://github.com/oiltea94/npp-formatter'
        homepage_label = {'en': 'Project homepage:', 'zh-CN': '项目主页：', 'zh-TW': '專案首頁：'}[language]
        homepage_line = f'{homepage_label} <a href="{homepage}">{homepage}</a>'
        links = [w for w, text in zip(about_controls, body)
                 if window_class(w) == 'SysLink' and text.endswith(homepage_line)]
        assert len(links) == 1, body
        content_rect, button_rect = W.RECT(), W.RECT()
        buttons = [w for w in about_controls if window_class(w) == 'Button']
        assert len(buttons) == 1, body
        assert USER32.GetWindowRect(links[0], C.byref(content_rect))
        assert USER32.GetWindowRect(buttons[0], C.byref(button_rect))
        assert content_rect.bottom <= button_rect.top, 'Homepage must be above the OK button'
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
        settings_before_parsers = ini_path.read_bytes()

        def current_buffer():
            return send(main_window, 2024 + 60, 0, 0)

        def new_document(value, host_language=0):
            old_buffer = current_buffer()
            send(main_window, 0x111, 41001, 0)  # File > New
            until(lambda: current_buffer() != old_buffer)
            send(editor, 2037, 65001, 0)  # UTF-8
            send(editor, 2031, 2, 0)  # LF
            assert send(main_window, 2024 + 6, 0, host_language)
            set_text(value)
            return current_buffer()

        def activate(buffer_id):
            position = send(main_window, 2024 + 57, buffer_id, 0)
            assert position >= 0
            send(main_window, 2024 + 28, position >> 30, position & 0x3FFFFFFF)
            until(lambda: current_buffer() == buffer_id)
            send(editor, 2031, 2, 0)  # Reactivating a tab restores its stored EOL mode.

        def format_to(expected_text):
            USER32.PostMessageW(main_window, 0x111, command, 0)
            until(lambda: text(editor) == expected_text)

        def replace_part(old, new):
            current = text(editor).encode('utf-8')
            start = current.index(old.encode('utf-8'))
            raw = new.encode('utf-8')
            assert KERNEL32.WriteProcessMemory(handle, memory, C.c_char_p(raw), len(raw), None)
            send(editor, 2190, start, 0)  # SCI_SETTARGETSTART
            send(editor, 2192, start + len(old.encode('utf-8')), 0)  # SCI_SETTARGETEND
            send(editor, 2194, len(raw), memory)  # SCI_REPLACETARGET

        format_as_command = menu_command(USER32.GetMenu(main_window), labels['format_as'])
        assert format_as_command is not None

        def wait_picker():
            picker = until(lambda: next((w for w in windows(process.pid)
                                        if window_class(w) == '#32770' and window_title(w) == PARSER_TITLES[language]), None))
            assert control_text(picker, 1) == labels['format']
            assert control_text(picker, 2) == labels['cancel']
            assert not USER32.IsWindowEnabled(get_control(picker, 1)), 'Picker must require an explicit choice'
            return picker

        def open_picker(command_id=command):
            USER32.PostMessageW(main_window, 0x111, command_id, 0)
            return wait_picker()

        def choose(picker, name):
            combo = get_control(picker, 401)
            wanted = C.create_unicode_buffer(name)
            index = send(combo, 0x158, -1, C.addressof(wanted))  # CB_FINDSTRINGEXACT
            assert index >= 0, name
            send(combo, 0x14E, index, 0)
            send(picker, 0x111, (1 << 16) | 401, combo)  # CBN_SELCHANGE
            assert USER32.IsWindowEnabled(get_control(picker, 1))
            USER32.PostMessageW(picker, 0x111, 1, 0)
            until(lambda: not USER32.IsWindow(picker))

        new_document('{"a":1}')
        format_to('{ "a": 1 }\n')
        new_document('const answer=42;', 58)  # L_JAVASCRIPT
        format_to('const answer = 42;\n')
        new_document('const answer:number=42;', 85)  # L_TYPESCRIPT
        format_to('const answer: number = 42;\n')
        new_document('{"a":1}', 22)  # L_PYTHON must not be silently treated as JSON.
        picker = open_picker()
        USER32.PostMessageW(picker, 0x111, 2, 0)
        until(lambda: not USER32.IsWindow(picker))
        assert text(editor) == '{"a":1}'
        print('PASS untitled: automatic JSON and Notepad++ JavaScript/TypeScript language selection', flush=True)

        first = new_document('const first=1;')
        picker = open_picker()
        USER32.PostMessageW(picker, 0x111, 2, 0)
        until(lambda: not USER32.IsWindow(picker))
        assert text(editor) == 'const first=1;', 'Cancel changed the document'
        picker = open_picker()
        choose(picker, 'JavaScript / JSX')
        until(lambda: text(editor) == 'const first = 1;\n')
        replace_part('first = 1', 'second=2')
        format_to('const second = 2;\n')

        second = new_document('const third=3;')
        picker = open_picker()  # Choice must not leak from the first document.
        USER32.PostMessageW(picker, 0x111, 2, 0)
        until(lambda: not USER32.IsWindow(picker))
        activate(first)
        replace_part('second = 2', 'fourth=4')
        format_to('const fourth = 4;\n')
        assert send(main_window, 2024 + 6, 0, 85)  # Changing language clears the manual choice.
        set_text('const fifth:number=5;')
        format_to('const fifth: number = 5;\n')
        assert send(main_window, 2024 + 6, 0, 0)
        picker = open_picker()
        USER32.PostMessageW(picker, 0x111, 2, 0)
        until(lambda: not USER32.IsWindow(picker))

        # Closing a document must clear the choice even if Notepad++ reuses its buffer ID.
        activate(second)
        choose(open_picker(), 'JavaScript / JSX')
        until(lambda: text(editor) == 'const third = 3;\n')
        send(editor, 2014, 0, 0)  # Mark clean so closing does not show a save prompt.
        send(main_window, 0x111, 41003, 0)  # File > Close
        until(lambda: current_buffer() != second)
        new_document('const fresh=6;')
        picker = open_picker()
        USER32.PostMessageW(picker, 0x111, 2, 0)
        until(lambda: not USER32.IsWindow(picker))
        assert text(editor) == 'const fresh=6;'
        choose(open_picker(), 'JavaScript / JSX')
        until(lambda: text(editor) == 'const fresh = 6;\n')
        set_text('{"saved":1}')
        saved_path = str(sandbox / 'saved.json').encode('utf-16-le') + b'\0\0'
        assert KERNEL32.WriteProcessMemory(handle, memory, C.c_char_p(saved_path), len(saved_path), None)
        assert send(main_window, 2024 + 78, 0, memory)  # NPPM_SAVECURRENTFILEAS
        format_to('{ "saved": 1 }\n')
        assert ini_path.read_bytes() == settings_before_parsers, 'Document choice must not write global settings'
        print('PASS untitled: localized picker, cancel, per-document memory, tab isolation, language change, close cleanup and saved-file inference', flush=True)

        def replace_document(value):
            raw = value.encode('utf-8') + b'\0'
            assert KERNEL32.WriteProcessMemory(handle, memory, C.c_char_p(raw), len(raw), None)
            send(editor, 2160, 0, -1)  # Select all, then replace selection as paste does.
            send(editor, 2170, 0, memory)

        def wait_parse_error():
            title, details, retry = PARSE_ERRORS[language]
            dialog = until(lambda: next((w for w in windows(process.pid)
                                        if window_class(w) == '#32770' and window_title(w) == title), None))
            assert retry in automation.text(dialog)
            return dialog

        # The saved JSON file can be formatted as JavaScript for one operation only.
        set_text('const temporary=7;')
        picker = open_picker(format_as_command)
        USER32.PostMessageW(picker, 0x111, 2, 0)
        until(lambda: not USER32.IsWindow(picker))
        assert text(editor) == 'const temporary=7;'
        choose(open_picker(format_as_command), 'JavaScript / JSX')
        until(lambda: text(editor) == 'const temporary = 7;\n')
        USER32.PostMessageW(main_window, 0x111, command, 0)
        error_dialog = wait_parse_error()  # Normal formatting still uses the .json extension.
        USER32.PostMessageW(error_dialog, 0x10, 0, 0)
        until(lambda: not USER32.IsWindow(error_dialog))
        assert text(editor) == 'const temporary = 7;\n'
        print('PASS one-time language override: saved file, cancellation and unchanged default parser', flush=True)

        new_document('const old=1;')
        choose(open_picker(), 'JavaScript / JSX')
        until(lambda: text(editor) == 'const old = 1;\n')
        replace_document('{"new":2}')
        format_to('{ "new": 2 }\n')
        replace_document('const again=3;')
        choose(open_picker(), 'JavaScript / JSX')
        until(lambda: text(editor) == 'const again = 3;\n')
        replace_document('')
        replace_document('body{color:red}')
        choose(open_picker(), 'CSS')
        until(lambda: text(editor) == 'body {\n  color: red;\n}\n')
        replace_part('red', 'blue')
        USER32.PostMessageW(main_window, 0x111, command, 0)
        until(lambda: labels['unchanged'] in status())  # Plugin writeback retained the CSS choice.
        assert text(editor) == 'body {\n  color: blue;\n}\n'
        print('PASS parser memory: select-all replacement and clear/paste reset; partial edits and formatter writeback retain choice', flush=True)

        new_document('const count=1;')
        choose(open_picker(), 'JavaScript / JSX')
        until(lambda: text(editor) == 'const count = 1;\n')
        replace_part('count = 1', 'count:number=1')
        invalid_js = text(editor)
        USER32.PostMessageW(main_window, 0x111, command, 0)
        error_dialog = wait_parse_error()
        automation.invoke(error_dialog, PARSE_ERRORS[language][1])
        # Invoke can return before DirectUI has expanded and exposed the details.
        until(lambda: 'SyntaxError' in automation.text(error_dialog))
        assert text(editor) == invalid_js
        USER32.PostMessageW(error_dialog, 0x10, 0, 0)
        until(lambda: not USER32.IsWindow(error_dialog))
        USER32.PostMessageW(main_window, 0x111, command, 0)
        error_dialog = wait_parse_error()
        USER32.PostMessageW(error_dialog, 1024 + 102, 100, 0)  # TDM_CLICK_BUTTON: retry
        choose(wait_picker(), 'TypeScript / TSX')
        until(lambda: text(editor) == 'const count: number = 1;\n')
        replace_part('count: number = 1', 'next:string="ok"')
        format_to('const next: string = "ok";\n')
        assert ini_path.read_bytes() == settings_before_parsers
        print('PASS parser recovery: original details, no replacement on failure, explicit retry and remembered correction', flush=True)

        java_source = 'class Hello{int value=1;}'
        java_expected = 'class Hello {\n\n  int value = 1;\n}\n'
        new_document(java_source, 6)  # L_JAVA
        USER32.PostMessageW(main_window, 0x111, command, 0)
        missing = until(lambda: next((w for w in windows(process.pid)
                                     if window_class(w) == '#32770' and window_title(w) == SETTING_ERRORS[language][0]), None))
        missing_text = automation.text(missing)
        assert JAVA_MISSING[language] in missing_text, missing_text
        assert 'npm install --global prettier-plugin-java' in missing_text
        assert text(editor) == java_source, 'Missing Java dependency changed the document'
        USER32.PostMessageW(missing, 0x10, 0, 0)
        until(lambda: not USER32.IsWindow(missing))
        for package in ('prettier-plugin-java', 'web-tree-sitter'):
            shutil.copytree(ROOT / 'node_modules' / package, sandbox / 'node_modules' / package)
        send(editor, 2171, 0, 0)  # SCI_EMPTYUNDOBUFFER
        send(editor, 2025, java_source.index('value'), 0)  # SCI_GOTOPOS
        format_to(java_expected)
        assert send(editor, 2008, 0, 0) == java_expected.index('value')
        send(editor, 2176, 0, 0)  # SCI_UNDO
        assert text(editor) == java_source, 'Java formatting must be one undo action'
        format_to(java_expected)
        print('PASS Java: localized missing dependency, install and retry, host language, caret and undo', flush=True)

        new_document(java_source)
        choose(open_picker(), 'Java')
        until(lambda: text(editor) == java_expected)
        replace_part('value = 1', 'value=2')
        format_to(java_expected.replace('1', '2'))
        # A one-time override also works while Notepad++ has another language selected.
        new_document(java_source, 58)
        choose(open_picker(format_as_command), 'Java')
        until(lambda: text(editor) == java_expected)
        saved_java = str(sandbox / 'Hello.java').encode('utf-16-le') + b'\0\0'
        assert KERNEL32.WriteProcessMemory(handle, memory, C.c_char_p(saved_java), len(saved_java), None)
        assert send(main_window, 2024 + 78, 0, memory)
        project_config.write_text('module.exports={tabWidth:4};', encoding='utf-8')
        format_to(java_expected.replace('  int', '    int'))
        (sandbox / '.prettierignore').write_text('Hello.java\n', encoding='utf-8')
        set_text(java_source)
        USER32.PostMessageW(main_window, 0x111, command, 0)
        until(lambda: '.prettierignore' in status())
        assert text(editor) == java_source
        project_config.unlink()
        print('PASS Java: picker memory, one-time override, saved extension, project config and ignore rules', flush=True)

        new_document('export const answer=1;', 6)
        USER32.PostMessageW(main_window, 0x111, command, 0)
        error_dialog = wait_parse_error()
        automation.invoke(error_dialog, PARSE_ERRORS[language][1])
        until(lambda: 'Failed to parse' in automation.text(error_dialog))
        assert text(editor) == 'export const answer=1;'
        USER32.PostMessageW(error_dialog, 1024 + 102, 100, 0)
        choose(wait_picker(), 'JavaScript / JSX')
        until(lambda: text(editor) == 'export const answer = 1;\n')
        assert ini_path.read_bytes() == settings_before_parsers
        print('PASS Java: original parse diagnostic, explicit language retry and unchanged global settings', flush=True)
        xml_source = '<root><item name="中文😀"/></root>'
        xml_expected = '<root><item name="中文😀" /></root>\n'
        new_document(xml_source, 9)  # L_XML
        USER32.PostMessageW(main_window, 0x111, command, 0)
        missing = until(lambda: next((w for w in windows(process.pid)
                                     if window_class(w) == '#32770' and window_title(w) == SETTING_ERRORS[language][0]), None))
        missing_text = automation.text(missing)
        assert XML_MISSING[language] in missing_text, missing_text
        assert 'npm install --global @prettier/plugin-xml' in missing_text
        assert text(editor) == xml_source, 'Missing XML dependency changed the document'
        USER32.PostMessageW(missing, 0x10, 0, 0)
        until(lambda: not USER32.IsWindow(missing))
        for package in ('@prettier/plugin-xml', '@xml-tools/parser', 'chevrotain', 'regexp-to-ast'):
            shutil.copytree(ROOT / 'node_modules' / package, sandbox / 'node_modules' / package)
        send(editor, 2171, 0, 0)
        send(editor, 2025, xml_source.encode('utf-8').index('中文'.encode('utf-8')), 0)
        format_to(xml_expected)
        assert send(editor, 2008, 0, 0) == xml_expected.encode('utf-8').index('中文'.encode('utf-8'))
        send(editor, 2176, 0, 0)
        assert text(editor) == xml_source, 'XML formatting must be one undo action'
        print('PASS XML: localized missing dependency, install and retry, host language, Unicode caret and undo', flush=True)

        new_document(xml_source)
        choose(open_picker(), 'XML')
        until(lambda: text(editor) == xml_expected)
        replace_part('name=', 'name = ')
        format_to(xml_expected)
        saved_xml = str(sandbox / 'example.xml').encode('utf-16-le') + b'\0\0'
        assert KERNEL32.WriteProcessMemory(handle, memory, C.c_char_p(saved_xml), len(saved_xml), None)
        assert send(main_window, 2024 + 78, 0, memory)
        project_config.write_text('module.exports={xmlWhitespaceSensitivity:"ignore",tabWidth:4};', encoding='utf-8')
        format_to('<root>\n    <item name="中文😀" />\n</root>\n')
        (sandbox / '.prettierignore').write_text('example.xml\n', encoding='utf-8')
        set_text(xml_source)
        USER32.PostMessageW(main_window, 0x111, command, 0)
        until(lambda: '.prettierignore' in status())
        assert text(editor) == xml_source
        project_config.unlink()
        new_document('const answer=1;', 9)
        USER32.PostMessageW(main_window, 0x111, command, 0)
        error_dialog = wait_parse_error()
        automation.invoke(error_dialog, PARSE_ERRORS[language][1])
        until(lambda: 'SyntaxError' in automation.text(error_dialog))
        assert text(editor) == 'const answer=1;'
        USER32.PostMessageW(error_dialog, 1024 + 102, 100, 0)
        choose(wait_picker(), 'JavaScript / JSX')
        until(lambda: text(editor) == 'const answer = 1;\n')
        print('PASS XML: picker memory, saved file, project config, ignore rules and explicit syntax-error recovery', flush=True)

        for name, source, expected_text in (
            ('JSONC', '// keep\n{"a":1}', '// keep\n{ "a": 1 }\n'),
            ('MDX', '# Hello\n\n<Box a={1+2}/>', '# Hello\n\n<Box a={1 + 2} />\n'),
            ('Handlebars', '<div>{{ name }}</div>', '<div>{{name}}</div>'),
        ):
            new_document(source, 58)  # Explicit override of Notepad++ JavaScript.
            choose(open_picker(format_as_command), name)
            until(lambda: text(editor) == expected_text)
        assert ini_path.read_bytes() == settings_before_parsers
        print('PASS language picker: JSONC, MDX and Handlebars without extra packages', flush=True)
        installed = set()

        def install_test_package(name):
            if name in installed:
                return
            installed.add(name)
            package_dir = ROOT / 'node_modules' / name
            shutil.copytree(package_dir, sandbox / 'node_modules' / name, dirs_exist_ok=True)
            metadata = json.loads((package_dir / 'package.json').read_text(encoding='utf-8'))
            for dependency in metadata.get('dependencies', {}):
                install_test_package(dependency)
            for dependency in metadata.get('optionalDependencies', {}):
                if (ROOT / 'node_modules' / dependency).is_dir():
                    install_test_package(dependency)

        for name, package, host_language, extension, source, formatted in (
            ('PHP', '@prettier/plugin-php', 1, 'php', '<?php $answer=1+2;', '<?php $answer = 1 + 2;\n'),
            ('SQL', 'prettier-plugin-sql', 17, 'sql', 'select a,b from users;', 'select\n  a,\n  b\nfrom\n  users;\n'),
            ('Properties', 'prettier-plugin-properties', 34, 'properties', 'greeting=中文😀', 'greeting = 中文😀\n'),
            ('TOML', 'prettier-plugin-toml', 92, 'toml', 'answer=42', 'answer = 42\n'),
            ('Shell / Bash', 'prettier-plugin-sh', 26, 'sh', 'if true;then echo "hello";fi', 'if true; then echo "hello"; fi\n'),
        ):
            new_document(source, host_language)
            USER32.PostMessageW(main_window, 0x111, command, 0)
            missing = until(lambda: next((w for w in windows(process.pid)
                                         if window_class(w) == '#32770' and window_title(w) == SETTING_ERRORS[language][0]), None))
            message = automation.text(missing)
            expected_message = (f'{name} formatting requires {package}.' if language == 'en'
                                else f'{name} 格式化需要 {package}。')
            if name in ('TOML', 'Shell / Bash'):
                assert ('Node.js 20+' if name == 'TOML' else 'Prettier 3.6+') in message
            else:
                assert expected_message in message, message
            assert f'npm install --global {package}' in message
            assert text(editor) == source
            USER32.PostMessageW(missing, 0x10, 0, 0)
            until(lambda: not USER32.IsWindow(missing))
            install_test_package(package)
            send(editor, 2171, 0, 0)
            format_to(formatted)
            send(editor, 2176, 0, 0)
            assert text(editor) == source, f'{name} formatting must be one undo action'
            new_document(source)
            choose(open_picker(), name)
            until(lambda: text(editor) == formatted)
            new_document(source)
            filename = str(sandbox / f'example.{extension}').encode('utf-16-le') + b'\0\0'
            assert KERNEL32.WriteProcessMemory(handle, memory, C.c_char_p(filename), len(filename), None)
            assert send(main_window, 2024 + 78, 0, memory)
            format_to(formatted)
            print(f'PASS {name}: localized dependency guidance, install/retry, host language, picker, saved file and undo', flush=True)

        bracket_sql = 'select [name] from [users];'
        formatted_sql = 'select\n  [name]\nfrom\n  [users];\n'
        new_document(bracket_sql, 17)
        USER32.PostMessageW(main_window, 0x111, command, 0)
        error_dialog = wait_parse_error()
        automation.invoke(error_dialog, PARSE_ERRORS[language][1])
        until(lambda: 'Parse error:' in automation.text(error_dialog))
        assert text(editor) == bracket_sql
        USER32.PostMessageW(error_dialog, 0x10, 0, 0)
        until(lambda: not USER32.IsWindow(error_dialog))
        dialog = open_settings()
        assert control_text(dialog, 106) == 'MySQL'
        send(get_control(dialog, 106), 0x14E, 5, 0)
        USER32.PostMessageW(dialog, 0x111, 1, 0)
        until(lambda: not USER32.IsWindow(dialog))
        format_to(formatted_sql)
        dialog = open_settings()
        assert control_text(dialog, 106) == 'SQL Server (T-SQL)'
        send(get_control(dialog, 106), 0x14E, 1, 0)
        USER32.PostMessageW(dialog, 0x111, 1, 0)
        until(lambda: not USER32.IsWindow(dialog))
        new_document(bracket_sql, 17)
        filename = str(sandbox / 'override.sql').encode('utf-16-le') + b'\0\0'
        assert KERNEL32.WriteProcessMemory(handle, memory, C.c_char_p(filename), len(filename), None)
        assert send(main_window, 2024 + 78, 0, memory)
        project_config.write_text('module.exports={language:"transactsql"};', encoding='utf-8')
        format_to(formatted_sql)
        project_config.unlink()
        assert ini_path.read_bytes() == settings_before_parsers
        print('PASS SQL dialect: persisted setting, original error, retry after change and project precedence', flush=True)

        shell_source = 'values=(one two)'
        new_document(shell_source, 26)
        USER32.PostMessageW(main_window, 0x111, command, 0)
        error_dialog = wait_parse_error()  # Saved POSIX setting rejects Bash arrays.
        assert text(editor) == shell_source
        USER32.PostMessageW(error_dialog, 0x10, 0, 0)
        until(lambda: not USER32.IsWindow(error_dialog))
        dialog = open_settings()
        assert control_text(dialog, 107) == 'POSIX sh'
        send(get_control(dialog, 107), 0x14E, 0, 0)
        USER32.PostMessageW(dialog, 0x111, 1, 0)
        until(lambda: not USER32.IsWindow(dialog))
        format_to(shell_source + '\n')
        dialog = open_settings()
        assert control_text(dialog, 107) == 'Bash'
        send(get_control(dialog, 107), 0x14E, 1, 0)
        USER32.PostMessageW(dialog, 0x111, 1, 0)
        until(lambda: not USER32.IsWindow(dialog))
        filename = str(sandbox / 'override.sh').encode('utf-16-le') + b'\0\0'
        assert KERNEL32.WriteProcessMemory(handle, memory, C.c_char_p(filename), len(filename), None)
        assert send(main_window, 2024 + 78, 0, memory)
        project_config.write_text('module.exports={variant:1};', encoding='utf-8')
        set_text(shell_source)
        format_to(shell_source + '\n')
        project_config.unlink()
        assert ini_path.read_bytes() == settings_before_parsers
        print('PASS Shell dialect: persisted setting, parse failure, retry and project precedence', flush=True)
        dialog = open_settings()
        report_text = check_environment(dialog)
        available = {'en': 'Available', 'zh-CN': '可用', 'zh-TW': '可用'}[language]
        for package in ('prettier-plugin-java', '@prettier/plugin-xml', '@prettier/plugin-php',
                        'prettier-plugin-sql', 'prettier-plugin-properties', 'prettier-plugin-toml', 'prettier-plugin-sh'):
            assert f'{package}: {available}' in report_text, report_text
        assert str(sandbox / 'override.sh') in report_text
        assert ini_path.read_bytes() == settings_before_parsers
        USER32.PostMessageW(dialog, 0x111, 2, 0)
        until(lambda: not USER32.IsWindow(dialog))
        print('PASS environment: all seven optional extensions, versions and current document context', flush=True)
        report = {'architecture': architecture, 'language': language, 'checks': 28,
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
