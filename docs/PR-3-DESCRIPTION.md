# PR 3 — Prepara la migración de workflows a Hostinger (descripción para copiar)

## Resumen

Sigue en borrador. No importa en producción, no publica, no fusiona, no despliega y **no aplica migraciones**. Las copias de `workflows/hostinger/` están desactivadas; los originales de `workflows/` no cambian. Drive Watch, Timeline y Weekly Digest quedan fuera de este despliegue.

## Entrada de Slack (`workflows/hostinger/slack-verifier/`, no desplegado)

- Firma de Slack sobre el cuerpo original; rechaza timestamps de más de cinco minutos. Challenge solo con firma válida.
- El evento se guarda en SQLite antes de confirmar. Un duplicado no se procesa otra vez. Un paso incierto bloquea los siguientes y exige reconciliación.
- El trabajador rechaza un HTTP 200 con error funcional (`error`, `status: error|blocked`, `ok: false`, `code`+`message`); el motivo queda en `last_error`.
- `wf01-ingest` exige `Internal Webhook Header`.

## Canal del aviso de crosslink

El `channel_id` del evento original viaja por ingest → crosslink → crosslink-notify. `CONFIGURED_CHANNEL` (en `Parse Payload`) **sigue vacío**. Un evento sin canal queda explícitamente bloqueado (`status: blocked`, `blocker: sin_canal_de_destino`, registrado por el trabajador) hasta que se elija un destino real. No hay canal por defecto.

## Reserva de avisos: persistente y atómica

Sustituye a los datos estáticos de n8n (no atómicos con varias réplicas).

- **Diseño:** tabla `public.notification_reservations (entry_id text primary key, state in ('inflight','done','uncertain'))` en la misma base de Supabase, accesible por todas las llamadas y réplicas. Cada aviso empieza con `INSERT`: la clave primaria hace que, entre llamadas simultáneas, una gane (201) y las demás reciban 409. Es la solución más simple porque no añade ningún servicio nuevo.
- **Slack acepta (`ok:true`):** `state='done'`; las siguientes llamadas responden `duplicate: true`.
- **Rechazo explícito (`ok:false` con `error`):** se borra la reserva (solo si está `inflight`) y se puede reintentar.
- **Timeout, corte, HTTP sin JSON o respuesta sin `ok`:** `state='uncertain'`; no se reenvía hasta reconciliar a mano (el mensaje pudo publicarse). Una reserva `inflight` abandonada (caída a mitad) bloquea igual (`aviso_en_curso_o_sin_confirmar`).
- Si no se puede reservar, no se publica. Reconciliación: ver `db/prepared-migrations/README.md`.
- Requisito: el nodo usa la credencial `Supabase account`, que debe ser la clave `service_role` (la tabla tiene RLS sin políticas).

## Migraciones preparadas (SIN APLICAR) — `db/prepared-migrations/`

- `001_precheck_metadata_file_name.sql` (solo SELECT: nulos, vacíos, duplicados, casi duplicados, estado actual).
- `001_metadata_file_name_unique.up.sql` / `.down.sql`: UNIQUE sobre `metadata.file_name`. El `up` bloquea la tabla, repite la comprobación en la misma transacción y aborta sin cambios si hay nulos, vacíos o duplicados. Es idempotente.
- `002_notification_reservations.up.sql` / `.down.sql`: la tabla de reservas.
- Probadas solo en un PostgreSQL local. Que hoy haya 19 filas sin duplicados es una comprobación favorable pero no una garantía; por eso el `up` vuelve a comprobar.

## Resultados (ejecutados el 18/10/2026)

### 1. Importación en n8n 2.43.7
Los seis workflows de `essential/` importan sin error.

### 2. Pruebas unitarias (offline)
`python3 -m unittest test_verifier test_workflows` → 26 de 26 (20 del verificador/trabajador + 6 estructurales: sin Function, comprobación de `ok` tras cada Slack, reserva externa sin datos estáticos, migraciones preparadas fuera de `supabase/migrations`, sin canal por defecto, `channel_id` reenviado). `validate.py` → `VALIDATION_OK`.

### 3. Integración (n8n 2.43.7 real, dos réplicas, PostgreSQL y PostgREST locales, credenciales ficticias, Anthropic/Slack/RPC simulados)
| Workflow / cadena | Pruebas | Resultado |
|---|---|---|
| NEYEN-ingest | 7 | 7 de 7 |
| NEYEN-crosslink | 9 | 9 de 9 |
| NEYEN-crosslink-notify | 7 | 7 de 7 |
| Cadena ingest → crosslink → aviso | 8 | 8 de 8 |
| Reserva atómica (14 llamadas simultáneas a 2 réplicas, wf02 directo simultáneo, rechazo libera, incierto bloquea, inflight abandonado, 409 de la clave primaria, upsert con `on_conflict`, reinicio de n8n) | 10 | 10 de 10 |
| Migraciones en PostgreSQL local (precheck, up, idempotencia, aborto con duplicados/vacíos, down, reservas) | 7 | 7 de 7 |

### Pendientes de prueba de ejecución
`NEYEN-auto-crosslink`, `NEYEN-slack-tagger` y `NEYEN-search` solo se han importado (más la prueba estructural de `ok:true`). No se han ejecutado.

## Fallos encontrados y corregidos

1. Nodos `Function` obsoletos en n8n 2.43.7 → `Code`.
2. La inserción enviaba `event_id`/`only_step` a `metadata` → se quitan.
3. HTTP 200 con error funcional se tomaba como éxito → corregido en el trabajador y en todos los nodos Slack (`ok:true`).
4. `crosslink-notify` publicaba un mensaje por relacionada y con canal vacío → un aviso, canal de origen o bloqueo.
5. Datos estáticos de n8n como protección → sustituidos por reserva atómica en Postgres.
6. Con la base real sin UNIQUE, `?on_conflict=file_name` falla con `42P10` (reproducido en PostgREST local sin la migración).
7. Una segunda instancia de n8n choca con el puerto 5679 del task broker; usar `N8N_RUNNERS_BROKER_PORT` distinto si se ejecutan réplicas en la misma máquina.

## Verificación de solo lectura en Supabase (neyen-mvp, 18/10/2026)

`crosslink_entry(p_file_name text)` devuelve `{status:'ok',…}` o `{status:'error', message:'Entry not found'}`. `metadata`: solo `id` y `file_name` NOT NULL; columnas de lista `jsonb`; sin UNIQUE sobre `file_name`; el único índice es `metadata_pkey`; 19 filas, 0 duplicados. `docs/DATABASE-SCHEMA.md` actualizado con esto.

## Límites de lo probado

- Slack, Anthropic y la RPC son simulados; Postgres/PostgREST son reales pero locales, no Supabase.
- No se han comprobado las rutas publicadas ni la configuración del n8n de producción.

## Lista de comprobaciones que requieren acceso a Hostinger / producción

1. Versión exacta de n8n en Hostinger (reportada 2.43.7) y que usa Node ≥ 24.
2. Rutas publicadas existentes: sin colisión con `wf01-ingest`, `wf02-crosslink`, `wf03-crosslink-notify` (y las de slack-tagger/search).
3. Crear las credenciales: `Internal Webhook Header`, `Header Auth account` (Anthropic), `Supabase account` con la clave `service_role`, `Slack account` con permiso `chat:write` y bot dentro del canal.
4. Variables/ajustes de n8n necesarios para los nodos Code y webhooks (sin `$env`), y que los workflows no se activen hasta aprobarlo.
5. En Supabase: copia/punto de restauración; ejecutar el precheck; aplicar 001 y 002; confirmar la restricción `metadata_file_name_key` y la tabla con RLS.
6. Desplegar el verificador, su secreto de firma de Slack y la cabecera interna; solo entonces cambiar la URL de Slack.
7. Decidir `CONFIGURED_CHANNEL` o aceptar eventos bloqueados.
8. Comparar las copias de abril con la versión de Render antes de activar.
9. Ejecutar en una instancia de prueba (no producción) auto-crosslink, slack-tagger y search.
10. Si hubiera más de una réplica de n8n en Hostinger, repetir la prueba de llamadas simultáneas allí.
