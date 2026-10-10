# Boot and hardware validation gate

All items below are **UNTESTED** until a developer records actual evidence.

| Check | Evidence needed |
|---|---|
| BIOS and UEFI boot | Guest screenshots, kernel log and successful startup in each mode |
| Secure Boot | Separate firmware test; not inferred from Debian packages |
| Live login | `jarvis` accepts only supplied password; autologin disabled; weak/default live password fails |
| Privilege boundaries | Normal user UID, passwordful sudo; no live-config passwordless PolicyKit rules |
| Session startup | Openbox, tint2, native desktop and user Core service run after login |
| Failure recovery | Kill Core; apps remain usable; service restarts within policy; UI reconnects |
| Screen lock/suspend | Windows+Escape locks; suspend triggers lock; password needed on resume |
| Networking | Connect/disconnect Wi-Fi/Ethernet; deterministic commands continue without internet |
| Local inference | Real authenticated tablet replies stream; model ID, latency and node memory recorded |
| Node disappearance | Stop node/Wi-Fi; UI remains usable, marks offline and reconnects after recovery |
| Cloud | Each configured official provider; explicit consent, 429 fallback, no private context |
| Files/apps | PCManFM external storage, browser on demand, desktop-entry launch and favorites |
| Audio | Output/input devices, volume commands, eSpeak, Vosk recording and microphone shutoff |
| Hardware | UHD 620 acceleration, actual Wi-Fi chipset, Bluetooth, USB, touchpad, display, battery |
| Installer | Only a disposable VM disk; custom files/session survive install; normal fresh user login |
| RAM/CPU | 60-second idle measurement, PSS components, CPU wakeups and boot/login timings |
| Shutdown | Confirmed request shuts down guest; no unattended power operation |

Inside a booted VM or laptop live environment:

```bash
sudo python3 scripts/measure-idle.py > idle-measurement.json
systemctl --user status jarvis-core.service
journalctl --user -u jarvis-core.service --no-pager
lspci -nnk
```

Run the measurement script from the extracted source; the built image includes core docs but not test/build tooling at runtime. Measure twice only if conditions differ meaningfully (e.g. UI closed/open), label both states, and exclude live AI/browser workloads from idle claims.

Keep Windows intact. Move from source to VM, then live USB, then real hardware checks. Full installation is a separate irreversible decision after backups and actual hardware validation.
