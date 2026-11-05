"""Tablas de la contabilidad base (prefijo cnt_). Todo es por empresa (ADR-004)."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
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

from app.core.database import Base, ConAuditoria, ahora_utc
from app.modules.seguridad.models import Usuario


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
    responsable: Mapped[str | None] = mapped_column(
        String(150), nullable=True
    )  # texto libre (anterior)
    # Usuario responsable: aprueba las solicitudes con reglas "responsable del centro de costo"
    responsable_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("seg_usuario.id"), nullable=True
    )
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    responsable_usuario: Mapped[Usuario | None] = relationship(lazy="joined")

    @property
    def responsable_nombre(self) -> str | None:
        return self.responsable_usuario.nombre if self.responsable_usuario else self.responsable


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


class ConfiguracionCxP(Base):
    """Cuándo se reconoce el cargo de una compra, por tipo de artículo, y su cuenta puente.

    momentos: {"bien_inventariable": "recepcion", "servicio": "facturacion", ...}
    - recepcion: al recibir, Debe gasto/existencia · Haber cuenta puente (4211 no emitidas);
      al facturar, Debe cuenta puente + IGV · Haber cuenta por pagar del perfil (4212).
    - facturacion: al facturar, Debe gasto/existencia + IGV · Haber cuenta por pagar (4212).
    """

    __tablename__ = "cnt_config_cxp"

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mae_empresa.id"), primary_key=True)
    momentos: Mapped[dict] = mapped_column(JSON, default=dict)
    cuenta_recepcion_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cnt_cuenta.id"), nullable=True
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=ahora_utc, onupdate=ahora_utc
    )
    actualizado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
