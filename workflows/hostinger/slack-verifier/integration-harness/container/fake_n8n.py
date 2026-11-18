"""n8n simulado para la prueba de contenedor. Solo registra; no hay datos reales."""
import json, os, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HNAME, HVALUE = os.environ["H_NAME"], os.environ["H_VALUE"]


class H(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        ok = self.path == "/webhook/wf01-ingest" and self.headers.get(HNAME) == HVALUE
        step = body.get("only_step")
        print(json.dumps({"step": step, "event": body.get("event_id"), "auth": ok}), flush=True)
        out = {"message": "rechazado"} if not ok else (
            {"file_name": "auto_slack_" + body["event_id"], "event_id": body["event_id"]} if step == "classify" else {"ok": True})
        data = json.dumps(out).encode()
        self.send_response(200 if ok else 403)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        return


ThreadingHTTPServer(("0.0.0.0", 5678), H).serve_forever()
