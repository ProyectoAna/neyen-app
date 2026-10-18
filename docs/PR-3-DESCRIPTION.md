# PR 3 — Prepara la migración de workflows a Hostinger (descripción para copiar)

## Resumen

Sigue en borrador. No importa en producción, no publica, no fusiona y no despliega. Las copias de `workflows/hostinger/` están desactivadas; los originales de `workflows/` no cambian.

## Entrada de Slack (`workflows/hostinger/slack-verifier/`, no desplegado)

- Firma de Slack sobre el cuerpo original; rechaza timestamps de más de cinco minutos. El challenge solo se responde con firma válida.
- El evento se guarda en SQLite antes de confirmar. Un duplicado no se procesa otra vez.
- Un paso incierto bloquea los siguientes y exige reconciliación.
- El trabajador rechaza un HTTP 200 con error funcional (`error`, `status: error|blocked`, `ok: false`, `code`+`message`) y una clasificación sin `file_name`/`event_id`; el motivo queda en `last_error`.
- `wf01-ingest` exige `Internal Webhook Header`.

## Canal de Slack del aviso de crosslink

- El `channel_id` del evento original viaja por toda la cadena (ingest → crosslink → crosslink-notify) y es el canal del aviso.
- Sin canal de origen, solo se usa el canal configurado explícitamente en `Parse Payload` (`CONFIGURED_CHANNEL`, **vacío en el repo**). Sin ninguno de los dos no se publica: el flujo responde `status: blocked`, `blocker: sin_canal_de_destino` y el trabajador lo registra como fallo. No hay canal por defecto.

## Protección contra duplicados y errores de Slack

- `crosslink-notify` reserva cada aviso por `entry_id` en datos estáticos del workflow (persisten tras reiniciar n8n, comprobado). Una llamada directa repetida a `wf02-crosslink` o `wf03-crosslink-notify` responde `duplicate: true` y no publica. Si Slack falla, la reserva se libera y se permite reintentar.
- Todas las llamadas a `chat.postMessage` (ingest, crosslink-notify, search, slack-tagger) van seguidas de una comprobación de `ok: true`; un HTTP 200 con `ok:false` hace fallar la ejecución.
- Limitación: los datos estáticos solo aplican a ejecuciones de producción (workflow activo) y no son atómicos si hay varias réplicas de n8n.

## Resultados (ejecutados el 18/10/2026)

### 1. Importación en n8n 2.43.7
Los seis workflows de `essential/` importan sin error. Antes de las correcciones ninguno importaba (nodos `Function` obsoletos).

### 2. Pruebas unitarias (offline)
`python3 -m unittest test_verifier test_workflows` → 24 de 24 (20 del verificador/trabajador + 4 estructurales: sin nodos Function, comprobación de `ok` tras cada Slack, sin canal por defecto, `channel_id` reenviado). `validate.py` → `VALIDATION_OK`.

### 3. Integración (n8n 2.43.7 real, SQLite propia, credenciales ficticias, Anthropic/Supabase/Slack simulados)
`NEYEN_IT=1 python3 -m unittest test_integration test_integration_chain` → 31 de 31.

| Workflow / cadena | Pruebas | Resultado |
|---|---|---|
| NEYEN-ingest (`test_integration.py`) | 7 | 7 de 7 |
| NEYEN-crosslink | 9 | 9 de 9 |
| NEYEN-crosslink-notify | 7 | 7 de 7 |
| Cadena ingest → crosslink → aviso | 8 | 8 de 8 |
| NEYEN-auto-crosslink, NEYEN-slack-tagger, NEYEN-search | — | solo importación; los nodos Slack añadidos solo tienen prueba estructural |

## Fallos encontrados y corregidos en la rama

1. Nodos `Function` obsoletos en n8n 2.43.7 → `Code`.
2. La inserción enviaba `event_id` y `only_step` a `metadata` → se quitan.
3. El trabajador marcaba éxito con HTTP 200 + error funcional → corregido.
4. `crosslink-notify` publicaba un mensaje por cada relacionada → un solo aviso con la lista.
5. El aviso se publicaba con canal vacío → canal de origen o configurado explícito; si no, bloqueo.
6. Llamadas directas repetidas a crosslink duplicaban el aviso → reserva por `entry_id`. Primera versión fallida: al lanzar error en el mismo nodo la reserva no se liberaba; ahora se libera y un nodo posterior falla.
7. Slack con HTTP 200 y `ok:false` no se trataba como fallo en n8n → comprobación `ok:true` en todos los nodos Slack.
8. `crosslink` ocultaba el fallo de `wf03` (continuaba con error) → ahora propaga el fallo.

## Comprobaciones de solo lectura en Supabase (proyecto neyen-mvp)

- `crosslink_entry(p_file_name text)` existe; devuelve `jsonb`: `{status:'ok', entry_id, file_name, tags, entities, summary, related_count, related_ids}` o `{status:'error', message:'Entry not found'}`. Coincide con lo que esperan los workflows (el simulador ya usa esa forma).
- **`metadata.file_name` NO tiene restricción UNIQUE** (solo la clave primaria `id`). El nodo `Insertar sin duplicar` usa `?on_conflict=file_name`, que PostgREST rechazará sin un índice único. 19 filas, 0 `file_name` duplicados, así que un índice único es viable.
- Las columnas de listas (`tags`, `entities`…) son `jsonb`, no `text[]` como dice `docs/DATABASE-SCHEMA.md`; `source` admite NULL en la base real.
- No se comprobaron las rutas publicadas en producción (sin acceso a n8n de producción).

## Límites de lo probado

- Los simuladores no son Supabase, Slack ni Anthropic reales.
- `NEYEN-auto-crosslink`, `NEYEN-slack-tagger` y `NEYEN-search` no se ejecutaron. `auto-crosslink` no tiene canal de origen: dependerá del canal configurado.
- `additional/` (Timeline, Weekly Digest) fuera de alcance: siguen con nodos `Function` y fallarán al importar en 2.43.7.

## Pendiente antes de desplegar

Necesitan acceso: credenciales en Hostinger (interna, Supabase, Anthropic, Slack); comprobar rutas publicadas en el n8n de producción; desplegar el verificador antes de cambiar la URL de Slack; comparar las copias de abril con la versión de Render.

Necesitan decisión de Ana: crear el índice UNIQUE sobre `metadata.file_name` (o cambiar la inserción); canal configurado de respaldo (o aceptar que esos avisos queden bloqueados); recuperar Drive Watch; convertir `additional/`.
