"""Require ISO9660, BIOS + UEFI entries and a live payload; not a boot test."""
from pathlib import Path
import re
import subprocess
import sys

def verify(path):
    path = Path(path)
    with path.open('rb') as stream:
        stream.seek(16 * 2048)
        descriptors = stream.read(16 * 2048)
    if not any(descriptors[offset:offset + 7] == b'\x01CD001\x01' for offset in range(0, len(descriptors), 2048)):
        raise ValueError('Not an ISO9660 image: primary volume descriptor missing')
    report = subprocess.run(['xorriso', '-indev', str(path), '-report_el_torito', 'plain'], capture_output=True, text=True, check=True)
    text = report.stdout + report.stderr
    for platform in ('BIOS', 'UEFI'):
        if not re.search(r'El Torito boot img\s*:\s*\d+\s+' + platform + r'\s+y\b', text):
            raise ValueError(f'Missing bootable {platform} El Torito entry')
    listing = subprocess.run(['xorriso', '-indev', str(path), '-find', '/live', '-type', 'f', '-exec', 'echo', '--'], capture_output=True, text=True, check=True)
    names = listing.stdout
    for pattern in (r'/live/filesystem\.squashfs', r'/live/vmlinuz[^\s\x27]*', r'/live/initrd[^\s\x27]*'):
        if not re.search(pattern, names):
            raise ValueError('Missing live payload: ' + pattern)
    return text

if __name__ == '__main__':
    try:
        print(verify(sys.argv[1]))
        print('ISO structure verified. Actual BIOS/UEFI boot testing is still required.')
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
