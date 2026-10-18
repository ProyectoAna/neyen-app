"""Verificador de entrada de Slack. No está desplegado.

Comprueba la firma sobre el cuerpo original y la antigüedad del timestamp.
Solo después guarda el evento y confirma la recepción. El procesamiento va aparte.
"""
import hashlib
import hmac
import json
import sqlite3
import time
from pathlib import Path

MAX_AGE_SECONDS = 300
STEPS = ("classify", "insert", "notify")


class Rejected(Exception):
    def __init__(self, status, reason):
        self.status = status
        self.reason = reason
        super().__init__(reason)


def sign(raw_body, timestamp, secret):
    if isinstance(raw_body, str):
        raw_body = raw_body.encode()
    basestring = b"v0:" + str(timestamp).encode() + b":" + raw_body
    digest = hmac.new(secret.encode(), basestring, hashlib.sha256).hexdigest()
    return "v0=" + digest


def verify_request(raw_body, timestamp, signature, secret, now):
    if not timestamp or not signature or not secret:
        raise Rejected(401, "firma ausente")
    try:
        ts = int(timestamp)
    except ValueError:
        raise Rejected(401, "timestamp inválido")
    if abs(now - ts) > MAX_AGE_SECONDS:
        raise Rejected(401, "timestamp antiguo")
    expected = sign(raw_body, timestamp, secret)
    if not hmac.compare_digest(expected, signature):
        raise Rejected(401, "firma inválida")


class EventStore:
    def __init__(self, path):
        self.path = Path(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            """
            create table if not exists events (
              event_id text primary key,
              payload text not null,
              status text not null,
              classify_state text not null default 'pending',
              insert_state text not null default 'pending',
              notify_state text not null default 'pending',
              classification text,
              last_error text
            )
            """
        )
        self.conn.commit()

    def persist_if_new(self, event_id, payload):
        cur = self.conn.execute(
            "insert or ignore into events(event_id, payload, status) values (?, ?, 'received')",
            (event_id, json.dumps(payload)),
        )
        self.conn.commit()
        return cur.rowcount == 1

    def get(self, event_id):
        row = self.conn.execute("select * from events where event_id = ?", (event_id,)).fetchone()
        return dict(row) if row else None

    def state(self, event_id, step):
        return self.get(event_id)[f"{step}_state"]

    def mark(self, event_id, step, state, classification=None, error=None):
        self.conn.execute(
            f"update events set {step}_state = ?, classification = coalesce(?, classification), last_error = ?, status = ? where event_id = ?",
            (state, json.dumps(classification) if classification is not None else None, error, "failed" if state == "started" and error else "processing", event_id),
        )
        self.conn.commit()

    def mark_processed(self, event_id):
        self.conn.execute("update events set status = 'processed', last_error = null where event_id = ?", (event_id,))
        self.conn.commit()

    def mark_failed(self, event_id, error):
        self.conn.execute("update events set status = 'failed', last_error = ? where event_id = ?", (error, event_id))
        self.conn.commit()


def planned_steps(payload):
    text = ((payload.get("event") or {}).get("text") or "")
    if text.startswith("/"):
        return ["notify"]
    return ["classify", "insert", "notify"]


def receive(raw_body, headers, secret, store, now=None):
    """Verifica y persiste. No procesa. No confirma si no pudo guardar."""
    now = time.time() if now is None else now
    timestamp = headers.get("X-Slack-Request-Timestamp", "")
    signature = headers.get("X-Slack-Signature", "")
    verify_request(raw_body, timestamp, signature, secret, now)
    payload = json.loads(raw_body.decode())
    if payload.get("type") == "url_verification":
        return {"status": 200, "body": {"challenge": payload.get("challenge")}, "persisted": False, "duplicate": False}
    event_id = payload.get("event_id")
    if not event_id:
        raise Rejected(400, "evento sin identificador")
    created = store.persist_if_new(event_id, payload)
    if not store.get(event_id):
        raise Rejected(500, "no se pudo conservar el evento")
    return {"status": 200, "body": {"ok": True}, "persisted": True, "duplicate": not created, "event_id": event_id}


def process(event_id, store, processor):
    """Ejecuta solo pasos que no han empezado. No repite Claude, inserciones ni avisos."""
    row = store.get(event_id)
    if not row:
        raise Rejected(404, "evento no conservado")
    if row["status"] == "processed":
        return {"skipped": True}
    payload = json.loads(row["payload"])
    classification = json.loads(row["classification"]) if row["classification"] else None
    for step in planned_steps(payload):
        state = row[f"{step}_state"] if step != "classify" else store.state(event_id, step)
        state = store.state(event_id, step)
        if state in ("started", "done", "uncertain"):
            continue
        store.mark(event_id, step, "started")
        try:
            if step == "classify":
                classification = processor.classify(payload)
                store.mark(event_id, step, "done", classification=classification)
            elif step == "insert":
                processor.insert(payload, classification)
                store.mark(event_id, step, "done")
            else:
                processor.notify(payload, classification)
                store.mark(event_id, step, "done")
        except Exception as exc:
            store.mark(event_id, step, "uncertain", error=str(exc))
            store.mark_failed(event_id, str(exc))
            raise
        row = store.get(event_id)
    pending = [step for step in planned_steps(payload) if store.state(event_id, step) != "done"]
    if pending:
        store.mark_failed(event_id, "pasos incompletos o inciertos")
        return {"skipped": False, "complete": False}
    store.mark_processed(event_id)
    return {"skipped": False, "complete": True}


def recover(event_id, store, processor):
    row = store.get(event_id)
    if not row or row["status"] != "failed":
        return {"recovered": False}
    process(event_id, store, processor)
    return {"recovered": True}


def forward_body(event_id, payload, step, classification=None):
    return {
        "verifier": "slack-verifier",
        "event_id": event_id,
        "only_step": step,
        "event": payload.get("event") or {},
        "classification": classification,
    }
