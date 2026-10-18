"""Trabajador de procesamiento. No está desplegado.

Llama a n8n solo con la cabecera interna y un paso cada vez.
"""
from queue import Empty
import json
from urllib import request

from verifier import forward_body, process


class N8nProcessor:
    def __init__(self, base_url, header_name, header_value, transport):
        if not header_name or not header_value:
            raise ValueError("cabecera interna incompleta")
        self.url = base_url.rstrip("/") + "/webhook/wf01-ingest"
        self.header_name = header_name
        self.header_value = header_value
        self.transport = transport

    def _post(self, step, payload, classification):
        body = forward_body(payload["event_id"], payload, step, classification)
        response = self.transport(
            self.url,
            {self.header_name: self.header_value, "Content-Type": "application/json"},
            body,
        )
        if int(response.get("status", 200)) >= 400:
            raise RuntimeError("n8n rechazo el paso")
        return response.get("body") or {}

    def classify(self, payload):
        return self._post("classify", payload, None)

    def insert(self, payload, classification):
        return self._post("insert", payload, classification)

    def notify(self, payload, classification):
        return self._post("notify", payload, classification)


def urllib_transport(url, headers, body):
    data = json.dumps(body).encode()
    req = request.Request(url, data=data, headers=headers, method="POST")
    with request.urlopen(req, timeout=30) as response:
        raw = response.read().decode() or "{}"
        return {"status": response.status, "body": json.loads(raw)}


def work_once(store, processor, event_id):
    return process(event_id, store, processor)


def work_queue(queue, store, processor, stop_event):
    while not stop_event.is_set():
        try:
            event_id = queue.get(timeout=0.1)
        except Empty:
            continue
        try:
            process(event_id, store, processor)
        finally:
            queue.task_done()
