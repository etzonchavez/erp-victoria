"""Tablas del módulo de maestros (prefijo mae_)."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, ConAuditoria


class Moneda(ConAuditoria, Base):
    """Monedas ISO 4217. Se precargan las de los países del roadmap."""

    __tablename__ = "mae_moneda"

    codigo: Mapped[str] = mapped_column(String(3), unique=True)  # PEN, USD
    nombre: Mapped[str] = mapped_column(String(60))
    simbolo: Mapped[str] = mapped_column(String(5))
    decimales: Mapped[int] = mapped_column(Integer, default=2)
    activo: Mapped[bool] = mapped_column(Boolean, default=False)


class TipoCambio(ConAuditoria, Base):
    """Tipo de cambio diario de una moneda contra la moneda base (PEN en Perú)."""

    __tablename__ = "mae_tipo_cambio"
    __table_args__ = (UniqueConstraint("moneda", "moneda_base", "fecha"),)

    moneda: Mapped[str] = mapped_column(ForeignKey("mae_moneda.codigo"), index=True)  # USD
    moneda_base: Mapped[str] = mapped_column(ForeignKey("mae_moneda.codigo"))  # PEN
    fecha: Mapped[date] = mapped_column(Date, index=True)
    compra: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    venta: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    fuente: Mapped[str] = mapped_column(String(20), default="manual")  # manual, excel, sbs


class Empresa(ConAuditoria, Base):
    """Empresa legal. Una instalación (base de datos) puede tener varias."""

    __tablename__ = "mae_empresa"
    __table_args__ = (UniqueConstraint("pais", "identificacion_fiscal"),)

    pais: Mapped[str] = mapped_column(String(2))  # pe
    identificacion_fiscal: Mapped[str] = mapped_column(String(20))  # RUC en Perú
    razon_social: Mapped[str] = mapped_column(String(200))
    nombre_comercial: Mapped[str | None] = mapped_column(String(150), nullable=True)
    direccion_fiscal: Mapped[str | None] = mapped_column(String(300), nullable=True)
    moneda_funcional: Mapped[str] = mapped_column(ForeignKey("mae_moneda.codigo"))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    unidades: Mapped[list["UnidadNegocio"]] = relationship(
        back_populates="empresa", lazy="selectin", order_by="UnidadNegocio.codigo"
    )


class UnidadNegocio(ConAuditoria, Base):
    __tablename__ = "mae_unidad_negocio"
    __table_args__ = (UniqueConstraint("empresa_id", "codigo"),)

    empresa_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("mae_empresa.id"), index=True)
    codigo: Mapped[str] = mapped_column(String(20))
    nombre: Mapped[str] = mapped_column(String(150))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    empresa: Mapped[Empresa] = relationship(back_populates="unidades")


class UnidadMedida(ConAuditoria, Base):
    """Unidad interna (UND, CAJA) mapeada al código oficial (SUNAT Catálogo N.° 03 / UN/ECE)."""

    __tablename__ = "mae_unidad_medida"

    codigo: Mapped[str] = mapped_column(String(10), unique=True)  # UND
    nombre: Mapped[str] = mapped_column(String(80))
    codigo_oficial: Mapped[str] = mapped_column(String(5))  # NIU
    tipo: Mapped[str] = mapped_column(String(20))  # cantidad, peso, volumen…
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class ConversionUnidad(ConAuditoria, Base):
    """1 unidad origen = factor unidades destino. Ej.: 1 KG = 1000 G.

    Conversiones generales. Las propias de un artículo (1 CAJA = 12 UND) van en el artículo.
    """

    __tablename__ = "mae_conversion_unidad"
    __table_args__ = (UniqueConstraint("origen", "destino"),)

    origen: Mapped[str] = mapped_column(ForeignKey("mae_unidad_medida.codigo"))
    destino: Mapped[str] = mapped_column(ForeignKey("mae_unidad_medida.codigo"))
    factor: Mapped[Decimal] = mapped_column(Numeric(18, 6))


class Categoria(ConAuditoria, Base):
    """Árbol de categorías de artículo, compartido por todas las empresas (hasta 3 niveles).

    El perfil contable de cada categoría lo asigna Contabilidad por empresa
    (cnt_categoria_perfil), así Maestros no depende de Contabilidad.
    """

    __tablename__ = "mae_categoria"

    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    nombre: Mapped[str] = mapped_column(String(120))
    padre_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("mae_categoria.id"), nullable=True
    )
    nivel: Mapped[int] = mapped_column(Integer)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class CondicionPago(ConAuditoria, Base):
    """Contado, 30 días… La orden de compra la toma del proveedor por defecto."""

    __tablename__ = "mae_condicion_pago"

    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    nombre: Mapped[str] = mapped_column(String(80))
    dias: Mapped[int] = mapped_column(Integer, default=0)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


mae_proveedor_categoria = Table(
    "mae_proveedor_categoria",
    Base.metadata,
    Column(
        "proveedor_id", Uuid, ForeignKey("mae_proveedor.id", ondelete="CASCADE"), primary_key=True
    ),
    Column("categoria_id", Uuid, ForeignKey("mae_categoria.id"), primary_key=True),
)


class Proveedor(ConAuditoria, Base):
    """Proveedor compartido por todas las empresas; cada empresa puede bloquearlo para sí."""

    __tablename__ = "mae_proveedor"
    __table_args__ = (UniqueConstraint("pais", "tipo_documento", "numero_documento"),)

    tipo_documento: Mapped[str] = mapped_column(String(5))  # RUC, DNI, EXT
    numero_documento: Mapped[str] = mapped_column(String(20), index=True)
    pais: Mapped[str] = mapped_column(String(2))  # país del proveedor (ISO 3166-1, minúsculas)
    razon_social: Mapped[str] = mapped_column(String(200), index=True)
    nombre_comercial: Mapped[str | None] = mapped_column(String(150), nullable=True)
    direccion: Mapped[str | None] = mapped_column(String(300), nullable=True)
    correo: Mapped[str | None] = mapped_column(String(200), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(40), nullable=True)
    moneda: Mapped[str] = mapped_column(ForeignKey("mae_moneda.codigo"))
    condicion_pago_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mae_condicion_pago.id"))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    condicion_pago: Mapped[CondicionPago] = relationship(lazy="joined")
    contactos: Mapped[list["ContactoProveedor"]] = relationship(
        lazy="selectin", order_by="ContactoProveedor.nombre", cascade="all, delete-orphan"
    )
    cuentas: Mapped[list["CuentaBancariaProveedor"]] = relationship(
        lazy="selectin", order_by="CuentaBancariaProveedor.creado_en", cascade="all, delete-orphan"
    )
    categorias: Mapped[list[Categoria]] = relationship(
        secondary=mae_proveedor_categoria, lazy="selectin", order_by="Categoria.codigo"
    )
    bloqueos: Mapped[list["BloqueoProveedor"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan"
    )


class ContactoProveedor(ConAuditoria, Base):
    __tablename__ = "mae_proveedor_contacto"

    proveedor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mae_proveedor.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(150))
    cargo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    correo: Mapped[str | None] = mapped_column(String(200), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(40), nullable=True)
    principal: Mapped[bool] = mapped_column(Boolean, default=False)


class CuentaBancariaProveedor(ConAuditoria, Base):
    __tablename__ = "mae_proveedor_cuenta"

    proveedor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mae_proveedor.id"), index=True)
    banco: Mapped[str] = mapped_column(String(100))
    tipo: Mapped[str] = mapped_column(String(20))  # corriente, ahorros, detracciones
    moneda: Mapped[str] = mapped_column(ForeignKey("mae_moneda.codigo"))
    numero: Mapped[str] = mapped_column(String(34))
    cci: Mapped[str | None] = mapped_column(String(20), nullable=True)
    swift: Mapped[str | None] = mapped_column(String(11), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class BloqueoProveedor(ConAuditoria, Base):
    """Una empresa no compra a este proveedor. Sin fila, el proveedor está habilitado."""

    __tablename__ = "mae_proveedor_bloqueo"
    __table_args__ = (UniqueConstraint("proveedor_id", "empresa_id"),)

    proveedor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mae_proveedor.id"), index=True)
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mae_empresa.id"))
    motivo: Mapped[str] = mapped_column(String(300))
