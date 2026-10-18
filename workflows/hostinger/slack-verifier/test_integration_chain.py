"""Integración local: NEYEN-crosslink, NEYEN-crosslink-notify y la cadena
ingest -> crosslink -> aviso. Opt-in: NEYEN_IT=1. Solo servicios simulados.

Requiere en n8n los workflows importados con URLs reescritas a los simuladores:
wf01-ingest-chain apunta al wf02 real de n8n, wf02 al wf03 real.
"""
import json
import os
import sys
import tempfile
import uuid
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


def uid(prefix):
    return prefix + uuid.uuid4().hex[:8]


def reset(**mode):
    base = {"supabase": "ok", "anthropic": "ok", "notify": "ok", "rpc": "five", "slack": "ok"}
    base.update(mode)
    mock("/control", {"reset": True, "mode": base})


@unittest.skipUnless(os.environ.get("NEYEN_IT") == "1", "integración opt-in")
class Crosslink(unittest.TestCase):
    def test_five_related_notifies_once_in_origin_channel(self):
        reset()
        fn = uid("auto_slack_A")
        status, body = post("/webhook/wf02-crosslink", {"file_name": fn, "channel_id": "CORIGIN"})
        self.assertEqual(status, 200)
        self.assertEqual(calls("/supabase-rpc")[0]["body"], {"p_file_name": fn})
        slack = calls("/slack")
        self.assertEqual(len(slack), 1)
        self.assertEqual(slack[0]["body"]["channel"], "CORIGIN")
        self.assertIn(fn, slack[0]["body"]["text"])
        self.assertIn("old_0", slack[0]["body"]["text"])

    def test_direct_duplicate_calls_do_not_repeat_notification(self):
        reset()
        fn = uid("auto_slack_DUP")
        first = post("/webhook/wf02-crosslink", {"file_name": fn, "channel_id": "CORIGIN"})
        second = post("/webhook/wf02-crosslink", {"file_name": fn, "channel_id": "CORIGIN"})
        third = post("/webhook/wf02-crosslink", {"file_name": fn, "channel_id": "CORIGIN"})
        self.assertEqual(first[0], 200)
        self.assertTrue(second[1].get("duplicate") and third[1].get("duplicate"))
        self.assertEqual(len(calls("/slack")), 1)

    def test_fewer_than_five_does_not_notify(self):
        reset(rpc="two")
        fn = uid("auto_slack_B")
        status, body = post("/webhook/wf02-crosslink", {"file_name": fn, "channel_id": "CORIGIN"})
        self.assertEqual(status, 200)
        self.assertEqual(body.get("file_name"), fn)
        self.assertEqual(calls("/slack"), [])

    def test_missing_file_name_fails_without_calls(self):
        reset()
        status, _ = post("/webhook/wf02-crosslink", {"x": 1})
        self.assertGreaterEqual(status, 400)
        self.assertEqual(calls("/supabase-rpc"), [])

    def test_rpc_functional_error_is_visible_and_not_notified(self):
        reset(rpc="err200")
        status, body = post("/webhook/wf02-crosslink", {"file_name": uid("auto_slack_C"), "channel_id": "CORIGIN"})
        self.assertEqual(status, 200)
        self.assertTrue(body.get("code") and body.get("message"))
        self.assertEqual(calls("/slack"), [])

    def test_rpc_entry_not_found_is_error_status_and_not_notified(self):
        reset(rpc="notfound")
        status, body = post("/webhook/wf02-crosslink", {"file_name": uid("auto_slack_NF"), "channel_id": "CORIGIN"})
        self.assertEqual((status, body.get("status")), (200, "error"))
        self.assertEqual(calls("/slack"), [])

    def test_bad_header_rejected(self):
        reset()
        status, _ = post("/webhook/wf02-crosslink", {"file_name": uid("auto_slack_D")}, header="wrong")
        self.assertIn(status, (401, 403))
        self.assertEqual(calls("/supabase-rpc"), [])

    def test_no_origin_channel_and_no_configured_channel_is_blocked_not_posted(self):
        reset()
        status, body = post("/webhook/wf02-crosslink-nofb", {"file_name": uid("auto_slack_NC")})
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "blocked")
        self.assertEqual(body.get("blocker"), "sin_canal_de_destino")
        self.assertEqual(calls("/slack"), [])

    def test_no_origin_channel_uses_only_explicit_configured_channel(self):
        reset()
        status, _ = post("/webhook/wf02-crosslink", {"file_name": uid("auto_slack_CF")})
        self.assertEqual(status, 200)
        self.assertEqual(calls("/slack")[0]["body"]["channel"], "CTESTFALLBACK")


@unittest.skipUnless(os.environ.get("NEYEN_IT") == "1", "integración opt-in")
class CrosslinkNotify(unittest.TestCase):
    def payload(self, **extra):
        p = {"entry_id": uid("e"), "file_name": uid("auto_slack_N"), "related_ids": ["r0", "r1", "r2", "r3", "r4"],
             "related_count": 5, "tags": ["a"], "entities": ["X"], "summary": "S", "channel_id": "CORIGIN"}
        p.update(extra)
        return p

    def test_single_slack_post_with_file_name_entries_and_channel(self):
        reset()
        p = self.payload()
        status, body = post("/webhook/wf03-crosslink-notify", p)
        self.assertEqual(status, 200)
        self.assertIs(body.get("ok"), True)
        slack = calls("/slack")
        self.assertEqual(len(slack), 1)
        self.assertEqual(slack[0]["body"]["channel"], "CORIGIN")
        self.assertIn(p["file_name"], slack[0]["body"]["text"])
        self.assertIn("old_4", slack[0]["body"]["text"])

    def test_without_related_ids_skips_supabase_read(self):
        reset()
        post("/webhook/wf03-crosslink-notify", self.payload(related_ids=[], related_count=0))
        self.assertEqual(calls("/supabase-related"), [])
        self.assertEqual(len(calls("/slack")), 1)

    def test_missing_entry_id_fails_without_post(self):
        reset()
        status, _ = post("/webhook/wf03-crosslink-notify", {"file_name": "x", "channel_id": "C1"})
        self.assertGreaterEqual(status, 400)
        self.assertEqual(calls("/slack"), [])

    def test_slack_ok_false_is_failure_and_allows_retry_without_duplicating(self):
        p = self.payload()
        reset(slack="err200")
        status, _ = post("/webhook/wf03-crosslink-notify", p)
        self.assertGreaterEqual(status, 400)
        mock("/control", {"mode": {"slack": "ok"}})
        status, body = post("/webhook/wf03-crosslink-notify", p)
        self.assertEqual((status, body.get("ok")), (200, True))
        again = post("/webhook/wf03-crosslink-notify", p)
        self.assertTrue(again[1].get("duplicate"))
        self.assertEqual(len(calls("/slack")), 2)  # 1 fallido + 1 correcto, ningun duplicado

    def test_direct_duplicate_posts_once(self):
        reset()
        p = self.payload()
        post("/webhook/wf03-crosslink-notify", p)
        again = post("/webhook/wf03-crosslink-notify", p)
        self.assertTrue(again[1].get("duplicate"))
        self.assertEqual(len(calls("/slack")), 1)

    def test_no_channel_anywhere_blocks_without_post(self):
        reset()
        status, body = post("/webhook/wf03-notify-nofb", self.payload(channel_id=""))
        self.assertEqual((status, body.get("status")), (200, "blocked"))
        self.assertEqual(calls("/slack"), [])

    def test_configured_channel_used_only_when_origin_missing(self):
        reset()
        post("/webhook/wf03-crosslink-notify", self.payload(channel_id=""))
        post("/webhook/wf03-crosslink-notify", self.payload(channel_id="CORIGIN"))
        self.assertEqual([c["body"]["channel"] for c in calls("/slack")], ["CTESTFALLBACK", "CORIGIN"])


def signed(eid, channel="C1"):
    from verifier import sign
    body = {"type": "event_callback", "event_id": eid,
            "event": {"type": "message", "text": "una nota larga sobre arquitectura", "user": "U1", "channel": channel}}
    raw = json.dumps(body).encode()
    return raw, {"X-Slack-Request-Timestamp": str(NOW), "X-Slack-Signature": sign(raw, str(NOW), SECRET)}


@unittest.skipUnless(os.environ.get("NEYEN_IT") == "1", "integración opt-in")
class Chain(unittest.TestCase):
    PATH = "/webhook/wf01-ingest-chain"

    def setUp(self):
        reset()
        self.tmp = tempfile.TemporaryDirectory()
        self.store = EventStore(Path(self.tmp.name) / "q.db")
        self.proc = N8nProcessor(N8N, HDR[0], HDR[1], urllib_transport)
        self.proc.url = N8N + self.PATH

    def tearDown(self):
        self.tmp.cleanup()

    def persist(self, eid, channel="C1"):
        raw, headers = signed(eid, channel)
        receive(raw, headers, SECRET, self.store, now=NOW)

    def counts(self):
        return tuple(len(calls(p)) for p in ("/anthropic", "/supabase-insert", "/supabase-rpc", "/slack"))

    def test_chain_delivers_data_and_origin_channel_end_to_end(self):
        eid = uid("EvCH")
        self.persist(eid, "CORIGIN")
        self.assertTrue(process(eid, self.store, self.proc)["complete"])
        self.assertEqual(self.counts(), (1, 1, 1, 1))
        self.assertEqual(calls("/supabase-insert")[0]["body"]["file_name"], "auto_slack_" + eid)
        self.assertEqual(calls("/supabase-rpc")[0]["body"], {"p_file_name": "auto_slack_" + eid})
        slack = calls("/slack")[0]["body"]
        self.assertEqual(slack["channel"], "CORIGIN")
        self.assertIn("auto_slack_" + eid, slack["text"])

    def test_chain_fewer_than_five_completes_without_slack(self):
        reset(rpc="two")
        eid = uid("EvCH")
        self.persist(eid)
        self.assertTrue(process(eid, self.store, self.proc)["complete"])
        self.assertEqual(calls("/slack"), [])

    def test_slack_ok_false_not_success_and_retry_does_not_duplicate(self):
        reset(slack="err200")
        eid = uid("EvCH")
        self.persist(eid)
        with self.assertRaises(Exception):
            process(eid, self.store, self.proc)
        self.assertNotEqual(self.store.get(eid)["status"], "processed")
        self.assertEqual(self.store.state(eid, "notify"), "uncertain")
        before = self.counts()
        mock("/control", {"mode": {"slack": "ok"}})
        r = process(eid, self.store, self.proc)
        self.assertFalse(r["complete"])
        self.assertEqual(r.get("blocked"), "notify")
        self.assertEqual(before, self.counts())

    def test_rpc_functional_error_not_success(self):
        reset(rpc="err200")
        eid = uid("EvCH")
        self.persist(eid)
        with self.assertRaises(Exception):
            process(eid, self.store, self.proc)
        self.assertNotEqual(self.store.get(eid)["status"], "processed")
        self.assertEqual(calls("/slack"), [])

    def test_rpc_entry_not_found_not_success(self):
        reset(rpc="notfound")
        eid = uid("EvCH")
        self.persist(eid)
        with self.assertRaises(Exception):
            process(eid, self.store, self.proc)
        self.assertNotEqual(self.store.get(eid)["status"], "processed")
        self.assertEqual(calls("/slack"), [])

    def test_duplicate_event_does_not_repeat_anything(self):
        eid = uid("EvCH")
        self.persist(eid)
        self.assertTrue(process(eid, self.store, self.proc)["complete"])
        raw, headers = signed(eid)
        self.assertTrue(receive(raw, headers, SECRET, self.store, now=NOW)["duplicate"])
        process(eid, self.store, self.proc)
        self.assertEqual(self.counts(), (1, 1, 1, 1))

    def test_replayed_notify_step_bypassing_worker_does_not_duplicate(self):
        eid = uid("EvCH")
        self.persist(eid, "CORIGIN")
        self.assertTrue(process(eid, self.store, self.proc)["complete"])
        payload = json.loads(self.store.get(eid)["payload"])
        again = self.proc.notify(payload, None)
        self.assertTrue(again.get("duplicate"))
        self.assertEqual(len(calls("/slack")), 1)

    def test_event_without_channel_and_without_config_is_blocked_and_recorded(self):
        self.proc.url = N8N + "/webhook/wf01-ingest-chain-nofb"
        eid = uid("EvCH")
        self.persist(eid, "")
        with self.assertRaises(Exception) as ctx:
            process(eid, self.store, self.proc)
        self.assertIn("sin_canal_de_destino", str(ctx.exception))
        self.assertEqual(calls("/slack"), [])
        row = self.store.get(eid)
        self.assertNotEqual(row["status"], "processed")
        self.assertIn("sin_canal_de_destino", row["last_error"] or "")


if __name__ == "__main__":
    unittest.main()
