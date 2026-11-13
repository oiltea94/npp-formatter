"""Fetch Ruff 0.17.5 for tests only; never include it in plugin packages."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = {
    'x64': ('ec/8c/e4db9ae1e0ee233c04df007ab6d0d42f799ae9abd95d352b6092ee7bc4bf/ruff-0.17.5-py3-none-win_amd64.whl',
            'aa415d57c244299279901d776607fee3df7831c2a7435433fbfacde8632c6550'),
    'arm64': ('e6/65/a1648bc1550e7683bf7bf1e2ce2485c9f8535cbca6cca9ec7b73cc12fb8e/ruff-0.17.5-py3-none-win_arm64.whl',
              '64a6fd668a336df959c522991de33e9e3c8be463afc0c9ac8f029f9d19ef756e'),
}


def download(arch):
    # x86 Notepad++ can call x64 Ruff on x64 Windows. Ruff has no win32 wheel.
    asset, expected = ASSETS['x64' if arch == 'x86' else arch]
    folder = ROOT / 'build' / arch / 'ruff'
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder / asset.rsplit('/', 1)[-1]
    if not archive.exists() or hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        temporary = archive.with_suffix('.download')
        command = ['curl.exe', '-fSL', '--retry', '3', '--max-time', '180']
        proxy = urllib.request.getproxies().get('https')
        if proxy:
            command += ['--proxy', proxy]
        subprocess.run(command + [f'https://files.pythonhosted.org/packages/{asset}', '-o', str(temporary)], check=True)
        if hashlib.sha256(temporary.read_bytes()).hexdigest() != expected:
            raise RuntimeError('Ruff checksum mismatch; extraction cancelled.')
        temporary.replace(archive)
    with zipfile.ZipFile(archive) as package:
        members = [name for name in package.namelist() if name.endswith('/scripts/ruff.exe')]
        if len(members) != 1:
            raise RuntimeError('Expected one Ruff executable in the test wheel.')
        (folder / 'ruff.exe').write_bytes(package.read(members[0]))
    print(f'PASS verified test-only Ruff 0.17.5 ({arch})')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=['x86', 'x64', 'arm64'], default='x64')
    download(parser.parse_args().arch)
