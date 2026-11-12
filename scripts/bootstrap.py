"""Download and verify the build-only LLVM-MinGW toolchain."""
import hashlib
from pathlib import Path
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NAME = 'llvm-mingw-20261104-ucrt-x86_64'
SHA256 = '552191b5754c49a5a20723276a6fc56541ea1922c4c50b7b669022333fc1b40f'
URL = f'https://github.com/mstorsjo/llvm-mingw/releases/download/20261104/{NAME}.zip'


def main():
    folder = ROOT / '.tools'
    folder.mkdir(exist_ok=True)
    archive = folder / f'{NAME}.zip'
    if not archive.exists() or hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        temporary = archive.with_suffix('.download')
        command = ['curl.exe', '-fSL', '--retry', '3', '--max-time', '900']
        proxy = urllib.request.getproxies().get('https')
        if proxy:
            command += ['--proxy', proxy]
        subprocess.run(command + [URL, '-o', str(temporary)], check=True)
        if hashlib.sha256(temporary.read_bytes()).hexdigest() != SHA256:
            raise RuntimeError('Compiler checksum mismatch; extraction cancelled.')
        temporary.replace(archive)
    with zipfile.ZipFile(archive) as package:
        for entry in package.infolist():
            if not (folder / entry.filename).resolve().is_relative_to(folder.resolve()):
                raise RuntimeError('Compiler archive contains an unsafe path.')
        package.extractall(folder)
    print('PASS verified LLVM-MinGW 20261104 toolchain')


if __name__ == '__main__':
    main()
