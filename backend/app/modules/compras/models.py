"""Tablas de órdenes de compra (prefijo cmp_).

Cabecera, línea y distribución llevan los atributos adicionales (ADR-005). Una orden toma
solicitudes aprobadas completas (cada línea de solicitud es una línea de la orden) y puede
tener además líneas directas.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.atributos import ConAtributos
from app.core.database import Base, ConAuditoria, ahora_utc

ESTADOS = {
    "borrador": "Borrador",
    "en_aprobacion": "En aprobación",
    "devuelta": "Devuelta",
    "rechazada": "Rechazada",
    "aprobada": "Aprobada",
    "enviada": "Enviada al proveedor",
    "anulada": "Anulada",
}
EDITABLES = {"borrador", "devuelta"}
ANULABLES_CON_PERMISO = {"aprobada", "enviada"}


class Correlativo(Base):
    """Último número usado por empresa y año: OC-2026-000001."""

    __tablename__ = "cmp_correlativo"

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mae_empresa.id"), primary_key=True)
    anio: Mapped[int] = mapped_column(Integer, primary_key=True)
    ultimo: Mapped[int] = mapped_column(Integer, default=0)


class Orden(ConAtributos, ConAuditoria, Base):
    __tablename__ = "cmp_orden"
    __table_args__ = (UniqueConstraint("empresa_id", "numero"),)

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mae_empresa.id"), index=True)
    unidad_negocio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mae_unidad_negocio.id"))
    numero: Mapped[str] = mapped_column(String(20))
    comprador_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seg_usuario.id"), index=True)
    proveedor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mae_proveedor.id"), index=True)
    contacto_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mae_proveedor_contacto.id"), nullable=True
    )
    condicion_pago_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mae_condicion_pago.id"))
    fecha: Mapped[date] = mapped_column(Date)
    fecha_entrega: Mapped[date | None] = mapped_column(Date, nullable=True)
    lugar_entrega: Mapped[str | None] = mapped_column(String(300), nullable=True)
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    moneda: Mapped[str] = mapped_column(ForeignKey("mae_moneda.codigo"))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    impuesto: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    # Total en la moneda de la empresa: lo miran las reglas de aprobación
    tipo_cambio: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=1)
    total_funcional: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    estado: Mapped[str] = mapped_column(String(25), default="borrador", index=True)
    ronda: Mapped[int] = mapped_column(Integer, default=0)
    enviada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    enviada_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    lineas: Mapped[list["LineaOrden"]] = relationship(
        lazy="selectin", order_by="LineaOrden.numero", cascade="all, delete-orphan"
    )


class LineaOrden(ConAtributos, ConAuditoria, Base):
    __tablename__ = "cmp_linea"

    orden_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cmp_orden.id", ondelete="CASCADE"), index=True
    )
    numero: Mapped[int] = mapped_column(Integer)
    # Origen (vacío = línea directa)
    solicitud_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sol_solicitud.id"), nullable=True, index=True
    )
    solicitud_linea_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sol_linea.id"), nullable=True
    )
    solicitud_numero: Mapped[str | None] = mapped_column(String(20), nullable=True)
    articulo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mae_articulo.id"))
    descripcion: Mapped[str] = mapped_column(String(240))
    cantidad: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    unidad: Mapped[str] = mapped_column(ForeignKey("mae_unidad_medida.codigo"))
    cantidad_base: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    precio: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=0)  # sin impuesto
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    impuesto_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cnt_impuesto.id"), nullable=True
    )
    tasa: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    impuesto_monto: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    perfil_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cnt_perfil.id"), nullable=True)
    cuenta_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cnt_cuenta.id"), nullable=True)

    distribuciones: Mapped[list["DistribucionOrden"]] = relationship(
        lazy="selectin", order_by="DistribucionOrden.numero", cascade="all, delete-orphan"
    )


class DistribucionOrden(ConAtributos, ConAuditoria, Base):
    __tablename__ = "cmp_distribucion"

    linea_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cmp_linea.id", ondelete="CASCADE"), index=True
    )
    numero: Mapped[int] = mapped_column(Integer)
    centro_costo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cnt_centro_costo.id"))
    porcentaje: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    monto: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)


class Formato(Base):
    """Formato PDF de la orden de compra: uno por empresa (ver pdf.FORMATO_BASE)."""

    __tablename__ = "cmp_formato"

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mae_empresa.id"), primary_key=True)
    configuracion: Mapped[dict] = mapped_column(JSON, default=dict)
    logo: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    logo_tipo: Mapped[str | None] = mapped_column(String(30), nullable=True)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=ahora_utc, onupdate=ahora_utc
    )
    actualizado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
