"""Valida offline las recetas SQL de reconciliacion de docs/DEPLOYMENT-PROCEDURE.md (seccion 10)
sobre el SQLite real del verificador."""
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path

from verifier import EventStore, receive, process, recover
from test_verifier import FakeProcessor, envelope, SECRET, NOW

DOC = (Path(__file__).resolve().parents[3] / "docs" / "DEPLOYMENT-PROCEDURE.md").read_text()


def recipe(marker):
    """Devuelve la sentencia 'update events ...' que sigue a `marker` en el documento."""
    tail = DOC[DOC.index(marker):]
    m = re.search(r"```sql\n(update events.*?;)\n```", tail, re.S)
    return m.group(1)


class Reconcile(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "e.sqlite"
        self.store = EventStore(self.path)
        raw, headers = envelope(event_id="EvREC")
        receive(raw, headers, SECRET, self.store, now=NOW)
        self.proc = FakeProcessor()
        self.store.mark("EvREC", "classify", "done", classification={"summary": "x"})
        self.store.mark("EvREC", "insert", "done")
        self.store.mark("EvREC", "notify", "uncertain", error="timeout")
        self.store.mark_failed("EvREC", "notify incierto")

    def tearDown(self):
        self.dir.cleanup()

    def run_sql(self, sql):
        sql = sql.replace("<event_id>", "EvREC")
        with sqlite3.connect(self.path) as c:
            c.execute(sql)

    def test_uncertain_blocks_until_reconciled(self):
        r = process("EvREC", self.store, self.proc)
        self.assertEqual(r.get("blocked"), "notify")
        self.assertEqual(self.proc.calls, [])

    def test_published_recipe_completes_without_resending(self):
        self.run_sql(recipe("**Paso 3a"))
        out = recover("EvREC", self.store, self.proc)
        self.assertTrue(out["recovered"])
        self.assertEqual(self.proc.calls, [])
        self.assertEqual(self.store.get("EvREC")["status"], "processed")

    def test_retry_recipe_resends_only_the_notification(self):
        self.run_sql(recipe("**Paso 3b"))
        out = recover("EvREC", self.store, self.proc)
        self.assertTrue(out["recovered"])
        self.assertEqual(self.proc.calls, ["notify"])
        self.assertEqual(self.store.get("EvREC")["status"], "processed")


if __name__ == "__main__":
    unittest.main()
