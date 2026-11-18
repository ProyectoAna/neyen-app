#!/bin/bash
# Reinicia las dos instancias de n8n de prueba (no toca Postgres ni PostgREST).
export PATH=/workspace/n8ntest/node_modules/.bin:$PATH N8N_ENCRYPTION_KEY=fake-test-key-not-secret N8N_DIAGNOSTICS_ENABLED=false N8N_VERSION_NOTIFICATIONS_ENABLED=false
pkill -f "n8n start"; sleep 3
cd /workspace/n8ntest
(N8N_USER_FOLDER=/workspace/n8ntest/home N8N_PORT=5680 nohup n8n start > n8n.log 2>&1 &)
(N8N_USER_FOLDER=/workspace/n8ntest/home_r2 N8N_PORT=5681 N8N_RUNNERS_BROKER_PORT=5689 nohup n8n start > n8n_r2.log 2>&1 &)
for i in $(seq 1 60); do
  a=$(curl -s -o /dev/null -w "%{http_code}" localhost:5680/healthz); b=$(curl -s -o /dev/null -w "%{http_code}" localhost:5681/healthz)
  [ "$a$b" = "200200" ] && exit 0; sleep 2
done; exit 1
