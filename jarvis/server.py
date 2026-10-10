import argparse
import fcntl
import json
import os
import signal
import socket
import socketserver
import threading
from .core import Core
from .ipc import MAX_FRAME, socket_path, verify_peer


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    slots = threading.BoundedSemaphore(8)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()

    def handle_error(self, request, client_address):
        # Never log request contents or keys.
        print("IPC client failed", flush=True)


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        generation = None
        iterator = None
        try:
            verify_peer(self.request)
            self.request.settimeout(15)
            line = self.rfile.readline(MAX_FRAME + 1)
            if len(line) > MAX_FRAME or not line.endswith(b"\n"):
                raise ValueError("Invalid or oversized IPC frame")
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("Request must be an object")
            self.request.settimeout(210)
            iterator = self.server.core.request(request)
            for event in iterator:
                if event["type"] == "generation":
                    generation = event["id"]
                frame = json.dumps(event, ensure_ascii=False).encode() + b"\n"
                if len(frame) > MAX_FRAME:
                    raise ValueError("Response exceeds IPC limit; narrow the query")
                self.wfile.write(frame)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass
        except Exception as error:
            # Known validation messages are safe; unexpected exception details are not.
            message = str(error) if isinstance(error, (ValueError, RuntimeError, FileNotFoundError)) else type(error).__name__
            try:
                self.wfile.write(json.dumps({"type": "error", "message": message}).encode() + b"\n")
                self.wfile.flush()
            except OSError:
                pass
        finally:
            if generation:
                with self.server.core.lock:
                    token = self.server.core.active.get(generation)
                if token:
                    token.cancel()
            if iterator is not None:
                iterator.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-dir")
    parser.add_argument("--data-dir")
    parser.add_argument("--allow-root-for-tests", action="store_true")
    args = parser.parse_args()
    if os.getuid() == 0 and not args.allow_root_for_tests:
        parser.error("JARVIS Core must run as a non-root user")
    os.umask(0o077)
    path = socket_path()
    with open(path.parent / "core.lock", "a") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error("Core is already running")
        if path.exists():
            path.unlink()
        core = Core(args.config_dir, args.data_dir)
        with Server(str(path), Handler) as server:
            path.chmod(0o600)
            server.core = core
            def stop(signum, frame):
                threading.Thread(target=server.shutdown, daemon=True).start()
            signal.signal(signal.SIGTERM, stop)
            signal.signal(signal.SIGINT, stop)
            print("JARVIS Core ready (private Unix socket)", flush=True)
            try:
                server.serve_forever(poll_interval=1)
            finally:
                for token in list(core.active.values()):
                    token.cancel()
                path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
