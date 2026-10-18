# PR 3 — Prepara la migración de workflows a Hostinger (descripción para copiar)

## Resumen

Sigue en borrador. No importa en producción, no publica, no fusiona y no despliega. Las copias de `workflows/hostinger/` están desactivadas; los originales de `workflows/` no cambian.

## Entrada de Slack (`workflows/hostinger/slack-verifier/`, no desplegado)

- Firma de Slack sobre el cuerpo original; rechaza timestamps de más de cinco minutos.
- El challenge solo se responde con firma válida.
- El evento se guarda en SQLite antes de confirmar. Un duplicado no se procesa otra vez.
- Un paso incierto bloquea los siguientes y exige reconciliación.
- El trabajador rechaza un HTTP 200 con error funcional (`error`, `status: error`, `ok: false`, `code`+`message`) y una clasificación sin `file_name`/`event_id`.
- `wf01-ingest` exige `Internal Webhook Header`.

## Resultados (ejecutados el 18/10/2026)

### 1. Importación en n8n 2.43.7
Los seis workflows de `essential/` importan sin error. Antes de la corrección ninguno importaba (nodos `Function` obsoletos).

### 2. Pruebas unitarias
`python3 -m unittest workflows/hostinger/slack-verifier/test_verifier.py` → 20 de 20 pasan. `validate.py` → `VALIDATION_OK`.

### 3. Integración por workflow
Entorno: n8n 2.43.7 (versión reportada en producción, npm, Node 24), SQLite propia, credenciales ficticias, Anthropic, Supabase y Slack simulados en `127.0.0.1`. Activar con `NEYEN_IT=1`. Las URLs se reescriben solo en una copia temporal.

| Workflow | Archivo de prueba | Resultado |
|---|---|---|
| NEYEN-ingest | `test_integration.py` | 7 de 7 |
| NEYEN-crosslink | `test_integration_chain.py` | 5 de 5 |
| NEYEN-crosslink-notify | `test_integration_chain.py` | 4 de 4 |
| Cadena ingest → crosslink → aviso | `test_integration_chain.py` | 5 de 5 |
| NEYEN-auto-crosslink, NEYEN-slack-tagger, NEYEN-search | — | solo importación, sin ejecutar |

La cadena comprueba que los datos llegan (`file_name`, `p_file_name`, entradas relacionadas en el aviso), que un HTTP 200 con error no cuenta como éxito (Supabase RPC y Slack `ok:false`), que un reintento tras resultado incierto no repite clasificación, inserción, RPC ni aviso, y que un evento duplicado no repite nada.

## Fallos encontrados y corregidos

1. Nodos `Function` obsoletos en n8n 2.43.7: convertidos a `Code` (mismo código) en `essential/`.
2. La inserción enviaba `event_id` y `only_step` a `metadata`: ahora se quitan.
3. El trabajador marcaba éxito con HTTP 200 + error funcional: corregido en `worker.py`.
4. `NEYEN-crosslink-notify` publicaba un mensaje de Slack por cada entrada relacionada (5 avisos por evento) y con la lista de relacionadas vacía: ahora un solo aviso con la lista completa.

## Límites de lo probado

- Los simuladores no son Supabase, Slack ni Anthropic reales. La forma de respuesta de la RPC `crosslink_entry` es una suposición deducida de lo que espera `crosslink-notify`; su definición no está en el repo.
- La protección frente a reintentos es del trabajador (estado en SQLite). Si alguien llama a `wf02-crosslink` directamente dos veces con 5+ relacionadas, se avisa dos veces.
- Slack real devuelve HTTP 200 con `ok:false` ante errores; n8n no lo trata como fallo. Solo el trabajador lo detecta.
- `NEYEN-auto-crosslink`, `NEYEN-slack-tagger` y `NEYEN-search` no se ejecutaron.
- `additional/` (Timeline, Weekly Digest) fuera de alcance: siguen con nodos `Function` y fallarán al importar en 2.43.7.

## Pendiente antes de desplegar

- Crear credenciales en Hostinger: interna, Supabase, Anthropic, Slack.
- Definir el canal de Slack para el aviso de crosslink: el payload no trae `channel_id`, así que `chat.postMessage` se envía con canal vacío y Slack real lo rechazará (`channel_not_found`).
- Confirmar `UNIQUE` en `metadata.file_name` en la base real y la forma de `crosslink_entry`.
- Comprobar colisiones con rutas publicadas.
- Desplegar el verificador y crear su configuración antes de cambiar la URL de Slack.
- Convertir `Function`→`Code` en `additional/` si se van a usar; Weekly Digest sigue sin canal; Drive Watch no está recuperado.
- Las copias salen de GitHub del 8 de abril de 2026 y pueden diferir de Render.
