"""Prepara un PostgreSQL LOCAL de prueba con la estructura verificada de metadata
(sin UNIQUE, columnas jsonb) y, opcionalmente, aplica las migraciones preparadas.
Nunca se conecta a Supabase. Uso: pg_setup.py [--no-migrations]"""
import sys
from pathlib import Path
import psycopg

DSN = "host=/tmp port=5544 user=postgres dbname=%s"
MIG = Path(__file__).resolve().parents[4] / "db" / "prepared-migrations"

SCHEMA = """
do $$ begin
  if not exists (select 1 from pg_roles where rolname='anon') then create role anon nologin; end if;
  if not exists (select 1 from pg_roles where rolname='authenticated') then create role authenticated nologin; end if;
  if not exists (select 1 from pg_roles where rolname='service_role') then create role service_role nologin bypassrls; end if;
  if not exists (select 1 from pg_roles where rolname='authenticator') then create role authenticator noinherit login; end if;
end $$;
grant anon, authenticated, service_role to authenticator;
create table if not exists public.metadata (
  id uuid primary key default gen_random_uuid(),
  file_name text not null, type text, summary text, tags jsonb, entities jsonb,
  emotional_tone text, source text, themes jsonb, concepts jsonb, keywords jsonb,
  mime_type text, created_at timestamptz default now(), cluster text, related_ids jsonb,
  date_estimated text, timeline_group text, narrative_role text);
grant usage on schema public to anon, authenticated, service_role;
grant all on public.metadata to service_role;
"""


def main():
    skip = "--no-migrations" in sys.argv
    with psycopg.connect(DSN % "postgres", autocommit=True) as c:
        c.execute("drop database if exists neyen_test with (force)")
        c.execute("create database neyen_test")
    with psycopg.connect(DSN % "neyen_test", autocommit=True) as c:
        c.execute(SCHEMA)
        if not skip:
            for f in ("001_metadata_file_name_unique.up.sql", "002_notification_reservations.up.sql"):
                c.execute((MIG / f).read_text())
        c.execute("grant all on all tables in schema public to service_role")
    print("ok", "sin migraciones" if skip else "migraciones aplicadas (solo en BD local)")


if __name__ == "__main__":
    main()
