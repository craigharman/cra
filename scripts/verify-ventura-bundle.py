#!/usr/bin/env python3
"""Reject an Intel test bundle containing a binary or plist requiring post-Ventura macOS."""
import plistlib
import re
import subprocess
import sys
from pathlib import Path


def version(text):
    return tuple((list(map(int, text.split('.'))) + [0, 0, 0])[:3])


def verify(app):
    failures = []
    binaries = 0
    magic = {bytes.fromhex(v) for v in ('cffaedfe', 'cefaedfe', 'cafebabe', 'bebafeca', 'cafebabf', 'bfbafeca')}
    for path in sorted(app.rglob('*')):
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(app)
        if path.name == 'Info.plist':
            data = plistlib.loads(path.read_bytes())
            minimum = data.get('LSMinimumSystemVersion')
            if minimum and version(minimum) > (13, 0, 0):
                failures.append(f'{relative}: plist requires macOS {minimum}')
        with path.open('rb') as stream:
            if stream.read(4) not in magic:
                continue
        binaries += 1
        arch = subprocess.run(['lipo', str(path), '-verify_arch', 'x86_64'], capture_output=True, text=True)
        if arch.returncode:
            failures.append(f'{relative}: missing Intel architecture: {arch.stderr.strip()}')
            continue
        load = subprocess.run(['otool', '-arch', 'x86_64', '-l', str(path)], capture_output=True, text=True, check=True)
        # Match only the OS minimum command, not dylib compatibility/SDK versions.
        minima = re.findall(r'cmd LC_BUILD_VERSION\s+cmdsize \d+\s+platform \S+\s+minos ([\d.]+)', load.stdout)
        minima += re.findall(r'cmd LC_VERSION_MIN_MACOSX\s+cmdsize \d+\s+version ([\d.]+)', load.stdout)
        if not minima:
            failures.append(f'{relative}: no minimum macOS version found')
        for minimum in minima:
            print(f'{relative}: minimum macOS {minimum}')
            if version(minimum) > (13, 0, 0):
                failures.append(f'{relative}: binary requires macOS {minimum}')
    if not binaries:
        failures.append('No Mach-O binaries found')
    if failures:
        raise SystemExit('\n'.join(failures))
    print(f'Verified {binaries} Intel binaries target macOS 13.0 or earlier.')


if __name__ == '__main__':
    if len(sys.argv) != 2 or not Path(sys.argv[1]).is_dir():
        raise SystemExit('Usage: verify-ventura-bundle.py /path/to/Cra.app')
    verify(Path(sys.argv[1]))
