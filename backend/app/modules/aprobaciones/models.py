"""Tablas del motor de aprobación (prefijo apr_).

El motor es común a todos los documentos que se aprueban (solicitud hoy; orden de compra
después). Una regla por empresa elige quién aprueba según condiciones; cada envío del
documento crea sus pasos de aprobación (una "ronda").
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, ConAuditoria

MODOS = {
    "serie": "En serie: aprueban uno tras otro, en el orden definido",
    "paralelo_todos": "Paralelo: deben aprobar todos",
    "paralelo_cualquiera": "Paralelo: basta con que apruebe uno",
}
TIPOS_APROBADOR = {
    "usuario": "Usuario específico",
    "rol": "Rol",
    "responsable_cc": "Responsable del centro de costo",
    "jefe": "Jefe del solicitante",
}
MAX_NIVELES = 3
# Documentos que se aprueban: nombre y prefijo de los permisos de sus reglas
DOCUMENTOS = {
    "solicitud": ("Solicitudes de compra", "solicitudes.regla"),
    "orden_compra": ("Órdenes de compra", "compras.regla"),
}


class Regla(ConAuditoria, Base):
    __tablename__ = "apr_regla"
    __table_args__ = (UniqueConstraint("empresa_id", "documento", "prioridad"),)

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mae_empresa.id"), index=True)
    documento: Mapped[str] = mapped_column(String(30))  # solicitud, orden_compra
    nombre: Mapped[str] = mapped_column(String(100))
    prioridad: Mapped[int] = mapped_column(Integer)  # 1 = se evalúa primero
    # Condiciones (vacías = cualquiera)
    unidad_negocio_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mae_unidad_negocio.id"), nullable=True
    )
    categoria_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mae_categoria.id"), nullable=True
    )
    tipo_articulo: Mapped[str | None] = mapped_column(String(30), nullable=True)
    centro_costo_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cnt_centro_costo.id"), nullable=True
    )
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    niveles: Mapped[list["Nivel"]] = relationship(
        lazy="selectin", order_by="Nivel.numero", cascade="all, delete-orphan"
    )


class Nivel(Base):
    __tablename__ = "apr_nivel"
    __table_args__ = (UniqueConstraint("regla_id", "numero"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    regla_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("apr_regla.id", ondelete="CASCADE"), index=True
    )
    numero: Mapped[int] = mapped_column(Integer)  # 1..3
    monto_desde: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)  # moneda de la empresa
    modo: Mapped[str] = mapped_column(String(25), default="serie")

    aprobadores: Mapped[list["Aprobador"]] = relationship(
        lazy="selectin", order_by="Aprobador.orden", cascade="all, delete-orphan"
    )


class Aprobador(Base):
    __tablename__ = "apr_aprobador"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nivel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("apr_nivel.id", ondelete="CASCADE"), index=True
    )
    orden: Mapped[int] = mapped_column(Integer)
    tipo: Mapped[str] = mapped_column(String(20))  # ver TIPOS_APROBADOR
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("seg_usuario.id"), nullable=True
    )
    rol_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("seg_rol.id"), nullable=True)
    # Condiciones del aprobador (vacías = siempre)
    unidad_negocio_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mae_unidad_negocio.id"), nullable=True
    )
    categoria_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mae_categoria.id"), nullable=True
    )
    centro_costo_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cnt_centro_costo.id"), nullable=True
    )


class Paso(Base):
    """Un aprobador de una ronda de aprobación de un documento."""

    __tablename__ = "apr_paso"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    documento: Mapped[str] = mapped_column(String(30))
    documento_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    ronda: Mapped[int] = mapped_column(Integer)  # cada envío es una ronda nueva
    regla_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    regla_nombre: Mapped[str] = mapped_column(String(100))
    nivel: Mapped[int] = mapped_column(Integer)
    modo: Mapped[str] = mapped_column(String(25))
    orden: Mapped[int] = mapped_column(Integer)
    tipo: Mapped[str] = mapped_column(String(20))
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    rol_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    descripcion: Mapped[str] = mapped_column(String(200))  # "Ana Pérez · Responsable de ADM-01"
    # en_espera, pendiente, aprobado, rechazado, devuelto, omitido, cancelado
    estado: Mapped[str] = mapped_column(String(20), index=True)
    motivo: Mapped[str | None] = mapped_column(String(200), nullable=True)  # por qué se omitió
    actuado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    actuado_por_nombre: Mapped[str | None] = mapped_column(String(150), nullable=True)
    actuado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    comentario: Mapped[str | None] = mapped_column(String(500), nullable=True)
