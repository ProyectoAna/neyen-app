"""Prueba las migraciones PREPARADAS (db/prepared-migrations) contra un PostgreSQL LOCAL
de prueba (NEYEN_PG_DSN, p. ej. 'host=/tmp port=5544 user=postgres'). Nunca contra Supabase.
Opt-in: NEYEN_IT=1 y psycopg instalado."""
import os
import unittest
from pathlib import Path

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None

MIG = Path(__file__).resolve().parents[3] / "db" / "prepared-migrations"
DSN = os.environ.get("NEYEN_PG_DSN", "host=/tmp port=5544 user=postgres")
TABLE = """create table public.metadata (id uuid primary key default gen_random_uuid(), file_name text not null,
  source text, created_at timestamptz default now())"""


def sql(name):
    return (MIG / name).read_text()


@unittest.skipUnless(os.environ.get("NEYEN_IT") == "1" and psycopg, "integración opt-in (psycopg)")
class Migrations(unittest.TestCase):
    def setUp(self):
        self.db = "mig_" + os.urandom(4).hex()
        with psycopg.connect(DSN + " dbname=postgres", autocommit=True) as c:
            c.execute(f"create database {self.db}")
        self.c = psycopg.connect(DSN + f" dbname={self.db}", autocommit=True)
        self.c.execute("create schema if not exists public")
        self.c.execute(TABLE)
        self.c.execute("do $$ begin if not exists (select 1 from pg_roles where rolname='anon') then create role anon nologin; end if; if not exists (select 1 from pg_roles where rolname='authenticated') then create role authenticated nologin; end if; end $$")

    def tearDown(self):
        self.c.close()
        with psycopg.connect(DSN + " dbname=postgres", autocommit=True) as c:
            c.execute(f"drop database if exists {self.db} with (force)")

    def has_unique(self):
        return self.c.execute("select count(*) from pg_constraint where conname='metadata_file_name_key'").fetchone()[0] == 1

    def test_precheck_is_read_only_and_runs_on_clean_data(self):
        self.c.execute("insert into public.metadata(file_name) values ('a'),('b')")
        before = self.c.execute("select count(*) from public.metadata").fetchone()[0]
        for stmt in [s for s in sql("001_precheck_metadata_file_name.sql").split(";") if s.strip()]:
            body = "\n".join(l for l in stmt.splitlines() if not l.strip().startswith("--")).strip()
            if not body:
                continue
            self.assertTrue(body.lower().startswith("select"), body[:40])
            self.c.execute(body)
        self.assertEqual(before, self.c.execute("select count(*) from public.metadata").fetchone()[0])

    def test_precheck_detects_duplicates(self):
        self.c.execute("insert into public.metadata(file_name) values ('a'),('a'),('b'),(' B ')")
        rows = self.c.execute("select file_name from public.metadata group by file_name having count(*)>1").fetchall()
        self.assertEqual(rows, [("a",)])

    def test_up_applies_and_is_idempotent_and_enables_upsert(self):
        self.c.execute("insert into public.metadata(file_name) values ('a'),('b')")
        self.c.execute(sql("001_metadata_file_name_unique.up.sql"))
        self.assertTrue(self.has_unique())
        self.c.execute(sql("001_metadata_file_name_unique.up.sql"))  # segunda vez: sin cambios
        self.assertTrue(self.has_unique())
        self.c.execute("insert into public.metadata(file_name, source) values ('a','x') on conflict (file_name) do update set source = excluded.source")
        self.assertEqual(self.c.execute("select count(*) from public.metadata where file_name='a'").fetchone()[0], 1)

    def test_up_aborts_without_changes_when_duplicates(self):
        self.c.execute("insert into public.metadata(file_name) values ('a'),('a')")
        with self.assertRaises(psycopg.errors.RaiseException):
            self.c.execute(sql("001_metadata_file_name_unique.up.sql"))
        self.c.execute("rollback") if self.c.info.transaction_status != psycopg.pq.TransactionStatus.IDLE else None
        self.assertFalse(self.has_unique())
        self.assertEqual(self.c.execute("select count(*) from public.metadata").fetchone()[0], 2)

    def test_up_aborts_on_empty_file_name(self):
        self.c.execute("insert into public.metadata(file_name) values ('a'),('  ')")
        with self.assertRaises(psycopg.errors.RaiseException):
            self.c.execute(sql("001_metadata_file_name_unique.up.sql"))
        self.c.execute("rollback") if self.c.info.transaction_status != psycopg.pq.TransactionStatus.IDLE else None
        self.assertFalse(self.has_unique())

    def test_down_rolls_back_without_touching_data(self):
        self.c.execute("insert into public.metadata(file_name) values ('a')")
        self.c.execute(sql("001_metadata_file_name_unique.up.sql"))
        self.c.execute(sql("001_metadata_file_name_unique.down.sql"))
        self.assertFalse(self.has_unique())
        self.c.execute(sql("001_metadata_file_name_unique.down.sql"))  # idempotente
        self.assertEqual(self.c.execute("select count(*) from public.metadata").fetchone()[0], 1)

    def test_reservations_up_down(self):
        self.c.execute(sql("002_notification_reservations.up.sql"))
        self.c.execute("insert into public.notification_reservations(entry_id,state) values ('e','inflight')")
        with self.assertRaises(psycopg.errors.UniqueViolation):
            self.c.execute("insert into public.notification_reservations(entry_id,state) values ('e','inflight')")
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.c.execute("insert into public.notification_reservations(entry_id,state) values ('f','bogus')")
        self.assertTrue(self.c.execute("select relrowsecurity from pg_class where relname='notification_reservations'").fetchone()[0])
        self.c.execute(sql("002_notification_reservations.up.sql"))  # idempotente
        self.c.execute(sql("002_notification_reservations.down.sql"))
        self.assertIsNone(self.c.execute("select to_regclass('public.notification_reservations')").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
