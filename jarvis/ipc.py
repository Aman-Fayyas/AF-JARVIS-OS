from pathlib import Path
import json
import os
import socket
import struct
from .config import private_dir

MAX_FRAME = 131072


def socket_path():
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if not runtime:
        raise RuntimeError("XDG_RUNTIME_DIR is required. Use a normal Linux login session.")
    path = Path(runtime)
    if not path.is_dir() or path.stat().st_uid != os.getuid() or path.is_symlink():
        raise RuntimeError("Unsafe runtime directory")
    return private_dir(path / "af-jarvis") / "core.sock"


def verify_peer(sock):
    _, uid, _ = struct.unpack("3i", sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
    if uid != os.getuid():
        raise PermissionError("IPC peer has a different user identity")


def events(request):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(210)
        connection.connect(str(socket_path()))
        verify_peer(connection)
        connection.sendall(json.dumps(request).encode() + b"\n")
        received = False
        with connection.makefile("rb") as stream:
            while True:
                line = stream.readline(MAX_FRAME + 1)
                if not line:
                    if not received:
                        raise RuntimeError("Core disconnected before replying")
                    return
                if len(line) > MAX_FRAME:
                    raise ValueError("IPC frame too large")
                received = True
                yield json.loads(line)


def call(request):
    result = list(events(request))
    if result and result[-1]["type"] == "error":
        raise RuntimeError(result[-1]["message"])
    return result[-1] if result else {"type": "error", "message": "Core disconnected"}
