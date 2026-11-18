"""Configuracion del verificador por variables de entorno.

Los secretos se leen de una variable o de un fichero (NOMBRE_FILE, p. ej. un secreto de Docker).
Los errores nombran la variable y el motivo; nunca incluyen el valor.
"""
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

TOKEN = re.compile(r"^[A-Za-z0-9!#$%&'*+.^_`|~-]+$")
MIN_SECRET = 16


class ConfigError(Exception):
    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


@dataclass(frozen=True)
class Config:
    signing_secret: str
    n8n_base_url: str
    header_name: str
    header_value: str
    sqlite_path: Path
    host: str
    port: int
    poll_seconds: float
    grace_seconds: float
    post_path: str

    def __repr__(self):  # nunca imprime secretos
        return (f"Config(n8n_base_url={self.n8n_base_url!r}, header_name={self.header_name!r}, "
                f"sqlite_path={str(self.sqlite_path)!r}, host={self.host!r}, port={self.port}, "
                f"post_path={self.post_path!r}, secretos=<ocultos>)")


def _read(env, name, problems, required=True):
    file_name = env.get(name + "_FILE")
    if file_name:
        try:
            value = Path(file_name).read_text().strip()
        except OSError:
            problems.append(f"{name}_FILE: no se puede leer el fichero indicado")
            return None
    else:
        value = (env.get(name) or "").strip()
    if not value:
        if required:
            problems.append(f"{name}: falta (variable {name} o {name}_FILE)")
        return None
    return value


def _is_internal(host):
    return host in ("localhost", "127.0.0.1", "::1") or "." not in host


def load_config(env=None):
    env = os.environ if env is None else env
    problems = []

    secret = _read(env, "SLACK_SIGNING_SECRET", problems)
    if secret and len(secret) < MIN_SECRET:
        problems.append(f"SLACK_SIGNING_SECRET: demasiado corto (minimo {MIN_SECRET} caracteres)")

    base_url = (env.get("N8N_BASE_URL") or "").strip()
    if not base_url:
        problems.append("N8N_BASE_URL: falta")
    else:
        u = urlparse(base_url)
        if u.scheme not in ("http", "https") or not u.hostname:
            problems.append("N8N_BASE_URL: debe ser una URL http(s) con host")
        elif u.query or u.fragment or u.username or u.password:
            problems.append("N8N_BASE_URL: no debe llevar credenciales, query ni fragmento")
        elif u.scheme == "http" and not _is_internal(u.hostname):
            problems.append("N8N_BASE_URL: http solo se admite para localhost o un nombre de servicio interno; use https")
        elif "/webhook" in u.path:
            problems.append("N8N_BASE_URL: indique solo la base, sin /webhook/...")

    header_name = (env.get("N8N_INTERNAL_HEADER_NAME") or "").strip()
    if not header_name:
        problems.append("N8N_INTERNAL_HEADER_NAME: falta")
    elif not TOKEN.match(header_name):
        problems.append("N8N_INTERNAL_HEADER_NAME: no es un nombre de cabecera valido")
    header_value = _read(env, "N8N_INTERNAL_HEADER_VALUE", problems)
    if header_value and len(header_value) < MIN_SECRET:
        problems.append(f"N8N_INTERNAL_HEADER_VALUE: demasiado corto (minimo {MIN_SECRET} caracteres)")
    if secret and header_value and secret == header_value:
        problems.append("N8N_INTERNAL_HEADER_VALUE: no puede ser igual al secreto de firma de Slack")

    sqlite_path = Path(env.get("SQLITE_PATH") or "/data/events.sqlite")
    parent = sqlite_path.parent
    if not parent.is_dir():
        problems.append("SQLITE_PATH: el directorio no existe (monte el volumen)")
    elif not os.access(parent, os.W_OK):
        problems.append("SQLITE_PATH: el directorio no es escribible")
    elif sqlite_path.exists() and not os.access(sqlite_path, os.R_OK | os.W_OK):
        problems.append("SQLITE_PATH: el fichero existente no es legible/escribible")

    def number(name, default, cast, low, high):
        raw = env.get(name)
        if raw in (None, ""):
            return default
        try:
            value = cast(raw)
        except ValueError:
            problems.append(f"{name}: no es un numero valido")
            return default
        if not (low <= value <= high):
            problems.append(f"{name}: fuera de rango ({low}-{high})")
            return default
        return value

    port = number("PORT", 8080, int, 1, 65535)
    poll = number("WORKER_POLL_SECONDS", 2.0, float, 0.1, 300)
    grace = number("SHUTDOWN_GRACE_SECONDS", 35.0, float, 1, 600)
    post_path = (env.get("SLACK_EVENTS_PATH") or "/slack/events").strip()
    if not post_path.startswith("/") or " " in post_path:
        problems.append("SLACK_EVENTS_PATH: debe empezar por / y no llevar espacios")

    if problems:
        raise ConfigError(problems)
    return Config(secret, base_url.rstrip("/"), header_name, header_value, sqlite_path,
                  (env.get("HOST") or "0.0.0.0").strip(), port, poll, grace, post_path)
