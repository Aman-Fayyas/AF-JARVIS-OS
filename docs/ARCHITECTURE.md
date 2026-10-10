# Architecture and resource decisions

## Component choices

| Component | Choice | Reason and tradeoff |
|---|---|---|
| Base | Debian 13 stable amd64 | Mature packages, firmware, security lifecycle and live-build tooling; current stable confirmed by Debian. Ubuntu LTS is viable, but a different base would repeat already completed work and brings no demonstrated RAM advantage here. |
| Window system | Xorg + Openbox | Established lightweight session and broad application compatibility. Wayland is a later option after locking, accessibility and hardware validation; no claimed X11 privacy isolation between same-session apps. |
| Native desktop | Python + GTK3/PyGObject | No browser renderer, familiar native controls and shared libraries. GTK4/Qt could be used, but changing the toolkit lacks a measured benefit for this alpha. GTK operations stay on the main thread. |
| Panel | tint2 | Native taskbar/tray; no JS runtime or compositor. |
| Core | Python standard library | Small service, bounded worker slots, no model weights, no HTTP application framework. |
| IPC | Private Unix stream socket | 0600 socket in a 0700 user runtime directory; Linux SO_PEERCRED checks same UID. No production TCP Core listener. |
| AI | Authenticated external OpenAI-compatible API | Hardware-neutral nodes; no laptop LLM, explicit trusted endpoints and encrypted transport where practical. |
| Memory | SQLite, ordinary keyword retrieval | Local storage and bounded reads without a vector daemon. LIKE scans are adequate for this alpha; FTS is a future optimization if measured growth warrants it. |
| Audio/voice | PipeWire; eSpeak NG; optional Vosk | Existing device infrastructure, offline speech, recognition loaded only during an explicit recording. |
| Network/power | NetworkManager, existing Linux drivers, XFCE power manager | Retain usable Wi-Fi, battery and suspend support. No blanket disabling of essential services to chase a benchmark. |

## Request behavior

A recognized deterministic intent is validated and performed without inference. AI output has no system execution path: prompts and provider text can never become shell commands.

For AI chat, one generation runs at a time to avoid overloading a one-slot tablet. Routine questions use primary local nodes, then configured advanced local nodes. Difficult-task heuristics prefer advanced local; if cloud is globally enabled, policy permits it and the task merits it, configured clouds are tried before local fallback. Cloud Preferred permits routine cloud requests; Local Only prevents every cloud request. Ask Before Cloud requires per-request consent.

Cloud requests contain the system instruction and current question only, never saved history or local facts. An explicit Sensitive checkbox and known-secret pattern detection block cloud. This is a heuristic, not a universal data classifier: mark private questions sensitive, and retain Local Only when all data must stay on the LAN. The Core does not read or automatically attach personal files.

For local chat, retrieve at most three relevant short facts and recent complete message pairs. Reserve output/context formatting space using conservative UTF-8 byte counting; this is an estimate rather than an exact model tokenizer. Reject an oversized current question instead of silently truncating it.

The provider parses real SSE data frames, including chunked network writes and UTF-8. Tokens are delivered immediately over framed IPC; GTK batches queued tokens when the main loop is ready. There is no typewriter delay. The UI uses event-driven queue wakeups and a 5-second status timer, not continuous token polling. Enabled local nodes are probed about once a minute while idle; cloud models are not probed in the background.

Provider failures enter a 60-second cooldown. If output was already displayed, partial output is not persisted or merged with a new fallback answer. Cancellation shuts down the underlying connection and wakes a stalled read. Requests have configured network timeouts, a 180-second generation deadline checked between reads and a bounded output size. A blocked initial connection can take the configured timeout to cancel; no success is claimed until completion.

## Permissions and lifetime

Safe read/launch actions run as the logged-in user. Folder creation, memory/history deletion, restart and shutdown are tied to exact confirmation nonces with a 60-second lifetime. Destructive file deletion, arbitrary shell execution and AI-controlled package installation are not implemented. OS updates remain explicit human-administered APT operations.

Config/keys and data use 0700 directories and 0600 files. Logging avoids upstream error bodies and request/secret contents. TLS certificate checks and no-redirect policies protect provider credentials. Core runs as a user service with NoNewPrivileges; root is allowed only behind explicit flags in a disposable test environment.

Openbox, tint2 and ordinary applications are independent of Core. A crash cannot remove the desktop or file manager. The user service restarts Core with bounded retries; production systemd recovery and startup still require VM validation.

Session startup guards DBus/user-manager imports and starts Core without waiting before running Openbox with the existing curated autostart. Failed Core startup cannot terminate the session. Curated startup avoids duplicate XDG applets, and session exit stops Core. The user unit shares session /tmp for X11 launches; NoNewPrivileges, private files and RestrictSUIDSGID remain enabled.

## Whole-OS measurement plan

RSS counts shared pages in each process; PSS apportions those pages and is more useful for summing components. Neither includes all kernel/cache accounting. Measure system used RAM using MemTotal minus MemAvailable after 60 seconds of idle, plus per-process PSS, services, boot time and model-node latency separately. Do not call container host memory an OS benchmark.

Below 500 MiB idle is a stretch goal; 500–700 MiB is a good target; below 1 GiB is preferred. None of these whole-OS targets has been measured yet. Optional zram is capped at 25% of RAM with lz4; this sets capacity and does not preallocate the full compressed device in physical memory.
