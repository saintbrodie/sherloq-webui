FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SHERLOQ_WORKDIR=/tmp/sherloq-webui-sessions

WORKDIR /app

COPY requirements-web.txt ./
RUN pip install --no-cache-dir -r requirements-web.txt

COPY web ./web

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin sherloq \
    && mkdir -p /tmp/sherloq-webui-sessions \
    && chown -R sherloq:sherloq /tmp/sherloq-webui-sessions

USER sherloq

EXPOSE 8000

CMD ["uvicorn", "web.main:app", "--host", "0.0.0.0", "--port", "8000"]
