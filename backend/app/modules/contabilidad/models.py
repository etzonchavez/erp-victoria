"""Tablas de la contabilidad base (prefijo cnt_). Todo es por empresa (ADR-004)."""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, ConAuditoria


class Cuenta(ConAuditoria, Base):
    """Cuenta del plan contable. Solo las imputables (sin hijas) se usan en transacciones."""

    __tablename__ = "cnt_cuenta"
    __table_args__ = (UniqueConstraint("empresa_id", "codigo"),)

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mae_empresa.id"), index=True)
    codigo: Mapped[str] = mapped_column(String(20))
    nombre: Mapped[str] = mapped_column(String(200))
    padre_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("cnt_cuenta.id"), nullable=True
    )
    nivel: Mapped[int] = mapped_column(Integer)
    naturaleza: Mapped[str] = mapped_column(String(20))  # activo, pasivo, gasto…
    imputable: Mapped[bool] = mapped_column(Boolean, default=True)
    plantilla: Mapped[str] = mapped_column(String(20), default="propia")  # PCGE-2019, propia
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Perfil(ConAuditoria, Base):
    """Cuentas de un tipo de compra. Las categorías de artículo apuntan a un perfil."""

    __tablename__ = "cnt_perfil"
    __table_args__ = (UniqueConstraint("empresa_id", "codigo"),)

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mae_empresa.id"), index=True)
    codigo: Mapped[str] = mapped_column(String(30))
    nombre: Mapped[str] = mapped_column(String(100))
    tipo_articulo: Mapped[str] = mapped_column(String(30))
    cuenta_cargo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cnt_cuenta.id"))
    cuenta_existencia_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cnt_cuenta.id"), nullable=True
    )
    cuenta_variacion_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cnt_cuenta.id"), nullable=True
    )
    cuenta_por_pagar_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cnt_cuenta.id"))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    cuenta_cargo: Mapped[Cuenta] = relationship(foreign_keys=[cuenta_cargo_id], lazy="joined")
    cuenta_existencia: Mapped[Cuenta | None] = relationship(
        foreign_keys=[cuenta_existencia_id], lazy="joined"
    )
    cuenta_variacion: Mapped[Cuenta | None] = relationship(
        foreign_keys=[cuenta_variacion_id], lazy="joined"
    )
    cuenta_por_pagar: Mapped[Cuenta] = relationship(
        foreign_keys=[cuenta_por_pagar_id], lazy="joined"
    )


class CentroCosto(ConAuditoria, Base):
    __tablename__ = "cnt_centro_costo"
    __table_args__ = (UniqueConstraint("empresa_id", "codigo"),)

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mae_empresa.id"), index=True)
    unidad_negocio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mae_unidad_negocio.id"))
    codigo: Mapped[str] = mapped_column(String(20))
    nombre: Mapped[str] = mapped_column(String(150))
    responsable: Mapped[str | None] = mapped_column(String(150), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Impuesto(ConAuditoria, Base):
    __tablename__ = "cnt_impuesto"
    __table_args__ = (UniqueConstraint("empresa_id", "codigo"),)

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mae_empresa.id"), index=True)
    codigo: Mapped[str] = mapped_column(String(20))
    nombre: Mapped[str] = mapped_column(String(100))
    tasa: Mapped[Decimal] = mapped_column(Numeric(7, 4))  # porcentaje: 18.0000
    cuenta_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cnt_cuenta.id"), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    cuenta: Mapped[Cuenta | None] = relationship(lazy="joined")


class CategoriaPerfil(ConAuditoria, Base):
    """Perfil contable que una empresa asigna a una categoría de artículo (compartida).

    Si una categoría no tiene fila para la empresa, hereda el perfil de su categoría padre.
    """

    __tablename__ = "cnt_categoria_perfil"
    __table_args__ = (UniqueConstraint("empresa_id", "categoria_id"),)

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mae_empresa.id"), index=True)
    categoria_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mae_categoria.id"))
    perfil_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cnt_perfil.id"))

    perfil: Mapped[Perfil] = relationship(lazy="joined")


class ArticuloPerfil(ConAuditoria, Base):
    """Excepción: perfil propio de un artículo en una empresa, en vez del de su categoría."""

    __tablename__ = "cnt_articulo_perfil"
    __table_args__ = (UniqueConstraint("empresa_id", "articulo_id"),)

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mae_empresa.id"), index=True)
    articulo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mae_articulo.id"), index=True)
    perfil_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cnt_perfil.id"))

    perfil: Mapped[Perfil] = relationship(lazy="joined")
