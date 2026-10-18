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

**Inventario de Hostinger (NO verificado por Ana)**: procede de un informe anterior de Comet: VPS `srv1121428`, Ubuntu 24.04, Docker con Easypanel, servicio `neyen_n8n.1.du8sb78p2jbr90n88mzzrsmji`, n8n 2.43.7, SQLite montado desde `/opt/n8n_data`. Dato adicional que encaja: el nombre `neyen_n8n` indica proyecto `neyen`, servicio `n8n` (convención de Easypanel `<proyecto>_<servicio>`).

Reconfirmado el 18/10/2026 **solo con lo público y sin credenciales** (sin iniciar sesión, sin tocar webhooks): `https://n8n.thespiralwithin.ai/healthz` y `/healthz/readiness` → 200 `{"status":"ok"}` (hay una instancia n8n viva en esa URL, detrás de Cloudflare). **No se pudo confirmar sin acceso**: la versión (el endpoint público `/rest/settings` no la expone), que sea 2.43.7, el servidor `srv1121428`, Ubuntu, Easypanel, el nombre del servicio, que la base sea SQLite en `/opt/n8n_data`, las rutas webhook publicadas (probar un webhook por GET puede ejecutarlo; no se hizo) y las credenciales existentes. Un SQLite local en n8n significa además que la base de n8n **no** es la de Supabase observada antes: son instancias distintas hasta que se demuestre lo contrario.

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

**Puertos, proxy, HTTPS y volúmenes — configuración concreta**

Publicar `127.0.0.1:8080` **no** sirve para el proxy: Traefik corre en otro contenedor y su `127.0.0.1` no es el del servicio (comprobado: desde otro contenedor, `127.0.0.1:8080` no llega; por nombre de servicio sí). Por eso `docker-compose.yml` **no publica puertos**; el proxy llega por la red del contenedor.

*A) Easypanel (el despliegue previsto; Easypanel usa Docker con Traefik propio)*
1. En el proyecto `neyen`, crear un servicio **App** llamado `slack-verifier`.
2. **Source**: el repositorio, rama aprobada. **Build**: Dockerfile, *Build Path* `/workflows/hostinger/slack-verifier` (es también el contexto de construcción; el `Dockerfile` copia solo ficheros de esa carpeta), ruta `Dockerfile`.
3. **Environment**: `SLACK_SIGNING_SECRET`, `N8N_BASE_URL`, `N8N_INTERNAL_HEADER_NAME`, `N8N_INTERNAL_HEADER_VALUE` (los valores se escriben en Easypanel, nunca en el repo). `N8N_BASE_URL` por la red interna: `http://neyen_n8n:5678` (nombre de servicio `<proyecto>_<servicio>`; **confirmar el nombre y el puerto 5678 en el paso 1.2**). Si el nombre interno no resuelve, usar `https://n8n.thespiralwithin.ai`.
4. **Domains**: dominio del verificador (DNS apuntando al VPS, p. ej. en Cloudflare), **HTTPS activado** (Let's Encrypt), protocolo interno **HTTP**, **puerto de destino 8080**. Sin sección *Ports* (no se publica nada en el host).
5. **Storage → Mounts → Volume**: nombre `data`, ruta del contenedor `/data`. Es un volumen gestionado: hereda el propietario del directorio de la imagen (uid 10001), por lo que el usuario no root escribe sin cambios. Programar la copia de seguridad del volumen en Easypanel.
6. Si en lugar de *Volume* se usa **Bind** (carpeta del host), esa carpeta debe pertenecer al uid 10001 (`chown 10001:10001 <carpeta>`); si no, el arranque falla rápido con `SQLITE_PATH: el directorio no es escribible` (comprobado).
7. **Una sola réplica.** Deploy. Un redeploy envía SIGTERM y espera al paso en curso (ver *Reinicio controlado*).

*B) Docker Compose con Traefik propio* (solo si no se usa Easypanel): `docker compose -f docker-compose.yml -f docker-compose.traefik.yml up -d --build` con `TRAEFIK_NETWORK` (la red a la que está unido Traefik), `VERIFIER_DOMAIN` y `TRAEFIK_CERTRESOLVER`. Ese superpuesto une el servicio a esa red y publica las etiquetas de Traefik (router solo para `/slack/events`, TLS, puerto 8080). Solo se comprobó que el superpuesto se fusiona; **no se probó con un Traefik real**.

*C) Pruebas locales*: `docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build` publica `127.0.0.1:8080` solo en esa máquina.

- URL que se daría a Slack **más adelante (paso 8)**: `https://<dominio-del-verificador>/slack/events`. Cualquier otra ruta responde 404.
- Volumen persistente `/data` (SQLite en modo WAL), una réplica (SQLite no se comparte entre réplicas). Debe sobrevivir a redeploys y entrar en las copias de seguridad.
- `GET /healthz` devuelve `{"status","db","worker"}` (`ok`/`error`), 200 o 503, sin versiones, rutas, secretos ni contadores. El `HEALTHCHECK` ejecuta `python service.py healthcheck`.

**Reinicio controlado**: `SIGTERM` (docker stop / redeploy) detiene la recepción, deja terminar el paso en curso (hasta 35 s; `stop_grace_period: 40s`) y sale con código 0. Al arrancar, el trabajador retoma de SQLite los eventos recibidos que no se procesaron. Un paso que quedó a medias por una caída brusca (`SIGKILL`, corte de luz) queda `started`: **no se reenvía solo**; se reconcilia como en la sección 10.

5.1 Crear el servicio (A) o `docker compose … up -d --build` (B/C), **sin** apuntar Slack a él. **PARAR** si `check-config` falla (el contenedor sale con código 2 y un mensaje por variable) o si el servicio no queda sano.
5.2 Comprobar: `GET https://<dominio>/healthz` → 200; un POST sin firma o con firma errónea a `/slack/events` → **401** y nada en SQLite. **PARAR** si acepta una firma errónea o si el dominio no llega al servicio (revisar puerto de destino 8080 y red).
5.3 Redeploy/reinicio del servicio: vuelve a estar sano y los datos de `/data` siguen. **PARAR** si el volumen se pierde.

> **Qué está probado y qué no.** En la caja de pruebas, con **podman rootless 5.4.2** (no Docker; mismo formato de imagen y compose), `integration-harness/container/run_container_test.sh` construyó la imagen y comprobó, con n8n simulado y secretos ficticios: usuario no root (uid 10001) que escribe en un volumen con nombre; fallo rápido con un bind de otro propietario; `/healthz` limpio y healthcheck del compose; recepción firmada (200) y firma errónea (401, sin llegar a n8n); alcance por nombre de servicio y no por loopback; persistencia de SQLite tras **recrear** el contenedor y reenvío de Slack sin reprocesar; apagado ordenado con código 0; logs sin secretos. **No probado**: Docker Engine, Easypanel real, Traefik real, build con BuildKit/Buildx, ni el planificador de healthchecks del motor (en podman sin systemd se ejecuta el comando a mano).

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
