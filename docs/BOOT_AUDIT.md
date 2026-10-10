# Existing-project boot audit

## Repository and actual checks

Reviewed the existing Python modules, GTK/configuration, IPC, SQLite, providers/router, deterministic actions, voice/search, Openbox assets, user unit, LightDM, package list, live-build configuration/hooks, scripts/tests and docs. Source identity matched the supplied ZIP before editing. No project reset or architecture replacement was performed.

The initial 17 tests passed (audit-initial-tests.txt). The expanded 33 checks passed (audit-test-results.txt), with compilation, shell/XML validation and real build-tree preparation. Native GTK actually ran under Xvfb against the real Core code through an explicitly test-only loopback transport and an authenticated HTTP/SSE fixture. Production remains Unix-only; sandbox EPERM prevented that transport. desktop-tested.png is an actual GTK screenshot.

## Corrections

| Finding | Correction and evidence |
|---|---|
| Session exited before Openbox after Core/DBus failure | Guarded imports and nonblocking Core start; shell test proves Openbox starts when service stubs fail; exit stops Core |
| Live-user/PAM dependencies omitted with recommends disabled | Explicit user-setup and libpam-systemd; Debian's live user creation is package gated |
| X11/process/audio dependencies implicit | Explicit xauth, procps and pipewire-alsa; Debian APT metadata check remains mandatory on actual builder |
| Graphical target implicit | Chroot hook selects graphical.target after enabling LightDM |
| Login hook locked user on rerun after consuming hash | Success marker; isolated hook executed twice with no relock; missing hash still locks/fails closed |
| Legacy login-hook include path | Canonical /usr/lib/live/config with matching chmod/validator |
| Core PrivateTmp hid session paths and depended on user namespaces | Removed mount namespace directive for reliable X11 launches; kept non-root startup, same-UID IPC, private files, NoNewPrivileges and RestrictSUIDSGID |
| Possible duplicate applets from XDG startup | Openbox uses existing curated autostart explicitly; existing rc.xml/menu/panel retained |
| First-event disconnect leaked busy state/lock | Yield moved inside cleanup scope; request iterator explicitly closed; regression immediately runs another command |
| Invalid reload corrupted live settings | Transactional rollback; local chat still works after rejected reload |
| String booleans enabled providers/insecure LAN unexpectedly | Strict booleans, bounded strings and relative private key paths |
| Privacy/retention changes raced generation | Changes rejected until generation stops |
| Malformed SSE/model shapes caused uncaught type errors | Explicit shape validation; deterministic commands work after failure |
| Unicode facts exceeded IPC | 96 kB response budget, all stored facts preserved; outgoing frame limit enforced |
| Disabled clouds triggered consent | Enabled cloud candidate required |
| Offline UI retained stale node state | Clear status on Core loss |
| Build diagnostics/ISO checks incomplete | Full preflight/install guidance, one-command builder, ISO9660 plus BIOS/UEFI/live-payload verification |

Session/login checks execute scripts against isolated stubs, not real PAM/systemd. Confirmed directory creation was executed only inside a temporary test directory. Host shutdown/reboot were not performed.

## Actual build limitations

Executed the existing build-iso.sh --build, then the improved build entry point; exit 1, no image. iso-build-attempt.txt records Ubuntu 24.04.3, missing lb/debootstrap/mksquashfs/xorriso/EFI tooling, and a real tmpfs mount denied with permission error. Effective and bounding capability sets are zero: UID 0 does not grant CAP_SYS_ADMIN here. An actual user-namespace attempt also failed. Installing tools cannot remove this privilege restriction.

QEMU launcher was attempted and stopped because qemu-system-x86_64 is missing; there is also no ISO. KVM is absent but TCG is supported, so KVM alone is not required. No Linux/guest/session/network/shutdown boot claim is made.

Production Core startup with the explicit test-root flag failed at AF_UNIX creation with EPERM. Normal production invocation correctly refuses root. User systemd verification could not access its sockets/bus; the image ExecStart path is not installed on this host. See environment-audit.json. Service recovery remains untested.

## Routing/security evidence

| Scenario | Actual result |
|---|---|
| Simple OS command | Deterministic code, zero AI requests |
| Normal question | Authenticated local HTTP/SSE fixture |
| High-effort question, cloud allowed | Cloud-shaped adapter with test-only HTTP transport seam; current question/system instruction only |
| Cloud quota/outage | Real fixture HTTP 429 or malformed response, then authenticated local fallback |
| Local/both AI failure | Deterministic commands still run; generation lock cleaned |
| Core stops | GTK visible/responsive, actual Gio test-utility launch succeeds |
| Hostile LLM text | Text only, system execution function never called |
| Destructive action | Expiring exact-action nonce, replay/expiry/deletion tests, confirmed temporary folder creation |
| Keys/context/endpoints | Private backend key files; public config excludes keys; no cloud history/facts; real 401 rejection; private-LAN/HTTPS URL validation |

The transport seam exists only in tests and does not permit HTTP cloud endpoints in production. Actual cloud credentials/quotas and inference quality/latency are untested. Secret classification is heuristic; use Local Only for data that must remain private.

## Known limitations

No target APT solve/chroot/image build, genuine image validation or BIOS/UEFI boot has completed. Live passwordful login/sudo, locking, audio, NetworkManager, PCManFM/Firefox/xterm in a guest, removable storage, installer and Secure Boot remain untested. No Windows disk changes occurred.

Node configuration is generic and editable; default disabled loopback plus SSH tunnel avoids a permanent tablet IP. Automatic DNS/mDNS discovery is absent. Real tablet tests remain required. No laptop LLM, Electron, browser startup, embedding/index daemon or telemetry was added.

This is a repeatable source recipe, not proof of byte-identical binary reproducibility: Debian repositories update. Preserve logs, resolved manifests and source checksums. The unresolved gate is an actual build and boot; no new product features were added.
