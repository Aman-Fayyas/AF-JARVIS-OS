from pathlib import Path
from datetime import datetime
import os
import re
import shutil
import subprocess
import time


def run(argv):
    """Only callers with fixed allowlisted argv use this function; never a shell."""
    return subprocess.run(argv, check=True, timeout=15, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True).stdout.strip()


def process_memory():
    values = {}
    try:
        for line in Path('/proc/self/smaps_rollup').read_text().splitlines():
            if line.startswith(('Rss:', 'Pss:')):
                key, count, _ = line.split()
                values[key.rstrip(':').lower() + '_mib'] = round(int(count) / 1024, 2)
    except OSError:
        values['unavailable'] = True
    return values


class Monitor:
    def __init__(self):
        self.previous_cpu = None

    def snapshot(self):
        values = {}
        try:
            for line in Path("/proc/meminfo").read_text().splitlines():
                key, value = line.split(":", 1)
                values[key] = int(value.split()[0])
            used = (values["MemTotal"] - values["MemAvailable"]) / 1024
            ram = {"used_mb": round(used, 1), "total_mb": round(values["MemTotal"] / 1024, 1)}
        except (OSError, KeyError, ValueError):
            ram = None
        cpu_percent = None
        try:
            fields = [int(x) for x in Path("/proc/stat").read_text().splitlines()[0].split()[1:9]]
            total, idle = sum(fields), fields[3] + fields[4]
            if self.previous_cpu:
                dt = total - self.previous_cpu[0]
                if dt > 0:
                    cpu_percent = round(100 * (1 - (idle - self.previous_cpu[1]) / dt), 1)
            self.previous_cpu = (total, idle)
        except (OSError, ValueError, IndexError):
            pass
        disk = shutil.disk_usage(Path.home())
        battery = None
        power = Path("/sys/class/power_supply")
        if power.exists():
            for device in power.glob("BAT*"):
                try:
                    battery = {"percent": int((device / "capacity").read_text()),
                               "state": (device / "status").read_text().strip()}
                    break
                except (OSError, ValueError):
                    pass
        connected = []
        for device in Path("/sys/class/net").glob("*"):
            try:
                if device.name != "lo" and (device / "operstate").read_text().strip() == "up":
                    connected.append(device.name)
            except OSError:
                pass
        return {"time": datetime.now().isoformat(timespec="seconds"), "ram": ram,
                "cpu_percent": cpu_percent, "disk": {"used_gb": round(disk.used / 2**30, 1),
                "total_gb": round(disk.total / 2**30, 1)}, "battery": battery,
                "network": connected, "internet": "Not checked (no background internet probes)"}


def intent(text):
    clean = text.strip().lower().rstrip(".!?")
    patterns = {
        "time": {"time", "what time is it", "what's the time"},
        "ram": {"show ram usage", "ram usage", "show memory usage"},
        "cpu": {"show cpu usage", "cpu usage"},
        "battery": {"battery", "battery percentage", "what's my battery percentage"},
        "processes": {"what's using the most memory", "show memory processes"},
        "restart": {"restart", "restart the computer"},
        "shutdown": {"shutdown", "shut down", "shutdown the computer"},
        "volume_down": {"turn volume down", "volume down"},
        "volume_up": {"turn volume up", "volume up"},
    }
    for key, matches in patterns.items():
        if clean in matches:
            return {"kind": key}
    match = re.fullmatch(r"(?:open|launch) (firefox|browser|files|terminal|godot|downloads|home)", clean)
    if match:
        return {"kind": "open", "target": match[1]}
    match = re.fullmatch(r"create a folder called (.{1,80})", text.strip(), re.I)
    if match:
        name = match[1].strip()
        if re.fullmatch(r"[\w -]{1,80}", name) and name not in {".", ".."}:
            return {"kind": "mkdir", "name": name}
        raise ValueError("Use a simple folder name with letters, numbers, spaces, hyphens or underscores")
    return None


def perform(action, monitor):
    kind = action["kind"]
    if kind == "time":
        return datetime.now().strftime("It is %H:%M on %A, %d %B %Y.")
    if kind in {"ram", "cpu", "battery"}:
        state = monitor.snapshot()
        if kind == "ram":
            value = state["ram"]
            return f"RAM used: {value['used_mb']} / {value['total_mb']} MiB." if value else "RAM data unavailable."
        if kind == "cpu":
            value = state["cpu_percent"]
            return f"CPU: {value}% since the previous sample." if value is not None else "CPU baseline sampled; ask again."
        value = state["battery"]
        return f"Battery: {value['percent']}% ({value['state']})." if value else "No battery information available."
    if kind == "processes":
        return "\n".join(run(["ps", "-eo", "comm,rss", "--sort=-rss"]).splitlines()[:12])
    if kind == "open":
        target = action["target"]
        if target in {"home", "downloads"}:
            path = Path.home() if target == "home" else Path.home() / "Downloads"
            if not path.exists():
                return "That folder does not exist."
            argv = ["pcmanfm", str(path)]
        else:
            argv = {"firefox": ["firefox-esr"], "browser": ["firefox-esr"],
                    "files": ["pcmanfm"], "terminal": ["x-terminal-emulator"],
                    "godot": ["godot"]}[target]
        if not shutil.which(argv[0]):
            return f"Application {argv[0]} is not installed."
        subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        return "Launched " + target + "."
    if kind == "mkdir":
        root = Path.home().resolve()
        path = root / action["name"]
        if path.exists() or path.is_symlink():
            raise ValueError("That name already exists")
        path.mkdir(mode=0o700)
        return f"Created {path}."
    if kind in {"restart", "shutdown"}:
        run(["systemctl", "reboot" if kind == "restart" else "poweroff"])
        return "Requested " + kind + "."
    if kind in {"volume_down", "volume_up"}:
        run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-5%" if kind == "volume_down" else "+5%"])
        return "Adjusted volume by 5%."
    raise ValueError("Unknown action")
