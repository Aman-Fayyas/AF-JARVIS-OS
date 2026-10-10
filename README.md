# AF JARVIS OS v0.1 Alpha — source development release

A native, lightweight Linux control desktop for Aman Fayyas's HP 250 G7 (i3-8130U, Intel UHD 620, 4 GB RAM). The laptop runs the desktop, routing, memory and deterministic actions. **LLM inference runs on an external authenticated Local AI Node.** Cloud AI is optional and disabled by default.

This release includes working source and a Debian 13 live-image recipe. **There is no ISO in this package. It has not booted in a VM or been validated on the HP laptop.** Read `docs/STATUS.md` before treating a feature as verified.

This checkpoint continues the supplied existing project. Read `docs/BOOT_AUDIT.md` for fixes and actual build attempts. On a suitable Debian 13 amd64 machine, the single build command is:

```bash
bash scripts/build.sh
```

It reports missing dependencies with installation commands, requests sudo, asks you to choose the live-login password and preserves previous build directories. `bash scripts/build.sh --check` diagnoses the builder. See `docs/PERFORMANCE.md` and `docs/LIVE_USB.md` for measurement and safe live testing.

## What is included

- Python standard-library Core; no Electron, web UI, tokenizer, embeddings or laptop model process.
- Native GTK3 dashboard and assistant; true SSE streaming, stop, regenerate, new chat and local history.
- Deterministic time/CPU/RAM/battery/process commands; allowlisted application launches, volume and folder actions. Reboot, shutdown, creating folders and deleting memory require a short-lived confirmation.
- SQLite local memory, keyword retrieval, bounded recent context, retention, disabling and deletion.
- Four AI modes, authenticated OpenAI-compatible nodes, advanced local routing, cloud fallback, deadlines and cooldowns. Cloud context excludes saved facts and conversation history.
- Desktop-entry application launcher with search, categories, favorites, recent apps and keyboard navigation.
- Node/key settings, existing Linux settings tools, PCManFM files and Firefox ESR launched on demand.
- Browser search, optional private SearXNG JSON retrieval and source links.
- On-demand eSpeak NG speech output; optional Vosk microphone transcription. No microphone process at idle.
- Openbox session, tint2 panel, LightDM login, PipeWire, NetworkManager, power manager, screen lock and zram configuration.
- Build scripts, tests, resource measurement, screenshot, documentation and honest test evidence.

## Start here

1. **Read `docs/QUICKSTART.md`** to run the Core and native UI on Debian without building an OS image.
2. Read `docs/LOCAL_AI_NODE.md` to connect the Tab A7 Lite or another node.
3. Run `bash scripts/check.sh` for automated Core and static build checks.
4. On a supported privileged Debian 13 amd64 builder, follow `docs/BUILD.md`.
5. Boot the generated image in QEMU and complete `docs/VM_CHECKLIST.md` before live USB testing. Keep Windows 11 until hardware verification is complete.

The source starts with every provider disabled. Supply your own endpoint, exact model ID and authentication key in Settings. The default SmolLM2 alias is `smollm2-360m`; optional advanced alias is `qwen3-1.7b`. The source does not contain weights, keys, personal memory or a live password.

## Source layout

| Directory | Purpose |
|---|---|
| `jarvis/` | Core, providers, routing, SQLite, IPC, native desktop, search, voice and system actions |
| `config/` | Safe defaults copied into the user's private configuration on first start |
| `desktop/` | Openbox, autostart, menu and tint2 configuration |
| `distro/` | Debian live-build recipe, package list, image files and hooks |
| `scripts/` | Checks, image preparation/build, VM launch, measurements and packaging |
| `tests/` | Core tests and explicit test-only network/GUI fixtures |
| `docs/` | Setup, architecture, evidence, status and troubleshooting |

Source version: 0.1.0-alpha. This is a development release with a boot validation gate, not an installation-ready distribution.
