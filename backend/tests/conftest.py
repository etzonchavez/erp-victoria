"""Cada prueba corre sobre una base SQLite en memoria, limpia y con el catálogo cargado."""

import os

os.environ["BOOTSTRAP_ON_STARTUP"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.arranque import preparar_sistema  # noqa: E402
from app.core.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402

ADMIN = {"email": "admin@erp-victoria.local", "password": "Admin123!"}
API = "/api/v1/seguridad"


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Sesion = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Sesion() as s:
        preparar_sistema(s)

    def _get_db():
        with Sesion() as s:
            yield s

    app.dependency_overrides[get_db] = _get_db
    yield Sesion
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def client(db):
    return TestClient(app)


def login(client: TestClient, email: str, password: str) -> dict:
    r = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def admin(client) -> dict:
    return login(client, **ADMIN)
