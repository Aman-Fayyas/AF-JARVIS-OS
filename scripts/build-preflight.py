"""Diagnose the supported builder without installing anything or deleting files."""
from pathlib import Path
import argparse
import json
import os
import platform
import shutil
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--mount', action='store_true', help='also require root and prove a tmpfs mount')
args = parser.parse_args()
release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
host_ok = release.get('ID', '').strip('"') == 'debian' and release.get('VERSION_ID', '').strip('"') == '13' and platform.machine() == 'x86_64'
commands = ['lb', 'debootstrap', 'mksquashfs', 'xorriso', 'mount', 'umount', 'chroot', 'rg', 'openssl', 'python3', 'dpkg', 'mcopy', 'mkfs.vfat', 'grub-mkstandalone']
missing = [name for name in commands if not shutil.which(name)]
cap = next(line.split()[1] for line in Path('/proc/self/status').read_text().splitlines() if line.startswith('CapEff:'))
report = {'host': release.get('PRETTY_NAME', '').strip('"'), 'architecture': platform.machine(),
          'supported_host': host_ok, 'uid': os.getuid(), 'cap_sys_admin_effective': bool(int(cap, 16) & (1 << 21)),
          'missing_build_commands': missing, 'qemu_available': bool(shutil.which('qemu-system-x86_64')),
          'kvm_available': os.access('/dev/kvm', os.R_OK | os.W_OK), 'mount_probe': 'not requested',
          'install_build_dependencies': 'sudo apt update && sudo apt install live-build debootstrap squashfs-tools xorriso isolinux syslinux-common grub-pc-bin grub-efi-amd64-bin mtools dosfstools rsync ripgrep openssl python3',
          'install_boot_test_dependencies': 'sudo apt install qemu-system-x86 ovmf',
          'requirement': 'Debian 13 amd64 VM or physical machine; sudo/root with mount and chroot privileges. A rootless/restricted container is insufficient.'}
mount_ok = True
if args.mount:
    mount_ok = False
    if os.getuid() != 0:
        report['mount_probe'] = 'root required'
    else:
        with tempfile.TemporaryDirectory(prefix='af-jarvis-mount-') as directory:
            probe = subprocess.run(['mount', '-t', 'tmpfs', '-o', 'size=1m', 'tmpfs', directory], capture_output=True, text=True)
            if probe.returncode == 0:
                unmount = subprocess.run(['umount', directory], capture_output=True, text=True)
                if unmount.returncode:
                    raise RuntimeError('Preflight tmpfs could not be unmounted: ' + unmount.stderr.strip())
                mount_ok = True
                report['mount_probe'] = 'mounted and unmounted successfully'
            else:
                report['mount_probe'] = probe.stderr.strip()
print(json.dumps(report, indent=2))
raise SystemExit(0 if host_ok and not missing and mount_ok else 1)
