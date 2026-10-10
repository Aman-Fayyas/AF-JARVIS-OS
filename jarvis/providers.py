import ipaddress
import json
import ssl
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

CLOUD_HOSTS = {"api.groq.com", "generativelanguage.googleapis.com", "openrouter.ai"}
LOCAL_NETS = [ipaddress.ip_network(n) for n in
              ("127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "::1/128", "fc00::/7")]


class ProviderError(Exception):
    pass


def validate_url(url, kind, insecure=False):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname or
            parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("Endpoint must be an HTTP(S) base URL without credentials or query")
    port = parsed.port  # validates port syntax/range
    if kind == "cloud":
        if parsed.scheme != "https" or parsed.hostname not in CLOUD_HOSTS or port not in {None, 443}:
            raise ValueError("Cloud endpoint must use HTTPS on an approved provider host")
    else:
        host = "127.0.0.1" if parsed.hostname == "localhost" else parsed.hostname
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            raise ValueError("Local endpoints require a manually trusted LAN IP or localhost") from None
        if not any(address in net for net in LOCAL_NETS):
            raise ValueError("Local endpoint must be loopback or a private LAN address")
        if parsed.scheme == "http" and not address.is_loopback and not insecure:
            raise ValueError("LAN HTTP requires explicit allow_insecure_lan=true; prefer TLS or SSH")
    return url.rstrip("/")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProviderError("Endpoint redirect refused to protect credentials")


def opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
                                      urllib.request.HTTPSHandler(context=ssl.create_default_context()))


class Cancellation:
    def __init__(self):
        self.event = threading.Event()
        self.response = None
        self.lock = threading.Lock()

    def cancel(self):
        self.event.set()
        with self.lock:
            if self.response:
                # close() can wait for a buffered reader lock. Shutdown wakes it
                # without blocking the IPC cancel request; the reader owns close.
                try:
                    self.response.fp.raw._sock.shutdown(socket.SHUT_RDWR)
                except (AttributeError, OSError):
                    pass

    def attach(self, response):
        with self.lock:
            if self.event.is_set():
                response.close()
            else:
                self.response = response

    def detach(self):
        with self.lock:
            self.response = None


class OpenAIProvider:
    def __init__(self, config, profile):
        self.profile = profile
        self.base = validate_url(profile["url"], profile["kind"], profile.get("allow_insecure_lan", False))
        self.key = config.key(profile)
        self.timeout = config.data["timeout_seconds"]
        self.limit = config.data["max_response_chars"]
        self.http = opener()

    def request(self, suffix, payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(self.base + suffix, data=data, headers={
            "Authorization": "Bearer " + self.key, "Content-Type": "application/json",
            "Accept": "text/event-stream" if payload else "application/json",
            "User-Agent": "AF-JARVIS-OS/0.1"})
        try:
            return self.http.open(request, timeout=self.timeout)
        except urllib.error.HTTPError as error:
            # Do not relay upstream bodies: they can echo secrets or prompts.
            raise ProviderError(f"Provider HTTP {error.code}; check model, key or quota") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise ProviderError("Provider unreachable or timed out") from None

    def models(self):
        with self.request("/models") as response:
            raw = response.read(262145)
            if len(raw) > 262144:
                raise ProviderError("Model list too large")
            try:
                entries = json.loads(raw)["data"]
                if not isinstance(entries, list):
                    raise ValueError("Invalid models")
                ids = [x["id"] for x in entries[:100]]
                if any(not isinstance(x, str) or len(x) > 256 for x in ids):
                    raise ValueError("Invalid model ID")
                return ids
            except (ValueError, KeyError, TypeError):
                raise ProviderError("Malformed provider model list") from None

    def stream(self, messages, cancel):
        payload = {"model": self.profile["model"], "messages": messages, "stream": True,
                   "max_tokens": self.profile["max_tokens"], "temperature": 0.6}
        if not payload["model"]:
            raise ProviderError("Choose a model ID in configuration first")
        if cancel.event.is_set():
            return
        response = self.request("/chat/completions", payload)
        cancel.attach(response)
        started = time.monotonic()
        total = 0
        lines = []
        finished = False
        try:
            if "text/event-stream" not in response.headers.get("Content-Type", ""):
                raise ProviderError("Provider did not return an SSE stream")
            while not cancel.event.is_set():
                if time.monotonic() - started > 180:
                    raise ProviderError("Generation exceeded the 180-second deadline")
                line = response.readline(65537)
                if len(line) > 65536:
                    raise ProviderError("Oversized SSE event")
                if not line:
                    break
                line = line.decode("utf-8").rstrip("\r\n")
                if line.startswith("data:"):
                    lines.append(line[5:].lstrip())
                    if sum(map(len, lines)) > 65536:
                        raise ProviderError("Oversized SSE event")
                elif not line and lines:
                    data = "\n".join(lines)
                    lines.clear()
                    if data == "[DONE]":
                        finished = True
                        break
                    obj = json.loads(data)
                    if not isinstance(obj, dict) or not isinstance(obj.get("choices", []), list):
                        raise ProviderError("Malformed provider choices")
                    if "error" in obj:
                        raise ProviderError("Provider returned a stream error")
                    for choice in obj.get("choices", []):
                        if not isinstance(choice, dict) or not isinstance(choice.get("delta", {}), dict):
                            raise ProviderError("Malformed provider delta")
                        token = choice.get("delta", {}).get("content") or ""
                        if not isinstance(token, str):
                            raise ProviderError("Unsupported stream content")
                        if choice.get("finish_reason"):
                            finished = True
                        total += len(token)
                        if total > self.limit:
                            raise ProviderError("Response exceeded configured size limit")
                        if token:
                            yield token
            if not finished and not cancel.event.is_set():
                raise ProviderError("Stream disconnected before completion")
        except (ValueError, OSError, TimeoutError, AttributeError) as error:
            if not cancel.event.is_set():
                raise ProviderError("Malformed, interrupted or timed-out provider stream") from error
        finally:
            cancel.detach()
            response.close()
