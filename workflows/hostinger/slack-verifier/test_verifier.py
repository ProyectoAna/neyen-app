import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verifier import EventStore, Rejected, forward_body, planned_steps, receive, recover, sign, process


SECRET = "secreto-de-prueba"
NOW = 1_700_000_000


class FakeProcessor:
    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on

    def classify(self, payload):
        self.calls.append("classify")
        if self.fail_on == "classify":
            raise RuntimeError("claude no disponible")
        return {"summary": "ficha de prueba", "event_id": payload["event_id"]}

    def insert(self, payload, classification):
        self.calls.append("insert")
        if self.fail_on == "insert":
            raise RuntimeError("insercion fallida")
        return {"file_name": "auto_slack_" + payload["event_id"]}

    def notify(self, payload, classification):
        self.calls.append("notify")
        if self.fail_on == "notify":
            raise RuntimeError("aviso fallido")
        return {"sent": True}


def envelope(event_id="EvTEST", text="una nota", challenge=None, timestamp=NOW):
    if challenge:
        body = {"type": "url_verification", "challenge": challenge}
    else:
        body = {"type": "event_callback", "event_id": event_id, "event": {"type": "message", "text": text, "user": "U1", "channel": "C1"}}
    raw = json.dumps(body).encode()
    headers = {
        "X-Slack-Request-Timestamp": str(timestamp),
        "X-Slack-Signature": sign(raw, timestamp, SECRET),
    }
    return raw, headers


class VerifierTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.store = EventStore(Path(self.dir.name) / "events.sqlite")

    def tearDown(self):
        self.dir.cleanup()

    def test_valid_signature_persists_before_ack(self):
        raw, headers = envelope()
        result = receive(raw, headers, SECRET, self.store, now=NOW)
        self.assertEqual(result["status"], 200)
        self.assertTrue(result["persisted"])
        self.assertIsNotNone(self.store.get("EvTEST"))

    def test_invalid_signature_is_rejected_and_not_stored(self):
        raw, headers = envelope()
        headers["X-Slack-Signature"] = "v0=" + "ab" * 32
        with self.assertRaises(Rejected) as caught:
            receive(raw, headers, SECRET, self.store, now=NOW)
        self.assertEqual(caught.exception.status, 401)
        self.assertIsNone(self.store.get("EvTEST"))

    def test_old_timestamp_is_rejected(self):
        raw, headers = envelope(timestamp=NOW - 301)
        with self.assertRaises(Rejected) as caught:
            receive(raw, headers, SECRET, self.store, now=NOW)
        self.assertEqual(caught.exception.reason, "timestamp antiguo")

    def test_challenge_requires_valid_signature(self):
        raw, headers = envelope(challenge="reto-ficticio")
        ok = receive(raw, headers, SECRET, self.store, now=NOW)
        self.assertEqual(ok["body"]["challenge"], "reto-ficticio")
        headers["X-Slack-Signature"] = "v0=" + "cd" * 32
        with self.assertRaises(Rejected):
            receive(raw, headers, SECRET, self.store, now=NOW)

    def test_repeated_event_does_not_process_again(self):
        raw, headers = envelope()
        first = receive(raw, headers, SECRET, self.store, now=NOW)
        processor = FakeProcessor()
        process(first["event_id"], self.store, processor)
        second = receive(raw, headers, SECRET, self.store, now=NOW)
        self.assertTrue(second["duplicate"])
        again = FakeProcessor()
        process(second["event_id"], self.store, again)
        self.assertEqual(again.calls, [])

    def test_failure_after_persist_does_not_ack_early_and_recovery_skips_done_steps(self):
        raw, headers = envelope()
        stored = receive(raw, headers, SECRET, self.store, now=NOW)
        self.assertEqual(stored["status"], 200)
        failing = FakeProcessor(fail_on="insert")
        with self.assertRaises(RuntimeError):
            process(stored["event_id"], self.store, failing)
        self.assertEqual(failing.calls, ["classify", "insert"])
        self.assertEqual(self.store.get("EvTEST")["status"], "failed")
        recovery = FakeProcessor()
        recover(stored["event_id"], self.store, recovery)
        self.assertEqual(recovery.calls, ["notify"])
        self.assertNotIn("classify", recovery.calls)
        self.assertNotIn("insert", recovery.calls)
        self.assertEqual(self.store.get("EvTEST")["status"], "failed")

    def test_uncertain_notification_is_not_repeated(self):
        raw, headers = envelope()
        stored = receive(raw, headers, SECRET, self.store, now=NOW)
        failing = FakeProcessor(fail_on="notify")
        with self.assertRaises(RuntimeError):
            process(stored["event_id"], self.store, failing)
        recovery = FakeProcessor()
        recover(stored["event_id"], self.store, recovery)
        self.assertNotIn("notify", recovery.calls)
        self.assertEqual(self.store.state("EvTEST", "notify"), "uncertain")

    def test_command_does_not_plan_claude_or_insert(self):
        self.assertEqual(planned_steps({"event": {"text": "/tag nota"}}), ["notify"])

    def test_internal_endpoint_rejects_bypass(self):
        workflow = json.loads(Path(__file__).resolve().parents[1].joinpath("essential/NEYEN-ingest.json").read_text())
        webhook = next(node for node in workflow["nodes"] if node["name"] == "Webhook Trigger")
        self.assertEqual(webhook["parameters"]["authentication"], "headerAuth")
        self.assertEqual(webhook["credentials"]["httpHeaderAuth"]["name"], "Internal Webhook Header")
        body = forward_body("EvTEST", {"event": {"text": "hola"}}, "classify")
        self.assertEqual(body["verifier"], "slack-verifier")
        self.assertNotIn("secret", json.dumps(body).lower())


if __name__ == "__main__":
    unittest.main()
