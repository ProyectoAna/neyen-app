"""Integración local: NEYEN-crosslink, NEYEN-crosslink-notify y la cadena
ingest -> crosslink -> aviso. Opt-in: NEYEN_IT=1. Solo servicios simulados.

Requiere en n8n los workflows importados con URLs reescritas a los simuladores:
wf01-ingest-chain apunta al wf02 real de n8n, wf02 al wf03 real.
"""
import json
import os
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verifier import EventStore, receive, process
from worker import N8nProcessor, urllib_transport
from test_verifier import envelope, SECRET, NOW
from test_integration import N8N, HDR, mock, calls


def post(path, body, header=HDR[1]):
    req = urllib.request.Request(
        N8N + path, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", HDR[0]: header},
    )
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {}


def reset(**mode):
    base = {"supabase": "ok", "anthropic": "ok", "notify": "ok", "rpc": "five", "slack": "ok"}
    base.update(mode)
    mock("/control", {"reset": True, "mode": base})


@unittest.skipUnless(os.environ.get("NEYEN_IT") == "1", "integración opt-in")
class Crosslink(unittest.TestCase):
    def test_five_related_notifies_once_with_entries(self):
        reset()
        status, body = post("/webhook/wf02-crosslink", {"file_name": "auto_slack_A"})
        self.assertEqual(status, 200)
        self.assertEqual(calls("/supabase-rpc")[0]["body"], {"p_file_name": "auto_slack_A"})
        slack = calls("/slack")
        self.assertEqual(len(slack), 1)
        self.assertIn("auto_slack_A", slack[0]["body"]["text"])
        self.assertIn("old_0", slack[0]["body"]["text"])

    def test_fewer_than_five_does_not_notify(self):
        reset(rpc="two")
        status, body = post("/webhook/wf02-crosslink", {"file_name": "auto_slack_B"})
        self.assertEqual(status, 200)
        self.assertEqual(body.get("file_name"), "auto_slack_B")
        self.assertEqual(calls("/slack"), [])

    def test_missing_file_name_fails_without_calls(self):
        reset()
        status, _ = post("/webhook/wf02-crosslink", {"x": 1})
        self.assertGreaterEqual(status, 400)
        self.assertEqual(calls("/supabase-rpc"), [])

    def test_rpc_functional_error_is_visible_and_not_notified(self):
        reset(rpc="err200")
        status, body = post("/webhook/wf02-crosslink", {"file_name": "auto_slack_C"})
        self.assertEqual(status, 200)
        self.assertTrue(body.get("code") and body.get("message"))
        self.assertEqual(calls("/slack"), [])

    def test_bad_header_rejected(self):
        reset()
        status, _ = post("/webhook/wf02-crosslink", {"file_name": "auto_slack_D"}, header="wrong")
        self.assertIn(status, (401, 403))
        self.assertEqual(calls("/supabase-rpc"), [])


@unittest.skipUnless(os.environ.get("NEYEN_IT") == "1", "integración opt-in")
class CrosslinkNotify(unittest.TestCase):
    PAYLOAD = {"entry_id": "e1", "file_name": "auto_slack_N", "related_ids": ["r0", "r1", "r2", "r3", "r4"],
               "related_count": 5, "tags": ["a"], "entities": ["X"], "summary": "S"}

    def test_single_slack_post_with_file_name_and_entries(self):
        reset()
        status, body = post("/webhook/wf03-crosslink-notify", self.PAYLOAD)
        self.assertEqual(status, 200)
        slack = calls("/slack")
        self.assertEqual(len(slack), 1)
        self.assertIn("auto_slack_N", slack[0]["body"]["text"])
        self.assertIn("old_4", slack[0]["body"]["text"])

    def test_without_related_ids_skips_supabase_read(self):
        reset()
        post("/webhook/wf03-crosslink-notify", dict(self.PAYLOAD, related_ids=[], related_count=0))
        self.assertEqual(calls("/supabase-related"), [])
        self.assertEqual(len(calls("/slack")), 1)

    def test_missing_entry_id_fails_without_post(self):
        reset()
        status, _ = post("/webhook/wf03-crosslink-notify", {"file_name": "x"})
        self.assertGreaterEqual(status, 400)
        self.assertEqual(calls("/slack"), [])

    def test_slack_ok_false_is_returned_not_hidden(self):
        reset(slack="err200")
        status, body = post("/webhook/wf03-crosslink-notify", self.PAYLOAD)
        self.assertEqual(status, 200)
        self.assertIs(body.get("ok"), False)


@unittest.skipUnless(os.environ.get("NEYEN_IT") == "1", "integración opt-in")
class Chain(unittest.TestCase):
    def setUp(self):
        reset()
        self.tmp = tempfile.TemporaryDirectory()
        self.store = EventStore(Path(self.tmp.name) / "q.db")
        self.proc = N8nProcessor(N8N, HDR[0], HDR[1], urllib_transport)
        self.proc.url = N8N + "/webhook/wf01-ingest-chain"

    def tearDown(self):
        self.tmp.cleanup()

    def persist(self, eid):
        raw, headers = envelope(event_id=eid, text="una nota larga sobre arquitectura")
        receive(raw, headers, SECRET, self.store, now=NOW)

    def test_chain_delivers_data_end_to_end(self):
        self.persist("EvCH1")
        self.assertTrue(process("EvCH1", self.store, self.proc)["complete"])
        self.assertEqual(len(calls("/anthropic")), 1)
        self.assertEqual(calls("/supabase-insert")[0]["body"]["file_name"], "auto_slack_EvCH1")
        self.assertEqual(calls("/supabase-rpc")[0]["body"], {"p_file_name": "auto_slack_EvCH1"})
        slack = calls("/slack")
        self.assertEqual(len(slack), 1)
        self.assertIn("auto_slack_EvCH1", slack[0]["body"]["text"])

    def test_chain_fewer_than_five_completes_without_slack(self):
        reset(rpc="two")
        self.persist("EvCH2")
        self.assertTrue(process("EvCH2", self.store, self.proc)["complete"])
        self.assertEqual(calls("/slack"), [])

    def test_slack_functional_error_not_success_and_retry_does_not_duplicate(self):
        reset(slack="err200")
        self.persist("EvCH3")
        with self.assertRaises(Exception):
            process("EvCH3", self.store, self.proc)
        row = self.store.get("EvCH3")
        self.assertNotEqual(row["status"], "processed")
        self.assertEqual(self.store.state("EvCH3", "notify"), "uncertain")
        before = (len(calls("/anthropic")), len(calls("/supabase-insert")),
                  len(calls("/supabase-rpc")), len(calls("/slack")))
        reset_mode = {"mode": {"slack": "ok"}}
        mock("/control", reset_mode)
        r = process("EvCH3", self.store, self.proc)
        self.assertFalse(r["complete"])
        self.assertEqual(r.get("blocked"), "notify")
        after = (len(calls("/anthropic")), len(calls("/supabase-insert")),
                 len(calls("/supabase-rpc")), len(calls("/slack")))
        self.assertEqual(before, after)

    def test_rpc_functional_error_not_success(self):
        reset(rpc="err200")
        self.persist("EvCH4")
        with self.assertRaises(Exception):
            process("EvCH4", self.store, self.proc)
        self.assertNotEqual(self.store.get("EvCH4")["status"], "processed")
        self.assertEqual(calls("/slack"), [])

    def test_duplicate_event_does_not_repeat_anything(self):
        self.persist("EvCH5")
        self.assertTrue(process("EvCH5", self.store, self.proc)["complete"])
        raw, headers = envelope(event_id="EvCH5", text="una nota larga sobre arquitectura")
        self.assertTrue(receive(raw, headers, SECRET, self.store, now=NOW)["duplicate"])
        process("EvCH5", self.store, self.proc)
        for p in ("/anthropic", "/supabase-insert", "/supabase-rpc", "/slack"):
            self.assertEqual(len(calls(p)), 1, p)


if __name__ == "__main__":
    unittest.main()
