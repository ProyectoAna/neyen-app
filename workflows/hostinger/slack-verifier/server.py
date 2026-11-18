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


def make_handler(secret, store, queue, post_paths=None, health=None):
    """post_paths: rutas POST admitidas (None = cualquiera). health: funcion sin argumentos
    que devuelve (estado_http, dict) para GET /healthz."""

    class Handler(BaseHTTPRequestHandler):
        def _reply(self, status, body):
            encoded = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            if health is not None and self.path.split("?", 1)[0] == "/healthz":
                try:
                    status, body = health()
                except Exception:
                    status, body = 503, {"status": "error"}
                self._reply(status, body)
            else:
                self._reply(404, {"error": "no encontrado"})

        def do_POST(self):
            if post_paths is not None and self.path.split("?", 1)[0] not in post_paths:
                length = int(self.headers.get("Content-Length", "0"))
                self.rfile.read(length)
                self._reply(404, {"error": "no encontrado"})
                return
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


def serve(host, port, secret, store, queue=None, post_paths=None, health=None):
    if not secret:
        raise ValueError("falta el secreto de firma")
    queue = Queue() if queue is None else queue
    server = ThreadingHTTPServer((host, port), make_handler(secret, store, queue, post_paths, health))
    server.queue = queue
    return server
