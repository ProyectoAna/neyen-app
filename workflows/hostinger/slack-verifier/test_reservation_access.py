"""La tabla notification_reservations NO debe ser accesible a clientes publicos.
Comprueba el catalogo y el acceso real via PostgREST con anon, authenticated y service_role.
Opt-in: NEYEN_IT=1, psycopg, PostgreSQL y PostgREST locales de prueba (nunca Supabase)."""
import os
import re
import subprocess
import sys
import unittest
import urllib.error
import urllib.request
from pathlib import Path

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None

HERE = Path(__file__).resolve().parent
MIG = HERE.parents[2] / "db" / "prepared-migrations" / "002_notification_reservations.up.sql"
DSN = os.environ.get("NEYEN_PG_DSN", "host=/tmp port=5544 user=postgres") + " dbname=" + os.environ.get("NEYEN_PG_DB", "neyen_test")
PGRST = os.environ.get("NEYEN_PGRST_URL", "http://127.0.0.1:3000")
CONF = os.environ.get("NEYEN_PGRST_CONF", "/workspace/n8ntest/postgrest.conf")


def jwt(role):
    return subprocess.check_output([sys.executable, str(HERE / "integration-harness" / "make_jwt.py"), CONF, role]).decode().strip()


def http(method, token, body=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(PGRST + "/notification_reservations" + ("?select=*" if method == "GET" else ""),
                                 method=method, headers=headers, data=body)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


class MigrationText(unittest.TestCase):
    """Offline: lo que dice la migracion preparada."""

    def test_migration_enables_rls_without_policies_and_revokes_public_roles(self):
        sql = MIG.read_text().lower()
        self.assertIn("enable row level security", sql)
        self.assertNotIn("create policy", sql)
        self.assertRegex(sql, r"revoke all on public\.notification_reservations from anon, authenticated")
        self.assertNotRegex(sql, r"grant .* to (anon|authenticated|public)")


@unittest.skipUnless(os.environ.get("NEYEN_IT") == "1" and psycopg, "integración opt-in (psycopg)")
class LocalCatalogAndAccess(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = psycopg.connect(DSN, autocommit=True)

    @classmethod
    def tearDownClass(cls):
        cls.c.close()

    def q(self, sql):
        return self.c.execute(sql).fetchall()

    def test_rls_enabled_and_no_policies(self):
        self.assertEqual(self.q("select relrowsecurity from pg_class where oid='public.notification_reservations'::regclass"), [(True,)])
        self.assertEqual(self.q("select count(*) from pg_policies where tablename='notification_reservations'"), [(0,)])

    def test_no_privileges_for_public_roles(self):
        for role in ("anon", "authenticated"):
            for priv in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"):
                self.assertEqual(self.q(f"select has_table_privilege('{role}','public.notification_reservations','{priv}')"), [(False,)], (role, priv))
        self.assertEqual(self.q("select count(*) from information_schema.role_table_grants where table_name='notification_reservations' and grantee in ('anon','authenticated','PUBLIC')"), [(0,)])

    def test_default_privileges_would_have_granted_so_revoke_is_what_protects(self):
        # el entorno imita los privilegios por defecto de Supabase: metadata si los tiene
        self.assertEqual(self.q("select has_table_privilege('anon','public.metadata','SELECT')"), [(True,)])

    def test_real_access_via_postgrest_by_role(self):
        for token in (None, jwt("anon"), jwt("authenticated")):
            for method, body in (("GET", None), ("POST", b'{"entry_id":"x","state":"done"}'),
                                 ("PATCH", b'{"state":"done"}'), ("DELETE", None)):
                self.assertIn(http(method, token, body), (401, 403), (bool(token), method))
        self.assertEqual(http("GET", jwt("service_role")), 200)


if __name__ == "__main__":
    unittest.main()
