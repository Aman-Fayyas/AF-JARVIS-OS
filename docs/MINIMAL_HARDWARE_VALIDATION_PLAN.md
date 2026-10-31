# Minimal Hardware Validation Plan

Status: planning checkpoint
Base: `main` (preserved; no changes made to the stable branch)
Branch: `minimal-hardware-validation`

## Why this branch exists

The current source is a substantial native, local-first Linux control desktop, not a blank-slate project. Keep its Python Core, GTK3 desktop, SQLite memory, authenticated AI-node routing, deterministic actions, Openbox session and Debian 13 live-build recipe. Do not replace it with Electron, a browser dashboard, or a laptop-hosted large language model.

The repository's current evidence is explicit: 33 automated checks and several isolated component/integration checks passed, but no ISO was produced and no VM or physical HP boot has been verified. The old Ubuntu build attempt was blocked by missing tools and denied mount capabilities. These are validation gaps, not a reason to rewrite the architecture.

## Non-negotiable safety rules

- Keep `main` unchanged while experimenting here.
- Do not install AF JARVIS to the HP SSD or alter Windows partitions.
- Do not write an image to a USB drive until its checksum and BIOS/UEFI VM boots have been checked.
- Use a disposable VM disk for any installer test; never attach the HP's real disk.
- Do not disable security, authentication, privacy boundaries, or essential network/power services to reduce RAM.
- Never commit API keys, passwords, password hashes, personal memory, or device-specific secrets.
- Do not claim hardware support, RAM targets, or successful boot without recorded evidence.

## Phase 1 — Source baseline

1. Run `bash scripts/check.sh` on a supported Linux development environment.
2. Save the full test output and source commit SHA.
3. Review any failure before editing application code.
4. Keep the current 33-check baseline as the comparison point.

Acceptance: all existing checks pass, or each failure is documented and understood.

## Phase 2 — Produce a real image

Preferred route: run the repository's existing `.github/workflows/build-iso.yml` on GitHub Actions from this branch, after reviewing the workflow and its logs. This avoids asking the HP 4 GB machine to perform a memory- and disk-intensive image build.

If CI cannot build the image, use a dedicated Debian 13 amd64 VM with root, mount and chroot privileges, at least 15 GB free disk, and the dependencies listed in `docs/BUILD.md`. Do not attempt the build inside the restricted Ubuntu container environment described in `docs/BOOT_AUDIT.md`.

Acceptance: a genuine ISO and SHA256 checksum are produced by the existing verifier; keep the build log and package manifest.

## Phase 3 — VM boot gate

1. Verify the ISO checksum.
2. Boot BIOS mode with the existing `scripts/run-vm.sh` launcher.
3. Boot UEFI mode separately.
4. Complete every relevant item in `docs/VM_CHECKLIST.md`.
5. Record screenshots, logs, failures and fixes; do not infer success from ISO creation alone.

Acceptance: successful BIOS and UEFI live boots, login/session checks, and documented known failures.

## Phase 4 — HP live-USB validation

Only after Phase 3 passes, create a live USB using a verified image. Boot the HP from USB without installing. Keep Windows and its partitions untouched.

Measure whole-system idle memory using the project's measurement script and record Wi-Fi, UHD 620, audio, battery, suspend/lock, USB and touchpad behavior. The existing 500–700 MiB preferred RAM target is aspirational and unverified; do not promise it.

Acceptance: a completed hardware report with actual measurements and reproducible observations.

## Phase 5 — AI-node integration

Only after the desktop is stable, connect the Tab A7 Lite or another supported authenticated OpenAI-compatible local node. Test node loss/recovery, model ID, response latency and memory use. Keep cloud AI disabled by default; any cloud provider must remain opt-in and must not receive saved facts or conversation history.

Acceptance: local node tests pass and the desktop remains responsive when the node or network disappears.

## Current next action

Inspect and, if sound, run the existing ISO workflow on this branch. Do not add new UI/features until a real image can be built and booted.
