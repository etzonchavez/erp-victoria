FROM python:3.12-slim

WORKDIR /code

COPY pyproject.toml .
COPY app ./app
RUN pip install --no-cache-dir .

COPY alembic.ini .
COPY migrations ./migrations

EXPOSE 8000
# Aplica las migraciones pendientes y luego inicia la API
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]
