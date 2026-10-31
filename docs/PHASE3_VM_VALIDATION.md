# Phase 3 — Full-system VM validation

Status: IN PROGRESS
Branch: minimal-hardware-validation
Scope: disposable QEMU guest only; no physical disks or installer target.

## Evidence entering Phase 3

- Phase 2B GTK/Core integration workflow passed on commit 6e3e7adbb7244068f9b84041823de52eac72362.
- BIOS and UEFI QEMU screenshots show the desktop rendered.
- The existing QEMU workflow appends LightDM autologin to its disposable CI chroot. Therefore those screenshots do not validate the normal login screen or password handling.
- Existing QEMU logs were empty. Screenshots are useful visual evidence, not complete boot logs.
- Phase 2B used a test-fixture AI response. It did not validate a real AI provider or local tablet node.
- No whole-OS idle RAM measurement has been recorded.

## Safety boundary

- Never attach the host's physical disk to QEMU.
- Never run the installer against a host disk.
- Use a newly created disposable virtual disk only if installer testing is explicitly added later.
- Do not change Windows partitions, BitLocker, Secure Boot or firmware settings for this phase.
- Do not publish a live-image password or its hash. The hash is embedded in the ISO; keep the ISO private.
- Do not mark a check passed without a dated observation, log or screenshot.

## Gate A — Build and verify a private test ISO

Use a dedicated Debian 13 amd64 builder or the reviewed CI build workflow. Generate a unique live-login password locally on the builder; do not share it in chat or commit it.

```bash
umask 077
openssl passwd -6 > "$HOME/jarvis-live-password.hash"
sudo env JARVIS_LIVE_PASSWORD_HASH_FILE="$HOME/jarvis-live-password.hash" \
  bash scripts/build-iso.sh --build "$PWD/build/phase3-vm"
python3 scripts/verify-iso.py build/phase3-vm/AF-JARVIS-OS-v0.1-alpha.iso
sha256sum build/phase3-vm/AF-JARVIS-OS-v0.1-alpha.iso
```

Keep the ISO and hash private. Do not upload the password/hash to CI artifacts. Store the checksum and build manifest in local test notes, not in a public issue.

## Gate B — BIOS and UEFI normal-login tests

Boot separately using the existing launcher:

```bash
bash scripts/run-vm.sh build/phase3-vm/AF-JARVIS-OS-v0.1-alpha.iso bios
bash scripts/run-vm.sh build/phase3-vm/AF-JARVIS-OS-v0.1-alpha.iso uefi
```

For each firmware mode, record:
- ISO checksum and source commit.
- Firmware mode, QEMU version, RAM and vCPU allocation.
- LightDM greeter appears (no CI autologin).
- Correct live-user password permits login; an incorrect password does not.
- Openbox, panel and AF JARVIS desktop appear after login.
- Core service is active for the logged-in user.
- Desktop remains usable after Core is stopped; service recovery/reconnect behavior is observed.
- No critical boot/session errors in the journal.

Useful commands in the guest:

```bash
systemctl --user status jarvis-core.service
journalctl --user -b --no-pager
systemctl --user --failed
systemctl --failed
```

## Gate C — Desktop and OS behavior

Complete each item separately and attach evidence:
- [ ] Normal login and failed-password rejection.
- [ ] Desktop session and Core start after login.
- [ ] Core stop/restart and UI reconnect.
- [ ] Network connect/disconnect; deterministic local actions remain available offline.
- [ ] Screen lock and password-required unlock.
- [ ] Suspend/resume and lock-on-resume, if supported by the VM.
- [ ] Audio output/input detection; record unavailable virtual devices honestly.
- [ ] File manager and installed desktop entries launch.
- [ ] Confirmed guest shutdown works.
- [ ] No unexpected failed system or user units.

A VM may not accurately emulate laptop battery, Wi-Fi chipset, Bluetooth, touchpad, UHD 620 acceleration or physical suspend. Mark these HARDWARE-ONLY, not passed.

## Gate D — Whole-system idle RAM

After a successful login, wait at least 60 seconds. Close browser/optional apps, do not run AI generation or voice capture, then run:

```bash
sudo python3 scripts/measure-idle.py > idle-measurement.json
```

Retain the complete JSON and note firmware mode, VM RAM allocation, QEMU version, boot time, session state and whether the measurement was taken with the dashboard open. Report MemTotal, MemAvailable, used RAM, swap and the largest process PSS values.

Do not compare process RSS/PSS sums with whole-system used RAM. VM memory results are guest-specific and are not a substitute for the HP's physical hardware measurement.

## Exit criteria

Phase 3 passes only when:
1. BIOS and UEFI normal-login flows are documented without CI autologin.
2. Desktop/Core lifecycle and the relevant VM checklist behaviors have evidence.
3. Whole-system idle RAM JSON is captured from inside the guest.
4. Failures and VM-only limitations are recorded.

Only then consider Phase 4: a live USB boot on the HP 250 G7. No installation. Keep Windows and all partitions untouched.
