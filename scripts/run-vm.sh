#!/bin/bash
set -euo pipefail
jarvis_iso=${1:?Usage: run-vm.sh path.iso [bios|uefi]}
jarvis_boot=${2:-bios}
command -v qemu-system-x86_64 >/dev/null || { echo 'Install QEMU: sudo apt install qemu-system-x86 ovmf' >&2; exit 1; }
[[ -s "$jarvis_iso" ]] || { echo 'ISO does not exist.' >&2; exit 1; }
jarvis_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
python3 "$jarvis_root/scripts/verify-iso.py" "$jarvis_iso" >/dev/null
jarvis_args=(-m 2048 -smp 2 -cdrom "$jarvis_iso" -boot d -nic user,model=virtio-net-pci -device intel-hda -device hda-duplex)
# No host disk attached. QEMU user networking can access the internet/LAN.
if [[ -r /dev/kvm && -w /dev/kvm ]]; then
    jarvis_args+=(-enable-kvm -cpu host)
else
    jarvis_args+=(-accel tcg)
fi
if [[ "$jarvis_boot" == uefi ]]; then
    jarvis_firmware=${JARVIS_OVMF_CODE:-/usr/share/OVMF/OVMF_CODE_4M.fd}
    [[ -r "$jarvis_firmware" ]] || { echo 'Install OVMF or set JARVIS_OVMF_CODE.' >&2; exit 1; }
    jarvis_args+=(-drive "if=pflash,format=raw,readonly=on,file=$jarvis_firmware")
elif [[ "$jarvis_boot" != bios ]]; then
    exit 2
fi
exec qemu-system-x86_64 "${jarvis_args[@]}"
