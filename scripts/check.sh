#!/bin/bash
set -euo pipefail
jarvis_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$jarvis_root"
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m compileall -q jarvis tests scripts
for jarvis_script in scripts/*.sh; do bash -n "$jarvis_script"; done
sh -n distro/auto-config
sh -n distro/0100-jarvis.hook.chroot
jarvis_scratch=$(mktemp -d)
trap 'python3 -c "import shutil,sys; shutil.rmtree(sys.argv[1])" "$jarvis_scratch"' EXIT
bash scripts/build-iso.sh --prepare "$jarvis_scratch/live"
