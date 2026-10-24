# Harvest Expedition API — JagaPanen V2 P0
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN touch README.md
COPY app ./app
COPY infra ./infra

RUN pip install --user --no-cache-dir .

# -------------------------
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

RUN adduser --disabled-password --gecos '' appuser

COPY --from=builder /root/.local /home/appuser/.local
COPY ./app ./app
COPY ./infra ./infra
COPY ./scripts/docker_entrypoint.py /entrypoint.py

RUN chown -R appuser:appuser /app /home/appuser/.local /entrypoint.py

ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

USER appuser

EXPOSE 8009

ENTRYPOINT ["python", "/entrypoint.py"]
