"""Pruebas del servicio (config, entrada, salud, reinicio) con n8n simulado. Sin Slack ni n8n reales.

El servicio se arranca como lo hace el contenedor: carpeta limpia con solo los ficheros que copia
el Dockerfile, entorno vacio (env -i) y variables de la definicion del servicio.
"""
import json
import os
import re
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from config import ConfigError, load_config
from verifier import EventStore, receive, sign

SECRET = "firma-ficticia-0123456789"
HVALUE = "cabecera-ficticia-abcdef0123"
HNAME = "X-Neyen-Internal"
COPIED = ("config.py", "server.py", "service.py", "verifier.py", "worker.py")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class FakeN8n:
    """n8n simulado: registra (paso, evento, cabecera) y responde como los flujos reales."""

    def __init__(self, classify_delay=0.0):
        self.calls = []
        self.classify_delay = classify_delay
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                step = body.get("only_step")
                outer.calls.append((step, body["event_id"], self.headers.get(HNAME)))
                if self.path != "/webhook/wf01-ingest" or self.headers.get(HNAME) != HVALUE:
                    out, code = {"message": "rechazado"}, 403
                else:
                    code = 200
                    if step == "classify":
                        time.sleep(outer.classify_delay)
                        out = {"file_name": "auto_slack_" + body["event_id"], "event_id": body["event_id"]}
                    else:
                        out = {"ok": True}
                data = json.dumps(out).encode()
                self.send_response(code)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                return

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def steps(self, event_id):
        return [c[0] for c in self.calls if c[1] == event_id]

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def event(event_id):
    body = {"type": "event_callback", "event_id": event_id,
            "event": {"type": "message", "text": "nota " + event_id, "user": "U1", "channel": "CPRUEBA"}}
    raw = json.dumps(body).encode()
    ts = str(int(time.time()))
    return raw, {"X-Slack-Request-Timestamp": ts, "X-Slack-Signature": sign(raw, ts, SECRET)}


def post(port, path, raw, headers):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=raw, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def get(port, path):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def valid_env(**over):
    env = {"SLACK_SIGNING_SECRET": SECRET, "N8N_BASE_URL": "http://127.0.0.1:1",
           "N8N_INTERNAL_HEADER_NAME": HNAME, "N8N_INTERNAL_HEADER_VALUE": HVALUE}
    env.update(over)
    return {k: v for k, v in env.items() if v is not None}


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.sqlite = str(Path(self.dir.name) / "e.sqlite")

    def tearDown(self):
        self.dir.cleanup()

    def env(self, **over):
        return valid_env(**{"SQLITE_PATH": self.sqlite, **over})

    def problems(self, **over):
        with self.assertRaises(ConfigError) as cm:
            load_config(self.env(**over))
        return cm.exception.problems

    def test_valid_config_and_repr_hides_secrets(self):
        cfg = load_config(self.env())
        text = repr(cfg)
        self.assertNotIn(SECRET, text)
        self.assertNotIn(HVALUE, text)
        self.assertEqual(cfg.port, 8080)

    def test_missing_variables_are_named(self):
        with self.assertRaises(ConfigError) as cm:
            load_config({"SQLITE_PATH": self.sqlite})
        text = " ".join(cm.exception.problems)
        for name in ("SLACK_SIGNING_SECRET", "N8N_BASE_URL", "N8N_INTERNAL_HEADER_NAME", "N8N_INTERNAL_HEADER_VALUE"):
            self.assertIn(name, text)

    def test_errors_never_contain_values(self):
        probs = " ".join(self.problems(SLACK_SIGNING_SECRET="corto-secreto", N8N_INTERNAL_HEADER_VALUE="corto-valor",
                                       N8N_BASE_URL="http://n8n.example.com"))
        self.assertIn("demasiado corto", probs)
        self.assertNotIn("corto-secreto", probs)
        self.assertNotIn("corto-valor", probs)

    def test_public_http_url_requires_https(self):
        self.assertTrue(any("https" in p for p in self.problems(N8N_BASE_URL="http://n8n.example.com")))
        load_config(self.env(N8N_BASE_URL="https://n8n.example.com"))
        load_config(self.env(N8N_BASE_URL="http://n8n:5678"))

    def test_bad_base_url_and_port_and_path(self):
        self.assertTrue(self.problems(N8N_BASE_URL="n8n:5678"))
        self.assertTrue(self.problems(N8N_BASE_URL="https://x.example.com/webhook/wf01-ingest"))
        self.assertTrue(self.problems(PORT="99999"))
        self.assertTrue(self.problems(PORT="abc"))
        self.assertTrue(self.problems(SLACK_EVENTS_PATH="sin-barra"))

    def test_header_secret_must_differ_and_name_valid(self):
        self.assertTrue(self.problems(N8N_INTERNAL_HEADER_VALUE=SECRET))
        self.assertTrue(self.problems(N8N_INTERNAL_HEADER_NAME="mala cabecera"))

    def test_sqlite_dir_must_exist_and_secrets_from_files(self):
        self.assertTrue(any("SQLITE_PATH" in p for p in self.problems(SQLITE_PATH="/no/existe/e.sqlite")))
        f = Path(self.dir.name) / "firma"
        f.write_text(SECRET + "\n")
        cfg = load_config(self.env(SLACK_SIGNING_SECRET=None, SLACK_SIGNING_SECRET_FILE=str(f)))
        self.assertEqual(cfg.signing_secret, SECRET)
        self.assertTrue(any("_FILE" in p for p in self.problems(SLACK_SIGNING_SECRET=None,
                                                                   SLACK_SIGNING_SECRET_FILE="/no/existe")))


class StaticDefinitionTests(unittest.TestCase):
    def test_dockerfile_copies_existing_files_and_runs_non_root(self):
        text = (HERE / "Dockerfile").read_text()
        copied = re.search(r"^COPY (.+) \./$", text, re.M).group(1).split()
        self.assertEqual(sorted(copied), sorted(COPIED))
        for name in copied:
            self.assertTrue((HERE / name).exists(), name)
        self.assertRegex(text, r"(?m)^USER verifier")
        self.assertIn("/healthz", text)
        self.assertIn('VOLUME ["/data"]', text)

    def test_compose_and_env_example_have_no_secret_values(self):
        compose = (HERE / "docker-compose.yml").read_text()
        for name in ("SLACK_SIGNING_SECRET", "N8N_INTERNAL_HEADER_VALUE"):
            self.assertRegex(compose, name + r": \$\{" + name + r":\?")
        self.assertIn("verifier-data:/data", compose)
        self.assertIn("127.0.0.1:", compose)
        example = (HERE / ".env.example").read_text()
        for name in ("SLACK_SIGNING_SECRET", "N8N_INTERNAL_HEADER_VALUE"):
            self.assertRegex(example, r"(?m)^" + name + r"=$")


class ServiceProcessTests(unittest.TestCase):
    """Arranque desde cero en una carpeta limpia, con el entorno vacio."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.app = self.root / "app"
        self.data = self.root / "data"
        self.app.mkdir()
        self.data.mkdir()
        for name in COPIED:
            shutil.copy(HERE / name, self.app / name)
        self.sqlite = self.data / "events.sqlite"
        self.n8n = FakeN8n()
        self.proc = None
        self.port = free_port()

    def tearDown(self):
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait()
        self.n8n.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def env(self, **over):
        base = {"N8N_BASE_URL": f"http://127.0.0.1:{self.n8n.port}", "SQLITE_PATH": str(self.sqlite),
                "PORT": str(self.port), "HOST": "127.0.0.1", "WORKER_POLL_SECONDS": "0.2",
                "PATH": os.environ["PATH"]}
        return valid_env(**{**base, **over})

    def start(self, **over):
        self.proc = subprocess.Popen([sys.executable, "service.py", "serve"], cwd=self.app, env=self.env(**over),
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                if get(self.port, "/healthz")[0] == 200:
                    return
            except OSError:
                time.sleep(0.1)
        self.fail("el servicio no arranco")

    def stop(self, sig=signal.SIGTERM):
        self.proc.send_signal(sig)
        code = self.proc.wait(timeout=15)
        out, err = self.proc.stdout.read(), self.proc.stderr.read()
        return code, out + err

    def row(self, event_id):
        with sqlite3.connect(self.sqlite) as c:
            c.row_factory = sqlite3.Row
            r = c.execute("select * from events where event_id=?", (event_id,)).fetchone()
            return dict(r) if r else None

    def wait_status(self, event_id, status, timeout=10):
        deadline = time.time() + timeout
        while time.time() < deadline:
            r = self.row(event_id)
            if r and r["status"] == status:
                return r
            time.sleep(0.1)
        self.fail(f"{event_id} no llego a {status}: {self.row(event_id)}")

    def test_fail_fast_with_clear_non_secret_error(self):
        p = subprocess.run([sys.executable, "service.py", "serve"], cwd=self.app,
                           env=self.env(N8N_BASE_URL="http://n8n.example.com", SLACK_SIGNING_SECRET="corto-secreto"),
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, 2)
        self.assertIn("CONFIGURACION INVALIDA", p.stderr)
        self.assertIn("N8N_BASE_URL", p.stderr)
        self.assertIn("SLACK_SIGNING_SECRET", p.stderr)
        self.assertNotIn("corto-secreto", p.stdout + p.stderr)
        self.assertFalse(self.sqlite.exists())

    def test_check_config_does_not_open_port_or_db(self):
        p = subprocess.run([sys.executable, "service.py", "check-config"], cwd=self.app, env=self.env(),
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, 0)
        self.assertNotIn(SECRET, p.stdout + p.stderr)
        self.assertNotIn(HVALUE, p.stdout + p.stderr)
        self.assertFalse(self.sqlite.exists())

    def test_signed_event_is_stored_acked_and_processed_once_and_health_is_clean(self):
        self.start()
        code, health = get(self.port, "/healthz")
        self.assertEqual((code, health), (200, {"status": "ok", "db": "ok", "worker": "ok"}))
        self.assertNotIn(SECRET, json.dumps(health))
        raw, headers = event("EvA")
        self.assertEqual(post(self.port, "/slack/events", raw, headers), (200, {"ok": True}))
        self.wait_status("EvA", "processed")
        self.assertEqual(self.n8n.steps("EvA"), ["classify", "insert", "notify"])
        self.assertTrue(all(c[2] == HVALUE for c in self.n8n.calls))
        # reenvio de Slack: 200 y sin reprocesar
        self.assertEqual(post(self.port, "/slack/events", raw, headers)[0], 200)
        time.sleep(0.8)
        self.assertEqual(self.n8n.steps("EvA"), ["classify", "insert", "notify"])
        code, out = self.stop()
        self.assertEqual(code, 0, out)
        self.assertNotIn(SECRET, out)
        self.assertNotIn(HVALUE, out)

    def test_bad_signature_wrong_path_and_challenge(self):
        self.start()
        raw, headers = event("EvBAD")
        headers["X-Slack-Signature"] = "v0=" + "0" * 64
        status, body = post(self.port, "/slack/events", raw, headers)
        self.assertEqual(status, 401)
        self.assertIsNone(self.row("EvBAD"))
        self.assertEqual(self.n8n.calls, [])
        raw, headers = event("EvPATH")
        self.assertEqual(post(self.port, "/otra", raw, headers)[0], 404)
        self.assertIsNone(self.row("EvPATH"))
        self.assertEqual(get(self.port, "/otra")[0], 404)
        ch = json.dumps({"type": "url_verification", "challenge": "abc"}).encode()
        ts = str(int(time.time()))
        ok = {"X-Slack-Request-Timestamp": ts, "X-Slack-Signature": sign(ch, ts, SECRET)}
        self.assertEqual(post(self.port, "/slack/events", ch, ok), (200, {"challenge": "abc"}))
        self.assertEqual(self.n8n.calls, [])
        self.assertEqual(self.stop()[0], 0)

    def test_restart_with_pending_events_processes_each_once(self):
        self.start()
        raw, headers = event("EvDONE")
        post(self.port, "/slack/events", raw, headers)
        self.wait_status("EvDONE", "processed")
        self.assertEqual(self.stop()[0], 0)
        # Slack ya recibio el 200 y el servicio cayo antes de procesar: dos eventos solo en SQLite
        store = EventStore(self.sqlite)
        for eid in ("EvP1", "EvP2"):
            raw, headers = event(eid)
            receive(raw, headers, SECRET, store)
        self.assertEqual(self.row("EvP1")["status"], "received")
        self.start()
        self.wait_status("EvP1", "processed")
        self.wait_status("EvP2", "processed")
        for eid in ("EvP1", "EvP2"):
            self.assertEqual(self.n8n.steps(eid), ["classify", "insert", "notify"])
        self.assertEqual(self.n8n.steps("EvDONE"), ["classify", "insert", "notify"])  # no se repitio
        self.assertEqual(self.stop()[0], 0)

    def test_hard_kill_mid_step_blocks_resend_until_reconciled_then_recover(self):
        self.n8n.classify_delay = 3
        self.start()
        raw, headers = event("EvCRASH")
        post(self.port, "/slack/events", raw, headers)
        deadline = time.time() + 5
        while "classify" not in self.n8n.steps("EvCRASH") and time.time() < deadline:
            time.sleep(0.05)
        self.proc.kill()
        self.proc.wait()
        self.assertEqual(self.row("EvCRASH")["classify_state"], "started")
        self.n8n.classify_delay = 0
        self.n8n.calls.clear()
        self.start()
        time.sleep(1.0)
        self.assertEqual(self.n8n.steps("EvCRASH"), [])        # no reenvia un paso incierto
        self.assertNotEqual(self.row("EvCRASH")["status"], "processed")
        self.assertEqual(self.stop()[0], 0)
        # receta de reconciliacion (docs/DEPLOYMENT-PROCEDURE.md): paso no hecho -> pendiente
        with sqlite3.connect(self.sqlite) as c:
            c.execute("update events set classify_state='pending', status='failed', last_error=null,"
                      " claim_owner=null, claimed_at=null, authorized=0 where event_id='EvCRASH'")
        p = subprocess.run([sys.executable, "service.py", "recover", "EvCRASH"], cwd=self.app, env=self.env(),
                           capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(self.row("EvCRASH")["status"], "processed")
        self.assertEqual(self.n8n.steps("EvCRASH"), ["classify", "insert", "notify"])

    def test_sigterm_during_step_waits_for_it(self):
        self.n8n.classify_delay = 1.5
        self.start()
        raw, headers = event("EvTERM")
        post(self.port, "/slack/events", raw, headers)
        deadline = time.time() + 5
        while "classify" not in self.n8n.steps("EvTERM") and time.time() < deadline:
            time.sleep(0.05)
        code, out = self.stop()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.row("EvTERM")["classify_state"], "done")   # el paso en curso termino


if __name__ == "__main__":
    unittest.main()
