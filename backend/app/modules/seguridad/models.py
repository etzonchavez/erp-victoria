"""Tablas del módulo de seguridad (prefijo seg_)."""

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Table,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, ConAuditoria, ahora_utc

seg_usuario_rol = Table(
    "seg_usuario_rol",
    Base.metadata,
    Column("usuario_id", Uuid, ForeignKey("seg_usuario.id", ondelete="CASCADE"), primary_key=True),
    Column("rol_id", Uuid, ForeignKey("seg_rol.id", ondelete="CASCADE"), primary_key=True),
)

seg_rol_permiso = Table(
    "seg_rol_permiso",
    Base.metadata,
    Column("rol_id", Uuid, ForeignKey("seg_rol.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "permiso_codigo",
        String(100),
        ForeignKey("seg_permiso.codigo", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Modulo(Base):
    __tablename__ = "seg_modulo"

    codigo: Mapped[str] = mapped_column(String(50), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    abreviatura: Mapped[str] = mapped_column(String(3))
    orden: Mapped[int] = mapped_column(Integer, default=0)
    activo: Mapped[bool] = mapped_column(Boolean, default=False)
    obligatorio: Mapped[bool] = mapped_column(Boolean, default=False)


class Permiso(Base):
    __tablename__ = "seg_permiso"

    codigo: Mapped[str] = mapped_column(String(100), primary_key=True)
    modulo: Mapped[str] = mapped_column(ForeignKey("seg_modulo.codigo"))
    descripcion: Mapped[str] = mapped_column(String(200))


class Rol(ConAuditoria, Base):
    __tablename__ = "seg_rol"

    codigo: Mapped[str] = mapped_column(String(50), unique=True)
    modulo: Mapped[str] = mapped_column(ForeignKey("seg_modulo.codigo"))
    nombre: Mapped[str] = mapped_column(String(100))
    descripcion: Mapped[str | None] = mapped_column(String(300), nullable=True)
    tipo: Mapped[str] = mapped_column(String(20), default="operativo", server_default="operativo")
    estandar: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    permisos: Mapped[list[Permiso]] = relationship(secondary=seg_rol_permiso, lazy="selectin")


class Usuario(ConAuditoria, Base):
    __tablename__ = "seg_usuario"

    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(150))
    password_hash: Mapped[str] = mapped_column(String(300))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    es_administrador: Mapped[bool] = mapped_column(Boolean, default=False)
    ultimo_acceso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    roles: Mapped[list[Rol]] = relationship(secondary=seg_usuario_rol, lazy="selectin")


class Auditoria(Base):
    __tablename__ = "seg_auditoria"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc, index=True)
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    usuario_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    accion: Mapped[str] = mapped_column(String(50))
    entidad: Mapped[str] = mapped_column(String(50), index=True)
    entidad_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    detalle: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Personalizacion(Base):
    """Marca del cliente: una sola fila (id = 1)."""

    __tablename__ = "seg_personalizacion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    nombre_empresa: Mapped[str | None] = mapped_column(String(150), nullable=True)
    logo: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    logo_tipo: Mapped[str | None] = mapped_column(String(30), nullable=True)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=ahora_utc, onupdate=ahora_utc
    )
    actualizado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


class Atributo(ConAuditoria, Base):
    """Configuración de un atributo adicional de un documento operativo (ADR-005).

    Una fila por atributo configurado alguna vez; los que no tienen fila están inactivos.
    La configuración es una sola para todo el grupo de empresas.
    """

    __tablename__ = "seg_atributo"
    __table_args__ = (UniqueConstraint("documento", "nivel", "tipo", "numero"),)

    documento: Mapped[str] = mapped_column(String(30))  # solicitud, orden_compra…
    nivel: Mapped[str] = mapped_column(String(20))  # cabecera, linea, distribucion
    tipo: Mapped[str] = mapped_column(String(10))  # texto, numero, fecha
    numero: Mapped[int] = mapped_column(Integer)  # 1..10
    etiqueta: Mapped[str | None] = mapped_column(String(60), nullable=True)
    ayuda: Mapped[str | None] = mapped_column(String(200), nullable=True)
    valor_defecto: Mapped[str | None] = mapped_column(String(240), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=False)
    # Atributo del documento siguiente al que se copia (mismo nivel y tipo)
    copiar_documento: Mapped[str | None] = mapped_column(String(30), nullable=True)
    copiar_numero: Mapped[int | None] = mapped_column(Integer, nullable=True)

    valores: Mapped[list["AtributoValor"]] = relationship(
        lazy="selectin", order_by="AtributoValor.orden", cascade="all, delete-orphan"
    )


class AtributoValor(Base):
    """Lista de valores de un atributo de texto."""

    __tablename__ = "seg_atributo_valor"
    __table_args__ = (UniqueConstraint("atributo_id", "valor"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    atributo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("seg_atributo.id", ondelete="CASCADE"), index=True
    )
    valor: Mapped[str] = mapped_column(String(240))
    orden: Mapped[int] = mapped_column(Integer, default=0)
