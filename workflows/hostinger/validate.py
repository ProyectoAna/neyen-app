#!/usr/bin/env python3
"""Validación local de las copias Hostinger. No hace llamadas externas."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FORBIDDEN = [
    "REPLACE_WITH_SUPABASE_KEY",
    "SLACK_WEBHOOK_PLACEHOLDER",
    "SLACK_WEBHOOK_NEYEN_CORE",
    "$env",
    "helpers.httpRequest",
    "hooks.slack.com",
    "onrender.com",
    "eyJ",
]
ESSENTIAL = {
    "NEYEN-ingest.json",
    "NEYEN-crosslink.json",
    "NEYEN-crosslink-notify.json",
    "NEYEN-slack-tagger.json",
    "NEYEN-search.json",
    "NEYEN-auto-crosslink.json",
}
ADDITIONAL = {"NEYEN-timeline.json", "NEYEN-weekly-digest.json"}


def main():
    errors = []
    blockers = []
    files = sorted(ROOT.rglob("*.json"))
    names = {p.name for p in files}
    if names != ESSENTIAL | ADDITIONAL:
        errors.append(f"conjunto inesperado: {sorted(names)}")
    if any(p.parent == ROOT for p in files):
        errors.append("quedan JSON en la raíz de hostinger")
    for p in files:
        raw = p.read_text()
        data = json.loads(raw)
        if data.get("active") is not False:
            errors.append(f"{p.name}: active no es false")
        for term in FORBIDDEN:
            if term in raw:
                errors.append(f"{p.name}: contiene {term}")
        node_names = {n["name"] for n in data["nodes"]}
        for src, conn in data.get("connections", {}).items():
            if src not in node_names:
                errors.append(f"{p.name}: origen ausente {src}")
            for group in conn.get("main") or []:
                for link in group or []:
                    if link.get("node") not in node_names:
                        errors.append(f"{p.name}: destino ausente {src} -> {link.get('node')}")
        for node in data["nodes"]:
            code = (node.get("parameters") or {}).get("functionCode") or ""
            if any(x in code for x in ("apikey", "Authorization", "REPLACE_WITH", "SLACK_WEBHOOK")):
                errors.append(f"{p.name}/{node['name']}: clave o marcador en código")
            url = str((node.get("parameters") or {}).get("url") or "")
            creds = node.get("credentials") or {}
            if "/rest/v1/" in url and "supabaseApi" not in creds:
                errors.append(f"{p.name}/{node['name']}: Supabase sin credencial")
            if "slack.com/api/" in url and "slackApi" not in creds:
                errors.append(f"{p.name}/{node['name']}: Slack sin credencial")
            if node["type"].endswith("webhook"):
                path = (node.get("parameters") or {}).get("path")
                auth = (node.get("parameters") or {}).get("authentication")
                if path == "wf01-ingest" and auth != "headerAuth":
                    errors.append("wf01-ingest aceptaría una petición que evite el verificador")
                elif path != "wf01-ingest" and auth != "headerAuth":
                    errors.append(f"{p.name}/{node['name']}: webhook interno sin headerAuth")
        if p.name == "NEYEN-weekly-digest.json":
            blockers.append("Weekly Digest no trae channel_id; chat.postMessage fallará cerrado")
    blockers.append("las credenciales pending-hostinger aún no existen en Hostinger")
    blockers.append("el verificador de Slack está preparado pero no desplegado")
    blockers.append("Drive Watch no está incluido")
    print(f"archivos {len(files)}")
    print(f"errores {len(errors)}")
    for item in errors:
        print("ERROR", item)
    print(f"bloqueos {len(set(blockers))}")
    for item in sorted(set(blockers)):
        print("BLOQUEO", item)
    if errors:
        return 1
    print("VALIDATION_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
