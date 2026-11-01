#!/usr/bin/env bash
set -euo pipefail

cd /work/AF-JARVIS-OS

# Install the complete, documented Debian 13 image-builder toolchain in the
# disposable chroot. debootstrap intentionally creates only a minimal base.
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  live-build \
  debootstrap \
  squashfs-tools \
  xorriso \
  isolinux \
  syslinux-common \
  grub-pc-bin \
  grub-efi-amd64-bin \
  mtools \
  dosfstools \
  rsync \
  ripgrep \
  openssl \
  python3

# Fail early with the same complete dependency report used by the normal
# builder, before modifying the build tree or attempting live-build.
python3 scripts/build-preflight.py --mount

# Verify every target package against the freshly updated Debian 13 indexes.
python3 scripts/check-packages.py distro/packages.list.chroot

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
[[ -r "$JARVIS_LIVE_PASSWORD_HASH_FILE" ]] || {
  echo "CI password hash was not provisioned in the disposable builder." >&2
  exit 1
}
bash scripts/build-iso.sh --build /work/AF-JARVIS-OS/build/qemu-normal-login
rm -f "$JARVIS_LIVE_PASSWORD_HASH_FILE"
