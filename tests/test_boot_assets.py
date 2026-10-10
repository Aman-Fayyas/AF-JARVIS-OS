"""Execute shell assets against isolated stubs; these are not Linux boot tests."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
import importlib.util
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

class BootAssetsTests(unittest.TestCase):
    def test_session_starts_openbox_when_user_services_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            log = folder / 'calls'
            for command, status in [('systemctl', 1), ('dbus-update-activation-environment', 1), ('openbox', 0)]:
                stub = folder / command
                stub.write_text(f'#!/bin/sh\necho "{command} $*" >> "$JARVIS_TEST_LOG"\nexit {status}\n')
                stub.chmod(0o700)
            result = subprocess.run(['sh', str(ROOT / 'distro/includes/usr/local/bin/af-jarvis-session')],
                                    env={**os.environ, 'PATH': str(folder) + ':/usr/bin:/bin', 'JARVIS_TEST_LOG': str(log)}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("openbox --startup /bin/sh /etc/xdg/openbox/autostart", log.read_text())
            self.assertIn('systemctl --user stop jarvis-core.service', log.read_text())

    def test_login_hook_idempotence_and_missing_hash_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            log = folder / 'calls'
            for command in ('getent', 'usermod', 'passwd'):
                stub = folder / command
                stub.write_text(f'#!/bin/sh\necho "{command} $*" >> "$JARVIS_TEST_LOG"\nexit 0\n')
                stub.chmod(0o700)
            script = (ROOT / 'distro/includes/usr/lib/live/config/9999-jarvis-login').read_text()
            for path in ('/var/lib/live/config', '/etc/af-jarvis', '/etc/sudoers.d'):
                script = script.replace(path, str(folder) + path)
            hook = folder / 'hook'
            hook.write_text(script)
            key = folder / 'etc/af-jarvis/live-password.hash'
            key.parent.mkdir(parents=True)
            key.write_text('$6$testonly$' + 'x' * 86)
            env = {**os.environ, 'PATH': str(folder) + ':/usr/bin:/bin', 'JARVIS_TEST_LOG': str(log)}
            for _ in range(2):
                result = subprocess.run(['sh', str(hook)], env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(log.read_text().count('usermod -p'), 1)
            self.assertNotIn('passwd -l', log.read_text())
            self.assertFalse(key.exists())
            (folder / 'var/lib/live/config/jarvis-login').unlink()
            result = subprocess.run(['sh', str(hook)], env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('passwd -l jarvis', log.read_text())

    def test_renamed_archive_rejected_as_iso(self):
        spec = importlib.util.spec_from_file_location('verify_iso', ROOT / 'scripts/verify-iso.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            fake = Path(temporary) / 'renamed.iso'
            fake.write_bytes(b'PK\x03\x04not-an-iso')
            with self.assertRaisesRegex(ValueError, 'Not an ISO9660'):
                module.verify(fake)

    def test_boot_and_service_security_assets(self):
        packages = set((ROOT / 'distro/packages.list.chroot').read_text().splitlines())
        self.assertTrue({'user-setup', 'libpam-systemd', 'xauth', 'procps'} <= packages)
        unit = (ROOT / 'distro/includes/etc/systemd/user/jarvis-core.service').read_text()
        self.assertIn('NoNewPrivileges=true', unit)
        self.assertIn('UMask=0077', unit)
        self.assertNotIn('\nUser=root', unit)
        self.assertNotIn('\nPrivateTmp=true', unit)
        self.assertIn('systemctl set-default graphical.target', (ROOT / 'distro/0100-jarvis.hook.chroot').read_text())

    def test_iso_validator_requires_both_firmware_entries_and_payload(self):
        spec = importlib.util.spec_from_file_location('verify_iso', ROOT / 'scripts/verify-iso.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # Synthetic descriptor + mocked xorriso: parser regression, not an ISO.
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary) / 'descriptor.fixture'
            fixture.write_bytes(b'\x00' * (16 * 2048) + b'\x01CD001\x01' + b'\x00' * 2041)
            bios = 'El Torito boot img : 1 BIOS y none 0x0000\n'
            both = bios + 'El Torito boot img : 2 UEFI y none 0x0000\n'
            def completed(stdout):
                return subprocess.CompletedProcess([], 0, stdout, '')
            with patch.object(module.subprocess, 'run', return_value=completed(bios)):
                with self.assertRaisesRegex(ValueError, 'UEFI'):
                    module.verify(fixture)
            with patch.object(module.subprocess, 'run', side_effect=[completed(both), completed('/live/vmlinuz\n/live/initrd.img\n')]):
                with self.assertRaisesRegex(ValueError, 'Missing live payload'):
                    module.verify(fixture)
            with patch.object(module.subprocess, 'run', side_effect=[completed(both), completed('/live/vmlinuz\n/live/initrd.img\n/live/filesystem.squashfs\n')]) as run:
                module.verify(fixture)
                self.assertEqual(run.call_args.args[0][-3:], ['-exec', 'echo', '--'])

if __name__ == '__main__':
    unittest.main()
