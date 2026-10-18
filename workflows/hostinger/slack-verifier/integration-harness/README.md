# Harness de integración local (solo pruebas, servicios simulados)

Todo es local y descartable. Nada se conecta a Supabase, Slack, Anthropic ni a Hostinger.

- `mock.py`: Anthropic, Supabase (REST de `metadata` y RPC `crosslink_entry`) y Slack simulados en 127.0.0.1:9100. Registra las llamadas. Modos: `ok`, `err200` (HTTP 200 con `ok:false`), `drop` (corta la conexión: resultado incierto), `slow`.
- `pg_setup.py`: crea un PostgreSQL **local** (puerto 5544) con la estructura verificada de `metadata` (sin UNIQUE, columnas `jsonb`) y aplica las migraciones preparadas de `db/prepared-migrations/`. Con `--no-migrations` las omite (para reproducir el fallo de `on_conflict` sin UNIQUE).
- PostgREST local (`postgrest.conf.example`, puerto 3000) sirve la tabla `notification_reservations` y `metadata` con un JWT ficticio firmado con un secreto de prueba. Así la atomicidad de la reserva la da la clave primaria de un Postgres real, no un simulador.
- `sync.sh`: reescribe URLs en **copias temporales** de los workflows, las importa en **dos instancias de n8n 2.43.7** (5680 y 5681, réplicas con carpeta y SQLite propias; la segunda necesita `N8N_RUNNERS_BROKER_PORT=5689` para no chocar con el broker 5679) y las arranca. No toca los JSON del repo.
- `make_jwt.py`: genera el JWT ficticio para PostgREST (copiar `postgrest.conf.example` a `postgrest.conf` con un secreto local propio).
- `restart_n8n.sh`: reinicia las dos instancias (prueba de reinicio).
- Rutas absolutas en los scripts (`/workspace/...`): ajustar. Requiere n8n 2.43.7 y Node 24, PostgreSQL (p. ej. `embedded-postgres` de npm), PostgREST y `psycopg`.

Pruebas (con `NEYEN_IT=1`):
`python3 -m unittest test_integration test_integration_chain test_integration_reservation test_migrations`
Reinicio: añadir `NEYEN_RESTART_SCRIPT=/ruta/restart_n8n.sh`.

El canal de respaldo de pruebas (`CTESTFALLBACK`) solo existe en la copia temporal; en el repo `CONFIGURED_CHANNEL` queda vacío.
