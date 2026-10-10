#!/bin/bash
# Supported host: Debian 13 amd64 with root/mount/chroot privileges.
set -euo pipefail
umask 022
jarvis_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
jarvis_mode=${1:---prepare}
jarvis_work=${2:-"$jarvis_root/build/live"}
if [[ "$jarvis_mode" != --prepare && "$jarvis_mode" != --build ]]; then
    echo 'Usage: build-iso.sh --prepare|--build [new-build-directory]' >&2
    exit 2
fi
jarvis_work=$(realpath -m -- "$jarvis_work")
if [[ -e "$jarvis_work" ]]; then
    echo 'Choose a new, empty build directory. Existing build trees are never deleted.' >&2
    exit 2
fi
if [[ "$jarvis_mode" == --build ]]; then
    python3 "$jarvis_root/scripts/build-preflight.py" --mount
    if [[ $EUID -ne 0 ]]; then
        echo 'ISO build requires root on a dedicated Debian 13 builder.' >&2
        exit 1
    fi
    . /etc/os-release
    if [[ "$ID" != debian || "$VERSION_ID" != 13 || $(dpkg --print-architecture) != amd64 ]]; then
        echo 'Use a Debian 13 amd64 VM or physical builder.' >&2
        exit 1
    fi
    for jarvis_command in lb debootstrap mksquashfs xorriso mount chroot rg; do
        command -v "$jarvis_command" >/dev/null || { echo "Missing build dependency: $jarvis_command" >&2; exit 1; }
    done
    if [[ ! -r "${JARVIS_LIVE_PASSWORD_HASH_FILE:-}" ]]; then
        echo 'Set JARVIS_LIVE_PASSWORD_HASH_FILE to your private SHA-512 crypt hash file.' >&2
        exit 1
    fi
    python3 "$jarvis_root/scripts/check-packages.py" "$jarvis_root/distro/packages.list.chroot"
    python3 "$jarvis_root/scripts/validate-password-hash.py" "$JARVIS_LIVE_PASSWORD_HASH_FILE"
    jarvis_check=$(mktemp -d)
    trap 'rmdir "$jarvis_check" 2>/dev/null || true' EXIT
    if ! mount -t tmpfs -o size=1m tmpfs "$jarvis_check"; then
        echo 'Builder lacks mount/CAP_SYS_ADMIN privileges. No ISO was created.' >&2
        exit 1
    fi
    umount "$jarvis_check"
    rmdir "$jarvis_check"
    trap - EXIT
fi
mkdir -p "$jarvis_work/auto" "$jarvis_work/config/package-lists" "$jarvis_work/config/hooks/live" "$jarvis_work/config/includes.chroot"
cp "$jarvis_root/distro/auto-config" "$jarvis_work/auto/config"
cp "$jarvis_root/distro/packages.list.chroot" "$jarvis_work/config/package-lists/jarvis.list.chroot"
cp "$jarvis_root/distro/0100-jarvis.hook.chroot" "$jarvis_work/config/hooks/live/0100-jarvis.hook.chroot"
cp -a "$jarvis_root/distro/includes/." "$jarvis_work/config/includes.chroot/"
jarvis_payload="$jarvis_work/config/includes.chroot/opt/af-jarvis"
mkdir -p "$jarvis_payload"
cp -a "$jarvis_root/jarvis" "$jarvis_root/config" "$jarvis_root/desktop" "$jarvis_root/docs" "$jarvis_payload/"
python3 - "$jarvis_payload" <<'PY'
from pathlib import Path
import shutil
import sys
for cache in Path(sys.argv[1]).rglob('__pycache__'):
    shutil.rmtree(cache)
PY
chmod 755 "$jarvis_work/auto/config" "$jarvis_work/config/hooks/live/0100-jarvis.hook.chroot"
python3 "$jarvis_root/scripts/validate-build-tree.py" "$jarvis_work"
if [[ "$jarvis_mode" == --prepare ]]; then
    echo "Build tree prepared and statically validated: $jarvis_work"
    echo 'No ISO was built. Use --build on a supported privileged Debian builder.'
    exit 0
fi
install -D -m 600 "$JARVIS_LIVE_PASSWORD_HASH_FILE" "$jarvis_work/config/includes.chroot/etc/af-jarvis/live-password.hash"
cd "$jarvis_work"
lb config
lb build 2>&1 | tee build.log
jarvis_image=live-image-amd64.hybrid.iso
[[ -s "$jarvis_image" ]] || { echo 'live-build did not produce the expected ISO.' >&2; exit 1; }
python3 "$jarvis_root/scripts/verify-iso.py" "$jarvis_image" | tee el-torito-report.txt
cp "$jarvis_image" AF-JARVIS-OS-v0.1-alpha.iso
sha256sum AF-JARVIS-OS-v0.1-alpha.iso > AF-JARVIS-OS-v0.1-alpha.iso.sha256
cp live-image-amd64.packages package-manifest.txt
printf 'ISO generated. VM boot and live-login validation are still required: %s\n' "$jarvis_work/AF-JARVIS-OS-v0.1-alpha.iso"
