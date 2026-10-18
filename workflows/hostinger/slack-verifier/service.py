"""Punto de entrada del verificador de Slack: servidor de recepcion + trabajador.

    python service.py serve            # arranca (valida la configuracion antes)
    python service.py check-config     # solo valida; no abre puertos ni toca SQLite
    python service.py recover EVENT_ID # reanuda un evento tras reconciliarlo (ver docs)
    python service.py healthcheck      # exit 0 si GET /healthz local da 200 (lo usa el contenedor)

Un SIGTERM/SIGINT detiene el servidor, deja terminar el paso en curso (hasta
SHUTDOWN_GRACE_SECONDS) y sale con codigo 0. Los eventos pendientes quedan en SQLite y se
retoman al arrancar.
"""
import signal
import sys
import threading
from queue import Empty, Queue

from config import ConfigError, load_config
from server import serve
from verifier import EventStore, recover
from worker import N8nProcessor, urllib_transport, work_available


def build(config, transport=urllib_transport):
    store = EventStore(config.sqlite_path)
    processor = N8nProcessor(config.n8n_base_url, config.header_name, config.header_value, transport)
    return store, processor


def worker_loop(store, processor, queue, stop_event, poll_seconds):
    """SQLite es la fuente de trabajo; la cola solo despierta al trabajador."""
    work_available(store, processor)  # recuperacion al arrancar
    while not stop_event.is_set():
        try:
            queue.get(timeout=poll_seconds)
            queue.task_done()
        except Empty:
            pass
        if stop_event.is_set():
            break
        work_available(store, processor)


def make_health(store, worker_thread):
    def health():
        ok_db = True
        try:
            store.list_available()
        except Exception:
            ok_db = False
        ok_worker = worker_thread.is_alive()
        status = 200 if (ok_db and ok_worker) else 503
        return status, {"status": "ok" if status == 200 else "error",
                        "db": "ok" if ok_db else "error",
                        "worker": "ok" if ok_worker else "error"}
    return health


def run(config, transport=urllib_transport, install_signals=True, ready=None):
    store, processor = build(config, transport)
    queue = Queue()
    stop = threading.Event()
    thread = threading.Thread(target=worker_loop, args=(store, processor, queue, stop, config.poll_seconds),
                              name="worker", daemon=True)
    thread.start()
    httpd = serve(config.host, config.port, config.signing_secret, store, queue,
                  post_paths={config.post_path}, health=make_health(store, thread))

    def shutdown(*_):
        stop.set()
        threading.Thread(target=httpd.shutdown, daemon=True).start()

    if install_signals:
        signal.signal(signal.SIGTERM, shutdown)
        signal.signal(signal.SIGINT, shutdown)
    if ready:
        ready(httpd, shutdown)
    print(f"verificador escuchando en {config.host}:{httpd.server_address[1]} (ruta {config.post_path})", flush=True)
    try:
        httpd.serve_forever()
    finally:
        stop.set()
        httpd.server_close()
        thread.join(timeout=config.grace_seconds)
        if thread.is_alive():
            print("aviso: el paso en curso no termino en el plazo; quedara para reconciliar", flush=True)
    return 0


def main(argv=None, env=None):
    argv = sys.argv[1:] if argv is None else argv
    command = argv[0] if argv else "serve"
    if command not in ("serve", "check-config", "recover", "healthcheck"):
        print("uso: service.py serve | check-config | recover EVENT_ID | healthcheck", file=sys.stderr)
        return 2
    if command == "healthcheck":
        import os
        import urllib.request
        try:
            url = "http://127.0.0.1:%s/healthz" % ((env or os.environ).get("PORT") or "8080")
            return 0 if urllib.request.urlopen(url, timeout=4).status == 200 else 1
        except Exception:
            return 1
    try:
        config = load_config(env)
    except ConfigError as exc:
        print("CONFIGURACION INVALIDA:", file=sys.stderr)
        for problem in exc.problems:
            print(" - " + problem, file=sys.stderr)
        return 2
    if command == "check-config":
        print("configuracion valida: " + repr(config))
        return 0
    if command == "recover":
        if len(argv) != 2:
            print("uso: service.py recover EVENT_ID", file=sys.stderr)
            return 2
        store, processor = build(config)
        result = recover(argv[1], store, processor)
        print({k: v for k, v in result.items() if k in ("recovered", "complete", "blocked", "skipped", "busy")})
        return 0 if result.get("recovered") else 1
    return run(config)


if __name__ == "__main__":
    sys.exit(main())
