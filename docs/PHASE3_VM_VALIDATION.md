# Phase 3 — Full-system VM validation

Status: IN PROGRESS — automated ISO build and BIOS/UEFI desktop boot gate passed; interactive validation gates remain open.
Branch: minimal-hardware-validation
Scope: disposable QEMU guest only; no physical disks or installer target.

## Latest automated evidence — 2026-10-31

- QEMU Boot Test workflow completed successfully on commit `19420f883fd5433679b2748f1bfcdd39cc37e431`.
- Workflow run: https://github.com/Aman-Fayyas/AF-JARVIS-OS/actions/runs/41212431001
- Artifact: https://github.com/Aman-Fayyas/AF-JARVIS-OS/actions/runs/41212431001/artifacts/13046683357
- The workflow built the ISO and completed BIOS and UEFI QEMU boot steps. Both guests remained running through the 240-second observation window, and screenshots and logs were uploaded.
- Critical limitation: this workflow enables LightDM autologin in its disposable CI image. It does not test the normal greeter or password authentication.
- It does not assert Core health/recovery, desktop behavior, or collect whole-system idle RAM.

This is a successful automated build-and-boot milestone, not completion of all Phase 3 exit criteria.

## Safety boundary

- Never attach the host's physical disk to QEMU or run an installer against a host disk.
- Do not change Windows partitions, BitLocker, Secure Boot or firmware settings.
- Do not publish a live-image password/hash or upload a password-bearing ISO publicly.
- Do not mark a check passed without dated runtime evidence.
- CI autologin is permitted only in a disposable test image and must never be mistaken for normal-login validation.

## Gate A — Build and verify a private test ISO

Use a dedicated Debian 13 amd64 builder. Generate a unique live-login password locally; do not share it or commit it.

```bash
umask 077
openssl passwd -6 > "$HOME/jarvis-live-password.hash"
sudo env JARVIS_LIVE_PASSWORD_HASH_FILE="$HOME/jarvis-live-password.hash" \
  bash scripts/build-iso.sh --build "$PWD/build/phase3-vm"
python3 scripts/verify-iso.py build/phase3-vm/AF-JARVIS-OS-v0.1-alpha.iso
sha256sum build/phase3-vm/AF-JARVIS-OS-v0.1-alpha.iso
```

Keep the ISO and hash private.

## Gate B — BIOS and UEFI normal-login tests

Use a fresh build with the repository's normal LightDM configuration (no autologin). Boot separately in BIOS and UEFI using `scripts/run-vm.sh`. For each mode record:
- ISO checksum, source commit, QEMU version, RAM and vCPU allocation.
- LightDM greeter appears.
- Correct password permits login; incorrect password is rejected.
- Openbox, panel and AF JARVIS desktop appear.
- Core service starts for the logged-in user and recovers after a controlled stop.
- Journal contains no unexplained critical session errors.

The current GitHub QEMU workflow is not evidence for these password/login checks because it intentionally enables CI autologin.

## Gate C — Read-only guest diagnostics

After a normal login, wait at least 60 seconds and run:

```bash
sudo /usr/local/bin/af-jarvis-phase3-check > phase3-guest-report.json
```

The command emits a JSON report with identity, boot marker, whole-system memory, top process PSS, Core service status/journal, failed units, network device state, audio device listings, display information, boot timing and application presence. It is diagnostic evidence, not a substitute for interactive checks. Retain the complete JSON privately with the VM mode, QEMU version and ISO checksum.

Manually test and record:
- [ ] Core stop/restart and UI reconnect.
- [ ] Network disconnect/reconnect; deterministic local actions remain available offline.
- [ ] Screen lock and password-required unlock.
- [ ] Suspend/resume and lock-on-resume, if supported by the VM.
- [ ] Audio playback and microphone behavior; note unavailable virtual devices.
- [ ] File manager and installed desktop entries launch.
- [ ] Confirmed guest shutdown works.
- [ ] No unexpected failed system or user units.

## Gate D — Whole-system idle RAM

The guest report includes MemTotal, MemAvailable and used estimate from `/proc/meminfo`, plus process PSS. Measure after 60 seconds idle, with browser/optional apps closed and no inference or voice capture. Process PSS totals are not whole-system used RAM. VM results are not a substitute for measuring the HP itself.

## VM limitations

A VM cannot fully validate laptop battery, Wi-Fi chipset, Bluetooth, touchpad, UHD 620 acceleration, physical suspend or actual audio hardware. Mark these HARDWARE-ONLY, not passed.

## Exit criteria

Phase 3 passes only when:
1. BIOS and UEFI normal-login flows are documented without CI autologin.
2. Desktop/Core lifecycle and relevant VM checklist behaviors have runtime evidence.
3. Whole-system idle RAM JSON is captured from inside the guest.
4. Failures and VM-only limitations are recorded.

Only then consider Phase 4: a live USB boot on the HP 250 G7. No installation. Keep Windows and all partitions untouched.
