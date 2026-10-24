"""Conexión a base de datos. Cada cliente (tenant) tendrá su propia BD según ADR-002."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

from sqlalchemy import DateTime, Uuid, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def ahora_utc() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Base de todos los modelos. Cada módulo define sus tablas heredando de aquí."""


class ConAuditoria:
    """Columnas estándar de toda tabla de negocio (ver Convenciones)."""

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    creado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=ahora_utc, onupdate=ahora_utc
    )
    actualizado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def database_is_up() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
