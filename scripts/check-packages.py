"""Validate target package availability using the Debian builder's APT metadata."""
from pathlib import Path
import subprocess
import sys
missing = []
for line in Path(sys.argv[1]).read_text().splitlines():
    if not line or line.startswith('#'):
        continue
    result = subprocess.run(['apt-cache', 'show', line], capture_output=True, text=True)
    if result.returncode or 'Package: ' not in result.stdout:
        missing.append(line)
if missing:
    raise SystemExit('Missing target packages (run apt update on Debian 13): ' + ', '.join(missing))
print('Target packages are available in the Debian builder APT metadata.')
