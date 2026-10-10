"""Loopback-only authenticated OpenAI-compatible fixture; no model inference."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time


class Node(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self):
        super().__init__(('127.0.0.1', 0), Handler)
        self.requests = []
        self.started = threading.Event()
        self.stall = threading.Event()
        self.behavior = 'ok'
        self.key = 'test-only-node-key'
        self.thread = threading.Thread(target=self.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self):
        return f'http://127.0.0.1:{self.server_port}/v1'

    def close(self):
        self.stall.set()
        self.shutdown()
        self.server_close()
        self.thread.join(2)


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'
    def log_message(self, *_):
        pass

    def authorized(self):
        if self.headers.get('Authorization') != 'Bearer ' + self.server.key:
            self.send_error(401)
            return False
        return True

    def do_GET(self):
        if not self.authorized():
            return
        if self.path == '/v1/models':
            body = json.dumps({'data': None} if self.server.behavior == 'bad-models' else {'data': [{'id': 'smollm2-360m'}]}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def do_POST(self):
        if not self.authorized():
            return
        payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.requests.append(payload)
        if self.server.behavior == 'quota':
            self.send_error(429)
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.end_headers()
        self.server.started.set()
        try:
            if self.server.behavior in {'null-choices', 'bad-delta', 'array-event'}:
                data = {'null-choices': {'choices': None}, 'bad-delta': {'choices': [{'delta': None}]}, 'array-event': []}[self.server.behavior]
                self.wfile.write(b'data: ' + json.dumps(data).encode() + b'\n\n')
                self.wfile.flush()
                return
            if self.server.behavior == 'malformed':
                self.wfile.write(b'data: not-json\n\n')
                self.wfile.flush()
                return
            if self.server.behavior == 'stall':
                self.wfile.flush()
                self.server.stall.wait(8)
                return
            for token in ['Hello ', 'Aman', ' — ', 'local stream.']:
                data = json.dumps({'choices': [{'delta': {'content': token}, 'finish_reason': None}]}, ensure_ascii=False).encode()
                # Split UTF-8/network writes deliberately; emit real SSE frames.
                frame = b'data: ' + data + b'\r\n\r\n'
                self.wfile.write(frame[:9])
                self.wfile.flush()
                time.sleep(0.025)
                self.wfile.write(frame[9:])
                self.wfile.flush()
                if self.server.behavior == 'disconnect':
                    return
            self.wfile.write(b'data: [DONE]\n\n')
            self.wfile.flush()
        except (OSError, ValueError):
            pass
