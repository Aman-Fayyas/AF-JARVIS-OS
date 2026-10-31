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
xdotool windowactivate --sync "$WINDOW"
printf 'sendkey ret\\n' | socat - UNIX-CONNECT:"$MONITOR"
sleep 90
import -window "$WINDOW" "$OUT/$MODE-login-greeter.png"
# CI image hides the user list so the standard username/password prompt is deterministic.
xdotool type --clearmodifiers --delay 80 jarvis
xdotool key Return
sleep 3
xdotool type --clearmodifiers --delay 35 "$PASSWORD"
xdotool key Return
# Require visible desktop evidence, not merely a QEMU process that stayed alive.
for _ in $(seq 1 90); do
  kill -0 "$QEMU_PID"
  import -window "$WINDOW" "$OUT/$MODE-after-login.png"
  tesseract "$OUT/$MODE-after-login.png" stdout 2>/dev/null >"$OUT/$MODE-screen-ocr.txt" || true
  if grep -Eqi 'AF[[:space:]]+JARVIS|JARVIS|Dashboard' "$OUT/$MODE-screen-ocr.txt"; then
    printf '{"mode":"%s","login":"desktop-visible","qemu_pid":%s}\n' "$MODE" "$QEMU_PID" >"$OUT/$MODE-normal-login-result.json"
    exit 0
  fi
  sleep 5
done
echo "Normal login did not produce recognizable AF JARVIS desktop text." >&2
cat "$OUT/$MODE-screen-ocr.txt" >&2 || true
exit 1
