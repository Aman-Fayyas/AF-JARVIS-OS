# AF JARVIS OS — current validation status

Last verified: 2026-11-02  
Branch: minimal-hardware-validation  
Known-good baseline: 4cca474666949fcadde00bb1429baa3219d53ef8  
Main branch: not modified by this validation work.

## Current result

Software CI: PASS

The latest baseline completed all four workflows successfully:

| Workflow | Run | Result |
|---|---:|---|
| Phase 3 normal login QEMU | [41487831027](https://github.com/Aman-Fayyas/AF-JARVIS-OS/actions/runs/41487831027) | PASS |
| Functional smoke tests | [41487830990](https://github.com/Aman-Fayyas/AF-JARVIS-OS/actions/runs/41487830990) | PASS — 35 tests |
| QEMU BIOS/UEFI boot | [41487831182](https://github.com/Aman-Fayyas/AF-JARVIS-OS/actions/runs/41487831182) | PASS |
| GTK + Core integration | [41487831436](https://github.com/Aman-Fayyas/AF-JARVIS-OS/actions/runs/41487831436) | PASS |

The Phase 3 workflow built a Debian 13 amd64 live ISO (about 1.7 GiB) in an ephemeral runner. BIOS and UEFI normal-login flows passed, including rejection of an intentionally wrong password, desktop startup with the correct temporary password, Core stop/restart with UI recovery, and guest diagnostics. QEMU guest checks also passed for virtual network recovery, GTK input, display-mode recovery, PipeWire virtual HDA routing, eSpeak WAV generation, and virtual PCM capture. The Vosk test used generated eSpeak audio and returned an exact 10-word match (WER 0.0).

The uploaded Phase 3 artifact contains screenshots, logs, JSON reports and the ISO checksum — not the ISO itself. The separate manually dispatched Build AF JARVIS OS ISO workflow has not been run as a downloadable-image build. No ISO is included in the source repository.

## What is actually proven

- 35 Python regression tests, Python compilation, shell syntax and generated build-tree checks pass.
- Debian 13 live-image build and ISO structure checks pass in hosted CI.
- BIOS and UEFI QEMU boot, LightDM normal login, wrong-password rejection and desktop visibility pass.
- Core user-service stop/restart and desktop reconnection pass in QEMU.
- GTK/Core integration and keyboard/mouse interaction checks pass.
- QEMU virtual networking reconnect and virtual display-mode change/restore pass.
- PipeWire virtual audio routing, eSpeak WAV generation and parec PCM capture path pass in a null-backend QEMU environment.
- Vosk streaming aggregation test passes on generated speech with exact transcription.

## Still unverified

- Physical HP 250 G7 boot, Secure Boot behavior and device compatibility.
- Intel UHD 620 acceleration, actual display panel, touchpad, Wi-Fi/Bluetooth adapters, battery and suspend/resume.
- Audible speaker output and physical microphone capture. QEMU's null audio backend cannot prove either.
- Real Tab A7 Lite connection, model inference, latency and node recovery.
- Real cloud credentials/provider quotas and production internet conditions.
- Installer behavior, persistence, encryption and installation safety.
- Whole-system idle RAM on the HP. Process PSS measurements are not a whole-OS RAM measurement.

## Stability rules

1. Keep 4cca474 as the known-good checkpoint until a later commit passes the full required workflows.
2. Make experimental changes only on minimal-hardware-validation; do not push validation edits to main.
3. Fix one reproducible issue at a time and add a regression test when practical.
4. Do not label a virtual test as a physical-hardware pass.
5. Do not install to, repartition, format or otherwise modify the Windows/BitLocker internal SSD during live testing.

## Next milestone

Continue software reliability work and preserve the green CI baseline. When a spare USB becomes available, run the documented read-only live-USB validation on the HP. Full installation remains a separate decision after hardware evidence.
