# Troubleshooting

| Symptom | Next check |
|---|---|
| Core offline | Run `python3 -m jarvis.server` as a normal user; inspect user-service log in the built session. The launcher works independently. |
| XDG_RUNTIME_DIR missing | Start inside a normal PAM graphical login. Do not substitute a shared/world-writable directory. |
| No module named gi | Use the distro `/usr/bin/python3` with python3-gi and gir1.2-gtk-3.0 installed. A separate Python/venv may not see system packages. |
| No AI node ready | Providers are disabled initially. Configure URL, model and key, enable a node, then use Test nodes. |
| Node offline / 401 | Verify node authentication and `/v1/models`; incorrect keys deliberately fail. Do not disable authentication to fix a login failure. |
| HTTP LAN rejected | Prefer an SSH tunnel to loopback. Direct private LAN HTTP requires explicit opt-in. |
| TLS failure | Use a certificate trusted by the OS and valid for the configured IP. No insecure TLS bypass is supplied. |
| Model not found | Use the exact model ID/alias exposed by the node/provider, not the GGUF filename unless that is the API ID. |
| Quota or HTTP 429 | Respect provider limits; configured fallbacks/cooldown operate without account rotation. |
| Short-context error | Shorten the question or choose a larger node/context. No full tokenizer runs on the laptop. |
| Stream interrupted | Partial output is not saved; wait for cooldown, reconnect and regenerate. |
| Stop during initial connect | The configured connection timeout bounds that wait. Active response reads are interrupted promptly. |
| Memory disabled | Saved facts can still be inspected/deleted; retrieval and new fact saving are disabled. Disable history separately to stop chat persistence. |
| Settings revert after TOML edits | UI values in private preferences.json override TOML. Stop Core and edit the relevant override, preserving unrelated values. |
| Search retrieval disabled | Browser Search works independently. JSON retrieval requires your own configured LAN/tunneled SearXNG with JSON output enabled. |
| Voice unavailable | eSpeak/pulseaudio-utils/Vosk model are optional prerequisites; no real audio hardware was tested here. |
| Build refuses output folder | Use a new directory; existing evidence is deliberately preserved. |
| Build says mount EPERM | Use a privileged dedicated Debian builder, not this restricted workspace. |
| Need one command | bash scripts/build.sh; --check reports host/dependencies/mount and installation commands. |
| Text login only | Inspect LightDM and default target; chroot hook now explicitly selects graphical.target. |
| Openbox with Core offline | Inspect user Core journal; session survives service failures. Do not run Core as root. |
| Facts list shorter than saved memory | Latest matches capped at 96 kB/100 entries; narrow search. Stored facts are preserved. |
| Invalid reload | Last valid configuration remains active; correct private TOML/JSON and reload again. |
| Package unavailable | Refresh builder APT metadata, include non-free-firmware, and inspect the named package on Debian 13. Never ignore missing package errors. |
| Live login fails | Inspect late live-config component execution and password-hash packaging in a disposable VM console. Do not enable autologin as a workaround. |

For reports, include source version, Linux version, sanitized error, configured model alias and observed behavior. Do not include keys, passwords, full private history or memory database.
