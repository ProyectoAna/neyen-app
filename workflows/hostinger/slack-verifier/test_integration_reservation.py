"""Reserva persistente y atomica de avisos (tabla notification_reservations en un
PostgreSQL + PostgREST LOCALES de prueba). Opt-in: NEYEN_IT=1.

Prueba llamadas simultaneas a dos instancias de n8n (replicas), reinicios,
rechazo explicito de Slack (libera) y resultado incierto (exige reconciliacion).
"""
import json
import os
import subprocess
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_integration import mock, calls
from test_integration_chain import reset, uid, HDR

N8N_A = os.environ.get("NEYEN_N8N_URL", "http://127.0.0.1:5680")
N8N_B = os.environ.get("NEYEN_N8N_URL_2", "http://127.0.0.1:5681")
PGRST = os.environ.get("NEYEN_PGRST_URL", "http://127.0.0.1:3000")
JWT = Path(os.environ.get("NEYEN_JWT_FILE", "/workspace/n8ntest/test.jwt"))
NOTIFY = "/webhook/wf03-crosslink-notify"
CROSS = "/webhook/wf02-crosslink"


def call(base, path, body):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", HDR[0]: HDR[1]})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {}


def rest(method, query, body=None, prefer=None):
    headers = {"Authorization": "Bearer " + JWT.read_text().strip(), "Content-Type": "application/json"}
    if prefer:
        headers["Prefer"] = prefer
    req = urllib.request.Request(PGRST + "/notification_reservations" + query, method=method, headers=headers,
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        return e.code, None


def state_of(eid):
    status, rows = rest("GET", "?select=state&entry_id=eq." + eid)
    return rows[0]["state"] if rows else None


def payload(eid=None, **extra):
    p = {"entry_id": eid or uid("res"), "file_name": uid("auto_slack_R"), "related_ids": [], "related_count": 0,
         "tags": ["a"], "entities": ["X"], "summary": "S", "channel_id": "CORIGIN"}
    p.update(extra)
    return p


@unittest.skipUnless(os.environ.get("NEYEN_IT") == "1", "integración opt-in")
class Reservation(unittest.TestCase):
    def setUp(self):
        reset()

    def test_simultaneous_calls_across_two_replicas_post_exactly_once(self):
        mock("/control", {"mode": {"slack": "slow", "delay": 0.6}})
        p = payload()
        results = []
        lock = threading.Lock()

        def go(base):
            r = call(base, NOTIFY, p)
            with lock:
                results.append(r)

        threads = [threading.Thread(target=go, args=(N8N_A if i % 2 else N8N_B,)) for i in range(14)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(len(calls("/slack")), 1)
        winners = [b for s, b in results if s == 200 and b.get("ok") is True and not b.get("duplicate")]
        self.assertEqual(len(winners), 1, results)
        for s, b in results:
            self.assertEqual(s, 200)
            self.assertTrue(b.get("duplicate") or b.get("status") == "blocked" or b.get("ok") is True, b)
        self.assertEqual(state_of(p["entry_id"]), "done")

    def test_simultaneous_distinct_entries_all_post(self):
        ps = [payload() for _ in range(8)]
        threads = [threading.Thread(target=call, args=(N8N_A if i % 2 else N8N_B, NOTIFY, p)) for i, p in enumerate(ps)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(len(calls("/slack")), 8)

    def test_direct_simultaneous_calls_to_wf02_post_once(self):
        mock("/control", {"mode": {"slack": "slow", "delay": 0.6}})
        fn = uid("auto_slack_W2")
        threads = [threading.Thread(target=call, args=(N8N_A if i % 2 else N8N_B, CROSS, {"file_name": fn, "channel_id": "CORIGIN"}))
                   for i in range(10)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(len(calls("/slack")), 1)

    def test_explicit_slack_rejection_releases_reservation(self):
        p = payload()
        mock("/control", {"mode": {"slack": "err200"}})
        status, _ = call(N8N_A, NOTIFY, p)
        self.assertGreaterEqual(status, 400)
        self.assertIsNone(state_of(p["entry_id"]))
        mock("/control", {"mode": {"slack": "ok"}})
        status, body = call(N8N_B, NOTIFY, p)
        self.assertEqual((status, body.get("ok")), (200, True))
        self.assertEqual(state_of(p["entry_id"]), "done")
        self.assertEqual(len(calls("/slack")), 2)

    def test_uncertain_result_requires_reconciliation_before_resend(self):
        p = payload()
        mock("/control", {"mode": {"slack": "drop"}})
        status, _ = call(N8N_A, NOTIFY, p)
        self.assertGreaterEqual(status, 400)
        self.assertEqual(state_of(p["entry_id"]), "uncertain")
        mock("/control", {"mode": {"slack": "ok"}})
        before = len(calls("/slack"))
        for base in (N8N_A, N8N_B):
            status, body = call(base, NOTIFY, p)
            self.assertEqual((status, body.get("status"), body.get("blocker")), (200, "blocked", "requiere_reconciliacion"))
        self.assertEqual(len(calls("/slack")), before)
        # reconciliacion manual: se comprobo en Slack que NO se publico -> se borra la reserva
        self.assertEqual(rest("DELETE", "?entry_id=eq." + p["entry_id"])[0], 204)
        status, body = call(N8N_A, NOTIFY, p)
        self.assertEqual((status, body.get("ok")), (200, True))

    def test_uncertain_marked_done_by_reconciliation_does_not_resend(self):
        p = payload()
        mock("/control", {"mode": {"slack": "drop"}})
        call(N8N_A, NOTIFY, p)
        mock("/control", {"mode": {"slack": "ok"}})
        rest("PATCH", "?entry_id=eq." + p["entry_id"], {"state": "done"})
        before = len(calls("/slack"))
        status, body = call(N8N_B, NOTIFY, p)
        self.assertTrue(body.get("duplicate"))
        self.assertEqual(len(calls("/slack")), before)

    def test_abandoned_inflight_reservation_blocks(self):
        p = payload()
        self.assertEqual(rest("POST", "", {"entry_id": p["entry_id"], "state": "inflight"}, "return=minimal")[0], 201)
        status, body = call(N8N_A, NOTIFY, p)
        self.assertEqual((status, body.get("status")), (200, "blocked"))
        self.assertEqual(body.get("blocker"), "aviso_en_curso_o_sin_confirmar")
        self.assertEqual(calls("/slack"), [])

    def test_primary_key_conflict_is_409(self):
        eid = uid("pk")
        self.assertEqual(rest("POST", "", {"entry_id": eid, "state": "inflight"}, "return=minimal")[0], 201)
        self.assertEqual(rest("POST", "", {"entry_id": eid, "state": "inflight"}, "return=minimal")[0], 409)

    def test_metadata_upsert_with_on_conflict_works_after_unique_migration(self):
        fn = uid("auto_slack_UP")
        h = {"Authorization": "Bearer " + JWT.read_text().strip(), "Content-Type": "application/json",
             "Prefer": "resolution=merge-duplicates,return=minimal"}
        for summary in ("uno", "dos"):
            req = urllib.request.Request(PGRST + "/metadata?on_conflict=file_name", method="POST", headers=h,
                                         data=json.dumps({"file_name": fn, "source": "slack", "summary": summary}).encode())
            self.assertIn(urllib.request.urlopen(req).status, (200, 201, 204))
        get = urllib.request.Request(PGRST + "/metadata?select=summary&file_name=eq." + fn, headers=h)
        rows = json.loads(urllib.request.urlopen(get).read())
        self.assertEqual(rows, [{"summary": "dos"}])

    @unittest.skipUnless(os.environ.get("NEYEN_RESTART_SCRIPT"), "reinicio opt-in (NEYEN_RESTART_SCRIPT)")
    def test_reservations_survive_n8n_restart(self):
        done, unsure = payload(), payload()
        call(N8N_A, NOTIFY, done)
        mock("/control", {"mode": {"slack": "drop"}})
        call(N8N_B, NOTIFY, unsure)
        mock("/control", {"mode": {"slack": "ok"}})
        self.assertEqual(subprocess.call([os.environ["NEYEN_RESTART_SCRIPT"]]), 0)
        before = len(calls("/slack"))
        status, body = call(N8N_B, NOTIFY, done)
        self.assertTrue(body.get("duplicate"))
        status, body = call(N8N_A, NOTIFY, unsure)
        self.assertEqual(body.get("blocker"), "requiere_reconciliacion")
        self.assertEqual(len(calls("/slack")), before)


if __name__ == "__main__":
    unittest.main()
