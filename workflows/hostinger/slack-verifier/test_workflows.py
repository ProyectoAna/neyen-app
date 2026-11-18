"""Pruebas estructurales offline de los JSON de essential/. Sin red."""
import json
import unittest
from pathlib import Path

ESS = Path(__file__).resolve().parent.parent / "essential"


def workflows():
    for p in sorted(ESS.glob("*.json")):
        yield p.name, json.loads(p.read_text())


class WorkflowStructure(unittest.TestCase):
    def test_no_deprecated_function_nodes(self):
        for name, d in workflows():
            for n in d["nodes"]:
                self.assertNotEqual(n["type"], "n8n-nodes-base.function", (name, n["name"]))

    def test_every_slack_post_is_followed_by_ok_check(self):  # notify usa 'Evaluar Slack' (ok===true)
        for name, d in workflows():
            by = {n["name"]: n for n in d["nodes"]}
            for n in d["nodes"]:
                if "chat.postMessage" not in json.dumps(n["parameters"]):
                    continue
                nxt = [t["node"] for out in d["connections"].get(n["name"], {}).get("main", []) for t in out]
                self.assertTrue(nxt, (name, n["name"], "sin comprobacion de ok"))
                for t in nxt:
                    self.assertIn("ok", by[t]["parameters"].get("jsCode", ""), (name, n["name"]))
                    self.assertIn("true", by[t]["parameters"]["jsCode"], (name, n["name"]))

    def test_reservation_is_external_and_atomic_not_static_data(self):
        for name, d in workflows():
            self.assertNotIn("getWorkflowStaticData", json.dumps(d), name)
        _, d = next(x for x in workflows() if x[0] == "NEYEN-crosslink-notify.json")
        by = {n["name"]: n for n in d["nodes"]}
        ins = by["Reservar aviso (INSERT atomico)"]["parameters"]
        self.assertEqual(ins["method"], "POST")
        self.assertIn("notification_reservations", ins["url"])
        # 409 = reserva existente; el resto de codigos no publica
        self.assertIn("409", by["Evaluar reserva"]["parameters"]["jsCode"])
        # incierto exige reconciliacion; rechazo explicito libera
        self.assertIn("uncertain", by["Marcar aviso como incierto"]["parameters"]["jsonBody"])
        self.assertEqual(by["Liberar reserva (rechazo explicito)"]["parameters"]["method"], "DELETE")
        self.assertIn("state=eq.inflight", by["Liberar reserva (rechazo explicito)"]["parameters"]["url"])
        self.assertEqual(by["Post to Slack"].get("onError"), "continueRegularOutput")

    def test_migrations_are_prepared_not_in_supabase_dir(self):
        root = Path(__file__).resolve().parents[3]
        self.assertFalse((root / "supabase" / "migrations").exists())
        for f in ("001_metadata_file_name_unique.up.sql", "001_metadata_file_name_unique.down.sql",
                  "001_precheck_metadata_file_name.sql", "002_notification_reservations.up.sql",
                  "002_notification_reservations.down.sql"):
            self.assertTrue((root / "db" / "prepared-migrations" / f).exists(), f)

    def test_no_default_channel_in_notify(self):
        _, d = next(x for x in workflows() if x[0] == "NEYEN-crosslink-notify.json")
        code = next(n for n in d["nodes"] if n["name"] == "Parse Payload")["parameters"]["jsCode"]
        self.assertIn("const CONFIGURED_CHANNEL = '';", code)

    def test_origin_channel_is_forwarded(self):
        by = {n: {x["name"]: x for x in d["nodes"]} for n, d in workflows()}
        self.assertIn("channel_id", by["NEYEN-ingest.json"]["Notificar paso pendiente"]["parameters"]["jsonBody"])
        self.assertIn("channel_id", by["NEYEN-crosslink.json"]["Extract File Name"]["parameters"]["jsCode"])


if __name__ == "__main__":
    unittest.main()
