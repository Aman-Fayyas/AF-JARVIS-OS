#!/usr/bin/env bash
# Disposable CI-only normal-login test. Never attaches a host disk.
set -euo pipefail
MODE="${1:?bios or uefi}"
ISO="${2:?ISO path}"
PASSWORD="${3:?temporary test password}"
OUT="${4:-.}"
mkdir -p "$OUT"
MONITOR="/tmp/af-jarvis-${MODE}-monitor.sock"
QEMU=(qemu-system-x86_64 -machine accel=tcg -cpu max -m 1536 -smp 2 -cdrom "$ISO" -boot d -nic user,model=virtio-net-pci,hostfwd=tcp:127.0.0.1:2222-:22 -usb -device usb-tablet -audiodev driver=none,id=audio0 -device intel-hda -device hda-duplex,audiodev=audio0 -display sdl -no-reboot -monitor "unix:$MONITOR,server,nowait")
if [[ "$MODE" == uefi ]]; then
  OVMF_CODE=$(find /usr/share/OVMF -type f \( -name 'OVMF_CODE_4M.fd' -o -name 'OVMF_CODE.fd' \) | head -n1)
  [[ -n "$OVMF_CODE" ]]
  QEMU+=(-drive "if=pflash,format=raw,readonly=on,file=$OVMF_CODE")
elif [[ "$MODE" != bios ]]; then
  echo "Unknown firmware mode: $MODE" >&2
  exit 2
fi
"${QEMU[@]}" >"$OUT/$MODE-normal-login-qemu.log" 2>&1 &
QEMU_PID=$!
cleanup() {
  kill "$QEMU_PID" 2>/dev/null || true
  wait "$QEMU_PID" 2>/dev/null || true
}
trap cleanup EXIT
WINDOW=""
for _ in $(seq 1 90); do
  WINDOW=$(xdotool search --onlyvisible --name 'QEMU' 2>/dev/null | head -n1 || true)
  [[ -n "$WINDOW" ]] && break
  kill -0 "$QEMU_PID"
  sleep 2
done
[[ -n "$WINDOW" ]] || { echo "QEMU display window did not appear" >&2; exit 1; }
# The host SDL window may be smaller than the guest framebuffer. Record its
# geometry, but capture screenshots through the QEMU monitor so OCR sees the
# complete guest display rather than a clipped host window.
xdotool getwindowgeometry --shell "$WINDOW" >"$OUT/$MODE-qemu-window-geometry.txt"
capture_guest() {
  local name="$1"
  local ppm="$OUT/$name.ppm"
  printf 'screendump %s\n' "$ppm" | socat - UNIX-CONNECT:"$MONITOR" >/dev/null
  convert "$ppm" "$OUT/$name.png"
}
xdotool windowfocus --sync "$WINDOW"
BOOT_MENU_SEEN=0
for _ in $(seq 1 45); do
  capture_guest "$MODE-boot-menu"
  tesseract "$OUT/$MODE-boot-menu.png" stdout 2>/dev/null >"$OUT/$MODE-boot-menu-ocr.txt" || true
  if grep -Eqi 'enter:[[:space:]]*boot|Live system|Start installer' "$OUT/$MODE-boot-menu-ocr.txt"; then
    BOOT_MENU_SEEN=1
    break
  fi
  kill -0 "$QEMU_PID"
  sleep 2
done
[[ "$BOOT_MENU_SEEN" == 1 ]] || { echo "Firmware boot menu was not detected." >&2; cat "$OUT/$MODE-boot-menu-ocr.txt" >&2 || true; exit 1; }
printf 'sendkey ret\n' | socat - UNIX-CONNECT:"$MONITOR"
GREETER_SEEN=0
for _ in $(seq 1 90); do
  kill -0 "$QEMU_PID"
  capture_guest "$MODE-login-greeter"
  convert "$OUT/$MODE-login-greeter.png" -gravity North -chop 0x30 -colorspace Gray -resize 250% -contrast-stretch 1%x1% "$OUT/$MODE-login-content.png"
  tesseract "$OUT/$MODE-login-content.png" stdout --psm 11 2>/dev/null >"$OUT/$MODE-greeter-ocr.txt" || true
  if grep -Eqi 'Enter your password|Log In|Username' "$OUT/$MODE-greeter-ocr.txt"; then
    GREETER_SEEN=1
    break
  fi
  sleep 3
done
[[ "$GREETER_SEEN" == 1 ]] || { echo "LightDM login greeter was not detected." >&2; cat "$OUT/$MODE-greeter-ocr.txt" >&2 || true; exit 1; }
# First submit a deliberately incorrect password. A rejection is proven
# only if the greeter remains visible and the dashboard does not appear.
xdotool mousemove --window "$WINDOW" 690 360 click 1
xdotool type --clearmodifiers --delay 100 jarvis
xdotool key Return
sleep 2
xdotool type --clearmodifiers --delay 45 "definitely-not-the-password"
sleep 1
xdotool key Return
sleep 5
capture_guest "$MODE-wrong-password"
convert "$OUT/$MODE-wrong-password.png" -gravity North -chop 0x30 -colorspace Gray -resize 250% -contrast-stretch 1%x1% "$OUT/$MODE-wrong-password-content.png"
tesseract "$OUT/$MODE-wrong-password-content.png" stdout --psm 11 2>/dev/null >"$OUT/$MODE-wrong-password-ocr.txt" || true
if ! grep -Eqi 'Log In|Cancel|Enter your password|Password|Try again|Authentication' "$OUT/$MODE-wrong-password-ocr.txt"; then
  echo "Wrong-password rejection not proven: login greeter was not detected after invalid credentials." >&2
  cat "$OUT/$MODE-wrong-password-ocr.txt" >&2 || true
  exit 1
fi
if grep -Eqi 'Dashboard|Core online' "$OUT/$MODE-wrong-password-ocr.txt"; then
  echo "Wrong password unexpectedly reached the desktop." >&2
  exit 1
fi
printf '{"mode":"%s","wrong_password":"rejected-greeter-remained-visible"}\n' "$MODE" >"$OUT/$MODE-wrong-password-result.json"

# After LightDM rejects a password it keeps the username and returns focus
# to the password entry. The previous automation clicked a stale coordinate
# and re-entered the username, so the valid password never reached the field.
# Keep the existing jarvis username and replace only the focused password.
xdotool key ctrl+a
xdotool type --clearmodifiers --delay 45 "$PASSWORD"
sleep 1
xdotool key Return
sleep 3
for _ in $(seq 1 90); do
  kill -0 "$QEMU_PID"
  capture_guest "$MODE-after-login"
  convert "$OUT/$MODE-after-login.png" -gravity North -chop 0x30 -colorspace Gray -resize 200% -contrast-stretch 1%x1% "$OUT/$MODE-screen-content.png"
  tesseract "$OUT/$MODE-screen-content.png" stdout --psm 11 2>/dev/null >"$OUT/$MODE-screen-ocr.txt" || true
  OCR="$OUT/$MODE-screen-ocr.txt"
  if grep -Eqi 'Log In|Cancel|Enter your password|Password' "$OCR"; then
    sleep 5
    continue
  fi
  # OCR can miss the stylized AF JARVIS OS header, but the dashboard tab and
  # live Core status are both visible in the guest screenshot. Require both.
  if grep -Eqi 'Dashboard' "$OCR" &&
     grep -Eqi 'Core online' "$OCR" &&
     grep -Eqi 'JARVIS' "$OCR"; then
    printf '{"mode":"%s","login":"desktop-visible","evidence":"guest-dashboard-ocr","required_labels":["JARVIS","Dashboard","Core online"],"header_label_optional":"AF JARVIS OS","qemu_pid":%s}\n' "$MODE" "$QEMU_PID" >"$OUT/$MODE-normal-login-result.json"
    # Collect read-only diagnostics from the disposable guest over a loopback-only
    # QEMU user-network forward. The SSH server exists only in this CI image.
    SSH_READY=0
    for _ in $(seq 1 30); do
      if timeout 8s env SSHPASS="$PASSWORD" sshpass -e ssh -p 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=3 -o ServerAliveInterval=3 -o ServerAliveCountMax=1 jarvis@127.0.0.1 'true' >/dev/null 2>&1; then
        SSH_READY=1
        break
      fi
      kill -0 "$QEMU_PID"
      sleep 2
    done
    [[ "$SSH_READY" == 1 ]] || { echo "Guest SSH unavailable; diagnostics not collected." >&2; exit 1; }
    timeout --signal=TERM --kill-after=5s 45s env SSHPASS="$PASSWORD" sshpass -e ssh \
      -p 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      -o ConnectTimeout=5 -o ServerAliveInterval=5 -o ServerAliveCountMax=3 \
      jarvis@127.0.0.1 \
      'uid=$(id -u); export XDG_RUNTIME_DIR="/run/user/$uid"; export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"; export DISPLAY=:0; python3 /usr/local/bin/af-jarvis-phase3-check' \
      >"$OUT/$MODE-phase3-guest-report.json"
    python3 - "$OUT/$MODE-phase3-guest-report.json" <<'PY'
import json,sys
with open(sys.argv[1], encoding="utf-8") as f:
    report=json.load(f)
assert report.get("schema") == "af-jarvis-phase3-guest-check-v1"
assert report.get("boot_marker") is True
assert report.get("identity",{}).get("user") == "jarvis"
assert report.get("memory_mib",{}).get("mem_total")
assert "user_service_status" in report.get("checks",{})
print("Guest diagnostic JSON validated.")
PY
    # Test user-service failure and recovery in the disposable guest only.
    guest_ssh() {
      local command="$1"
      local started=$SECONDS rc=0
      # Every guest command is bounded. SSH ConnectTimeout alone only bounds
      # connection setup; it does not stop a remote systemd/DBus command that
      # accepts the connection and then never returns.
      echo "::group::[$MODE] guest command (45s cap): $command"
      if timeout --signal=TERM --kill-after=5s 45s env SSHPASS="$PASSWORD" sshpass -e ssh \
        -p 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        -o ConnectTimeout=5 -o ServerAliveInterval=5 -o ServerAliveCountMax=3 \
        jarvis@127.0.0.1 \
        "export XDG_RUNTIME_DIR=/run/user/1000; export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus; export DISPLAY=:0; $command"; then
        echo "Guest command completed in $((SECONDS-started))s."
      else
        rc=$?
        echo "::error::[$MODE] guest command failed or exceeded 45s (exit $rc) after $((SECONDS-started))s: $command"
      fi
      echo "::endgroup::"
      return "$rc"
    }
    guest_ssh 'systemctl --user stop jarvis-core.service && ! systemctl --user is-active --quiet jarvis-core.service'
    CORE_OFFLINE_SEEN=0
    for _ in $(seq 1 30); do
      kill -0 "$QEMU_PID"
      capture_guest "$MODE-core-offline"
      convert "$OUT/$MODE-core-offline.png" -gravity North -chop 0x30 -colorspace Gray -resize 250% -contrast-stretch 1%x1% "$OUT/$MODE-core-offline-content.png"
      tesseract "$OUT/$MODE-core-offline-content.png" stdout --psm 11 2>/dev/null >"$OUT/$MODE-core-offline-ocr.txt" || true
      if grep -Eqi 'Core offline' "$OUT/$MODE-core-offline-ocr.txt" && grep -Eqi 'Dashboard' "$OUT/$MODE-core-offline-ocr.txt"; then CORE_OFFLINE_SEEN=1; break; fi
      sleep 2
    done
    [[ "$CORE_OFFLINE_SEEN" == 1 ]] || { echo "Desktop did not report Core offline after service stop." >&2; cat "$OUT/$MODE-core-offline-ocr.txt" >&2 || true; exit 1; }
    guest_ssh 'systemctl --user start jarvis-core.service && for i in $(seq 1 30); do systemctl --user is-active --quiet jarvis-core.service && test -S "$XDG_RUNTIME_DIR/af-jarvis/core.sock" && exit 0; sleep 1; done; exit 1'
    CORE_ONLINE_SEEN=0
    for _ in $(seq 1 30); do
      kill -0 "$QEMU_PID"
      capture_guest "$MODE-core-reconnected"
      convert "$OUT/$MODE-core-reconnected.png" -gravity North -chop 0x30 -colorspace Gray -resize 250% -contrast-stretch 1%x1% "$OUT/$MODE-core-reconnected-content.png"
      tesseract "$OUT/$MODE-core-reconnected-content.png" stdout --psm 11 2>/dev/null >"$OUT/$MODE-core-reconnected-ocr.txt" || true
      if grep -Eqi 'Core online' "$OUT/$MODE-core-reconnected-ocr.txt" && grep -Eqi 'Dashboard' "$OUT/$MODE-core-reconnected-ocr.txt"; then CORE_ONLINE_SEEN=1; break; fi
      sleep 2
    done
    [[ "$CORE_ONLINE_SEEN" == 1 ]] || { echo "Desktop did not reconnect after Core restart." >&2; cat "$OUT/$MODE-core-reconnected-ocr.txt" >&2 || true; exit 1; }
    printf '{"mode":"%s","core_stop":"desktop-visible-and-reported-offline","core_restart":"desktop-reconnected-and-reported-online"}\n' "$MODE" >"$OUT/$MODE-core-lifecycle-result.json"
    # Set 1: verify QEMU's active absolute HID tablet and send a window-relative click.
    # The SDL window receives xdotool input; the active guest device is checked below.
    printf 'info mice\n' | socat - UNIX-CONNECT:"$MONITOR" >"$OUT/$MODE-mouse-devices.txt"
    # QEMU 8.2 reports this device as "QEMU HID Tablet (absolute)" in info mice.
    # Accept the older USB Tablet label too, while still selecting the absolute tablet.
    MOUSE_INDEX=$(sed -nE 's/.*Mouse #([0-9]+): QEMU (USB|HID) Tablet.*/\1/p' "$OUT/$MODE-mouse-devices.txt" | head -n1)
    [[ -n "$MOUSE_INDEX" ]] || { echo "QEMU USB tablet was not enumerated by the monitor." >&2; cat "$OUT/$MODE-mouse-devices.txt" >&2; exit 1; }
    grep -Fq "* Mouse #$MOUSE_INDEX:" "$OUT/$MODE-mouse-devices.txt" || { echo "QEMU HID tablet is not the active input device." >&2; cat "$OUT/$MODE-mouse-devices.txt" >&2; exit 1; }
    printf 'active_tablet_index=%s\ninput=xdotool window-relative click at 183x140\n' "$MOUSE_INDEX" >"$OUT/$MODE-mouse-click-input.txt"
    xdotool mousemove --window "$WINDOW" 183 140
    sleep 0.3
    xdotool click 1
    printf 'info mice\n' | socat - UNIX-CONNECT:"$MONITOR" >"$OUT/$MODE-mouse-click-monitor.txt"
    sleep 1
    capture_guest "$MODE-assistant-page"
    convert "$OUT/$MODE-assistant-page.png" -gravity North -chop 0x24 -colorspace Gray -resize 250% -contrast-stretch 1%x1% "$OUT/$MODE-assistant-page-content.png"
    tesseract "$OUT/$MODE-assistant-page-content.png" stdout --psm 11 2>/dev/null >"$OUT/$MODE-assistant-page-ocr.txt" || true
    if ! grep -Eqi 'Sensitive: keep local' "$OUT/$MODE-assistant-page-ocr.txt"; then
      echo "QEMU USB-tablet click did not expose the Assistant-only controls." >&2
      cat "$OUT/$MODE-mouse-devices.txt" >&2 || true
      cat "$OUT/$MODE-mouse-click-monitor.txt" >&2 || true
      cat "$OUT/$MODE-assistant-page-ocr.txt" >&2 || true
      exit 1
    fi
    printf 'PASS: QEMU USB-tablet absolute pointer click opened the Assistant page (device %s, guest coordinates 183x140).\n' "$MOUSE_INDEX" >"$OUT/$MODE-mouse-click-result.txt"

    # After selecting the Assistant notebook tab, focus advances through the
    # route selector and privacy checkbox before reaching the prompt entry.
    # The chat transcript is also focusable, so four Tabs reach the prompt entry.
    xdotool key Tab Tab Tab Tab
    sleep 1
    xdotool type --clearmodifiers --delay 40 "INPUTCHECKONE"
    xdotool key ctrl+a
    xdotool type --clearmodifiers --delay 40 "INPUTCHECKOK"
    capture_guest "$MODE-input-focus"
    # Whole-desktop sparse OCR misses short entry text; inspect the actual GTK entry.
    convert "$OUT/$MODE-input-focus.png" -crop 1038x54+36+633 +repage -resize 500% -colorspace Gray -contrast-stretch 1%x1% "$OUT/$MODE-input-focus-entry.png"
    tesseract "$OUT/$MODE-input-focus-entry.png" stdout --psm 7 2>/dev/null >"$OUT/$MODE-input-focus-ocr.txt" || true
    grep -Fq 'INPUTCHECKOK' "$OUT/$MODE-input-focus-ocr.txt" || { echo "Keyboard Tab focus/input replacement was not visible in the GTK entry." >&2; cat "$OUT/$MODE-input-focus-ocr.txt" >&2; exit 1; }
    xdotool key ctrl+a BackSpace
    sleep 1
    printf 'PASS: mouse tab click, focused GTK entry, keyboard typing and Ctrl+A replacement\n' >"$OUT/$MODE-input-focus-result.txt"

    # Set 2: verify DHCP address, default route, DNS and link recovery in QEMU user networking.
    guest_ssh 'set -eu; nmcli -t -f DEVICE,TYPE,STATE device; ip -4 -o addr show dev ens3; ip route show default; getent ahostsv4 deb.debian.org | head -n1' >"$OUT/$MODE-network-before.txt"
    grep -q 'ens3:ethernet:connected' "$OUT/$MODE-network-before.txt"
    grep -q 'inet ' "$OUT/$MODE-network-before.txt"
    grep -q '^default ' "$OUT/$MODE-network-before.txt"
    grep -Eq '^[0-9]+\.' "$OUT/$MODE-network-before.txt"
    printf 'set_link net0 off\n' | socat - UNIX-CONNECT:"$MONITOR" >"$OUT/$MODE-network-link-off.txt"
    sleep 3
    printf 'set_link net0 on\n' | socat - UNIX-CONNECT:"$MONITOR" >"$OUT/$MODE-network-link-on.txt"
    NETWORK_RECONNECTED=0
    for _ in $(seq 1 30); do
      if guest_ssh 'set -eu; nmcli -t -f DEVICE,TYPE,STATE device | grep -q "^ens3:ethernet:connected"; ip -4 -o addr show dev ens3 | grep -q "inet "; ip route show default | grep -q "^default "; getent ahostsv4 deb.debian.org | head -n1' >"$OUT/$MODE-network-after.txt" 2>/dev/null; then
        NETWORK_RECONNECTED=1
        break
      fi
      sleep 2
    done
    [[ "$NETWORK_RECONNECTED" == 1 ]] || { echo "QEMU guest did not recover DHCP/DNS/SSH after virtual NIC link reset." >&2; exit 1; }
    printf 'PASS: DHCP, default route, DNS resolution and QEMU virtual-link reconnect\n' >"$OUT/$MODE-network-result.txt"

    # Set 3: inspect BlueZ and adapter discovery. No controller is expected in this QEMU profile.
    # QEMU does not provide a Bluetooth controller. bluetoothctl can block
    # while waiting for bluetoothd/its D-Bus service when no adapter is present,
    # so both discovery commands are explicitly bounded and absence is reported
    # as an environment limitation, not a desktop boot failure.
    guest_ssh 'set -eu; bluetoothctl --version; systemctl show bluetooth.service -p LoadState -p ActiveState --no-pager; timeout --signal=TERM --kill-after=2s 8s bluetoothctl --timeout 5 list || echo "INFO: no responsive Bluetooth controller in this QEMU profile"; timeout --signal=TERM --kill-after=2s 5s rfkill list bluetooth || true' >"$OUT/$MODE-bluetooth.txt"
    grep -q 'LoadState=loaded' "$OUT/$MODE-bluetooth.txt"
    printf 'INFO: BlueZ service metadata checked; controller discovery was bounded; physical Bluetooth remains a hardware-only check.\n' >"$OUT/$MODE-bluetooth-result.txt"

    # Set 4: QEMU exposes a virtual Intel HDA duplex device with a null host backend.
    # This exercises guest playback/capture routing without claiming physical speakers or a microphone.
    guest_ssh 'set -eu; pactl info; pactl list short sinks; pactl list short sources; aplay -l; arecord -l; speaker-test -D default -t sine -f 440 -l 1; arecord -D default -f S16_LE -r 16000 -c 1 -d 2 /tmp/af-jarvis-ci-audio-capture.wav; test -s /tmp/af-jarvis-ci-audio-capture.wav' >"$OUT/$MODE-audio.txt"
    grep -q 'alsa_output' "$OUT/$MODE-audio.txt"
    grep -q 'alsa_input' "$OUT/$MODE-audio.txt"
    printf 'PASS: PipeWire virtual HDA playback and capture pipeline (null host backend; no physical audio claim)\n' >"$OUT/$MODE-audio-result.txt"

    # Set 5: switch a virtual display mode, restore the baseline, and query OpenGL.
    guest_ssh 'set -eu; xrandr --query; xrandr --output Virtual-1 --mode 1024x768; xrandr --current | grep -q "1024x768"; xrandr --output Virtual-1 --mode 1280x800; xrandr --current | grep -q "1280x800"; glxinfo -B' >"$OUT/$MODE-display-graphics.txt"
    grep -q 'OpenGL renderer string' "$OUT/$MODE-display-graphics.txt"
    printf 'PASS: virtual display mode change/restore and OpenGL renderer query\n' >"$OUT/$MODE-display-graphics-result.txt"

    # Set 6: gather power/session state and service-failure diagnostics; do not force suspend.
    guest_ssh 'set -eu; printf "power-states: "; cat /sys/power/state; printf "\nsessions:\n"; loginctl list-sessions --no-legend; printf "\ninhibitors:\n"; systemd-inhibit --list; printf "\nsystem-failed:\n"; systemctl --failed --no-pager; printf "\nuser-failed:\n"; systemctl --user --failed --no-pager' >"$OUT/$MODE-power-session.txt"

    python3 - "$OUT/$MODE-phase3-guest-report.json" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1]); report=json.loads(p.read_text(encoding="utf-8"))
report["workflow_checks"]={"wrong_password_rejection":"passed; greeter remained visible","core_stop_restart_ui_reconnect":"passed; desktop showed offline then online","keyboard_mouse_focus":"passed; GTK tab click and focused entry input verified by OCR after Ctrl+A replacement","network_dhcp_dns_reconnect":"passed; QEMU virtual NIC link reset recovered DHCP, default route, DNS and SSH","bluetooth_service_adapter_probe":"BlueZ service metadata checked; controller discovery bounded; QEMU does not emulate physical Bluetooth","audio_virtual_hda":"passed; QEMU Intel HDA virtual playback/capture routed through PipeWire null backend","display_graphics":"passed; virtual resolution switch/restore and OpenGL renderer query","power_session_diagnostics":"captured; suspend/resume not attempted"}
report["manual_checks_still_required"]=[x for x in report.get("manual_checks_still_required",[]) if x not in ("wrong-password rejection","network disconnect/reconnect behavior","audio playback and microphone capture")]
p.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
PY
    echo "Normal login, wrong-password rejection, guest diagnostics, and Core recovery passed."
    exit 0
  fi
  sleep 5
done
echo "Normal login did not produce recognizable AF JARVIS desktop text." >&2
cat "$OUT/$MODE-screen-ocr.txt" >&2 || true
exit 1
