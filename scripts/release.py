"""Validate release versions and assemble verified packages for all architectures."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import tempfile
import zipfile

from verify_package import FILES, MACHINES, PE, verify_dll

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'oiltea94/npp-formatter'
MINIMUM_NPP = '8.9.6'
SOURCE_FILES = {
    'bridge.cjs': 'bridge/bridge.cjs',
    'README.md': 'README.md', 'README.zh-CN.md': 'README.zh-CN.md',
    'licenses/NotepadPlusPlus-GPL.txt': 'third_party/npp/LICENSE',
    'licenses/Scintilla.txt': 'third_party/npp/Scintilla-LICENSE.txt',
    'licenses/nlohmann-json.txt': 'third_party/json/LICENSE.MIT',
}


def version_parts(version):
    if not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', version):
        raise ValueError('Expected a stable MAJOR.MINOR.PATCH version')
    parts = tuple(map(int, version.split('.')))
    if any(part > 65535 for part in parts):
        raise ValueError('Windows version components must be at most 65535')
    return parts + (0,)


def check_tag(tag, version):
    version_parts(version)
    if tag != 'v' + version:
        raise ValueError('Tag does not match package.json version')


def release_notes(changelog, version):
    for section in re.split(r'^## ', changelog, flags=re.MULTILINE)[1:]:
        heading, _, body = section.partition('\n')
        if heading.strip() == version and body.strip():
            return body.strip() + '\n'
    raise ValueError(f'Missing or empty changelog section for {version}')


def prepare_version(build_dir, version):
    parts = version_parts(version)
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / 'version.hpp').write_text(
        '#pragma once\n#define NPP_FORMATTER_VERSION_W L"' + version + '"\n', encoding='utf-8')
    numeric = ','.join(map(str, parts))
    resource = f'''#include <windows.h>
1 VERSIONINFO
 FILEVERSION {numeric}
 PRODUCTVERSION {numeric}
 FILEFLAGSMASK 0x3fL
 FILEFLAGS 0
 FILEOS VOS_NT_WINDOWS32
 FILETYPE VFT_DLL
 FILESUBTYPE 0
BEGIN
 BLOCK "StringFileInfo"
 BEGIN
  BLOCK "040904b0"
  BEGIN
   VALUE "FileDescription", "NppFormatter\\0"
   VALUE "FileVersion", "{version}\\0"
   VALUE "InternalName", "NppFormatter\\0"
   VALUE "OriginalFilename", "NppFormatter.dll\\0"
   VALUE "ProductName", "NppFormatter\\0"
   VALUE "ProductVersion", "{version}\\0"
  END
 END
 BLOCK "VarFileInfo"
 BEGIN
  VALUE "Translation", 0x0409, 1200
 END
END
'''
    (build_dir / 'version.rc').write_text(resource, encoding='utf-8')


def metadata(data):
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def check_archive(data, arch, version, prefix=''):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        if set(names) != {prefix + name for name in FILES} or len(names) != len(FILES):
            raise ValueError('Unexpected or duplicate ZIP entries')
        entries = {name: archive.read(prefix + name) for name in FILES}
    dll = entries['NppFormatter.dll']
    verify_dll(dll, arch)
    if PE(dll).version() != version_parts(version):
        raise ValueError('DLL version does not match package.json / release tag')
    return entries


def build_entry(version, arch, digest, repository=REPOSITORY):
    version_parts(version)
    if arch not in MACHINES or not re.fullmatch(r'[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('Invalid architecture or owner/repository')
    if not re.fullmatch(r'[0-9a-f]{64}', digest):
        raise ValueError('Expected a SHA-256 digest')
    homepage = 'https://github.com/' + repository
    return {
        'folder-name': 'NppFormatter', 'display-name': 'NppFormatter', 'version': version,
        'npp-compatible-versions': f'[{MINIMUM_NPP},]', 'id': digest,
        'repository': f'{homepage}/releases/download/v{version}/NppFormatter-{version}-{arch}-plugin-admin.zip',
        'description': 'Format with Prettier, Python with Ruff, or C/C++ with clang-format and project configuration. Optional Java, XML, PHP, '
                       'SQL, Properties, TOML and Shell packages. Includes environment checks. '
                       'Install clang-format for C/C++, Ruff for Python, or Node.js, Prettier and optional packages for Prettier languages.',
        'author': 'OILTEA', 'homepage': homepage,
    }


def assemble(candidates, output, version, source_root=ROOT, repository=REPOSITORY):
    version_parts(version)
    if output.exists():
        raise FileExistsError(output)
    payloads, architectures = {}, {}
    for arch in MACHINES:
        name = f'NppFormatter-{version}-{arch}.zip'
        matches = list(candidates.rglob(name))
        if len(matches) != 1:
            raise ValueError(f'Expected exactly one release candidate: {name}')
        path = matches[0]
        data = path.read_bytes()
        digest = metadata(data)['sha256']
        if path.with_suffix('.zip.sha256').read_text(encoding='ascii').strip() != f'{digest}  {name}':
            raise ValueError(f'Archive checksum mismatch: {name}')
        entries = check_archive(data, arch, version, 'NppFormatter/')
        for filename, source in SOURCE_FILES.items():
            # Windows checkouts can use CRLF; compare the tracked text consistently on Linux.
            if entries[filename].replace(b'\r\n', b'\n') != (source_root / source).read_bytes().replace(b'\r\n', b'\n'):
                raise ValueError(f'Package differs from source: {filename}')
        admin_name = f'NppFormatter-{version}-{arch}-plugin-admin.zip'
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for filename, content in sorted(entries.items()):
                info = zipfile.ZipInfo(filename, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, content)
        admin = buffer.getvalue()
        check_archive(admin, arch, version)
        payloads[name], payloads[admin_name] = data, admin
        record = {'manual': dict(name=name, **metadata(data)),
                  'admin': dict(name=admin_name, **metadata(admin)),
                  'dll': metadata(entries['NppFormatter.dll'])}
        architectures[arch] = record
        entry = build_entry(version, arch, record['admin']['sha256'], repository)
        payloads[f'nppPluginList-entry-{arch}.json'] = (json.dumps(entry, indent=2) + '\n').encode()
    manifest = {'version': version, 'repository': repository, 'architectures': architectures}
    payloads['manifest.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    payloads['SHA256SUMS'] = ''.join(f'{metadata(data)["sha256"]}  {name}\n'
                                   for name, data in sorted(payloads.items())).encode()
    # Publish the directory only after all three candidates passed every check.
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        staging = Path(temporary) / 'release'
        staging.mkdir()
        for name, data in payloads.items():
            (staging / name).write_bytes(data)
        shutil.move(str(staging), str(output))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare')
    prepare.add_argument('--build-dir', type=Path, required=True)
    validate = commands.add_parser('check')
    validate.add_argument('--tag')
    collect = commands.add_parser('assemble')
    collect.add_argument('--candidates', type=Path, required=True)
    collect.add_argument('--output', type=Path, required=True)
    collect.add_argument('--notes', type=Path, required=True)
    collect.add_argument('--repository', default=REPOSITORY)
    args = parser.parse_args()
    version = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))['version']
    if args.command == 'prepare':
        prepare_version(args.build_dir, version)
    else:
        version_parts(version)
        lock = json.loads((ROOT / 'package-lock.json').read_text(encoding='utf-8'))
        if lock['version'] != version or lock['packages']['']['version'] != version:
            raise ValueError('package-lock.json version differs from package.json')
        notes = release_notes((ROOT / 'CHANGELOG.md').read_text(encoding='utf-8'), version)
        if args.command == 'check':
            if args.tag is not None:
                check_tag(args.tag, version)
            print(f'PASS release version and changelog: {version}')
        else:
            assemble(args.candidates, args.output, version, repository=args.repository)
            args.notes.write_text(notes, encoding='utf-8')
            print(f'PASS release assembly: {version}, x86/x64/ARM64, 6 ZIPs, manifest, catalog entries, SHA256SUMS')


if __name__ == '__main__':
    main()
