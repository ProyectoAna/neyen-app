import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from queue import Queue

sys.path.insert(0, str(Path(__file__).resolve().parent))
from server import accept, serve
from verifier import EventStore, Rejected, forward_body, planned_steps, receive, recover, sign, process
from worker import N8nProcessor, work_available, work_once, work_queue


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
        result = recover(stored["event_id"], self.store, recovery)
        self.assertEqual(recovery.calls, [])
        self.assertEqual(result.get("blocked"), "insert")
        self.assertEqual(self.store.state("EvTEST", "notify"), "pending")
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

    def test_second_worker_does_not_run_while_claimed(self):
        raw, headers = envelope()
        stored = receive(raw, headers, SECRET, self.store, now=NOW)
        self.assertTrue(self.store.try_claim(stored["event_id"], "worker-a", NOW))
        other = EventStore(self.store.path)
        processor = FakeProcessor()
        result = process(stored["event_id"], other, processor, owner="worker-b", now=NOW)
        self.assertTrue(result["busy"])
        self.assertEqual(processor.calls, [])

    def test_server_acks_after_persist_and_does_not_process(self):
        raw, headers = envelope(event_id="EvSERVER")
        queue = Queue()
        status, body, enqueued = accept(raw, headers, SECRET, self.store, queue, now=NOW)
        self.assertEqual(status, 200)
        self.assertEqual(body, {"ok": True})
        self.assertTrue(enqueued)
        self.assertEqual(queue.get_nowait(), "EvSERVER")
        self.assertIsNotNone(self.store.get("EvSERVER"))
        again = accept(raw, headers, SECRET, self.store, queue, now=NOW)
        self.assertFalse(again[2])

    def test_worker_sends_one_step_with_internal_header(self):
        raw, headers = envelope(event_id="EvWORK")
        stored = receive(raw, headers, SECRET, self.store, now=NOW)
        seen = []

        def transport(url, request_headers, body):
            seen.append((url, request_headers, body))
            if body["only_step"] == "classify":
                return {"status": 200, "body": {"summary": "ok", "file_name": "auto_slack_EvWORK", "event_id": "EvWORK"}}
            return {"status": 200, "body": {}}

        processor = N8nProcessor(
            "https://n8n.thespiralwithin.ai",
            "X-Internal-Webhook",
            "cabecera-de-prueba",
            transport,
        )
        result = work_once(self.store, processor, stored["event_id"])
        self.assertTrue(result["complete"])
        self.assertEqual([item[2]["only_step"] for item in seen], ["classify", "insert", "notify"])
        self.assertEqual(seen[0][1]["X-Internal-Webhook"], "cabecera-de-prueba")
        self.assertTrue(seen[0][0].endswith("/webhook/wf01-ingest"))

    def test_worker_rejects_http200_with_functional_error(self):
        for step, body in (("classify", {"summary": "x"}), ("insert", {"code": "23502", "message": "x"}), ("notify", {"status": "error"})):
            processor = N8nProcessor("http://x", "H", "v", lambda u, h, b, body=body: {"status": 200, "body": body})
            payload = {"event_id": "E", "event": {"text": "t"}}
            with self.assertRaises(RuntimeError):
                getattr(processor, step)(payload, {"file_name": "f"}) if step != "classify" else processor.classify(payload)

    def test_local_server_rejects_bad_signature(self):
        queue = Queue()
        httpd = serve("127.0.0.1", 0, SECRET, self.store, queue)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            raw, headers = envelope(event_id="EvHTTP")
            headers["X-Slack-Signature"] = "v0=" + "ab" * 32
            req = urllib.request.Request(
                "http://127.0.0.1:%s/" % httpd.server_address[1],
                data=raw,
                headers=headers,
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(req, timeout=3)
            self.assertEqual(caught.exception.code, 401)
            caught.exception.close()
            self.assertTrue(queue.empty())
        finally:
            httpd.shutdown()
            thread.join(timeout=2)
            httpd.server_close()

    def test_worker_loop_processes_queued_event_once(self):
        raw, headers = envelope(event_id="EvQUEUE")
        queue = Queue()
        accept(raw, headers, SECRET, self.store, queue, now=NOW)
        processor = FakeProcessor()
        stop = threading.Event()

        def run():
            work_queue(queue, self.store, processor, stop)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        queue.join()
        stop.set()
        thread.join(timeout=2)
        self.assertEqual(processor.calls, ["classify", "insert", "notify"])
        self.assertEqual(self.store.get("EvQUEUE")["status"], "processed")

    def test_crash_after_insert_started_does_not_notify(self):
        raw, headers = envelope(event_id="EvCRASH")
        stored = receive(raw, headers, SECRET, self.store, now=NOW)
        self.store.mark(stored["event_id"], "classify", "done", classification={"summary": "ya clasificado"})
        self.store.mark(stored["event_id"], "insert", "started")
        processor = FakeProcessor()
        result = process(stored["event_id"], self.store, processor, now=NOW)
        self.assertEqual(result["blocked"], "insert")
        self.assertTrue(result["reconciliation"])
        self.assertEqual(processor.calls, [])
        self.assertNotIn("notify", processor.calls)
        self.assertNotIn(stored["event_id"], self.store.list_available())

    def test_restart_after_ack_keeps_event_available(self):
        raw, headers = envelope(event_id="EvRESTART")
        queue = Queue()
        status, _body, enqueued = accept(raw, headers, SECRET, self.store, queue, now=NOW)
        self.assertEqual(status, 200)
        self.assertTrue(enqueued)
        restarted = EventStore(self.store.path)
        self.assertIn("EvRESTART", restarted.list_available())
        outcomes = work_available(restarted, FakeProcessor())
        self.assertEqual(outcomes[0][1]["complete"], True)
        self.assertEqual(restarted.get("EvRESTART")["status"], "processed")

    def test_one_event_fails_and_the_next_is_processed(self):
        first, first_headers = envelope(event_id="EvBAD")
        second, second_headers = envelope(event_id="EvGOOD")
        receive(first, first_headers, SECRET, self.store, now=NOW)
        receive(second, second_headers, SECRET, self.store, now=NOW)

        class Selective(FakeProcessor):
            def classify(self, payload):
                if payload["event_id"] == "EvBAD":
                    self.calls.append("classify")
                    raise RuntimeError("claude no disponible")
                return super().classify(payload)

        processor = Selective()
        work_available(self.store, processor)
        self.assertEqual(self.store.state("EvBAD", "classify"), "uncertain")
        self.assertEqual(self.store.state("EvBAD", "notify"), "pending")
        self.assertEqual(self.store.get("EvGOOD")["status"], "processed")
        self.assertEqual(self.store.state("EvGOOD", "notify"), "done")
        again = FakeProcessor()
        work_available(self.store, again)
        self.assertEqual(again.calls, [])

    def test_receive_and_process_do_not_interfere(self):
        raw_a, headers_a = envelope(event_id="EvA")
        stored = receive(raw_a, headers_a, SECRET, self.store, now=NOW)
        started = threading.Event()
        release = threading.Event()
        errors = []

        class Slow(FakeProcessor):
            def classify(self, payload):
                started.set()
                release.wait(2)
                return super().classify(payload)

        def run_process():
            try:
                process(stored["event_id"], EventStore(self.store.path), Slow(), now=NOW)
            except Exception as exc:
                errors.append(exc)

        worker = threading.Thread(target=run_process)
        worker.start()
        self.assertTrue(started.wait(2))
        raw_b, headers_b = envelope(event_id="EvB")
        other = EventStore(self.store.path)
        received = receive(raw_b, headers_b, SECRET, other, now=NOW)
        release.set()
        worker.join(timeout=3)
        self.assertEqual(errors, [])
        self.assertTrue(received["persisted"])
        self.assertIsNotNone(other.get("EvB"))
        self.assertEqual(other.get("EvA")["status"], "processed")
        self.assertEqual(other.state("EvA", "notify"), "done")

    def test_authorized_claim_does_not_expire(self):
        raw, headers = envelope(event_id="EvCLAIM")
        stored = receive(raw, headers, SECRET, self.store, now=NOW)
        self.assertTrue(self.store.try_claim(stored["event_id"], "worker-a", NOW))
        later = EventStore(self.store.path)
        self.assertFalse(later.try_claim(stored["event_id"], "worker-b", NOW + 10_000))
        self.store.mark(stored["event_id"], "classify", "done", classification={"summary": "sigue autorizado"})
        current = later.get(stored["event_id"])
        self.assertEqual(current["claim_owner"], "worker-a")
        self.assertEqual(current["authorized"], 1)
        self.assertEqual(current["classify_state"], "done")
        processor = FakeProcessor()
        blocked = process(stored["event_id"], later, processor, owner="worker-b", now=NOW + 10_000)
        self.assertTrue(blocked["busy"])
        self.assertEqual(processor.calls, [])


if __name__ == "__main__":
    unittest.main()
