"""Exercise the built plugin in a separate, hidden portable Notepad++ instance."""
import ctypes as C
import argparse
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


def window_class(window):
    name = C.create_unicode_buffer(256)
    USER32.GetClassNameW(window, name, len(name))
    return name.value


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


def run(sandbox, architecture):
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
        command = until(lambda: menu_command(USER32.GetMenu(main_window), 'Format document'))
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
            setting_command = menu_command(USER32.GetMenu(main_window), 'Settings...')
            assert setting_command is not None
            USER32.PostMessageW(main_window, 0x111, setting_command, 0)
            return until(lambda: next((w for w in windows(process.pid) if window_class(w) == 'NppFormatterSettings'), None))

        def detect(dialog, identifier):
            USER32.PostMessageW(dialog, 0x111, identifier, 0)
            until(lambda: 'Detecting ' in control_text(dialog, 105))
            assert not USER32.IsWindowEnabled(get_control(dialog, 1)), 'Save stayed enabled during detection'
            until(lambda: USER32.IsWindowEnabled(get_control(dialog, identifier)), timeout=15)
            assert control_text(dialog, 105).startswith('Detected.'), control_text(dialog, 105)

        ini_path = config_dir / 'NppFormatter.ini'
        before = ini_path.read_bytes()
        dialog = open_settings()
        for browse_id, detect_id in ((201, 203), (202, 204)):
            browse_rect, detect_rect = W.RECT(), W.RECT()
            assert get_control(dialog, detect_id), 'Auto-detect button is missing'
            USER32.GetWindowRect(get_control(dialog, browse_id), C.byref(browse_rect))
            USER32.GetWindowRect(get_control(dialog, detect_id), C.byref(detect_rect))
            assert detect_rect.left > browse_rect.right, 'Auto-detect is not after Browse'
        set_control(dialog, 101, '')
        set_control(dialog, 102, 'keep this value')
        USER32.PostMessageW(dialog, 0x111, 204, 0)
        until(lambda: 'Node.js first' in control_text(dialog, 105))
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
        until(lambda: 'Detecting ' in control_text(dialog, 105))
        started = time.monotonic()
        USER32.PostMessageW(dialog, 0x111, 2, 0)
        until(lambda: not USER32.IsWindow(dialog))
        assert time.monotonic() - started < 2, 'Cancel blocked during detection'
        assert ini_path.read_bytes() == before
        dialog = open_settings()
        detect(dialog, 204)
        USER32.PostMessageW(dialog, 0x111, 1, 0)
        until(lambda: not USER32.IsWindow(dialog))
        assert str(project_prettier) in ini_path.read_text(encoding='utf-16')
        assert ini_path.with_suffix('.ini.bak').read_bytes() == before
        print('PASS settings: detection buttons, Node/project discovery, preserve on failure, Cancel and explicit Save', flush=True)

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
        until(lambda: 'already formatted' in status())
        assert not send(editor, 2174, 0, 0), 'No-op added an undo record'
        print('PASS real editor: no-op preserves undo history', flush=True)

        # Delay user config to make the edit-during-format race deterministic.
        project_config = sandbox / 'prettier.config.cjs'
        project_config.write_text('Atomics.wait(new Int32Array(new SharedArrayBuffer(4)),0,0,800);module.exports={};', encoding='utf-8')
        set_text(original)
        USER32.PostMessageW(main_window, 0x111, command, 0)
        until(lambda: status() == 'NppFormatter: formatting...')
        changed = original + '// typed while formatting\n'
        started = time.monotonic()
        set_text(changed)
        assert time.monotonic() - started < 0.5, 'Editor blocked during formatting'
        until(lambda: 'result discarded' in status())
        assert text(editor) == changed, 'Stale result overwrote the edit'
        print('PASS real editor: responsive during formatting; stale result discarded', flush=True)
        project_config.unlink()
        report = {'architecture': architecture, 'checks': 6, 'result': 'PASS'}
        (ROOT / 'build' / architecture / 'editor-smoke.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
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
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='npp-formatter-test-\u4e2d\u6587 ') as directory:
        run(Path(directory), args.arch)
