# HP live-USB validation

Proceed only after you have a genuine ISO file, its matching SHA256, and passing BIOS/UEFI QEMU evidence for that exact source revision. The latest CI run built and tested an ephemeral ISO, but did not upload the ISO binary; the repository source package also contains no ISO. Use the manual build workflow or a local Debian 13 builder to create a private ISO before any USB test. Keep Windows and the internal disk intact.

1. Back up Windows data and save the BitLocker/device-encryption recovery key if enabled. Use a spare USB whose contents may be erased.
2. Copy the builder's genuine ISO/checksum to Windows. Compare `Get-FileHash .\AF-JARVIS-OS-v0.1-alpha.iso -Algorithm SHA256` with the builder SHA256.
3. Use a trusted Windows USB image writer. Select only the spare USB and verify its identity/capacity yourself before erasure. Do not select an internal disk. No raw-disk write command is supplied here.
4. Select the USB from the HP firmware boot menu. Consult the machine documentation for firmware keys. Secure Boot is unverified; record its state/rejections rather than silently lowering firmware security.
5. Choose the live environment; log in as jarvis with your chosen build password and AF JARVIS session. Do not start the installer. Verify Openbox/panel/GTK/Core and VM_CHECKLIST.md items on actual devices.
6. Test UHD620/display, touchpad, battery, Wi-Fi, suspend/lock/resume, USB, audio, and browser/files/terminal. Stop AI/Core in turn; ordinary desktop tools must remain usable.
7. After 60 seconds idle with browser closed and no generation/microphone, run measure-idle.py from extracted source as root. Save evidence to separate removable storage. Record system used RAM, per-process PSS, swap/zram and CPU activity.
8. Connect the real tablet using LOCAL_AI_NODE.md, verify model ID/auth/SSE, measure latency and recovery after node/Wi-Fi interruption. Keep keys out of reports. Save evidence before testing shutdown.

Normal live sessions are ephemeral. Facts/config can vanish on reboot unless validated persistence is intentionally configured; persistence/encryption and installation are untested. Do not place irreplaceable memory only in this live session. Installation is a separate later decision after backups and hardware proof.
