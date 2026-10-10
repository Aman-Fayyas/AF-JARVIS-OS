# Official sources checked during development

Checked 2026-10-10; provider model lists, prices and quotas may change. No permanently unlimited free inference is assumed.

- Debian releases: https://www.debian.org/releases/ — confirms Debian 13/trixie as stable.
- Debian 13 release notes: https://www.debian.org/releases/stable/release-notes/index.html — architecture/kernel/platform changes.
- Debian Live manual package customization: https://live-team.pages.debian.net/live-manual/html/live-manual/customizing-package-installation.en.html
- Debian Live manual runtime customization: https://live-team.pages.debian.net/live-manual/html/live-manual/customizing-run-time-behaviours.en.html
- Debian live-build trixie options: https://manpages.debian.org/trixie/live-build/lb_config.1.en.html
- Debian live-config components and noautologin: https://manpages.debian.org/trixie/live-config-doc/live-config.7.en.html
- Debian Live installer integration: https://live-team.pages.debian.net/live-manual/html/live-manual/customizing-installer.en.html
- PyGObject threading guidance: https://pygobject.gnome.org/guide/threading.html — main-thread GTK with GLib callbacks.
- llama.cpp server documentation: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md — OpenAI-compatible chat, streaming, key file and TLS options.
- Groq OpenAI compatibility: https://console.groq.com/docs/openai — adapter base URL and unsupported-parameter caveats.
- Gemini OpenAI compatibility: https://ai.google.dev/gemini-api/docs/openai — adapter base URL and authenticated compatibility endpoints.
- OpenRouter limits: https://openrouter.ai/docs/api/reference/limits — free-model and credit limits, 402/429 conditions.
- Debian package availability: https://packages.debian.org/trixie/network-manager-applet and https://packages.debian.org/trixie/lxpolkit — updated package names/agent; policykit-1-gnome is unavailable in trixie.
- Debian zram tools: https://packages.debian.org/trixie/zram-tools
- Debian live user source: https://sources.debian.org/src/live-config/11.0.5/components/0030-user-setup
- Debian LightDM source: https://sources.debian.org/src/live-config/11.0.5/components/0100-lightdm
- Openbox startup source: https://sources.debian.org/src/openbox/3.6.1-12/data/autostart/openbox-autostart.in/
- systemd namespace/security semantics: https://manpages.debian.org/trixie/systemd/systemd.exec.5.en.html
- GNU xorriso native find/El Torito commands: https://www.gnu.org/software/xorriso/man_1_xorriso.html

Cloud profiles use legitimate documented endpoints. All begin disabled with blank model IDs and no keys. Select current models/limits in your own provider dashboard; actual calls, quotas, intelligence and latency have not been validated with provider credentials here. Free tiers differ by account, region and model, and may carry different data-use terms. Review current provider privacy terms before enabling a cloud profile.
