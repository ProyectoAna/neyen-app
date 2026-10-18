"""Verificador de entrada de Slack. No está desplegado.

Comprueba la firma sobre el cuerpo original y la antigüedad del timestamp.
Solo después guarda el evento y confirma la recepción. El procesamiento va aparte.
"""
import hashlib
import hmac
import json
import sqlite3
import time
import uuid
from pathlib import Path

MAX_AGE_SECONDS = 300
CLAIM_TTL_SECONDS = 900
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


class _Transaction:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        self.conn.execute("BEGIN IMMEDIATE")
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self.conn.execute("COMMIT")
            else:
                self.conn.execute("ROLLBACK")
        finally:
            self.conn.close()


class EventStore:
    def __init__(self, path):
        self.path = Path(path)
        with self._transaction() as conn:
            conn.execute(
                """
                create table if not exists events (
                  event_id text primary key,
                  payload text not null,
                  status text not null,
                  classify_state text not null default 'pending',
                  insert_state text not null default 'pending',
                  notify_state text not null default 'pending',
                  classification text,
                  last_error text,
                  claim_owner text,
                  claimed_at real,
                  authorized integer not null default 0
                )
                """
            )
            columns = {row[1] for row in conn.execute("pragma table_info(events)")}
            if "claim_owner" not in columns:
                conn.execute("alter table events add column claim_owner text")
                conn.execute("alter table events add column claimed_at real")
            if "authorized" not in columns:
                conn.execute("alter table events add column authorized integer not null default 0")

    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("pragma journal_mode=WAL")
        conn.execute("pragma busy_timeout=5000")
        return conn

    def _transaction(self):
        return _Transaction(self._connect())

    def persist_if_new(self, event_id, payload):
        with self._transaction() as conn:
            cur = conn.execute(
                "insert or ignore into events(event_id, payload, status) values (?, ?, 'received')",
                (event_id, json.dumps(payload)),
            )
            return cur.rowcount == 1

    def get(self, event_id):
        with self._transaction() as conn:
            row = conn.execute("select * from events where event_id = ?", (event_id,)).fetchone()
            return dict(row) if row else None

    def state(self, event_id, step):
        if step not in STEPS:
            raise Rejected(500, "paso no permitido")
        return self.get(event_id)[f"{step}_state"]

    def mark(self, event_id, step, state, classification=None, error=None):
        if step not in STEPS:
            raise Rejected(500, "paso no permitido")
        status = "failed" if state in ("started", "uncertain") else "processing"
        with self._transaction() as conn:
            conn.execute(
                f"update events set {step}_state = ?, classification = coalesce(?, classification), last_error = ?, status = ? where event_id = ?",
                (state, json.dumps(classification) if classification is not None else None, error, status, event_id),
            )

    def mark_processed(self, event_id):
        with self._transaction() as conn:
            conn.execute("update events set status = 'processed', last_error = null where event_id = ?", (event_id,))

    def mark_failed(self, event_id, error):
        with self._transaction() as conn:
            conn.execute("update events set status = 'failed', last_error = ? where event_id = ?", (error, event_id))

    def try_claim(self, event_id, owner, now):
        with self._transaction() as conn:
            row = conn.execute(
                "select claim_owner, authorized, status, classify_state, insert_state, notify_state from events where event_id = ?",
                (event_id,),
            ).fetchone()
            if not row or row["status"] == "processed":
                return False
            if row["authorized"] and row["claim_owner"] != owner:
                return False
            if any(row[f"{step}_state"] in ("started", "uncertain") for step in STEPS):
                return False
            if row["claim_owner"] and row["claim_owner"] != owner:
                return False
            conn.execute(
                "update events set claim_owner = ?, claimed_at = ?, authorized = 1, status = 'processing' where event_id = ?",
                (owner, now, event_id),
            )
            return True

    def release_claim(self, event_id, owner):
        with self._transaction() as conn:
            conn.execute(
                "update events set claim_owner = null, claimed_at = null, authorized = 0 where event_id = ? and claim_owner = ?",
                (event_id, owner),
            )

    def list_available(self):
        with self._transaction() as conn:
            rows = conn.execute(
                """
                select event_id from events
                where status != 'processed'
                  and ifnull(authorized, 0) = 0
                  and claim_owner is null
                  and classify_state in ('pending', 'done')
                  and insert_state in ('pending', 'done')
                  and notify_state in ('pending', 'done')
                order by event_id
                """
            ).fetchall()
            return [row["event_id"] for row in rows]


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


def process(event_id, store, processor, owner=None, now=None):
    """Ejecuta solo pasos pendientes. Un paso incierto bloquea los siguientes."""
    row = store.get(event_id)
    if not row:
        raise Rejected(404, "evento no conservado")
    if row["status"] == "processed":
        return {"skipped": True, "busy": False, "complete": True}
    payload = json.loads(row["payload"])
    for step in planned_steps(payload):
        if row[f"{step}_state"] in ("started", "uncertain"):
            store.mark_failed(event_id, step + " requiere reconciliacion")
            return {
                "skipped": False,
                "busy": False,
                "complete": False,
                "blocked": step,
                "reconciliation": True,
            }
    owner = owner or str(uuid.uuid4())
    now = time.time() if now is None else now
    if not store.try_claim(event_id, owner, now):
        return {"skipped": True, "busy": True, "complete": False}
    try:
        row = store.get(event_id)
        classification = json.loads(row["classification"]) if row["classification"] else None
        for step in planned_steps(payload):
            if step not in STEPS:
                raise Rejected(500, "paso no permitido")
            state = store.state(event_id, step)
            if state in ("started", "uncertain"):
                store.mark_failed(event_id, step + " requiere reconciliacion")
                return {
                    "skipped": False,
                    "busy": False,
                    "complete": False,
                    "blocked": step,
                    "reconciliation": True,
                }
            if state == "done":
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
        pending = [step for step in planned_steps(payload) if store.state(event_id, step) != "done"]
        if pending:
            store.mark_failed(event_id, "pasos incompletos o inciertos")
            return {"skipped": False, "busy": False, "complete": False, "blocked": pending[0]}
        store.mark_processed(event_id)
        return {"skipped": False, "busy": False, "complete": True}
    finally:
        store.release_claim(event_id, owner)


def recover(event_id, store, processor):
    row = store.get(event_id)
    if not row or row["status"] != "failed":
        return {"recovered": False}
    result = process(event_id, store, processor)
    result["recovered"] = bool(result.get("complete"))
    return result


def forward_body(event_id, payload, step, classification=None):
    return {
        "verifier": "slack-verifier",
        "event_id": event_id,
        "only_step": step,
        "event": payload.get("event") or {},
        "classification": classification,
    }
