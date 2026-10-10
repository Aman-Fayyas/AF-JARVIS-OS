from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
root = Path(sys.argv[1])
required = ['auto/config', 'config/package-lists/jarvis.list.chroot', 'config/hooks/live/0100-jarvis.hook.chroot',
            'config/includes.chroot/usr/share/xsessions/af-jarvis.desktop',
            'config/includes.chroot/usr/local/bin/af-jarvis-session',
            'config/includes.chroot/usr/lib/live/config/9999-jarvis-login',
            'config/includes.chroot/opt/af-jarvis/jarvis/core.py',
            'config/includes.chroot/etc/systemd/user/jarvis-core.service']
for relative in required:
    assert (root / relative).is_file(), relative
for path in root.rglob('*'):
    if not path.is_file():
        continue
    if path.suffix == '.xml':
        ET.parse(path)
    if path.read_bytes().startswith(b'#!/bin/sh'):
        subprocess.run(['sh', '-n', str(path)], check=True)
packages = (root / required[1]).read_text().splitlines()
assert all(line and ' ' not in line for line in packages)
assert {'openbox', 'python3-gi', 'lightdm', 'firefox-esr', 'network-manager', 'live-boot', 'user-setup', 'libpam-systemd', 'xauth', 'procps'} <= set(packages)
print('Build tree: required assets, shell syntax, XML and package list validated.')
