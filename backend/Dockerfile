FROM python:3.12-slim

WORKDIR /code

# Librerías que WeasyPrint necesita para generar el PDF de la orden de compra (ADR-007)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY app ./app
RUN pip install --no-cache-dir .

COPY alembic.ini .
COPY migrations ./migrations

EXPOSE 8000
# Aplica las migraciones pendientes y luego inicia la API
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]
