"""Servidor de recepción. No está desplegado y no procesa antes de responder."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from queue import Queue

from verifier import Rejected, receive


def accept(raw_body, headers, secret, store, queue, now=None):
    result = receive(raw_body, headers, secret, store, now=now)
    enqueued = False
    if result.get("persisted") and not result.get("duplicate"):
        queue.put(result["event_id"])
        enqueued = True
    return result["status"], result["body"], enqueued


def make_handler(secret, store, queue):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            headers = {key: self.headers[key] for key in self.headers.keys()}
            try:
                status, body, _enqueued = accept(raw, headers, secret, store, queue)
            except Rejected as exc:
                status, body = exc.status, {"error": exc.reason}
            encoded = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, fmt, *args):
            return

    return Handler


def serve(host, port, secret, store, queue=None):
    if not secret:
        raise ValueError("falta el secreto de firma")
    queue = Queue() if queue is None else queue
    server = ThreadingHTTPServer((host, port), make_handler(secret, store, queue))
    server.queue = queue
    return server
