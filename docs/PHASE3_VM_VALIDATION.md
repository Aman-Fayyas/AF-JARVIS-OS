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

## Normal-login CI gate — added 2026-10-31

A separate workflow, `.github/workflows/phase3-normal-login.yml`, builds a disposable ISO without adding any LightDM autologin keys. It sets a temporary random password for the disposable `jarvis` account and enables the greeter's hidden-user mode only in the temporary builder copy so CI can enter the standard username/password flow deterministically.

The workflow runs the same ISO in BIOS and UEFI QEMU guests under Xvfb, captures the greeter, submits the temporary username/password, and requires OCR evidence of the AF JARVIS desktop before passing. It uploads screenshots, OCR text, QEMU logs, result JSON and the ISO checksum as a short-lived artifact. The temporary password is masked in workflow logs and is not uploaded; the password hash is removed from the builder after image creation.

This gate is an automated normal-password-login attempt, unlike the earlier autologin boot test. It does **not** yet verify incorrect-password rejection, interactive Core recovery, lock/unlock, suspend/resume, network/audio behavior, or export the guest's whole-system RAM diagnostic JSON. A green workflow is evidence only for the exact checks asserted by that run. Inspect its artifact and logs before marking the BIOS/UEFI login gate complete.


## Normal-login OCR correction — 2026-11-01

The first run of the updated normal-login workflow completed green, but post-run artifact inspection showed both BIOS and UEFI screenshots still on the LightDM username/password dialog. The automation had treated the string `jarvis` as proof of desktop visibility. That run is invalid as login evidence and must not be counted as passed.

The test script was corrected on commit `522a54657d6253e654e9578a21fb975911c5f8bc`: it explicitly clicks the greeter's Log In button after entering the temporary password, rejects screenshots containing greeter labels, and requires three dashboard-specific OCR labels — `AF JARVIS OS`, `Dashboard`, and `Core online` — from the guest display with the QEMU title bar cropped out. The next run's BIOS and UEFI screenshots and OCR text must still be inspected before accepting the result. This improves the assertion but does not independently verify every login/security behavior.

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
python3 /usr/local/bin/af-jarvis-phase3-check > phase3-guest-report.json
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


## Wrong-password and guest-diagnostics automation — 2026-11-01

The Phase 3 normal-login script now attempts a deliberately invalid password before the correct ephemeral password. It captures the guest display and requires LightDM greeter/authentication text to remain visible while dashboard labels remain absent. This is a visual rejection check, not a full PAM policy audit; inspect both BIOS and UEFI evidence before marking it passed.

The disposable CI image also includes OpenSSH Server. QEMU exposes guest port 22 only on runner loopback (127.0.0.1:2222), and after successful normal login the runner invokes the existing read-only `af-jarvis-phase3-check` as the `jarvis` account. The resulting JSON is schema-checked for the AF JARVIS boot marker, account identity, whole-system MemTotal and Core service diagnostic, then uploaded with the screenshots. The SSH server and port forward are CI-only; no host disk is attached. The temporary guest password is not written into the report or artifact.

These checks are pending until a run completes and the uploaded wrong-password screenshots/results and diagnostic JSON are inspected. A failed SSH readiness check must be treated as an infrastructure/diagnostic failure, not a product pass.
