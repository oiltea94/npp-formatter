"""Fetch a hash-pinned portable editor for isolated integration tests."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = {
    'x86': ('npp.8.9.6.portable.zip', 'f1f40ba76eb357ce5ab86f5ba451197f35467c711a133399b69af2493c7719b0'),
    'x64': ('npp.8.9.6.portable.x64.zip', '5528d2de7e44fcc676bb1a4d59d212c74b23f365b5db54f474058d6a68db4041'),
    'arm64': ('npp.8.9.6.portable.arm64.zip', '4fb150a5a1db9e9e13770362ec0e77cc508f60ca863b5e66d0a58693bc51ba91'),
}


def download(arch):
    name, expected = ASSETS[arch]
    folder = ROOT / 'build' / arch / 'editor'
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder / name
    if not archive.exists() or hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        temporary = archive.with_suffix('.download')
        command = ['curl.exe', '-fSL', '--retry', '3', '--max-time', '180']
        proxy = urllib.request.getproxies().get('https')
        if proxy:
            command += ['--proxy', proxy]
        url = f'https://github.com/notepad-plus-plus/notepad-plus-plus/releases/download/v8.9.6/{name}'
        subprocess.run(command + [url, '-o', str(temporary)], check=True)
        if hashlib.sha256(temporary.read_bytes()).hexdigest() != expected:
            raise RuntimeError('Editor checksum mismatch; extraction cancelled.')
        temporary.replace(archive)
    with zipfile.ZipFile(archive) as package:
        for name in ('notepad++.exe', 'langs.model.xml', 'stylers.model.xml'):
            package.extract(name, folder)
    print(f'PASS verified portable Notepad++ 8.9.6 ({arch})')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=ASSETS, default='x64')
    download(parser.parse_args().arch)
