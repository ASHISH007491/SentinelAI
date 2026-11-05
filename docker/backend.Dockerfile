# SentinelAI backend — FastAPI + Alembic + agent pipeline.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first (better layer caching), then the app.
COPY pyproject.toml ./
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
RUN pip install --upgrade pip && pip install .

COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh && mkdir -p var/uploads

EXPOSE 8000
CMD ["./docker-entrypoint.sh"]
