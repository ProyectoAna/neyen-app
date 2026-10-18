# Copias para Hostinger

Estas copias preparan la migración. No están importadas ni publicadas en n8n.

Los archivos originales de `workflows/WF-*.json` no se han modificado.

## Qué cambia

- El nombre ya no usa WF-02, WF-05 ni WF-07, porque en Hostinger esos números pertenecen a otros flujos.
- Las llamadas internas apuntan a `https://n8n.thespiralwithin.ai`, no a Render.
- `active` queda en `false`.
- Las claves escritas en el código se sustituyen por `REPLACE_WITH_SUPABASE_KEY`.
- El host de Supabase se sustituye por `REPLACE_WITH_SUPABASE_HOST`.
- El webhook de Slack deja de tener una URL fija. Solo queda `$env.SLACK_WEBHOOK_NEYEN_CORE`.
- Los identificadores de credencial quedan en `pending-hostinger`. Hay que volver a elegirlas al importar.

## Correspondencia

| Original | Copia | Función |
|---|---|---|
| WF-01: Ingestion Pipeline | NEYEN Ingest | Recibe Slack en `POST /webhook/wf01-ingest` |
| WF-02: Crosslink | NEYEN Crosslink | `POST /webhook/wf02-crosslink` |
| WF-03: Crosslink Notify | NEYEN Crosslink Notify | `POST /webhook/wf03-crosslink-notify` |
| WF-04: Timeline Engine | NEYEN Timeline | `POST /webhook/wf04-timeline` |
| WF-04: Weekly Digest | NEYEN Weekly Digest | `POST /webhook/wf04-weekly-digest` |
| WF-05: Slack Tagger | NEYEN Slack Tagger | `POST /webhook/wf05-slack-tagger` |
| WF-06: Search | NEYEN Search | `POST /webhook/wf06-search` |
| WF-07: Auto Crosslink | NEYEN Auto Crosslink | `POST /webhook/wf07-auto-crosslink` |

## No incluido

Drive Watch no está localizado. La integración con Google Drive sigue documentada como pendiente y no forma parte de estas copias.

## Antes de importar

- Crear en Hostinger la credencial de Supabase y la de Anthropic. Ahora no existen.
- Unificar los dos nombres usados en los originales: `Supabase account` y `Supabase API`.
- Definir `SLACK_WEBHOOK_NEYEN_CORE` si se quiere conservar el aviso a Slack. La credencial de Slack ya presente no sustituye esa URL.
- Comprobar que las rutas `wf01-ingest`, `wf02-crosslink`, `wf05-slack-tagger` y el resto no coinciden con webhooks ya publicados.
- No publicar hasta completar lo anterior. No ejecutar llamadas de prueba desde esta rama.
