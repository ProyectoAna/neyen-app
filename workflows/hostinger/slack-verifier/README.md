# Verificador de Slack

No está desplegado. Slack no debe apuntar todavía a n8n ni a este servicio.

n8n 2.43 no puede comprobar la firma dentro de un nodo Function o Code sin escribir el secreto en el flujo o abrir el acceso general a variables de entorno. Este verificador hace esa comprobación fuera de n8n.

## Orden

1. Comprueba la firma sobre el cuerpo original y que el timestamp no tenga más de cinco minutos.
2. Si es un challenge, solo lo devuelve cuando la firma es válida. No lo reenvía a n8n.
3. Guarda el evento en SQLite.
4. Solo entonces responde `200` a Slack.
5. Después procesa, en otro paso.

Si no puede guardar el evento, no confirma la recepción.

## Deduplicación y recuperación

Un `event_id` repetido recibe `200` y no vuelve a procesarse.

Cada paso queda en `pending`, `done` o `uncertain`:

- `classify` es la llamada a Claude.
- `insert` es la inserción. En n8n va con `on_conflict=file_name` para no crear otra ficha si el nombre ya existe.
- `notify` cubre avisos y el cruce.

Solo un paso `done` permite avanzar. `started` y `uncertain` bloquean los siguientes y exigen reconciliación; no se reintentan solos.

SQLite es la fuente de trabajo. Al arrancar, y de forma periódica, se recuperan los eventos pendientes. La cola en memoria solo avisa; no es el único mecanismo.

Una reserva autorizada no caduca por tiempo mientras ese trabajador pueda seguir escribiendo.

`server.py` recibe, guarda y responde. `worker.py` procesa después, un paso cada vez, con la cabecera interna. Ninguno está desplegado.

Los comandos que empiezan por `/` no planifican Claude ni inserción.

## Endpoint interno

`wf01-ingest` exige la credencial `Internal Webhook Header`. Una petición directa de Slack, sin pasar por este verificador, no lleva esa cabecera y n8n la rechaza.

El secreto de firma no está en el código. Se pasa al ejecutar el verificador y las pruebas usan un valor ficticio.

## Pruebas

```bash
python3 -m unittest workflows/hostinger/slack-verifier/test_verifier.py
```

## Servicio (entrada, configuración y contenedor)

- `service.py serve | check-config | recover EVENT_ID`; configuración por variables de entorno en `config.py` (ver `.env.example`; los secretos nunca van al repo).
- `Dockerfile` + `docker-compose.yml` (sin puertos publicados, volumen `/data`, `GET /healthz`), `docker-compose.local.yml` (loopback, pruebas) y `docker-compose.traefik.yml` (Traefik propio). HTTPS lo termina el proxy. Detalle, puertos y pasos en `docs/DEPLOYMENT-PROCEDURE.md`, sección 5.
- Pruebas del servicio: `python3 -m unittest test_service` (arranca `service.py` desde carpeta limpia, con n8n simulado).
- Prueba de contenedor (podman o docker): `bash integration-harness/container/run_container_test.sh` (n8n simulado, secretos ficticios, efímera).
