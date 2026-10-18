# Procedimiento de despliegue — ingest → crosslink → notify (Hostinger)

**Estado: PROPUESTO. Nada de esto se ha ejecutado.** Lo aprueba Ana antes del paso 1. Cada paso marca **PARAR** donde, si falla la comprobación, no se continúa y se avisa a Ana.

Alcance del primer despliegue: solo `NEYEN-ingest`, `NEYEN-crosslink`, `NEYEN-crosslink-notify`, el verificador de Slack y las migraciones 001 y 002. **Quedan FUERA del primer despliegue** (no se importan, no se activan, no se cambia su estado actual): `NEYEN-auto-crosslink`, `NEYEN-slack-tagger`, `NEYEN-search`, Timeline, Weekly Digest y Drive Watch.

**Decisión aceptada (Ana)**: `CONFIGURED_CHANNEL` queda vacío. Un evento sin canal se bloquea de forma explícita; no hay canal alternativo ni por defecto.

**Puerta previa a cualquier mensaje real**: la prueba real usa un **canal de Slack dedicado de pruebas**. Ana confirma su ID (`C…`) **por escrito antes del primer mensaje**. Sin esa confirmación no se envía nada a Slack, ni siquiera de prueba.

Roles: **Ana** aprueba y decide; ejecuta quien tenga acceso a Hostinger, Supabase y Slack. Ninguna fase posterior empieza sin el "OK" de Ana a la anterior.

---

## 0. Qué se verificó el 18/10/2026 y qué no

Verificado en solo lectura (conector Supabase, proyecto `neyen-mvp`, PostgreSQL 17.6; solo SELECT sobre catálogos y tablas de n8n, sin credenciales ni JSON de nodos):

- `crosslink_entry(p_file_name text)` existe, `SECURITY DEFINER`, devuelve `{status:'ok',…}` o `{status:'error', message:'Entry not found'}`. **EXECUTE solo para `authenticated`, `service_role` y `postgres`; `anon` no puede.**
- `metadata`: RLS activado y **sin políticas**; `anon`/`authenticated`/`service_role` tienen privilegios de tabla. Sin UNIQUE sobre `file_name`; único índice `metadata_pkey`; 19 filas; 0 duplicados.
- `notification_reservations` **no existe** todavía.
- Esta base contiene también las tablas internas de **un** n8n (`workflow_entity`, `webhook_entity`, `execution_entity`…). Rutas publicadas y activas en esa instancia: `wf01-ingest`, `wf02-crosslink`, `wf03-crosslink-notify`, `wf04-weekly-digest`, `wf05-slack-tagger`, `wf06-search`, `wf07-auto-crosslink`, `system` y una del bot de Telegram. Última ejecución: 16/10/2026 07:06 UTC (18 en total). Último cambio de esquema de n8n en esa base: 23/03/2026.
- n8n 2.43.7: existe la imagen `n8nio/n8n:2.43.7` (publicada el 16/10/2026) y su base trae **su propio Node 24**. El paquete npm exige Node ≥ 24.

**No se pudo verificar** (sin acceso): versión real de n8n en Hostinger y cómo se ejecuta (Docker o npm), si esa instancia es la dueña de la base anterior, rutas publicadas en Hostinger, credenciales existentes, el servidor donde irá el verificador, el bot y los permisos de Slack, ni los valores por defecto/RLS de otras tablas.

> **Sobre colisiones de rutas**: que esa base de Supabase contenga tablas de un n8n **no determina** si hay colisión de webhooks en la instancia de destino. Los datos anteriores son solo una observación de esa base. La comprobación de rutas se hace **sobre la instancia n8n concreta** donde se va a desplegar (paso 1.3).

**Inventario de Hostinger**: no existe en el repo ni en los ficheros de trabajo un inventario obtenido por inspección de Hostinger. Solo hay referencias antiguas y no verificadas: correos de Ana de noviembre de 2025 (VPS Hostinger + Easypanel + Docker + Traefik, SSL Let's Encrypt, DNS en Cloudflare, n8n en `n8n.thespiralwithin.ai`) y los flujos de CI del repo, que consultan `/healthz` de esa URL. **Todo ello debe confirmarse** en el paso 1 (versión de n8n, modo de ejecución, rutas, credenciales, red interna entre contenedores, dominio libre para el verificador).

---

## 1. Pre-comprobaciones (solo lectura)

1.1 **Versión y modo de ejecución de n8n en Hostinger** (panel o servidor, no por la API pública): anotar versión y si corre con Docker o npm.
- Docker: usar la imagen `n8nio/n8n:2.43.7` (ya trae Node 24); **no** hay que actualizar Node en el servidor.
- npm/instalación directa: exige Node ≥ 24. Solo en ese caso hay que subir Node, y es decisión de Ana.
- **PARAR** si la versión no es 2.43.7 o no se puede determinar: las pruebas se hicieron con 2.43.7 (los nodos `Function` ya no importan en esa versión).

1.2 **Confirmar el inventario de Hostinger** (sección 0): servidor, Easypanel, red interna, nombre del servicio n8n, dominio y puerto previstos para el verificador, credenciales ya creadas. Anotar qué ha cambiado respecto a lo supuesto. **PARAR** si algo de lo que exige esta guía (HTTPS público para el verificador, volumen persistente) no está disponible.

1.3 **Rutas publicadas en la instancia n8n concreta** (la que recibirá los workflows): lista de workflows y webhooks activos de **esa** instancia. Si ya existen `wf01-ingest`, `wf02-crosslink` o `wf03-crosslink-notify`, o cualquier otro flujo que llame a `wf03-crosslink-notify` sin `channel_id` (quedaría bloqueado), **PARAR** y que Ana decida (renombrar rutas en las copias, instancia separada, o sustituir tras exportar). Si no hay colisión, continuar. Compartir la base de Supabase con otra instancia no se considera colisión por sí mismo.

1.4 **Pruebas en el commit a desplegar** (en un equipo de desarrollo): `python3 -m unittest test_verifier test_workflows test_reservation_access` y `python3 workflows/hostinger/validate.py` → `VALIDATION_OK`. **PARAR** si algo falla.

1.5 **Verificador**: tiene entrada (`service.py`), configuración por variables de entorno (`config.py`), `Dockerfile` y `docker-compose.yml`. Pruebas del servicio: `python3 -m unittest test_service`. **PARAR** si fallan.

1.6 **Puerta del canal de pruebas**: Ana confirma por escrito el **ID** del canal dedicado de pruebas (el bot debe estar en él). **PARAR** y no enviar ningún mensaje hasta tenerlo. Si el ID no coincide con el canal que Ana confirmó, no se usa.

---

## 2. Copias de seguridad

2.1 Supabase: punto de restauración / copia de la base (panel de Supabase). Anotar su identificador. **PARAR** si no se puede crear.
2.2 Exportar de n8n (Hostinger) **todos** los workflows activos y las credenciales (sin secretos en claro, con el método seguro de n8n) a un lugar privado. **PARAR** si no se puede exportar.
2.3 Guardar la URL actual de eventos de Slack (la que hay hoy en la app de Slack) para el rollback.
2.4 Si en 1.3 hubo colisión y Ana decidió sustituir: guardar también el estado activo/inactivo de cada workflow tal como está.
2.5 Guardar el hash del commit que se despliega.

---

## 3. Migraciones (las aplica quien tenga acceso a Supabase; Ana las aprueba una a una)

Archivos en `db/prepared-migrations/`. Se ejecutan en el editor SQL de Supabase como `postgres`.

3.1 `001_precheck_metadata_file_name.sql`. Todas las consultas de problema deben devolver **0 filas** (nulos, vacíos, duplicados). **PARAR** si devuelve filas: no aplicar 001; decidir qué hacer con los duplicados.
3.2 `001_metadata_file_name_unique.up.sql`. Si lanza `ABORTADO` no cambia nada: **PARAR**. Comprobar: `select conname from pg_constraint where conname='metadata_file_name_key';` → 1 fila.
3.3 `002_notification_reservations.up.sql`. Comprobar:
```sql
select relrowsecurity from pg_class where oid='public.notification_reservations'::regclass;           -- true
select count(*) from pg_policies where tablename='notification_reservations';                           -- 0
select count(*) from information_schema.role_table_grants
 where table_name='notification_reservations' and grantee in ('anon','authenticated','PUBLIC');         -- 0
```
**PARAR** si alguna no coincide: `002_notification_reservations.down.sql` y avisar.
3.4 Esta migración se probó solo en un PostgreSQL local. En Supabase, los privilegios por defecto dan permisos a `anon`/`authenticated`; el `revoke` de 002 es lo que protege la tabla: por eso la comprobación de 3.3 es obligatoria.

---

## 4. Credenciales (en n8n de Hostinger; nunca en el repo, chat ni logs)

Crear con exactamente estos nombres:

| Nombre | Tipo | Contenido |
|---|---|---|
| `Internal Webhook Header` | Header Auth | cabecera y valor secretos nuevos, compartidos con el verificador |
| `Header Auth account` | Header Auth | clave de la API de Anthropic (`x-api-key`) |
| `Supabase account` | Supabase | host del proyecto + clave **`service_role`** |
| `Slack account` | Slack | token de bot con `chat:write`, bot dentro del canal |

- **Por qué `service_role` y no la clave `anon`**: `anon` no puede ejecutar `crosslink_entry` y `metadata`/`notification_reservations` no tienen políticas para ella. Los workflows originales del repo llevan una clave `anon` escrita en el JSON (verificado: es solo `anon`, no `service_role`); las copias de Hostinger no.
- La clave `service_role` solo vive en esa credencial de n8n (servidor). No va en el verificador, ni en el navegador, ni en el repo.
- **PARAR** si falta alguna credencial o si la de Supabase no es `service_role`.

---

## 5. Verificador de Slack

Carpeta: `workflows/hostinger/slack-verifier/` (`service.py`, `config.py`, `Dockerfile`, `docker-compose.yml`, `.env.example`). Solo biblioteca estándar de Python.

**Variables** (los valores NO van al repo; en Easypanel se definen en el servicio, con Docker Compose en un `.env` fuera del repo; también se admite `NOMBRE_FILE` para secretos en fichero):

| Variable | Obligatoria | Notas |
|---|---|---|
| `SLACK_SIGNING_SECRET` | sí | ≥ 16 caracteres; el de la app de Slack |
| `N8N_BASE_URL` | sí | solo la base, p. ej. `http://n8n:5678` (red interna) o `https://…`; `http` solo para localhost o nombre de servicio sin punto |
| `N8N_INTERNAL_HEADER_NAME` / `N8N_INTERNAL_HEADER_VALUE` | sí | los de la credencial `Internal Webhook Header`; el valor ≥ 16 caracteres y distinto del secreto de Slack |
| `SQLITE_PATH` | no (`/data/events.sqlite`) | el directorio debe existir y ser escribible |
| `PORT` (8080), `WORKER_POLL_SECONDS` (2), `SHUTDOWN_GRACE_SECONDS` (35), `SLACK_EVENTS_PATH` (`/slack/events`), `HOST` | no | |

**Arranque**: `python service.py serve` valida la configuración **antes** de abrir puerto o tocar SQLite. Si algo falla, sale con código 2 y escribe `CONFIGURACION INVALIDA` con la variable y el motivo, **nunca el valor**. `python service.py check-config` solo valida.

**Puertos, HTTPS y volúmenes**
- El contenedor escucha HTTP en `8080`. **El HTTPS lo termina el proxy** (Traefik de Easypanel, con Let's Encrypt): un dominio dedicado al verificador, apuntando al puerto 8080 del servicio. El `docker-compose.yml` solo publica `127.0.0.1:8080` para no exponer HTTP en claro.
- URL que se daría a Slack **más adelante (paso 8)**: `https://<dominio-del-verificador>/slack/events`. Cualquier otra ruta responde 404; solo se acepta POST firmado en esa ruta.
- Volumen persistente `/data` (SQLite en modo WAL). **Debe sobrevivir a redeploys** y entrar en las copias de seguridad. Un solo contenedor (una réplica): SQLite no se comparte entre réplicas.
- `GET /healthz` devuelve `{"status","db","worker"}` (`ok`/`error`), 200 o 503, sin versiones, rutas, secretos ni contadores. Es lo que usa el `HEALTHCHECK` del Dockerfile. Si se expone por el dominio público solo revela que el servicio vive.

**Reinicio controlado**: `SIGTERM` (docker stop / redeploy) detiene la recepción, deja terminar el paso en curso (hasta 35 s; `stop_grace_period: 40s`) y sale con código 0. Al arrancar, el trabajador retoma de SQLite los eventos recibidos que no se procesaron. Un paso que quedó a medias por una caída brusca (`SIGKILL`, corte de luz) queda `started`: **no se reenvía solo**; se reconcilia como en la sección 10.

5.1 Construir y arrancar **sin** apuntar Slack a él: `docker compose up -d --build` (o crear el servicio en Easypanel desde el `Dockerfile`). **PARAR** si `check-config` falla o el contenedor no queda `healthy`.
5.2 Comprobar: `GET /healthz` → 200; un POST sin firma o con firma errónea a `/slack/events` → **401** y nada en SQLite. **PARAR** si acepta una firma errónea.
5.3 Reiniciar el servicio (`docker compose restart`) y comprobar que vuelve a `healthy` y que los datos de `/data` siguen. **PARAR** si el volumen se pierde.

> El `Dockerfile` y el `docker-compose.yml` **no se han construido** en el entorno de pruebas (no hay Docker). Lo probado es `service.py` arrancado desde una carpeta limpia con solo los ficheros que copia el `Dockerfile`, con entorno vacío, y su definición revisada por pruebas estáticas. La primera construcción real ocurre en este paso 5.1.

---

## 6. Despliegue de los workflows en n8n (todo inactivo hasta el final)

6.1 Importar desde `workflows/hostinger/essential/`: `NEYEN-crosslink-notify.json`, `NEYEN-crosslink.json`, `NEYEN-ingest.json`. **No importar ni activar** auto-crosslink, slack-tagger, search, Timeline, Weekly Digest.
6.2 En cada workflow, asignar las credenciales de la sección 4 a los nodos (en el JSON figuran como `pending-hostinger`).
6.3 Dejar `CONFIGURED_CHANNEL` vacío en `Parse Payload` de crosslink-notify.
6.4 Activar **en este orden**, comprobando tras cada uno que no aparece error: `NEYEN-crosslink-notify` → `NEYEN-crosslink` → `NEYEN-ingest`.
6.5 Comprobar que auto-crosslink, slack-tagger y search siguen inactivos. **PARAR** si alguno está activo.

---

## 7. Prueba controlada (antes de cambiar la URL de Slack)

Sin tocar Slack. Con el canal de pruebas que Ana indicó. Sustituir `<ID>` por un identificador de prueba nuevo.

7.1 **Sin canal → bloqueo**: llamar a `wf03-crosslink-notify` (con la cabecera interna) con `entry_id` nuevo y sin `channel_id`. Esperado: `status: blocked`, `blocker: sin_canal_de_destino`, **ningún mensaje** en Slack. **PARAR** si publica.
7.2 **Con canal → un aviso**: mismo cuerpo con `channel_id` del canal de pruebas, `related_ids` vacío. Esperado: 1 mensaje, respuesta `ok: true`, y fila `done` en `notification_reservations`. **PARAR** si hay 0 o 2 mensajes.
7.3 **Duplicado**: repetir 7.2. Esperado: `duplicate: true`, **ningún mensaje nuevo**. **PARAR** si publica otra vez.
7.4 **Cadena real**: enviar al verificador un evento firmado de prueba (canal de pruebas confirmado en 1.6). Esperado: ficha en `metadata` (`file_name = auto_slack_<event_id>`, una sola fila), aviso solo si hay 5+ relacionadas, evento `processed` en SQLite.
7.5 **Limpieza**: borrar las filas de prueba de `metadata` y `notification_reservations` (solo las identificadas por Ana, una a una).
7.6 Si cualquier paso falla: ir a la sección 9 (rollback) y no cambiar Slack.

---

## 8. Cambio de URL de Slack (decisión de Ana, solo tras 7 completa)

8.1 Ana cambia la URL de eventos de Slack a la del verificador (HTTPS). Slack envía un challenge; el verificador debe responderlo.
8.2 Observar 30 minutos (consultas de la sección 11). Si algo falla: volver a la URL guardada en 2.3.

---

## 9. Rollback

Orden, parando en el primer nivel que resuelva el problema:

1. **Slack**: restaurar la URL guardada (2.3). Detiene la entrada de eventos.
2. **Workflows**: desactivar `NEYEN-ingest`, `NEYEN-crosslink`, `NEYEN-crosslink-notify` (orden inverso al de activación). Si se sustituyeron antiguos: reimportar la exportación de 2.2 y restaurar su estado activo.
3. **Verificador**: pararlo. Conservar su SQLite (contiene eventos pendientes y su estado).
4. **002**: antes, guardar `select * from public.notification_reservations;`. Después `002_notification_reservations.down.sql`. Se pierde la protección contra duplicados.
5. **001**: `001_metadata_file_name_unique.down.sql` (no toca datos). Con 001 revertido `on_conflict=file_name` vuelve a fallar: no reactivar el flujo de inserción.
6. **Supabase completo**: restaurar el punto de 2.1 solo si hay daño en datos y lo decide Ana (perdería lo escrito después).

---

## 10. Reconciliar una reserva incierta (`uncertain` o `inflight` abandonada)

**Cuándo ocurre**: Slack no respondió (timeout, corte, respuesta sin `ok`) o n8n se cayó a mitad. El mensaje **pudo publicarse**. Mientras la reserva no esté `done` ni se borre, no se reenvía nada: las llamadas devuelven `status: blocked` (`requiere_reconciliacion` o `aviso_en_curso_o_sin_confirmar`).

**Quién decide**: **Ana** (única con acceso al canal de Slack). Quien tenga acceso a la base solo ejecuta el SQL que Ana indique por escrito. Nunca se reenvía "por si acaso".

**Paso 1 — Localizar** (Supabase, solo lectura):
```sql
select r.entry_id, r.state, r.created_at, r.updated_at, m.file_name
from public.notification_reservations r
left join public.metadata m on m.id::text = r.entry_id
where r.state <> 'done' order by r.created_at;
```
El `file_name` es `auto_slack_<event_id>`; el `event_id` es el de Slack.

**Paso 2 — Comprobar en Slack** (Ana): buscar en el canal del evento un mensaje "Crosslink Alert" con "Entrada nueva: `<file_name>`" cercano a `updated_at`.

**Paso 3a — SÍ se publicó → marcar como enviado**:
```sql
update public.notification_reservations
set state = 'done', updated_at = now()
where entry_id = '<entry_id>' and state in ('uncertain','inflight');
```
Y en el SQLite del verificador (para que el evento se dé por completado):
```sql
update events set notify_state = 'done', last_error = null where event_id = '<event_id>';
```
Después, en el contenedor: `python service.py recover <event_id>` (`docker compose exec slack-verifier python service.py recover <event_id>`). Marca el evento como `processed` sin reenviar nada.

**Paso 3b — NO se publicó → autorizar reintento expresamente** (Ana lo escribe: "autorizo reenviar `<entry_id>`"):
```sql
delete from public.notification_reservations
where entry_id = '<entry_id>' and state in ('uncertain','inflight');
```
Y en el SQLite del verificador:
```sql
update events set notify_state = 'pending', status = 'failed', last_error = null,
       claim_owner = null, claimed_at = null, authorized = 0
where event_id = '<event_id>';
```
Después `python service.py recover <event_id>` repite solo el aviso (clasificación e inserción ya están `done`). También lo retomaría el trabajador por sí solo en pocos segundos.

**Paso 4 — Verificar**: la fila queda `done` (3a) o se crea una nueva y acaba `done` (3b); en Slack hay **exactamente un** mensaje. Anotar fecha, `entry_id`, quién decidió y el motivo.

**Caída brusca a mitad de paso** (evento con `classify_state`, `insert_state` o `notify_state` en `started`): Ana decide con el mismo criterio. Si el paso no llegó a hacerse (p. ej. clasificación), `update events set classify_state='pending', status='failed', last_error=null, claim_owner=null, claimed_at=null, authorized=0 where event_id='<event_id>';` y `recover`. Si pudo hacerse (inserción, aviso), primero comprobar el efecto real (ficha en `metadata`, mensaje en Slack) y marcar `done` o `pending` según corresponda. Probado con SQLite real en `test_service.py`.

**Si no se puede comprobar en Slack**: no tocar. La reserva sigue bloqueando; mejor un aviso menos que uno duplicado.

---

## 11. Vigilancia tras el despliegue

```sql
select state, count(*) from public.notification_reservations group by state;          -- 'uncertain'/'inflight' deben ser 0
select count(*) from (select file_name from public.metadata group by file_name having count(*)>1) d;  -- 0
```
En el SQLite del verificador: `select status, count(*) from events group by status;` — los `failed` se revisan a mano (sección 10 si es `notify`).

---

## 12. Eventos sin canal (decisión aceptada)

`CONFIGURED_CHANNEL` queda **vacío** por decisión de Ana; ya no es un punto pendiente. Un evento sin `channel_id` queda **bloqueado de forma explícita** (`sin_canal_de_destino`), el trabajador lo registra como fallo y **no se publica nada**. No hay canal por defecto ni alternativo. Cambiarlo exigiría una nueva decisión, un nuevo despliegue y repetir la sección 7. Un flujo ajeno que llame a `wf03-crosslink-notify` sin canal (ver 1.3) quedaría bloqueado.
