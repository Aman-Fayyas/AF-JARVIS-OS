from pathlib import Path
import json
import os
import stat
import tempfile
import tomllib

MODES = {"local_only", "local_first", "ask_before_cloud", "cloud_preferred"}


def private_dir(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or path.stat().st_uid != os.getuid():
        raise ValueError("Private directory must be owned by the current user")
    path.chmod(0o700)
    return path


def atomic_write(path, data):
    path = Path(path)
    private_dir(path.parent)
    fd, temp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def secure_read(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "r", encoding="utf-8") as stream:
        info = os.fstat(stream.fileno())
        if (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077
                or not stat.S_ISREG(info.st_mode) or info.st_size > 65536):
            raise ValueError("Configuration/key must be a private regular file (chmod 600)")
        return stream.read()


class Config:
    def __init__(self, directory=None):
        self.directory = private_dir(directory or Path(os.environ.get(
            "XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "af-jarvis")
        self.path = self.directory / "config.toml"
        if not self.path.exists():
            source = Path(__file__).resolve().parents[1] / "config/default.toml"
            atomic_write(self.path, source.read_text())
        self.reload()

    def reload(self):
        previous = getattr(self, "data", None)
        try:
            self.data = tomllib.loads(secure_read(self.path))
            overrides = self.directory / "preferences.json"
            if overrides.exists():
                self.data.update(json.loads(secure_read(overrides)))
            self.validate()
        except Exception:
            self.data = previous
            raise

    def validate(self):
        from .providers import validate_url
        if self.data.get("mode") not in MODES:
            raise ValueError("Invalid AI mode")
        for field in ("memory_enabled", "history_enabled", "cloud_enabled"):
            if not isinstance(self.data.get(field), bool):
                raise ValueError(f"{field} must be true or false")
        for key, low, high in (("retention_days", 1, 3650),
                               ("timeout_seconds", 1, 120),
                               ("max_response_chars", 100, 96000)):
            value = self.data.get(key)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"Invalid {key}")
        seen = set()
        for group, kinds in (("nodes", {"local", "advanced_local"}), ("cloud", {"cloud"})):
            profiles = self.data.get(group, [])
            if not isinstance(profiles, list) or len(profiles) > 16:
                raise ValueError("Invalid provider list")
            for profile in profiles:
                if not isinstance(profile, dict):
                    raise ValueError("Provider must be a table")
                if profile.get("kind") not in kinds:
                    raise ValueError("Provider in wrong group")
        for profile in self.data.get("nodes", []) + self.data.get("cloud", []):
            for field, limit in (("id", 64), ("label", 128), ("model", 256), ("url", 2048), ("key_file", 256)):
                if not isinstance(profile.get(field), str) or len(profile[field]) > limit:
                    raise ValueError(f"Invalid provider {field}")
            if not profile["id"]:
                raise ValueError("Provider id is empty")
            for field in ("enabled", "allow_insecure_lan"):
                if type(profile.get(field, False)) is not bool:
                    raise ValueError(f"Provider {field} must be true or false")
            relative = Path(profile["key_file"])
            if relative.is_absolute() or ".." in relative.parts or not relative.parts:
                raise ValueError("Provider key file must stay under the config directory")
            if profile["id"] in seen:
                raise ValueError("Duplicate provider id")
            seen.add(profile["id"])
            if profile.get("kind") not in {"local", "advanced_local", "cloud"}:
                raise ValueError("Invalid provider kind")
            validate_url(profile["url"], profile["kind"], profile.get("allow_insecure_lan", False))
            for key, low, high in (("context_tokens", 512, 32768), ("max_tokens", 32, 4096)):
                if type(profile.get(key)) is not int or not low <= profile[key] <= high:
                    raise ValueError(f"Invalid provider {key}")
            if profile["context_tokens"] <= profile["max_tokens"] + 256:
                raise ValueError("Output reservation exceeds context window")

    def preferences(self, changes):
        allowed = {"mode", "memory_enabled", "history_enabled", "retention_days", "cloud_enabled"}
        if not set(changes) <= allowed:
            raise ValueError("Unsupported preference")
        old = self.data.copy()
        try:
            self.data.update(changes)
            self.validate()
        except Exception:
            self.data = old
            raise
        self.persist()

    def persist(self):
        keys = {"mode", "memory_enabled", "history_enabled", "retention_days", "cloud_enabled", "nodes", "cloud", "voice"}
        atomic_write(self.directory / "preferences.json", json.dumps(
            {key: self.data[key] for key in keys if key in self.data}, indent=2))

    def update_profile(self, ident, changes, key=None):
        import copy
        allowed = {"enabled", "url", "model", "allow_insecure_lan", "context_tokens", "max_tokens"}
        if not set(changes) <= allowed:
            raise ValueError("Unsupported provider setting")
        old = copy.deepcopy(self.data)
        profile = next((p for p in self.data.get("nodes", []) + self.data.get("cloud", []) if p["id"] == ident), None)
        if not profile:
            raise ValueError("Unknown provider")
        try:
            profile.update(changes)
            self.validate()
            if key:
                if len(key) > 4096 or any(c.isspace() for c in key):
                    raise ValueError("Invalid key")
                relative = Path(profile["key_file"])
                path = self.directory / relative
                if relative.is_absolute() or ".." in relative.parts or not path.resolve().is_relative_to(self.directory.resolve()):
                    raise ValueError("Invalid key file")
                atomic_write(path, key + "\n")
            self.persist()
        except Exception:
            self.data = old
            raise

    def update_voice(self, model):
        if not isinstance(model, str) or len(model) > 4096:
            raise ValueError("Invalid speech model path")
        self.data["voice"]["stt_model"] = model
        self.persist()

    def key(self, profile):
        relative = Path(profile.get("key_file", ""))
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError("Key must be a file under the config directory")
        path = self.directory / relative
        if not path.resolve().is_relative_to(self.directory.resolve()):
            raise ValueError("Key escapes configuration directory")
        key = secure_read(path).strip()
        if not key or len(key) > 4096 or any(c.isspace() for c in key):
            raise ValueError("Missing or invalid provider key")
        return key

    def public(self):
        return {**{k: self.data[k] for k in ("mode", "cloud_enabled", "memory_enabled",
                                            "history_enabled", "retention_days")},
                "voice": self.data.get("voice", {}),
                "profiles": [{k: p.get(k) for k in ("id", "label", "kind", "enabled", "model", "url", "allow_insecure_lan", "context_tokens", "max_tokens")}
                             for p in self.data.get("nodes", []) + self.data.get("cloud", [])],
                "config_path": str(self.path)}
