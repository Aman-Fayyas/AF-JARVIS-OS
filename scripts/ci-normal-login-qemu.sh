#!/usr/bin/env bash
# Disposable CI-only normal-login test. Never attaches a host disk.
set -euo pipefail
MODE="${1:?bios or uefi}"
ISO="${2:?ISO path}"
PASSWORD="${3:?temporary test password}"
OUT="${4:-.}"
mkdir -p "$OUT"
MONITOR="/tmp/af-jarvis-${MODE}-monitor.sock"
QEMU=(qemu-system-x86_64 -machine accel=tcg -cpu max -m 1536 -smp 2 -cdrom "$ISO" -boot d -display sdl -no-reboot -monitor "unix:$MONITOR,server,nowait")
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
xdotool windowfocus --sync "$WINDOW"
BOOT_MENU_SEEN=0
for _ in $(seq 1 45); do
  import -window "$WINDOW" "$OUT/$MODE-boot-menu.png"
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
  import -window "$WINDOW" "$OUT/$MODE-login-greeter.png"
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
import -window "$WINDOW" "$OUT/$MODE-wrong-password.png"
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
printf '{"mode":"%s","wrong_password":"rejected-greeter-remained-visible"}\\n' "$MODE" >"$OUT/$MODE-wrong-password-result.json"

# Now authenticate with the correct ephemeral password.
xdotool mousemove --window "$WINDOW" 690 360 click 1
xdotool type --clearmodifiers --delay 100 jarvis
xdotool key Return
sleep 2
xdotool type --clearmodifiers --delay 45 "$PASSWORD"
sleep 1
xdotool key Return
sleep 3
xdotool mousemove --window "$WINDOW" 752 446 click 1
for _ in $(seq 1 90); do
  kill -0 "$QEMU_PID"
  import -window "$WINDOW" "$OUT/$MODE-after-login.png"
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
    exit 0
  fi
  sleep 5
done
echo "Normal login did not produce recognizable AF JARVIS desktop text." >&2
cat "$OUT/$MODE-screen-ocr.txt" >&2 || true
exit 1
