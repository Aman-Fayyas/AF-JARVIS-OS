"""60-second process-only GTK/Core measurement on Xvfb, not a boot benchmark.

No fake AI server or harness runs inside either measured process. Transport is
the same TEST ONLY loopback fixture used when this sandbox prohibits AF_UNIX.
"""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import time

def main():
    if '--ui-worker' in sys.argv:
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk, GLib
        from jarvis.desktop import Desktop
        from jarvis.system import process_memory
        from tests.loopback_fixture import test_events
        import jarvis.ipc as ipc
        port = int(Path(sys.argv[2]).read_text())
        ipc.events = lambda request: test_events(port, request)
        desktop = Desktop()
        def measure():
            assert desktop.config and not desktop.running
            Path(sys.argv[3]).write_text(json.dumps(process_memory()))
            desktop.closed = True
            desktop.destroy()
            Gtk.main_quit()
            return False
        GLib.timeout_add_seconds(60, measure)
        Gtk.main()
        return
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='jarvis-process-memory-') as temporary:
        directory = Path(temporary)
        env = dict(os.environ)
        for key, name in [('XDG_RUNTIME_DIR', 'runtime'), ('XDG_CONFIG_HOME', 'config'), ('XDG_DATA_HOME', 'data')]:
            child = directory / name
            child.mkdir(mode=0o700)
            env[key] = str(child)
        port_file, metrics = directory / 'port', directory / 'gtk-metrics'
        core = subprocess.Popen([sys.executable, '-m', 'tests.loopback_fixture', str(port_file)], env=env)
        ui = None
        try:
            deadline = time.monotonic() + 5
            while not port_file.exists():
                if core.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('Core fixture startup failed')
                time.sleep(.05)
            ui = subprocess.Popen([sys.executable, '-m', 'tests.runtime_memory', '--ui-worker', str(port_file), str(metrics)], env=env)
            deadline = time.monotonic() + 80
            while ui.poll() is None:
                if time.monotonic() > deadline:
                    raise RuntimeError('GTK measurement timed out')
                time.sleep(.1)
            if ui.returncode != 0 or not metrics.exists():
                raise RuntimeError('GTK measurement failed')
            from tests.loopback_fixture import test_events
            status = list(test_events(int(port_file.read_text()), {'method': 'status'}))[-1]
            result = {'date': '2026-10-10', 'environment': 'Ubuntu 24.04 container, native GTK3/Xvfb',
                      'idle_seconds': 60, 'ai_providers_enabled': False,
                      'transport': 'TEST ONLY loopback Core transport; production AF_UNIX unavailable',
                      'core_process': status['value']['core_memory'], 'gtk_process': json.loads(metrics.read_text()),
                      'whole_af_jarvis_os_idle_ram': 'UNMEASURED: Linux/Openbox/LightDM/audio/network services were not booted'}
            (root / 'docs/process-memory-results.json').write_text(json.dumps(result, indent=2) + '\n')
            print(json.dumps(result, indent=2))
        finally:
            for process in (ui, core):
                if process and process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)

if __name__ == '__main__':
    main()
