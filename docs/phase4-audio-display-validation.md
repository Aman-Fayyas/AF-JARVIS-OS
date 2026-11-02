# Phase 4: Audio, display and offline speech validation

These checks run only in disposable CI QEMU guests and hosted runners.

- eSpeak-NG: generate a WAV in the guest and validate its PCM header and frame count.
- PipeWire: verify PipeWire, PipeWire-Pulse and WirePlumber, plus the PulseAudio-compatible server and graph.
- GTK/Xorg: verify Xorg and X11 responsiveness while retaining QEMU guest desktop screenshots and OCR evidence.
- Resolution recovery: switch the virtual QEMU display to 1024x768 and back to 1280x800, verifying Xorg remains responsive.
- Microphone path: capture PCM through `parec` at 16 kHz mono and validate captured data. QEMU's host audio backend is null, so this does not prove a physical microphone works.
- Offline Vosk: use an eSpeak-generated test utterance and the small English Vosk model to verify local recognition without a cloud service.

These tests do not establish physical speaker output, microphone quality, Intel UHD 620 acceleration, or the laptop panel's native display behavior. Those still require a later live-USB test on the HP laptop.
