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

## Entrada de Slack

La firma se comprueba en `slack-verifier/`, fuera de n8n y sin desplegar. Usa el cuerpo original y rechaza un timestamp de más de cinco minutos. El challenge solo se devuelve si la firma es válida.

El verificador guarda el evento antes de responder `200`. Después procesa. Un evento repetido no vuelve a procesarse. La recuperación no repite pasos ya hechos ni pasos de resultado incierto.

`wf01-ingest` exige `Internal Webhook Header`. Una petición que no pase por el verificador no lleva esa cabecera y queda rechazada. El secreto no está en el flujo ni en el código.

## Validar

```bash
python3 workflows/hostinger/validate.py
```

No hace llamadas externas. Comprueba JSON, conexiones, ausencia de claves en código y que Slack y Supabase usen credencial.

## Pendiente antes de importar

- Crear en Hostinger `Supabase account`, `Slack account`, `Header Auth account` e `Internal Webhook Header`. Los identificadores del archivo son `pending-hostinger`.
- Elegir un canal para Weekly Digest si ese flujo adicional se importa.
- Desplegar el verificador y crear la credencial interna antes de cambiar la URL de Slack.
- Confirmar que `metadata.file_name` es único antes de usar la inserción sin duplicados.
- Confirmar que las rutas `wf01-ingest`, `wf02-crosslink` y las demás no chocan con webhooks ya publicados.
- Estas copias salen de GitHub del 8 de abril de 2026. Pueden no coincidir con la última ejecución de Render.
