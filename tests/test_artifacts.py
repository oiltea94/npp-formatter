"""Regression checks against actual built DLLs and packages."""
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from verify_package import MACHINES, PE, verify_dll, verify_package


class ArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.architectures = [arch for arch in MACHINES
                             if (ROOT / 'dist' / arch / 'NppFormatter/NppFormatter.dll').is_file()]
        if not cls.architectures:
            raise RuntimeError('Build at least one architecture before running artifact tests.')

    def test_rejects_wrong_machine_and_missing_export(self):
        for arch in self.architectures:
            with self.subTest(arch=arch):
                data = (ROOT / 'dist' / arch / 'NppFormatter/NppFormatter.dll').read_bytes()
                verify_dll(data, arch)
                other = next(candidate for candidate in MACHINES if candidate != arch)
                with self.assertRaisesRegex(ValueError, 'machine'):
                    verify_dll(data, other)
                pe = PE(data)
                broken = bytearray(data)
                struct.pack_into('<I', broken, pe.directories, 0)
                with self.assertRaisesRegex(ValueError, 'Missing plugin exports'):
                    verify_dll(broken, arch)

    def test_rejects_unbundled_runtime_import(self):
        for arch in self.architectures:
            with self.subTest(arch=arch):
                data = (ROOT / 'dist' / arch / 'NppFormatter/NppFormatter.dll').read_bytes()
                name = next(name for name in (b'KERNEL32.dll', b'kernel32.dll') if name in data)
                broken = data.replace(name, b'BADLIB32.dll')
                with self.assertRaisesRegex(ValueError, 'Unbundled DLL dependencies'):
                    verify_dll(broken, arch)

    def test_rejects_extra_files_and_stale_payload(self):
        version = json.loads((ROOT / 'package.json').read_text())['version']
        for arch in self.architectures:
            stage = ROOT / 'dist' / arch / 'NppFormatter'
            original = ROOT / 'dist' / f'NppFormatter-{version}-{arch}.zip'
            with zipfile.ZipFile(original) as package:
                entries = {name: package.read(name) for name in package.namelist()}
            for failure in ('extra', 'stale'):
                with self.subTest(arch=arch, failure=failure), tempfile.TemporaryDirectory() as directory:
                    modified = dict(entries)
                    if failure == 'extra':
                        modified['NppFormatter/node.exe'] = b'unwanted runtime'
                    else:
                        modified['NppFormatter/bridge.cjs'] = b'outdated bridge'
                    candidate = Path(directory) / 'candidate.zip'
                    with zipfile.ZipFile(candidate, 'w') as package:
                        for name, data in modified.items():
                            package.writestr(name, data)
                    with self.assertRaisesRegex(ValueError, 'Unexpected|differs'):
                        verify_package(candidate, arch, stage)


if __name__ == '__main__':
    unittest.main()
