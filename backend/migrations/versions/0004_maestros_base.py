"""maestros: empresas, unidades de negocio, monedas, tipo de cambio y unidades de medida

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-30

Los datos base (monedas, unidades SUNAT, conversiones) los carga la API al iniciar
(maestros.service.preparar), así una versión nueva puede agregar datos sin migración.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _auditoria() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("creado_por", sa.Uuid(), nullable=True),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actualizado_por", sa.Uuid(), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "mae_moneda",
        *_auditoria(),
        sa.Column("codigo", sa.String(3), nullable=False, unique=True),
        sa.Column("nombre", sa.String(60), nullable=False),
        sa.Column("simbolo", sa.String(5), nullable=False),
        sa.Column("decimales", sa.Integer(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "mae_tipo_cambio",
        *_auditoria(),
        sa.Column("moneda", sa.String(3), sa.ForeignKey("mae_moneda.codigo"), nullable=False),
        sa.Column("moneda_base", sa.String(3), sa.ForeignKey("mae_moneda.codigo"), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("compra", sa.Numeric(12, 6), nullable=False),
        sa.Column("venta", sa.Numeric(12, 6), nullable=False),
        sa.Column("fuente", sa.String(20), nullable=False),
        sa.UniqueConstraint("moneda", "moneda_base", "fecha"),
    )
    op.create_index("ix_mae_tipo_cambio_moneda", "mae_tipo_cambio", ["moneda"])
    op.create_index("ix_mae_tipo_cambio_fecha", "mae_tipo_cambio", ["fecha"])
    op.create_table(
        "mae_empresa",
        *_auditoria(),
        sa.Column("pais", sa.String(2), nullable=False),
        sa.Column("identificacion_fiscal", sa.String(20), nullable=False),
        sa.Column("razon_social", sa.String(200), nullable=False),
        sa.Column("nombre_comercial", sa.String(150), nullable=True),
        sa.Column("direccion_fiscal", sa.String(300), nullable=True),
        sa.Column(
            "moneda_funcional", sa.String(3), sa.ForeignKey("mae_moneda.codigo"), nullable=False
        ),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("pais", "identificacion_fiscal"),
    )
    op.create_table(
        "mae_unidad_negocio",
        *_auditoria(),
        sa.Column("empresa_id", sa.Uuid(), sa.ForeignKey("mae_empresa.id"), nullable=False),
        sa.Column("codigo", sa.String(20), nullable=False),
        sa.Column("nombre", sa.String(150), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("empresa_id", "codigo"),
    )
    op.create_index("ix_mae_unidad_negocio_empresa_id", "mae_unidad_negocio", ["empresa_id"])
    op.create_table(
        "mae_unidad_medida",
        *_auditoria(),
        sa.Column("codigo", sa.String(10), nullable=False, unique=True),
        sa.Column("nombre", sa.String(80), nullable=False),
        sa.Column("codigo_oficial", sa.String(5), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "mae_conversion_unidad",
        *_auditoria(),
        sa.Column(
            "origen", sa.String(10), sa.ForeignKey("mae_unidad_medida.codigo"), nullable=False
        ),
        sa.Column(
            "destino", sa.String(10), sa.ForeignKey("mae_unidad_medida.codigo"), nullable=False
        ),
        sa.Column("factor", sa.Numeric(18, 6), nullable=False),
        sa.UniqueConstraint("origen", "destino"),
    )


def downgrade() -> None:
    for tabla in (
        "mae_conversion_unidad",
        "mae_unidad_medida",
        "mae_unidad_negocio",
        "mae_empresa",
        "mae_tipo_cambio",
        "mae_moneda",
    ):
        op.drop_table(tabla)
