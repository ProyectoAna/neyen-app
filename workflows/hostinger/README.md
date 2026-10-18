# Copias para Hostinger

Preparación. No están importadas, publicadas ni ejecutadas.

Los originales de `workflows/WF-*.json` no cambian.

## Dónde está cada flujo

Esenciales, en `essential/`:

| Archivo | Nombre | Función |
|---|---|---|
| NEYEN-ingest.json | NEYEN Ingest | Recibe Slack |
| NEYEN-crosslink.json | NEYEN Crosslink | Cruza entradas |
| NEYEN-crosslink-notify.json | NEYEN Crosslink Notify | Avisa el cruce |
| NEYEN-slack-tagger.json | NEYEN Slack Tagger | Comandos de etiquetado |
| NEYEN-search.json | NEYEN Search | Búsqueda |
| NEYEN-auto-crosslink.json | NEYEN Auto Crosslink | Cruce automático |

Adicionales, en `additional/`:

| Archivo | Nombre | Función |
|---|---|---|
| NEYEN-timeline.json | NEYEN Timeline | Línea temporal |
| NEYEN-weekly-digest.json | NEYEN Weekly Digest | Resumen semanal |

Drive Watch no está aquí. No está localizado; la integración sigue documentada como pendiente.

## Slack

Todas las publicaciones a Slack usan el mismo mecanismo: un nodo HTTP Request a `https://slack.com/api/chat.postMessage` con la credencial `slackApi` llamada `Slack account`.

No queda `SLACK_WEBHOOK_PLACEHOLDER`. No queda `SLACK_WEBHOOK_NEYEN_CORE`. No se usa `$env`.

El canal sale de `channel_id` o `channel` del propio mensaje. Weekly Digest no trae canal, así que esa publicación no tiene destino y fallará cerrada.

## Supabase

`REPLACE_WITH_SUPABASE_KEY` ya no está en el código. Las llamadas REST van en nodos HTTP Request con la credencial `supabaseApi` llamada `Supabase account`. Timeline usa el nodo Supabase con ese mismo nombre.

La credencial de n8n 2.43 inyecta `apikey` y `Authorization`. No inyecta el host, así que la URL del proyecto sigue en el nodo. La clave no está en el archivo.

Los nodos Function que quedan solo preparan o leen datos. No llaman a HTTP ni leen credenciales. En esta versión el nodo Code no puede acceder a credenciales, y el nodo Function desaparece en n8n 3. No se ha desactivado `N8N_BLOCK_ENV_ACCESS_IN_NODE` para sortearlo.

## Webhooks internos

Los webhooks internos exigen la credencial `httpHeaderAuth` llamada `Internal Webhook Header`. Quien los llama usa la misma credencial. El valor no está en el archivo.

`wf01-ingest` no usa esa cabecera: Slack no puede enviarla. La firma `X-Slack-Signature` no está implementada. Tampoco se puede calcular dentro de un nodo Function o Code sin meter el secreto en el código o abrir el acceso a variables de entorno. No se ha hecho ninguna de las dos cosas.

## Reintentos

El flujo de contenido responde a Slack antes de clasificar. Las rutas de comandos de `wf01-ingest` no tienen un nodo de respuesta. Slack puede reintentarlas. No hay lectura de `X-Slack-Retry-Num` ni deduplicación en el workflow.

## Validar

```bash
python3 workflows/hostinger/validate.py
```

No hace llamadas externas. Comprueba JSON, conexiones, ausencia de claves en código y que Slack y Supabase usen credencial.

## Pendiente antes de importar

- Crear en Hostinger `Supabase account`, `Slack account`, `Header Auth account` e `Internal Webhook Header`. Los identificadores del archivo son `pending-hostinger`.
- Elegir un canal para Weekly Digest si ese flujo adicional se importa.
- Verificar la firma de Slack en `wf01-ingest` sin debilitar la seguridad.
- Responder a Slack en las rutas de comandos antes de trabajar, o aceptar los reintentos.
- Confirmar que las rutas `wf01-ingest`, `wf02-crosslink` y las demás no chocan con webhooks ya publicados.
- Estas copias salen de GitHub del 8 de abril de 2026. Pueden no coincidir con la última ejecución de Render.
