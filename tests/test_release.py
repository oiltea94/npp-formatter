"""Release assembly checks using the actual three-architecture build artifacts."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from release import assemble, check_tag, release_notes, version_parts
sys.path.insert(0, str(ROOT))
from scripts.catalog_pr import prepare, UPSTREAM


class ReleaseTests(unittest.TestCase):
    def test_tag_and_version_validation(self):
        check_tag('v0.1.0', '0.1.0')
        for tag in ('v0.2.0', '0.1.0', 'v0.1.0-rc1'):
            with self.assertRaises(ValueError):
                check_tag(tag, '0.1.0')
        for version in ('01.2.3', '1.2', '../1.2.3', '65536.0.0'):
            with self.assertRaises(ValueError):
                version_parts(version)

    def test_release_notes_require_exact_nonempty_section(self):
        self.assertEqual(release_notes('# Changes\n\n## 0.1.0\n\nNotes\n\n## 0.0.1\nOld\n', '0.1.0'), 'Notes\n')
        for text in ('## 0.1.0\n', '## 0.1.00\nNotes\n'):
            with self.assertRaises(ValueError):
                release_notes(text, '0.1.0')

    def candidates(self, directory):
        version = json.loads((ROOT / 'package.json').read_text())['version']
        source = Path(os.environ.get('RELEASE_CANDIDATES', ROOT / 'dist'))
        target = directory / 'candidates'
        target.mkdir()
        for arch in ('x86', 'x64', 'arm64'):
            name = f'NppFormatter-{version}-{arch}.zip'
            matches = list(source.rglob(name))
            if len(matches) != 1:
                raise RuntimeError(f'Expected one {name}; build all architectures or set RELEASE_CANDIDATES')
            folder = target / f'NppFormatter-{arch}'
            folder.mkdir()
            for suffix in ('', '.sha256'):
                shutil.copyfile(str(matches[0]) + suffix, folder / (name + suffix))
        return target, version

    def test_assemble_checks_layout_hashes_and_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            candidates, version = self.candidates(directory)
            output = directory / 'release'
            assemble(candidates, output, version, ROOT)
            manifest = json.loads((output / 'manifest.json').read_text())
            self.assertEqual(set(manifest['architectures']), {'x86', 'x64', 'arm64'})
            self.assertEqual(len(list(output.glob('*.zip'))), 6)
            for arch, record in manifest['architectures'].items():
                manual = output / record['manual']['name']
                admin = output / record['admin']['name']
                self.assertEqual(manual.read_bytes(), next(candidates.rglob(manual.name)).read_bytes())
                with zipfile.ZipFile(manual) as original, zipfile.ZipFile(admin) as package:
                    self.assertIn('NppFormatter.dll', package.namelist())
                    self.assertIn('bridge.cjs', package.namelist())
                    for name in package.namelist():
                        self.assertEqual(package.read(name), original.read('NppFormatter/' + name))
                entry = json.loads((output / f'nppPluginList-entry-{arch}.json').read_text())
                self.assertEqual(entry['id'], hashlib.sha256(admin.read_bytes()).hexdigest())
                self.assertTrue(entry['repository'].endswith('/' + admin.name))
            for line in (output / 'SHA256SUMS').read_text().splitlines():
                digest, name = line.split('  ')
                self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), digest)

    def test_invalid_candidates_leave_no_release_directory(self):
        for failure in ('missing', 'duplicate', 'checksum', 'wrong-arch', 'extra-file', 'stale-source', 'wrong-version'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                candidates, version = self.candidates(directory)
                archive = next(candidates.rglob(f'NppFormatter-{version}-x64.zip'))
                if failure == 'missing':
                    archive.unlink()
                elif failure == 'duplicate':
                    shutil.copyfile(archive, candidates / archive.name)
                elif failure == 'checksum':
                    archive.write_bytes(archive.read_bytes() + b'changed')
                else:
                    with zipfile.ZipFile(archive) as package:
                        entries = {name: package.read(name) for name in package.namelist()}
                    if failure == 'wrong-arch':
                        other = next(candidates.rglob(f'NppFormatter-{version}-x86.zip'))
                        with zipfile.ZipFile(other) as package:
                            entries['NppFormatter/NppFormatter.dll'] = package.read('NppFormatter/NppFormatter.dll')
                    elif failure == 'extra-file':
                        entries['NppFormatter/node.exe'] = b'unwanted dependency'
                    elif failure == 'stale-source':
                        entries['NppFormatter/bridge.cjs'] = b'outdated bridge'
                    else:
                        data = entries['NppFormatter/NppFormatter.dll']
                        signature = bytes.fromhex('bd04effe00000100')
                        offset = data.index(signature) + 8
                        entries['NppFormatter/NppFormatter.dll'] = data[:offset] + bytes.fromhex('09000900') + data[offset + 4:]
                    with zipfile.ZipFile(archive, 'w') as package:
                        for name, payload in entries.items():
                            package.writestr(name, payload)
                    archive.with_suffix('.zip.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name + '\n')
                output = directory / 'release'
                with self.assertRaises((ValueError, FileNotFoundError)):
                    assemble(candidates, output, version, ROOT)
                self.assertFalse(output.exists())

    def test_catalog_preparation_verifies_published_assets_without_writes(self):
        for failure in (None, 'manifest', 'checksum', 'draft'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                candidates, version = self.candidates(directory)
                release = directory / 'release'
                assemble(candidates, release, version, ROOT)
                repository, fork = 'oiltea94/npp-formatter', 'oiltea94/nppPluginList'
                args = SimpleNamespace(tag='v' + version, repository=repository, fork=fork, output=directory / 'proposal')

                def api(endpoint, method='GET', data=None):
                    self.assertEqual(method, 'GET', 'Preparation must never write to GitHub')
                    responses = {
                        f'repos/{repository}/releases/tags/v{version}': {
                            'draft': failure == 'draft', 'prerelease': False, 'tag_name': 'v' + version},
                        f'repos/{UPSTREAM}': {'default_branch': 'master'},
                        f'repos/{fork}': {'fork': True, 'parent': {'full_name': UPSTREAM}},
                        f'repos/{UPSTREAM}/commits/master': {'sha': 'upstream'},
                        f'repos/{fork}/git/matching-refs/heads/nppformatter-v{version}': [],
                    }
                    return responses[endpoint]

                def file_at(repo, path, ref):
                    self.assertEqual((repo, ref), (UPSTREAM, 'upstream'))
                    if path == 'pl.schema':
                        return json.dumps({'type': 'object', 'required': ['npp-plugins']})
                    return json.dumps({'name': 'npp-pluginList', 'version': '1', 'arch': path, 'npp-plugins': []})

                def download(url, path):
                    payload = (release / path.name).read_bytes()
                    if failure == 'manifest' and path.name == 'manifest.json':
                        document = json.loads(payload)
                        document['version'] = '99.0.0'
                        payload = json.dumps(document).encode()
                    elif failure == 'checksum' and path.suffix == '.zip':
                        payload += b'changed'
                    path.write_bytes(payload)
                    return payload

                with patch('scripts.catalog_pr.api', side_effect=api), \
                     patch('scripts.catalog_pr.pages', return_value=[]), \
                     patch('scripts.catalog_pr.file_at', side_effect=file_at), \
                     patch('scripts.catalog_pr.download', side_effect=download):
                    if failure:
                        with self.assertRaises(ValueError):
                            prepare(args)
                        self.assertFalse((args.output / 'plan.json').exists())
                    else:
                        plan, changes, body = prepare(args)
                        self.assertEqual(set(plan['entries']), {'x86', 'x64', 'arm64'})
                        self.assertEqual({item['path'] for item in changes}, {'src/pl.x86.json', 'src/pl.x64.json', 'src/pl.arm64.json'})
                        self.assertIn('NppFormatter', body)
                        self.assertTrue((args.output / 'plan.json').is_file())


if __name__ == '__main__':
    unittest.main()
