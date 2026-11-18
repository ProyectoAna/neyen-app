#!/bin/bash
# Prueba de contenedor aislada (podman rootless o docker). Sin credenciales reales: todo ficticio y efimero.
# Uso: bash run_container_test.sh   (desde cualquier carpeta)
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; SV="$HERE/../.."
ENGINE=${ENGINE:-podman}
PORT=${VERIFIER_HOST_PORT:-18080}
export SLACK_SIGNING_SECRET="firma-ficticia-contenedor-0123456789"
export N8N_BASE_URL="http://n8n:5678" N8N_INTERNAL_HEADER_NAME="X-Neyen-Internal" N8N_INTERNAL_HEADER_VALUE="cabecera-ficticia-contenedor-abcdef"
export VERIFIER_HOST_PORT=$PORT FAKE_N8N="$HERE/fake_n8n.py"
IMG=localhost/neyen/slack-verifier:local
P=nvtest; fail=0
ok(){ echo "OK   $1"; }; ko(){ echo "FAIL $1"; fail=1; }
check(){ if eval "$2"; then ok "$1"; else ko "$1"; fi; }
if [ "$ENGINE" = podman ]; then DC="podman-compose"; else DC="docker compose"; fi
C="$DC -p $P -f $SV/docker-compose.yml -f $SV/docker-compose.local.yml -f $HERE/compose.test.yml"
cleanup(){ $C down -v >/dev/null 2>&1; rm -rf "${BIND:-/nonexistent}"; }
trap cleanup EXIT; cleanup

$ENGINE build --format docker -t $IMG "$SV" >/dev/null 2>&1; check "imagen construida" "$ENGINE image exists $IMG"
check "usuario no root (uid 10001)" "[ \"\$($ENGINE run --rm --entrypoint id $IMG -u)\" = 10001 ]"
check "imagen sin ficheros de prueba ni .env" "! $ENGINE run --rm --entrypoint sh $IMG -c 'ls /app | grep -E \"^test_|^\\.env\"' >/dev/null 2>&1"
bad=$($ENGINE run --rm -e SLACK_SIGNING_SECRET=corto-secreto -e N8N_BASE_URL=http://n8n.example.com $IMG check-config 2>&1); rc=$?
check "config invalida: sale con 2 y sin valores" "[ $rc = 2 ] && ! echo '$bad' | grep -q corto-secreto && echo '$bad' | grep -q N8N_BASE_URL"

# volumen con permisos incorrectos (carpeta de host de otro propietario): debe fallar rapido y claro
BIND=$(mktemp -d); sudo chown 0:0 "$BIND"; sudo chmod 755 "$BIND"
out=$($ENGINE run --rm -v "$BIND:/data:z" -e SLACK_SIGNING_SECRET=$SLACK_SIGNING_SECRET -e N8N_BASE_URL=http://n8n:5678 -e N8N_INTERNAL_HEADER_NAME=X-Neyen-Internal -e N8N_INTERNAL_HEADER_VALUE=$N8N_INTERNAL_HEADER_VALUE $IMG check-config 2>&1); rc=$?
check "bind root:root sin permiso -> falla rapido (SQLITE_PATH no escribible)" "[ $rc = 2 ] && echo '$out' | grep -q 'SQLITE_PATH'"
sudo rm -rf "$BIND"; BIND=$(mktemp -d); chmod 777 "$BIND"; BIND=""

$C up -d >/dev/null 2>&1
for i in $(seq 1 30); do [ "$(curl -s -m 2 localhost:$PORT/healthz)" = '{"status": "ok", "db": "ok", "worker": "ok"}' ] && break; sleep 1; done
check "healthz 200 sin datos sensibles" "[ \"\$(curl -s -m 3 localhost:$PORT/healthz)\" = '{\"status\": \"ok\", \"db\": \"ok\", \"worker\": \"ok\"}' ]"
check "uid del proceso 10001 y escribe en /data (volumen con nombre)" "$ENGINE exec ${P}_slack-verifier_1 sh -c 'id -u; touch /data/.w && rm /data/.w' | head -1 | grep -qx 10001"
# podman rootless sin systemd no programa el healthcheck solo: se ejecuta el comando configurado a mano
check "healthcheck del compose (service.py healthcheck) devuelve 0" "$ENGINE healthcheck run ${P}_slack-verifier_1"

send(){ python3 - "$1" "$2" <<'P'
import hashlib,hmac,json,sys,time,urllib.request,urllib.error,os
eid,sig_ok=sys.argv[1],sys.argv[2]=="good"
body=json.dumps({"type":"event_callback","event_id":eid,"event":{"type":"message","text":"nota","user":"U1","channel":"CPRUEBA"}}).encode()
ts=str(int(time.time())); s=os.environ["SLACK_SIGNING_SECRET"]
sig="v0="+hmac.new(s.encode(),f"v0:{ts}:".encode()+body,hashlib.sha256).hexdigest()
if not sig_ok: sig="v0="+"0"*64
r=urllib.request.Request(f"http://127.0.0.1:{os.environ['VERIFIER_HOST_PORT']}/slack/events",data=body,headers={"X-Slack-Request-Timestamp":ts,"X-Slack-Signature":sig})
try: print(urllib.request.urlopen(r,timeout=5).status)
except urllib.error.HTTPError as e: print(e.code)
P
}
check "firma valida -> 200" "[ \"\$(send EvC1 good)\" = 200 ]"
check "firma erronea -> 401" "[ \"\$(send EvBAD bad)\" = 401 ]"
sleep 3
check "n8n recibio classify/insert/notify de EvC1 con la cabecera interna" "[ \"\$($ENGINE logs ${P}_n8n_1 2>&1 | grep EvC1 | grep -c '\"auth\": true')\" = 3 ]"
check "EvBAD no llego a n8n" "! $ENGINE logs ${P}_n8n_1 2>&1 | grep -q EvBAD"
check "proxy alcanza el servicio por nombre en la red del compose (n8n -> slack-verifier:8080)" "$ENGINE exec ${P}_n8n_1 python -c \"import urllib.request as u;print(u.urlopen('http://slack-verifier:8080/healthz',timeout=4).status)\" | grep -qx 200"
check "127.0.0.1 de otro contenedor NO llega al servicio (publicar en loopback no basta)" "! $ENGINE exec ${P}_n8n_1 python -c \"import urllib.request as u;u.urlopen('http://127.0.0.1:8080/healthz',timeout=3)\" >/dev/null 2>&1"

# persistencia tras recrear el contenedor
$C stop -t 2 slack-verifier >/dev/null 2>&1; $ENGINE rm -f ${P}_slack-verifier_1 >/dev/null 2>&1
$C up -d slack-verifier >/dev/null 2>&1
for i in $(seq 1 30); do curl -s -m 2 localhost:$PORT/healthz | grep -q '"ok"' && break; sleep 1; done
check "tras recrear el contenedor, EvC1 sigue en SQLite como processed" "$ENGINE exec ${P}_slack-verifier_1 python -c \"import sqlite3;print(sqlite3.connect('/data/events.sqlite').execute('select status from events where event_id=\\\"EvC1\\\"').fetchone()[0])\" | grep -qx processed"
check "reenvio de EvC1 -> 200 sin reprocesar" "[ \"\$(send EvC1 good)\" = 200 ] && sleep 2 && [ \"\$($ENGINE logs ${P}_n8n_1 2>&1 | grep -c EvC1)\" = 3 ]"

# superposicion para Traefik propio: fusiona sin ports y con la red externa del proxy
$ENGINE network create nvtest_proxy >/dev/null 2>&1
export TRAEFIK_NETWORK=nvtest_proxy VERIFIER_DOMAIN=verificador.invalido.test
$C -f $SV/docker-compose.traefik.yml config >/tmp/nv_traefik_cfg.txt 2>&1
check "docker-compose.traefik.yml se fusiona (red externa y etiquetas)" "grep -q nvtest_proxy /tmp/nv_traefik_cfg.txt && grep -q 'loadbalancer.server.port' /tmp/nv_traefik_cfg.txt"
$ENGINE network rm nvtest_proxy >/dev/null 2>&1

# apagado ordenado
t0=$(date +%s); $ENGINE stop -t 20 ${P}_slack-verifier_1 >/dev/null 2>&1; t1=$(date +%s)
check "apagado ordenado: codigo 0 en < 10 s" "[ \"\$($ENGINE inspect -f '{{.State.ExitCode}}' ${P}_slack-verifier_1)\" = 0 ] && [ $((t1-t0)) -lt 10 ]"
check "logs sin secretos" "! $ENGINE logs ${P}_slack-verifier_1 2>&1 | grep -q -e \"\$SLACK_SIGNING_SECRET\" -e \"\$N8N_INTERNAL_HEADER_VALUE\""
echo; [ $fail = 0 ] && echo "TODO OK" || echo "HAY FALLOS"; exit $fail
