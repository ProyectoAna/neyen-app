# Verificador de Slack de NEYEN. Solo biblioteca estandar de Python: no hay dependencias que instalar.
# Contexto de construccion: esta carpeta (workflows/hostinger/slack-verifier).
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 SQLITE_PATH=/data/events.sqlite

RUN useradd --system --uid 10001 --no-create-home verifier \
 && mkdir /data && chown verifier /data

WORKDIR /app
COPY config.py server.py service.py verifier.py worker.py ./

USER verifier
VOLUME ["/data"]
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "service.py", "healthcheck"]

ENTRYPOINT ["python", "service.py"]
CMD ["serve"]
