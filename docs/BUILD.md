# Debian live ISO pipeline

## What this environment validated

The generated live-build tree, required assets, shell syntax, XML and package list structure have been checked. An actual ISO build was not possible: the workspace is Ubuntu 24.04, has no effective Linux capabilities, refuses a tmpfs mount with EPERM, lacks live-build/debootstrap/QEMU, and prohibits AF_UNIX sockets. No bootable image or VM boot result is claimed.

The script prepares without root using `--prepare`. A real build requires a dedicated **Debian 13 amd64** VM or machine with root, mount and chroot privileges. Budget substantial free disk space (at least 15 GB) and internet access to Debian mirrors. Never use your Windows drive as the build target.

## Build dependencies

The simplest actual build entry point is `bash scripts/build.sh`, from the extracted source root on Debian 13 amd64. It diagnoses the host/tools, prints installation commands, requires a successful mount probe, privately prompts for the live user's password, and invokes the existing live-build pipeline. Dependencies are not installed automatically. Optional argument: a new output directory. Use `bash scripts/build.sh --check` for the diagnostic only.

On that Debian builder:

```bash
sudo apt update
sudo apt install live-build debootstrap squashfs-tools xorriso \
  isolinux syslinux-common grub-pc-bin grub-efi-amd64-bin \
  mtools dosfstools rsync ripgrep openssl python3 \
  qemu-system-x86 ovmf
```

The script checks named image packages against the builder's APT metadata before building. The image uses `main` and `non-free-firmware`, signed Debian repositories and security updates. Ensure those archive areas are configured on the builder for the package check.

## Choose your private live-login password

Do this on the builder yourself; the assistant does not need the password.

```bash
umask 077
openssl passwd -6 > "$HOME/jarvis-live-password.hash"
```

OpenSSL asks for the password on the terminal. Choose a strong password unique to this live image. Only its SHA-512 crypt hash is stored. The script requires the hash file to have private permissions.

The live user is `jarvis`. Autologin, live-config passwordless sudo, and live-config permissive PolicyKit customization are disabled. A late live-config component replaces the Debian live password with your supplied hash and adds the user to the standard sudo group. Missing hash leaves live login locked. These boot-time integrations require VM validation; they are not yet verified by a boot.

The hash is embedded in the immutable ISO. Deleting it from the running overlay cannot remove it from the ISO. Treat the image as private and use a separate unique password if you later distribute it. The source ZIP contains no password/hash.

## Prepare or build

From the source root:

```bash
bash scripts/build-iso.sh --prepare "$PWD/build/inspect"
```

This only prepares and validates a new directory. It does not create an ISO.

For the actual build, choose a different new directory:

```bash
sudo env JARVIS_LIVE_PASSWORD_HASH_FILE="$HOME/jarvis-live-password.hash" \
  bash scripts/build-iso.sh --build "$PWD/build/debian-alpha"
```

Existing build directories are refused rather than removed. You can keep a failed tree/log for inspection and choose a new output directory for a retry. Build scripts do not format a disk or write a USB drive.

The intended successful output is `build/debian-alpha/AF-JARVIS-OS-v0.1-alpha.iso`, its SHA256, a package-version manifest, build log and El Torito report. The script uses Debian live-build with an amd64 kernel, ISO-hybrid format, BIOS and EFI bootloaders, live filesystem and Debian live-installer integration. `xorriso` checks boot entries after creation. Installer behavior, Secure Boot, BIOS/UEFI boot, live-login customization and installed-session behavior still need testing.

## Reproducibility scope

The final artifact is now additionally gated by `scripts/verify-iso.py`: ISO9660 primary volume descriptor, bootable BIOS and UEFI El Torito entries, squashfs, kernel and initrd. A renamed archive is rejected. Structure validation is not a boot test. Both actual firmware boots remain mandatory.

This is a repeatable source/build recipe. Debian repositories update over time, so the same recipe is **not guaranteed to produce byte-identical ISOs**. Save the resolved package manifest, builder versions, logs and source checksum per build. A pinned Debian snapshot, deterministic filesystem timestamps and independent repeat-build comparison are planned before a reproducible-binary claim. Security updates remain enabled by default.

## VM before hardware

```bash
bash scripts/run-vm.sh build/debian-alpha/AF-JARVIS-OS-v0.1-alpha.iso bios
bash scripts/run-vm.sh build/debian-alpha/AF-JARVIS-OS-v0.1-alpha.iso uefi
```

The default VM has 2 GB RAM, 2 vCPUs, a read-only CD-ROM and user-mode networking. No host hard disk is attached. KVM is used only when available; otherwise QEMU uses TCG. To reach a host-side test node from QEMU user networking, configure that node appropriately (the host gateway is normally 10.0.2.2); avoid assuming guest loopback reaches the tablet.

The launcher is for live tests. Installer testing needs a separate **disposable virtual disk**, added intentionally by the developer after reviewing the VM checklist. Do not attach a real disk.
