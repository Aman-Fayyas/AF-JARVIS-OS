"""Run inside the booted OS after 60s idle; output actual system figures as JSON."""
from pathlib import Path
import json
import subprocess
import time
import os
values = {}
for line in Path('/proc/meminfo').read_text().splitlines():
    key, value = line.split(':', 1)
    values[key] = int(value.split()[0])
processes = []
unreadable = 0
for path in Path('/proc').iterdir():
    if not path.name.isdigit():
        continue
    try:
        name = (path / 'comm').read_text().strip()
        metrics = {}
        for line in (path / 'smaps_rollup').read_text().splitlines():
            if line.startswith(('Pss:', 'Rss:')):
                field, value, _ = line.split()
                metrics[field.rstrip(':').lower() + '_mib'] = round(int(value) / 1024, 2)
        processes.append({'pid': int(path.name), 'name': name, **metrics})
    except OSError:
        unreadable += 1
        continue
print(json.dumps({'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                  'memtotal_mib': values['MemTotal'] / 1024,
                  'memavailable_mib': values['MemAvailable'] / 1024,
                  'used_mib': (values['MemTotal'] - values['MemAvailable']) / 1024,
                  'swap_used_mib': (values['SwapTotal'] - values['SwapFree']) / 1024,
                  'af_jarvis_boot_marker': Path('/etc/issue').read_text().startswith('AF JARVIS OS'),
                  'measurement_uid': os.getuid(), 'unreadable_or_exited_processes': unreadable,
                  'pss_note': 'PSS apportions shared pages; process totals exclude kernel memory and do not equal whole-system used RAM.',
                  'processes_by_pss': sorted(processes, key=lambda p: p.get('pss_mib', 0), reverse=True),
                  'boot_time': subprocess.run(['systemd-analyze'], capture_output=True, text=True).stdout.strip()}, indent=2))
