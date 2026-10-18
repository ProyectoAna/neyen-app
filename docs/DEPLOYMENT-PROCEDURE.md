# Procedimiento de despliegue — ingest → crosslink → notify (Hostinger)

**Estado: PROPUESTO. Nada de esto se ha ejecutado.** Lo aprueba Ana antes del paso 1. Cada paso marca **PARAR** donde, si falla la comprobación, no se continúa y se avisa a Ana.

Alcance: solo `NEYEN-ingest`, `NEYEN-crosslink`, `NEYEN-crosslink-notify`, el verificador de Slack y las migraciones 001 y 002. **Fuera de alcance y desactivados**: `NEYEN-auto-crosslink`, `NEYEN-slack-tagger`, `NEYEN-search` (importan, pero no tienen prueba de ejecución), Timeline, Weekly Digest y Drive Watch. No se activa ninguno de ellos ni se cambia su estado actual.

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

> **Hallazgo que condiciona todo**: si la instancia de Hostinger usa esta misma base de Supabase, los workflows activos `wf01-ingest`, `wf02-crosslink` y `wf03-crosslink-notify` **ya existen con las mismas rutas** que las copias nuevas, y `wf07-auto-crosslink` (activo) llama a `wf03-crosslink-notify` sin `channel_id`: con la copia nueva esos avisos quedarían **bloqueados**. Ver paso 2.4.

---

## 1. Pre-comprobaciones (solo lectura)

1.1 **Versión y modo de ejecución de n8n en Hostinger** (panel o servidor, no por la API pública): anotar versión y si corre con Docker o npm.
- Docker: usar la imagen `n8nio/n8n:2.43.7` (ya trae Node 24); **no** hay que actualizar Node en el servidor.
- npm/instalación directa: exige Node ≥ 24. Solo en ese caso hay que subir Node, y es decisión de Ana.
- **PARAR** si la versión no es 2.43.7 o no se puede determinar: las pruebas se hicieron con 2.43.7 (los nodos `Function` ya no importan en esa versión).

1.2 **¿Misma base que la de arriba?** Comparar la configuración de base de datos de n8n en Hostinger con el proyecto `neyen-mvp`.
- Si es la misma: es el caso "colisión" (2.4). **PARAR y que Ana decida** (opciones: instancia separada de pruebas; renombrar rutas en las copias; o sustituir los tres workflows antiguos tras exportarlos).
- Si es otra: continuar.

1.3 **Rutas publicadas en Hostinger**: lista de workflows y rutas webhook activas. No debe haber ya `wf01-ingest`, `wf02-crosslink` ni `wf03-crosslink-notify` salvo decisión explícita de Ana. **PARAR** si hay colisión sin decisión.

1.4 **Pruebas en el commit a desplegar** (en un equipo de desarrollo): `python3 -m unittest test_verifier test_workflows test_reservation_access` y `python3 workflows/hostinger/validate.py` → `VALIDATION_OK`. **PARAR** si algo falla.

1.5 **Verificador**: el repo tiene `server.py`, `worker.py` y `verifier.py` pero **no un arranque ni configuración de servicio** (defecto D1 de la lista de bloqueos). **PARAR** en la fase 5 hasta que exista y Ana lo apruebe.

1.6 **Decisión previa de Ana (por escrito)**: canal de pruebas para la prueba controlada (el bot debe estar en él) y confirmación de que `CONFIGURED_CHANNEL` sigue vacío.

---

## 2. Copias de seguridad

2.1 Supabase: punto de restauración / copia de la base (panel de Supabase). Anotar su identificador. **PARAR** si no se puede crear.
2.2 Exportar de n8n (Hostinger) **todos** los workflows activos y las credenciales (sin secretos en claro, con el método seguro de n8n) a un lugar privado. **PARAR** si no se puede exportar.
2.3 Guardar la URL actual de eventos de Slack (la que hay hoy en la app de Slack) para el rollback.
2.4 Si hubo colisión de rutas y Ana decidió sustituir: guardar también el estado activo/inactivo de cada workflow tal como está.
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

5.1 Prerrequisito: defecto D1 resuelto (arranque, configuración por variables de entorno, servicio que se reinicia solo, HTTPS público delante). **PARAR** si no está.
5.2 Configurar: secreto de firma de Slack, URL interna de n8n (`.../webhook/wf01-ingest`), cabecera interna, ruta de la base SQLite (persistente, con copia de seguridad).
5.3 Arrancarlo **sin** apuntar Slack a él. Comprobar que rechaza una petición sin firma (401/403) y que responde al challenge solo con firma válida. **PARAR** si no.

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
7.4 **Cadena real**: enviar al verificador un evento firmado de prueba con ese canal. Esperado: ficha en `metadata` (`file_name = auto_slack_<event_id>`, una sola fila), aviso solo si hay 5+ relacionadas, evento `processed` en SQLite.
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
Después ejecutar la recuperación del trabajador para ese evento (`recover(event_id, …)`): marcará el evento como `processed` sin reenviar nada.

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
Después `recover(event_id, …)` repite solo el aviso (clasificación e inserción ya están `done`).

**Paso 4 — Verificar**: la fila queda `done` (3a) o se crea una nueva y acaba `done` (3b); en Slack hay **exactamente un** mensaje. Anotar fecha, `entry_id`, quién decidió y el motivo.

**Si no se puede comprobar en Slack**: no tocar. La reserva sigue bloqueando; mejor un aviso menos que uno duplicado.

---

## 11. Vigilancia tras el despliegue

```sql
select state, count(*) from public.notification_reservations group by state;          -- 'uncertain'/'inflight' deben ser 0
select count(*) from (select file_name from public.metadata group by file_name having count(*)>1) d;  -- 0
```
En el SQLite del verificador: `select status, count(*) from events group by status;` — los `failed` se revisan a mano (sección 10 si es `notify`).

---

## 12. Eventos sin canal (este primer alcance)

`CONFIGURED_CHANNEL` queda **vacío**. Un evento sin `channel_id` queda **bloqueado de forma explícita** (`sin_canal_de_destino`), el trabajador lo registra como fallo y **no se publica nada**. Se desbloquea solo cuando Ana elija un destino real, lo escriba en `Parse Payload` y se vuelva a desplegar (un cambio con su propia prueba de la sección 7). No hay canal por defecto. Los avisos de `wf07-auto-crosslink` (si sigue activo en la misma instancia) no llevan canal y quedarían bloqueados.
