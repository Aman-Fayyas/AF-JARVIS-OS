# Actual performance observations — 2026-10-10

**No whole-system AF JARVIS OS idle measurement exists.** No AF JARVIS kernel, Openbox, LightDM, panel, audio or networking services were booted here. Container host memory is not a substitute.

## Isolated process measurements

Native GTK3 ran under Xvfb on Ubuntu 24.04. Core and GTK were separate processes, with providers disabled and 60 seconds idle. Each process read its own /proc/self/smaps_rollup. Neither contained a fake AI node or parent test harness. Core used the explicit test-only loopback transport because AF_UNIX is prohibited; production still uses Unix IPC.

| Actual process | RSS MiB | PSS MiB |
|---|---:|---:|
| Core, no local model | 17.22 | 13.28 |
| Native GTK desktop | 73.97 | 59.53 |

The two process PSS values total 72.81 MiB. This excludes the OS, X server, Openbox, panel, display manager, audio/network/power/security services and kernel memory. It cannot establish any whole-system RAM target. See process-memory-results.json and process-memory-output.txt. Independent GTK integration, including its fake-node harness, measured 77.91 MiB RSS / 63.49 MiB PSS, and its Core measured 18.51 / 14.42 MiB.

RSS double-counts shared libraries across processes. PSS apportions shared pages. MemTotal minus MemAvailable is the primary whole-system used-RAM metric; process sums do not equal it. Measurements can vary across target Debian versions, devices, library sharing and allocator behavior.

## Existing resource controls retained

No laptop inference, tokenizer, embedding daemon, Electron, compositor, browser at startup, always-on microphone or background cloud requests. One AI generation at a time, bounded workers/IPC/provider outputs/context, capped fact reads, deterministic SQLite connection lifetime and event-driven GTK queue. Networking, power management, lock/authentication and user privilege boundaries remain intact. Duplicate XDG applet startup was removed from the curated session. No security feature was removed to chase a RAM number.

## Required booted-system measurement

On HP 250 G7 with 4 GB RAM, after actual live boot and 60 seconds idle, browser closed, no voice or generation:

```bash
sudo python3 scripts/measure-idle.py > idle-measurement.json
systemctl --failed
systemctl --user --failed
systemd-analyze
```

The script reports MemTotal, MemAvailable, used RAM, swap, per-process RSS/PSS, unreadable/exited process count, measurement UID and whether /etc/issue identifies AF JARVIS. Keep measurement context and firmware/device conditions with the result. Investigate the largest PSS processes and duplicate daemons before changes; measure again only after a meaningful change. Do not disable essential security, audio/network reliability or power support for a benchmark.

Targets remain: <500 MiB stretch; 500–700 MiB preferred; <1 GiB preferred maximum. None has been verified. Boot/login time, guest CPU activity, real model latency and tablet RAM are also unmeasured.
