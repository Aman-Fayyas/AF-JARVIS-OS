#!/bin/bash
# One-command supported-host build; never writes a USB or alters host partitions.
set -euo pipefail
export PATH="/usr/local/sbin:/usr/sbin:/sbin:$PATH"
jarvis_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [[ ${1:-} == --check ]]; then
    exec python3 "$jarvis_root/scripts/build-preflight.py" --mount
fi
if [[ $# -gt 1 ]]; then
    echo 'Usage: bash scripts/build.sh [new-build-directory] | --check' >&2
    exit 2
fi
python3 "$jarvis_root/scripts/build-preflight.py"
if [[ $EUID -ne 0 ]]; then
    exec sudo bash "$jarvis_root/scripts/build.sh" "$@"
fi
python3 "$jarvis_root/scripts/build-preflight.py" --mount
jarvis_work=${1:-"$jarvis_root/build/live-$(date -u +%Y%m%dT%H%M%SZ)"}
umask 077
jarvis_hash=$(mktemp /tmp/af-jarvis-login.XXXXXXXX)
trap 'python3 -c "import os,sys; os.unlink(sys.argv[1])" "$jarvis_hash"' EXIT
echo 'Choose the password for the live user jarvis. No default password is bundled.'
openssl passwd -6 > "$jarvis_hash"
JARVIS_LIVE_PASSWORD_HASH_FILE="$jarvis_hash" bash "$jarvis_root/scripts/build-iso.sh" --build "$jarvis_work"
