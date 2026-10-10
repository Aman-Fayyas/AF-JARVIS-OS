# Connect a Local AI Node

Any host with an authenticated OpenAI-compatible API can serve as a node. Core never installs or loads an LLM on the laptop. A future Raspberry Pi, mini PC or server uses the same profile format.

Aman's current target is a Tab A7 Lite with Android 14, about 3 GB RAM, Termux and llama.cpp. Preferred weights: **SmolLM2 360M Instruct Q6_K**. Optional slower weights: **Qwen3 1.7B Q4_K_M**. Actual speed, memory and compatibility on that tablet remain untested in this session.

## Preferred transport: SSH tunnel

If your installed `llama-server --help` includes `--api-key-file`, use a private key file rather than passing the key as a command-line argument. Example on the AI Node, adapting binary/model paths to your existing installation:

```bash
umask 077
mkdir -p "$HOME/.config/jarvis-node"
python3 -c 'import secrets; print(secrets.token_urlsafe(32))' > "$HOME/.config/jarvis-node/api.key"
llama-server -m /path/to/SmolLM2-360M-Instruct-Q6_K.gguf \
  --alias smollm2-360m --ctx-size 2048 --parallel 1 \
  --host 127.0.0.1 --port 8080 \
  --api-key-file "$HOME/.config/jarvis-node/api.key"
```

Keep the server terminal running. Enable SSH on your node using its normal procedure. Termux typically uses port 8022 and its own Android username. From the laptop:

```bash
ssh -N -L 127.0.0.1:8080:127.0.0.1:8080 -p 8022 YOUR_TERMUX_USER@YOUR_TABLET_LAN_IP
```

Verify the SSH host key through your own device rather than disabling host verification. The AI server stays bound to the tablet's loopback interface. Configure the laptop provider URL as `http://127.0.0.1:8080/v1`, model `smollm2-360m`, and the same node API key. Transfer that one key privately; never paste it into chat or a public source repository.

SSH encryption protects LAN traffic while the API key authenticates the model server. No public internet port forwarding is needed.

## Alternatives

- HTTPS with a certificate trusted by the laptop: use a private LAN IP that appears in the certificate's IP SAN. Certificate verification remains enabled.
- Direct private LAN HTTP: set `--host YOUR_TABLET_LAN_IP` on the node and explicitly enable Allow unencrypted LAN HTTP in the profile. Authentication is still required, but prompts and the key are exposed to LAN observers. This is an explicit opt-in; loopback/tunneling is the default.
- DNS/mDNS discovery: planned. Manual private IP configuration prevents automatic trust of arbitrary devices.

Core rejects public IPs for Local AI profiles, URL credentials, query strings, redirects, and HTTP cloud endpoints. It does not use system proxy settings for AI traffic.

No tablet IP is permanently encoded. SSH keeps the JARVIS endpoint at loopback while you change the SSH destination for a new address or replacement node. Direct private LAN endpoints are editable without rebuilding. DNS/mDNS are not automatically trusted.

## Current integration evidence

tests/fake_node.py is a real authenticated loopback HTTP server with /v1/models and streamed /v1/chat/completions. Tests fragment SSE/UTF-8, reject bad keys with 401, exercise cancellation, malformed/disconnected replies and 429 fallback; GTK displays actual streamed fixture tokens. It contains no model weights and is not installed in the image. The real tablet was not tested because no reachable endpoint/key was provided. Real alias/authentication, latency, node RAM, Android sleep/Wi-Fi and reconnection remain hardware tests. Future servers use the same API profiles.

## Advanced and future nodes

Run a stronger model on a stronger device, or stop the primary tablet model before switching to Qwen3. **Do not start both models concurrently on the 3 GB tablet without measuring available RAM.** Change the model alias/profile or use the Advanced Local profile pointed to a separate endpoint. No model quality is inferred from a quantization filename.

Up to 16 local profiles may be configured in `config.toml`. The settings dialog edits the bundled primary/advanced profiles; custom profiles are added manually. Cloud profiles are separate. Full multi-node scheduling and capability negotiation are planned; enabled nodes are attempted in the router's ordered list with a 60-second error cooldown.

Files live under `~/.config/af-jarvis/`. `preferences.json` stores UI overrides and takes precedence over same-named TOML settings. Stop Core before manual edits. Remove only the relevant override if you intend TOML to take precedence again, preserving secrets and unrelated values.
