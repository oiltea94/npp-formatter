"""Check PE architecture, plugin exports, runtime imports and ZIP contents."""
import argparse
from pathlib import Path
import struct
import zipfile

MACHINES = {'x86': 0x014C, 'x64': 0x8664, 'arm64': 0xAA64}
EXPORTS = {'isUnicode', 'getName', 'getFuncsArray', 'setInfo', 'beNotified', 'messageProc'}
FILES = {
    'NppFormatter.dll', 'bridge.cjs', 'README.md', 'README.zh-CN.md',
    'licenses/NotepadPlusPlus-GPL.txt', 'licenses/Scintilla.txt',
    'licenses/nlohmann-json.txt',
}


class PE:
    def __init__(self, data):
        self.data = data
        if data[:2] != b'MZ':
            raise ValueError('Missing DOS header')
        header = self.unpack('<I', 0x3C)[0]
        if data[header:header + 4] != b'PE\0\0':
            raise ValueError('Missing PE header')
        self.machine, count = self.unpack('<HH', header + 4)
        self.characteristics = self.unpack('<H', header + 22)[0]
        optional_size = self.unpack('<H', header + 20)[0]
        optional = header + 24
        magic = self.unpack('<H', optional)[0]
        if magic not in (0x10B, 0x20B):
            raise ValueError('Unsupported PE optional header')
        self.directories = optional + (96 if magic == 0x10B else 112)
        sections = optional + optional_size
        self.sections = [self.unpack('<IIII', sections + i * 40 + 8) for i in range(count)]

    def unpack(self, fmt, offset):
        return struct.unpack_from(fmt, self.data, offset)

    def offset(self, rva):
        for virtual_size, virtual_address, raw_size, raw_offset in self.sections:
            if virtual_address <= rva < virtual_address + max(virtual_size, raw_size):
                delta = rva - virtual_address
                if delta < raw_size:
                    return raw_offset + delta
        raise ValueError('Unmapped PE address')

    def string(self, rva):
        start = self.offset(rva)
        return self.data[start:self.data.index(b'\0', start)].decode('ascii')

    def exports(self):
        rva = self.unpack('<I', self.directories)[0]
        if not rva:
            return set()
        table = self.offset(rva)
        count = self.unpack('<I', table + 24)[0]
        names = self.offset(self.unpack('<I', table + 32)[0])
        return {self.string(self.unpack('<I', names + i * 4)[0]) for i in range(count)}

    def imports(self):
        rva = self.unpack('<I', self.directories + 8)[0]
        result = set()
        if rva:
            table = self.offset(rva)
            while any(self.unpack('<IIIII', table)):
                result.add(self.string(self.unpack('<I', table + 12)[0]).lower())
                table += 20
        return result


def verify_dll(data, arch):
    pe = PE(data)
    if pe.machine != MACHINES[arch]:
        raise ValueError(f'Expected {arch} machine, got 0x{pe.machine:04X}')
    if not pe.characteristics & 0x2000:
        raise ValueError('Plugin is not a DLL')
    missing = EXPORTS - pe.exports()
    if missing:
        raise ValueError(f'Missing plugin exports: {sorted(missing)}')
    system = {'kernel32.dll', 'user32.dll', 'gdi32.dll', 'comdlg32.dll', 'comctl32.dll',
              'advapi32.dll', 'shell32.dll', 'ole32.dll', 'ucrtbase.dll', 'msvcrt.dll',
              'ntdll.dll', 'bcrypt.dll'}
    external = {name for name in pe.imports() if name not in system
                and not name.startswith(('api-ms-win-', 'ext-ms-win-'))}
    if external:
        raise ValueError(f'Unbundled DLL dependencies: {sorted(external)}')


def verify_package(path, arch, stage):
    with zipfile.ZipFile(path) as archive:
        expected = {f'NppFormatter/{name}' for name in FILES}
        if set(archive.namelist()) != expected or len(archive.namelist()) != len(expected):
            raise ValueError('Unexpected or duplicate ZIP entries')
        for name in FILES:
            payload = archive.read(f'NppFormatter/{name}')
            if payload != (stage / name).read_bytes():
                raise ValueError(f'ZIP differs from staging: {name}')
        verify_dll(archive.read('NppFormatter/NppFormatter.dll'), arch)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=MACHINES, required=True)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--stage', type=Path, required=True)
    args = parser.parse_args()
    verify_package(args.package, args.arch, args.stage)
    print(f'PASS {args.arch}: PE machine, six exports, system imports, seven ZIP entries and staged bytes')
