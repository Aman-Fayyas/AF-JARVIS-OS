# Run the prototype on Linux

The native desktop requires Linux, Python 3.11 or newer, GTK3 and PyGObject. Windows cannot run the desktop natively. Use a Debian 13 VM for development; the source ZIP can be extracted and read on Windows.

On Debian 13:

```bash
sudo apt update
sudo apt install python3 python3-gi gir1.2-gtk-3.0 xterm pcmanfm firefox-esr espeak-ng
```

Extract this ZIP, open a terminal in `af-jarvis-os`, and run as your normal Linux user:

```bash
python3 -m jarvis.server
```

Leave that terminal open. In a second terminal in the same folder:

```bash
python3 -m jarvis.desktop
```

You must be inside a normal Linux graphical login session with `XDG_RUNTIME_DIR` set by PAM. Core refuses root outside explicit test mode. Do not use `sudo` for the assistant. Do not create an insecure public IPC endpoint.

Try `What time is it?`, `show RAM usage` and `what's my battery percentage?`. These do not need any AI server. AI questions will report that no node is configured until you connect one.

Open Settings → Primary Local Node. Enter its base URL and model ID, paste your key into the hidden input, enable the provider and save. Click Test enabled Local AI Nodes. A successful probe verifies authenticated model listing; it does not prove model quality.

The default mode is Local First with cloud disabled. To use cloud, configure a provider/key/model, enable that provider, enable cloud globally, and select Ask Before Cloud if you want approval per request. No keys are bundled. Secrets are written by the backend to private files with mode 0600.

## Development commands

```bash
python3 -m jarvis.cli status
python3 -m jarvis.cli chat 'Explain RAM.' --route local
python3 -m jarvis.cli conversations
python3 -m jarvis.cli remember 'I am building Project ReLife.'
bash scripts/check.sh
```

`python3 -m jarvis.cli confirm NONCE` executes only the exact action attached to a current confirmation. Approvals expire after 60 seconds and can be used once.

The UI application launcher works independently of Core. On the full OS session, the tint2 taskbar, right-click Openbox menu, Windows+Enter terminal and Windows+E file manager also remain available after a Core/UI crash. Session behavior still needs a booted VM test.

## Optional voice

Speech output uses eSpeak NG only when you click Read reply. For microphone transcription, install Vosk in a virtual environment using the distro's normal Python packaging guidance, obtain a small offline Vosk model, and set its extracted directory in Settings. The UI Python environment must have both Vosk and PyGObject available. The shipped OS does not install Vosk or download models automatically. PipeWire/PulseAudio capture uses `parec` from `pulseaudio-utils`.

Record captures at most approximately 8 seconds, then returns editable text; sending remains a separate action. Wake word and a separate voice activity detector are planned. Neither STT nor TTS has been tested with real audio hardware here.
