"""Tablas de las solicitudes de compra (prefijo sol_).

Cabecera, línea y distribución llevan los atributos adicionales (ADR-005).
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.atributos import ConAtributos
from app.core.database import Base, ConAuditoria

ESTADOS = {
    "borrador": "Borrador",
    "en_aprobacion": "En aprobación",
    "devuelta": "Devuelta",
    "rechazada": "Rechazada",
    "aprobada": "Aprobada",
    "parcialmente_atendida": "Parcialmente atendida",
    "atendida": "Atendida",
    "anulada": "Anulada",
}
EDITABLES = {"borrador", "devuelta"}


class Correlativo(Base):
    """Último número usado por empresa y año: SC-2026-000001."""

    __tablename__ = "sol_correlativo"

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mae_empresa.id"), primary_key=True)
    anio: Mapped[int] = mapped_column(Integer, primary_key=True)
    ultimo: Mapped[int] = mapped_column(Integer, default=0)


class Solicitud(ConAtributos, ConAuditoria, Base):
    __tablename__ = "sol_solicitud"
    __table_args__ = (UniqueConstraint("empresa_id", "numero"),)

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mae_empresa.id"), index=True)
    unidad_negocio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mae_unidad_negocio.id"))
    numero: Mapped[str] = mapped_column(String(20))
    solicitante_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seg_usuario.id"), index=True)
    fecha: Mapped[date] = mapped_column(Date)
    fecha_requerida: Mapped[date | None] = mapped_column(Date, nullable=True)
    titulo: Mapped[str] = mapped_column(String(150))
    justificacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    moneda: Mapped[str] = mapped_column(ForeignKey("mae_moneda.codigo"))
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    # Total en la moneda de la empresa: es el monto que miran las reglas de aprobación
    tipo_cambio: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=1)
    total_funcional: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    estado: Mapped[str] = mapped_column(String(25), default="borrador", index=True)
    ronda: Mapped[int] = mapped_column(Integer, default=0)  # envíos a aprobación

    lineas: Mapped[list["Linea"]] = relationship(
        lazy="selectin", order_by="Linea.numero", cascade="all, delete-orphan"
    )


class Linea(ConAtributos, ConAuditoria, Base):
    __tablename__ = "sol_linea"

    solicitud_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sol_solicitud.id", ondelete="CASCADE"), index=True
    )
    numero: Mapped[int] = mapped_column(Integer)
    articulo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mae_articulo.id"))
    descripcion: Mapped[str] = mapped_column(String(240))
    cantidad: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    unidad: Mapped[str] = mapped_column(ForeignKey("mae_unidad_medida.codigo"))
    cantidad_base: Mapped[Decimal] = mapped_column(Numeric(18, 4))  # en la unidad del artículo
    precio: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)  # estimado, sin impuesto
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    # Se fijan al enviar: salen del perfil contable del artículo en la empresa (ADR-004)
    perfil_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cnt_perfil.id"), nullable=True)
    cuenta_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cnt_cuenta.id"), nullable=True)

    distribuciones: Mapped[list["Distribucion"]] = relationship(
        lazy="selectin", order_by="Distribucion.numero", cascade="all, delete-orphan"
    )


class Distribucion(ConAtributos, ConAuditoria, Base):
    """Reparto de la línea entre centros de costo; los porcentajes suman 100."""

    __tablename__ = "sol_distribucion"

    linea_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sol_linea.id", ondelete="CASCADE"), index=True
    )
    numero: Mapped[int] = mapped_column(Integer)
    centro_costo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cnt_centro_costo.id"))
    porcentaje: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    monto: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
