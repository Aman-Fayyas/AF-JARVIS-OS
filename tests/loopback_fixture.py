"""TEST ONLY transport for sandboxes that forbid AF_UNIX. Never installed in OS.

Uses ephemeral loopback TCP; contains only synthetic test keys and conversation.
Production server remains Unix-only with Linux same-UID peer verification.
"""
import json
import socket
import socketserver
from pathlib import Path
from jarvis.core import Core
from jarvis.ipc import MAX_FRAME
import jarvis.server as production


def test_events(port, request):
    with socket.create_connection(('127.0.0.1', port), timeout=5) as connection:
        connection.sendall(json.dumps(request).encode() + b'\n')
        with connection.makefile('rb') as stream:
            for line in stream:
                if len(line) > MAX_FRAME:
                    raise ValueError('Oversized fixture frame')
                yield json.loads(line)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('port_file')
    args = parser.parse_args()
    production.verify_peer = lambda connection: None
    class FixtureServer(production.Server):
        address_family = socket.AF_INET
    with FixtureServer(('127.0.0.1', 0), production.Handler) as server:
        server.core = Core()
        Path(args.port_file).write_text(str(server.server_address[1]))
        server.serve_forever(poll_interval=0.2)


if __name__ == '__main__':
    main()
