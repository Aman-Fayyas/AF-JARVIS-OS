from pathlib import Path
import json
import os
import threading
import time
import uuid
from .config import Config, private_dir
from .memory import Memory, bounded_context
from .providers import OpenAIProvider, ProviderError, Cancellation
from .router import Router
from .system import Monitor, intent, perform, process_memory
from .search import web_search

SYSTEM = ("You are JARVIS, a helpful assistant in AF JARVIS OS. Be clear and concise. "
          "You cannot execute system commands. Never claim you performed actions. "
          "Say when you do not know. No live internet data is available in this chat.")


class Core:
    def __init__(self, config_dir=None, data_dir=None):
        self.config = Config(config_dir)
        self.memory = Memory(data_dir or Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / "af-jarvis")
        self.router = Router(self.config)
        self.monitor = Monitor()
        self.active = {}
        self.pending = {}
        self.lock = threading.RLock()
        self.chat_lock = threading.Lock() # Tablet has one slot; no parallel generations.
        self.memory.prune(self.config.data["retention_days"])

    def event(self, event_type, **payload):
        return {"type": event_type, **payload}

    def request(self, request):
        method = request.get("method")
        if method == "chat":
            yield from self.chat(request)
            return
        if method == "history_stream":
            for message in self.memory.iter_history(str(request["conversation"])):
                yield self.event("history_start", role=message["role"], route=message["route"])
                for start in range(0, len(message["content"]), 12000):
                    yield self.event("history_chunk", text=message["content"][start:start + 12000])
                yield self.event("history_end")
            yield self.event("result", value=True)
            return
        if method in {"probe", "search"}:
            # Never hold the state lock during network IO; status/cancel stay fast.
            with self.lock:
                if method == "probe":
                    profile = next((dict(p) for p in self.config.data.get("nodes", []) + self.config.data.get("cloud", []) if p["id"] == request["id"]), None)
                    if not profile:
                        raise ValueError("Unknown node")
                    provider = OpenAIProvider(self.config, profile)
                else:
                    settings = dict(self.config.data.get("search", {}))
            if method == "probe":
                value = {"id": profile["id"], "models": provider.models(), "online": True}
            else:
                value = web_search(settings, str(request["query"]))
            yield self.event("result", value=value)
            return
        with self.lock:
            if method == "status":
                value = {"system": self.monitor.snapshot(), "config": self.config.public(), "busy": bool(self.active), "core_memory": process_memory()}
            elif method == "new":
                value = self.memory.new()
            elif method == "history":
                value = self.memory.history(str(request["conversation"]))
            elif method == "conversations":
                value = self.memory.conversations()
            elif method == "facts":
                value = self.memory.facts(str(request.get("query", ""))[:200])
            elif method == "remember":
                if not self.config.data["memory_enabled"]:
                    raise ValueError("Long-term memory is disabled")
                value = self.memory.remember(str(request["content"]))
            elif method in {"delete_fact", "clear_memory", "delete_conversation"}:
                if self.active:
                    raise ValueError("Stop generation before deleting memory or history")
                action = {"kind": method, "id": request.get("id")}
                yield self.confirmation(action)
                return
            elif method == "preferences":
                if self.active:
                    raise ValueError("Stop generation before changing privacy or retention settings")
                self.config.preferences(request["changes"])
                self.memory.prune(self.config.data["retention_days"])
                value = self.config.public()
            elif method == "reload":
                if self.active:
                    raise ValueError("Stop the active generation before reloading")
                self.config.reload()
                self.router.cooldown.clear()
                value = self.config.public()
            elif method == "profile":
                if self.active:
                    raise ValueError("Stop generation before changing provider settings")
                self.config.update_profile(request["id"], request["changes"], request.get("key"))
                self.router.cooldown.clear()
                value = self.config.public()
            elif method == "voice_settings":
                self.config.update_voice(request.get("model", ""))
                value = self.config.public()
            elif method == "cancel":
                token = self.active.get(str(request.get("generation")))
                if token:
                    token.cancel()
                value = bool(token)
            elif method == "confirm":
                pending = self.pending.pop(str(request.get("nonce")), None)
                if not pending or pending[1] < time.monotonic():
                    raise ValueError("Confirmation expired or already used")
                action = pending[0]
                if action["kind"] in {"delete_fact", "delete_conversation", "clear_memory"} and self.active:
                    raise ValueError("Stop generation before deleting memory or history")
                if action["kind"] == "delete_fact":
                    self.memory.delete_fact(int(action["id"]))
                    value = "Memory deleted."
                elif action["kind"] == "delete_conversation":
                    self.memory.delete_conversation(str(action["id"]))
                    value = "Conversation deleted."
                elif action["kind"] == "clear_memory":
                    if self.active:
                        raise ValueError("Stop generation before clearing memory")
                    self.memory.clear()
                    value = "All memory and history cleared."
                else:
                    value = perform(action, self.monitor)
            else:
                raise ValueError("Unknown method")
        yield self.event("result", value=value)

    def confirmation(self, action):
        now = time.monotonic()
        self.pending = {k: v for k, v in self.pending.items() if v[1] > now}
        if len(self.pending) >= 32:
            raise ValueError("Too many pending confirmations")
        nonce = uuid.uuid4().hex
        self.pending[nonce] = (action, now + 60)
        return self.event("confirmation", action=action, nonce=nonce, expires_seconds=60)

    def chat(self, request):
        prompt = request.get("prompt", "")
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt.encode()) > 24000:
            raise ValueError("Message must contain 1–24000 bytes")
        if not self.chat_lock.acquire(blocking=False):
            raise ValueError("One generation is already running; stop it first")
        generation = uuid.uuid4().hex
        cancel = Cancellation()
        with self.lock:
            self.active[generation] = cancel
        try:
            yield self.event("generation", id=generation)
            action = intent(prompt)
            if action:
                if action["kind"] in {"mkdir", "restart", "shutdown"}:
                    with self.lock:
                        yield self.confirmation(action)
                    return
                yield self.event("route", kind="system", model="Deterministic")
                answer = perform(action, self.monitor)
                yield self.event("token", text=answer)
                yield self.event("done", cancelled=False, route="system", saved=False)
                return
            with self.lock:
                profiles, consent = self.router.candidates(prompt, bool(request.get("sensitive")),
                    request.get("cloud_consent"), request.get("route", "auto"))
            if consent:
                yield self.event("cloud_consent", message="Cloud would receive this question only. Use cloud for this request?")
                return
            if not profiles:
                raise ValueError("No allowed AI node is ready/configured. Open Settings to configure one. System commands still work.")
            conversation = request.get("conversation")
            if not conversation and self.config.data["history_enabled"]:
                conversation = self.memory.new()
                yield self.event("conversation", id=conversation)
            history = self.memory.history(conversation, byte_budget=32000) if self.config.data["history_enabled"] else []
            if request.get("regenerate") and len(history) >= 2 and history[-2]["content"] == prompt:
                history = history[:-2]
            for profile in profiles:
                if cancel.event.is_set():
                    break
                output = []
                try:
                    cloud = profile["kind"] == "cloud"
                    facts = self.memory.relevant(prompt) if self.config.data["memory_enabled"] and not cloud else []
                    messages = bounded_context(SYSTEM, [] if cloud else history, prompt, profile, facts)
                    provider = OpenAIProvider(self.config, profile)
                    yield self.event("route", kind=profile["kind"], model=profile["model"], node=profile["label"])
                    for token in provider.stream(messages, cancel):
                        if cancel.event.is_set():
                            break
                        output.append(token)
                        yield self.event("token", text=token)
                    saved = False
                    if not cancel.event.is_set() and output and self.config.data["history_enabled"]:
                        self.memory.save(conversation, prompt, "".join(output), profile["kind"])
                        saved = True
                    yield self.event("done", cancelled=cancel.event.is_set(), route=profile["kind"], saved=saved)
                    return
                except (ProviderError, ValueError, OSError) as error:
                    if cancel.event.is_set():
                        break
                    self.router.failed(profile["id"])
                    yield self.event("notice", message=f"{profile['label']}: {error}")
                    if output:
                        # Never concatenate an unrelated fallback onto a partial reply.
                        yield self.event("error", message="Response interrupted. Partial output was not saved. Regenerate to retry.")
                        return
            if cancel.event.is_set():
                yield self.event("done", cancelled=True, saved=False)
            else:
                raise ValueError("All allowed providers failed. System commands remain available; retry after 60 seconds or reconnect.")
        finally:
            with self.lock:
                self.active.pop(generation, None)
            self.chat_lock.release()
