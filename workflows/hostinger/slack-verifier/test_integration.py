"""Integración local con n8n real y servicios simulados. Opt-in: NEYEN_IT=1.

Requiere n8n en NEYEN_N8N_URL con el workflow NEYEN-ingest importado
(URLs reescritas a NEYEN_MOCK_URL) y credenciales ficticias.
Nunca usa servicios reales.
"""
import json
import os
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verifier import EventStore, receive, process
from worker import N8nProcessor, urllib_transport
from test_verifier import envelope, SECRET, NOW

N8N = os.environ.get("NEYEN_N8N_URL", "http://127.0.0.1:5680")
MOCK = os.environ.get("NEYEN_MOCK_URL", "http://127.0.0.1:9100")
HDR = ("X-Internal-Auth", os.environ.get("NEYEN_FAKE_HEADER", "fake-internal-secret"))


def mock(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(MOCK + path, data=data, method="POST" if data else "GET",
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())


def calls(prefix):
    return [c for c in mock("/calls") if c["path"].startswith(prefix)]


@unittest.skipUnless(os.environ.get("NEYEN_IT") == "1", "integración opt-in")
class Integration(unittest.TestCase):
    def setUp(self):
        mock("/control", {"reset": True, "mode": {"supabase": "ok", "anthropic": "ok", "notify": "ok"}})
        self.tmp = tempfile.TemporaryDirectory()
        self.store = EventStore(Path(self.tmp.name) / "q.db")
        self.proc = N8nProcessor(N8N, HDR[0], HDR[1], urllib_transport)

    def tearDown(self):
        self.tmp.cleanup()

    def persist(self, eid):
        raw, headers = envelope(event_id=eid, text="una nota larga sobre arquitectura")
        receive(raw, headers, SECRET, self.store, now=NOW)

    def test_full_path(self):
        self.persist("EvIT1")
        r = process("EvIT1", self.store, self.proc)
        self.assertTrue(r["complete"], r)
        self.assertEqual(len(calls("/anthropic")), 1)
        ins = calls("/supabase-insert")
        self.assertEqual(len(ins), 1)
        rec = ins[0]["body"]
        self.assertEqual(rec["file_name"], "auto_slack_EvIT1")
        self.assertEqual(rec["narrative_role"], "system")
        self.assertEqual(rec["tags"], ["a", "b", "c"])
        # columnas que no existen en metadata no deben llegar a Supabase
        self.assertNotIn("event_id", rec)
        self.assertNotIn("only_step", rec)
        nt = calls("/notify")
        self.assertEqual(len(nt), 1)
        self.assertEqual(nt[0]["body"]["file_name"], "auto_slack_EvIT1")

    def test_classify_returns_fields_and_preserves_ids(self):
        self.persist("EvIT2")
        c = self.proc.classify(json.loads(self.store.get("EvIT2")["payload"]))
        for k in ("file_name", "summary", "tags", "entities", "narrative_role", "event_id", "only_step"):
            self.assertIn(k, c)
        self.assertEqual(c["event_id"], "EvIT2")
        self.assertEqual(c["only_step"], "classify")

    def test_http200_functional_error_not_success_insert(self):
        mock("/control", {"mode": {"supabase": "err200"}})
        self.persist("EvIT3")
        with self.assertRaises(Exception):
            process("EvIT3", self.store, self.proc)
        self.assertNotEqual(self.store.get("EvIT3")["status"], "processed")
        self.assertEqual(len(calls("/notify")), 0)

    def test_http200_functional_error_not_success_notify(self):
        mock("/control", {"mode": {"notify": "err200"}})
        self.persist("EvIT4")
        try:
            process("EvIT4", self.store, self.proc)
        except Exception:
            pass
        self.assertNotEqual(self.store.get("EvIT4")["status"], "processed")

    def test_duplicate_event_not_reprocessed(self):
        self.persist("EvIT5")
        self.assertTrue(process("EvIT5", self.store, self.proc)["complete"])
        raw, headers = envelope(event_id="EvIT5", text="una nota larga sobre arquitectura")
        again = receive(raw, headers, SECRET, self.store, now=NOW)
        self.assertTrue(again["duplicate"])
        process("EvIT5", self.store, self.proc)
        self.assertEqual(len(calls("/anthropic")), 1)
        self.assertEqual(len(calls("/supabase-insert")), 1)
        self.assertEqual(len(calls("/notify")), 1)

    def test_uncertain_blocks_following_steps(self):
        self.persist("EvIT6")
        self.store.mark("EvIT6", "classify", "done", classification={"file_name": "auto_slack_EvIT6"})
        self.store.mark("EvIT6", "insert", "uncertain", error="timeout")
        r = process("EvIT6", self.store, self.proc)
        self.assertFalse(r["complete"])
        self.assertEqual(r.get("blocked"), "insert")
        self.assertEqual(calls("/supabase-insert"), [])
        self.assertEqual(calls("/notify"), [])

    def test_bad_internal_header_rejected(self):
        bad = N8nProcessor(N8N, HDR[0], "wrong", urllib_transport)
        self.persist("EvIT7")
        with self.assertRaises(Exception):
            bad.classify(json.loads(self.store.get("EvIT7")["payload"]))
        self.assertEqual(calls("/anthropic"), [])


if __name__ == "__main__":
    unittest.main()
