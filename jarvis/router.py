import re
import time

SECRET = re.compile(r"(?i)(password\s*[:=]|api[_ -]?key\s*[:=]|bearer\s+\S+|"
                    r"-----BEGIN .*PRIVATE KEY|sk-[a-zA-Z0-9]{12,}|token\s*[:=])")
HARD = re.compile(r"(?i)(complex|architecture|deep research|advanced mathematics|"
                  r"prove the|analy[sz]e.{0,20}code|difficult|research.{0,20}today)")


class Router:
    def __init__(self, config):
        self.config = config
        self.cooldown = {}

    def failed(self, ident):
        self.cooldown[ident] = time.monotonic() + 60

    def candidates(self, prompt, sensitive=False, consent=None, requested="auto"):
        data = self.config.data
        nodes = [p for p in data.get("nodes", []) if p.get("enabled")]
        primary = [p for p in nodes if p["kind"] == "local"]
        advanced = [p for p in nodes if p["kind"] == "advanced_local"]
        clouds = [p for p in data.get("cloud", []) if p.get("enabled")]
        complex_task = bool(HARD.search(prompt)) or len(prompt) > 1000
        private = sensitive or bool(SECRET.search(prompt))
        local = advanced + primary if complex_task or requested == "advanced_local" else primary + advanced
        if requested not in {"auto", "local", "advanced_local", "cloud"}:
            raise ValueError("Unknown route")
        cloud_allowed = (bool(clouds) and data["cloud_enabled"] and data["mode"] != "local_only" and not private
                         and consent is not False and requested not in {"local", "advanced_local"})
        wants_cloud = requested == "cloud" or complex_task or data["mode"] == "cloud_preferred"
        needs_consent = cloud_allowed and wants_cloud and data["mode"] == "ask_before_cloud" and consent is not True
        if needs_consent:
            return [], True
        if requested == "cloud" and not cloud_allowed:
            raise ValueError("Cloud blocked by privacy, mode or configuration; select local")
        preferred = clouds + local if cloud_allowed and wants_cloud else local
        # Routine requests never escalate automatically when a node goes offline.
        return [p for p in preferred if self.cooldown.get(p["id"], 0) <= time.monotonic()], False
