"""Run on a real X server or under Xvfb; uses a loopback fixture, not actual AI."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import time
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, Gio
from jarvis.config import Config
from jarvis.desktop import Desktop
from jarvis.ipc import call, events
from tests.fake_node import Node


def until(predicate, seconds=4):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError('GTK condition timed out')


def resource(pid):
    values = {}
    proc = '/proc/self' if pid == os.getpid() else f'/proc/{pid}'
    for line in Path(proc + '/smaps_rollup').read_text().splitlines():
        if line.startswith(('Rss:', 'Pss:')):
            key, count, _ = line.split()
            values[key.rstrip(':').lower() + '_mib'] = round(int(count) / 1024, 2)
    return values


def main():
    loopback = "--loopback-fixture" in sys.argv
    root = Path(__file__).resolve().parents[1]
    node = Node()
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        for field, child in [('XDG_RUNTIME_DIR', 'runtime'), ('XDG_CONFIG_HOME', 'config'), ('XDG_DATA_HOME', 'data')]:
            path = directory / child
            path.mkdir(mode=0o700)
            os.environ[field] = str(path)
        config = Config()
        config.update_profile('tablet', {'enabled': True, 'url': node.url}, node.key)
        command = [sys.executable, '-m', 'tests.loopback_fixture', str(directory / 'port')] if loopback else [sys.executable, '-m', 'jarvis.server', '--allow-root-for-tests']
        core = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        desktop = None
        try:
            deadline = time.monotonic() + 3
            ready_path = directory / 'port' if loopback else directory / 'runtime/af-jarvis/core.sock'
            while not ready_path.exists():
                if core.poll() is not None:
                    raise AssertionError(core.communicate())
                if time.monotonic() > deadline:
                    raise AssertionError('Core socket startup timed out')
                time.sleep(0.02)
            if loopback:
                from tests.loopback_fixture import test_events
                import jarvis.ipc as ipc
                port = int(ready_path.read_text())
                ipc.events = lambda request: test_events(port, request)
            assert call({'method': 'status'})['type'] == 'result'
            if not loopback:
                assert ready_path.stat().st_mode & 0o777 == 0o600
            desktop = Desktop()
            until(lambda: bool(desktop.config))
            desktop.send(prompt='What time is it?')
            until(lambda: not desktop.running)
            assert 'It is ' in desktop.buffer.get_text(desktop.buffer.get_start_iter(), desktop.buffer.get_end_iter(), True)
            desktop.send(prompt='Explain RAM.')
            until(lambda: not desktop.running)
            assert desktop.last_answer == 'Hello Aman — local stream.'
            assert len(node.requests) == 1
            assert desktop.conversation
            desktop.refresh_history()
            until(lambda: bool(desktop.history_list.get_children()))
            desktop.load_history(desktop.history_list, desktop.history_list.get_children()[0])
            until(lambda: desktop.last_answer == 'Hello Aman — local stream.')
            desktop.fact_entry.set_text('Aman builds Project ReLife.')
            desktop.remember()
            until(lambda: bool(desktop.fact_list.get_children()))
            assert desktop.engine.get_text() == 'LOCAL • smollm2-360m'
            desktop.notebook.set_current_page(1)
            # Let the frame render, then capture the native window.
            captured = time.monotonic()
            until(lambda: time.monotonic() - captured > 0.25)
            window = desktop.get_window()
            width, height = window.get_width(), window.get_height()
            image = Gdk.pixbuf_get_from_window(window, 0, 0, width, height)
            image.savev(str(root / 'docs/desktop-tested.png'), 'png', [], [])
            results = {'environment': 'Ubuntu 24.04 container, GTK3 on Xvfb; test fixture AI',
                       'checks': ['framed IPC status', 'native GTK launch', 'deterministic command', 'true SSE token display', 'local history', 'memory save/view', 'route label', 'Core failure leaves desktop responsive'],
                       'transport': 'TEST ONLY loopback fixture; Unix bind prohibited here' if loopback else 'production Unix socket',
                       'unix_permissions': 'UNTESTED here' if loopback else 'TESTED 0600',
                       'core': call({'method': 'status'})['value']['core_memory'], 'desktop_with_test_harness': resource(os.getpid()),
                       'whole_os_idle_ram': 'UNMEASURED: no booted AF JARVIS OS VM/hardware'}
            core.terminate()
            core.wait(timeout=4)
            desktop.status()
            until(lambda: 'offline' in desktop.connection.get_text())
            assert desktop.get_visible()
            # Exercise Gio application launching with Core stopped. This is a
            # harmless utility fixture, not a claim about Firefox/PCManFM boots.
            launcher = directory / 'launch-utility'
            marker = directory / 'utility-launched'
            launcher.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\n')
            launcher.chmod(0o700)
            utility = directory / 'utility.desktop'
            utility.write_text('[Desktop Entry]\nType=Application\nName=JARVIS test utility\nExec=' + str(launcher) + '\n')
            desktop.launch_app(Gio.DesktopAppInfo.new_from_filename(str(utility)))
            until(marker.exists)
            results['checks'].append('actual Gio test-utility launch with Core stopped')
            (root / 'docs/desktop-smoke-results.json').write_text(json.dumps(results, indent=2) + '\n')
            print(json.dumps(results, indent=2))
        finally:
            if desktop:
                desktop.closed = True
                desktop.destroy()
            if core.poll() is None:
                core.terminate()
                core.wait(timeout=4)
            node.close()


if __name__ == '__main__':
    main()
