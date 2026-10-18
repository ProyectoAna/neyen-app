# Harness de integración local (solo pruebas, servicios simulados)

- `mock.py`: Anthropic, Supabase (REST y RPC `crosslink_entry`) y Slack simulados en 127.0.0.1:9100. Registra las llamadas.
- `sync.sh`: reescribe las URLs de **copias temporales** de los workflows hacia los simuladores, las importa en un n8n local aislado (puerto 5680, carpeta de usuario propia, credenciales ficticias) y lo arranca. No toca los JSON del repo.
- Rutas absolutas de `sync.sh` (`/workspace/n8ntest`, `/workspace/neyen-app`): ajustar. Requiere n8n 2.43.7 y Node 24 (`npm i n8n@2.43.7 node@24`) y credenciales ficticias importadas con los nombres `Internal Webhook Header`, `Header Auth account`, `Supabase account`, `Slack account`.
- Pruebas: `NEYEN_IT=1 python3 -m unittest test_integration test_integration_chain`.
- El canal de respaldo de las pruebas (`CTESTFALLBACK`) solo existe en la copia temporal; en el repo `CONFIGURED_CHANNEL` queda vacío.
