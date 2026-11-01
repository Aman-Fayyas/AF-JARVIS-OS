#!/usr/bin/env bash
set -euo pipefail

cd /work/AF-JARVIS-OS

# CI-only LightDM configuration: retain a normal username/password login.
printf '%s\n' 'greeter-hide-users=true' >> distro/includes/etc/lightdm/lightdm.conf.d/50-jarvis.conf

# CI-only SSH access for diagnostics inside the disposable QEMU image.
mkdir -p distro/includes/etc/ssh/sshd_config.d
printf '%s\n' \
  'PasswordAuthentication yes' \
  'KbdInteractiveAuthentication no' \
  'PermitRootLogin no' \
  'UsePAM yes' \
  > distro/includes/etc/ssh/sshd_config.d/99-af-jarvis-ci.conf

mkdir -p distro/includes/etc/systemd/system/multi-user.target.wants
ln -sf /usr/lib/systemd/system/ssh.service \
  distro/includes/etc/systemd/system/multi-user.target.wants/ssh.service

export JARVIS_LIVE_PASSWORD_HASH_FILE=/tmp/af-jarvis-ci-password.hash
bash scripts/build-iso.sh --build /work/AF-JARVIS-OS/build/qemu-normal-login
rm -f "$JARVIS_LIVE_PASSWORD_HASH_FILE"
