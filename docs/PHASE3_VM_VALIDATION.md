# Phase 3 — Full-system VM validation

Automated BIOS/UEFI normal-login gate: PASS

Last verified: 2026-11-02  
Branch: minimal-hardware-validation  
Commit: 4cca474666949fcadde00bb1429baa3219d53ef8

## Latest evidence

- [Normal-login QEMU workflow — run 41487831027](https://github.com/Aman-Fayyas/AF-JARVIS-OS/actions/runs/41487831027)
- [QEMU boot workflow — run 41487831182](https://github.com/Aman-Fayyas/AF-JARVIS-OS/actions/runs/41487831182)
- [Functional tests — run 41487830990](https://github.com/Aman-Fayyas/AF-JARVIS-OS/actions/runs/41487830990)
- [GTK + Core integration — run 41487831436](https://github.com/Aman-Fayyas/AF-JARVIS-OS/actions/runs/41487831436)
- [Phase 3 evidence artifact](https://github.com/Aman-Fayyas/AF-JARVIS-OS/actions/runs/41487831027/artifacts/13164157182)

The normal-login workflow built a Debian 13 amd64 ISO in an ephemeral runner, verified ISO9660 and BIOS/UEFI El Torito entries, then tested both firmware modes in QEMU. The guest used a temporary CI-only password. Both modes passed the normal LightDM login flow; a deliberately incorrect password was rejected; the AF JARVIS desktop appeared; Core stop/restart recovered and the UI reconnected. Read-only guest diagnostics were schema-checked.

Additional guest checks passed for QEMU virtual networking recovery, keyboard/mouse interaction, virtual display resolution change/restore, PipeWire virtual HDA playback/capture routing, eSpeak WAV generation, and the parec capture path. The QEMU audio backend is null: these checks validate software routing only, not physical speakers or a microphone. The Vosk workflow generated eSpeak speech, normalized it to 16 kHz mono signed 16-bit PCM, mirrored the application's chunked result aggregation, and achieved an exact 10-word match (WER 0.0).

The uploaded artifact includes screenshots, OCR text, logs, JSON diagnostics and an ISO checksum. It does not include the ISO binary. The separate manual Build AF JARVIS OS ISO workflow has not been run to create a retained downloadable image.

## Remaining VM and hardware gates

| Area | Status |
|---|---|
| BIOS/UEFI boot and normal login | Passed in hosted QEMU |
| Wrong-password rejection | Passed in hosted QEMU |
| Core stop/restart and UI recovery | Passed in hosted QEMU |
| QEMU virtual network reconnect | Passed |
| Virtual display resolution recovery | Passed; not UHD 620 acceleration proof |
| PipeWire virtual audio graph and PCM path | Passed; null backend only |
| eSpeak file synthesis | Passed; not audible speaker proof |
| Vosk generated-speech streaming | Passed; not real-user speech or mic proof |
| Whole-system idle RAM | Guest diagnostics collected; no HP measurement |
| Secure Boot | Not tested |
| Suspend/resume and lock/unlock | Not tested |
| Real tablet inference | Not tested |
| HP hardware | Not tested |
| Installer and persistence | Not tested |

## Safety boundary

- Never attach the host's physical disk to QEMU or run an installer against it.
- Do not change Windows partitions, BitLocker, Secure Boot or firmware settings for this validation.
- Do not publish a live-image password/hash or upload a password-bearing ISO publicly.
- Do not mark a check passed without dated runtime evidence.
- CI autologin is permitted only in disposable test images and must never be mistaken for normal-login validation.

## Next steps

1. Keep the current passing commit as the rollback point.
2. Continue software-only reliability fixes and regression tests on this branch.
3. If a distributable/private ISO is needed, run the manual build workflow with a unique private JARVIS_LIVE_PASSWORD secret; the resulting image embeds its password hash and must be treated as private.
4. Only after obtaining a spare USB and verifying the ISO checksum, follow docs/LIVE_USB.md for a live-only HP test. Do not install to the internal SSD.
