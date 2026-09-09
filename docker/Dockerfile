# Sherloq WebUI container targets.
#
# The default/final target is the lightweight WebUI. Optional ML workers use
# separate base images because their dependency stacks are intentionally
# isolated from the normal application image.

FROM python:3.12-slim AS webui

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SHERLOQ_WORKDIR=/tmp/sherloq-webui-sessions

WORKDIR /app

COPY requirements-web.txt ./
RUN pip install --no-cache-dir -r requirements-web.txt

COPY web ./web
COPY logo ./logo

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin sherloq \
    && mkdir -p /tmp/sherloq-webui-sessions \
    && chown -R sherloq:sherloq /tmp/sherloq-webui-sessions

USER sherloq
EXPOSE 8000
CMD ["uvicorn", "web.main:app", "--host", "0.0.0.0", "--port", "8000"]


FROM python:3.11-slim AS noiseprint

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TF_CPP_MIN_LOG_LEVEL=2

WORKDIR /app

COPY requirements-noiseprint.txt ./
RUN pip install --no-cache-dir -r requirements-noiseprint.txt

COPY web ./web
COPY gui/noiseprint ./noiseprint

RUN useradd --create-home --uid 10002 --shell /usr/sbin/nologin sherloq-noiseprint
USER sherloq-noiseprint
EXPOSE 8101
CMD ["uvicorn", "web.noiseprint_worker:app", "--host", "0.0.0.0", "--port", "8101"]


FROM python:3.11-slim AS median

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SHERLOQ_MEDIAN_MODEL=/app/models/median_b64.json

WORKDIR /app

COPY requirements-median.txt ./
RUN pip install --no-cache-dir -r requirements-median.txt

COPY web ./web
COPY gui/models/median_b64.json ./models/median_b64.json

RUN useradd --create-home --uid 10003 --shell /usr/sbin/nologin sherloq-median
USER sherloq-median
EXPOSE 8103
CMD ["uvicorn", "web.median_worker:app", "--host", "0.0.0.0", "--port", "8103"]


FROM pytorch/pytorch:1.11.0-cuda11.3-cudnn8-runtime AS trufor

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SHERLOQ_TRUFOR_ROOT=/opt/trufor \
    SHERLOQ_TRUFOR_WEIGHTS=/opt/trufor/test_docker/weights/trufor.pth.tar \
    SHERLOQ_TRUFOR_GPU=-1

WORKDIR /app

COPY requirements-trufor.txt ./
RUN pip install --no-cache-dir -r requirements-trufor.txt

COPY web/__init__.py ./web/__init__.py
COPY web/trufor_worker.py ./web/trufor_worker.py

RUN useradd --create-home --uid 10004 sherloq-trufor \
    && chown -R sherloq-trufor:sherloq-trufor /app

USER sherloq-trufor
EXPOSE 8102
CMD ["uvicorn", "web.trufor_worker:app", "--host", "0.0.0.0", "--port", "8102"]


# Keep `docker build -f docker/Dockerfile .` intuitive: without --target it
# produces the normal lightweight WebUI rather than the final ML worker above.
FROM webui AS default
