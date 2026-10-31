"""contabilidad base: plan de cuentas, perfiles contables, centros de costo e impuestos (ADR-004)

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-30

La plantilla del país se carga al crear cada empresa. Para las empresas creadas antes
de esta versión, el contador la carga desde Contabilidad → Plan de cuentas.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
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


def _empresa() -> sa.Column:
    return sa.Column("empresa_id", sa.Uuid(), sa.ForeignKey("mae_empresa.id"), nullable=False)


def _cuenta(nombre: str, nula: bool) -> sa.Column:
    return sa.Column(nombre, sa.Uuid(), sa.ForeignKey("cnt_cuenta.id"), nullable=nula)


def upgrade() -> None:
    op.create_table(
        "cnt_cuenta",
        *_auditoria(),
        _empresa(),
        sa.Column("codigo", sa.String(20), nullable=False),
        sa.Column("nombre", sa.String(200), nullable=False),
        _cuenta("padre_id", True),
        sa.Column("nivel", sa.Integer(), nullable=False),
        sa.Column("naturaleza", sa.String(20), nullable=False),
        sa.Column("imputable", sa.Boolean(), nullable=False),
        sa.Column("plantilla", sa.String(20), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("empresa_id", "codigo"),
    )
    op.create_table(
        "cnt_perfil",
        *_auditoria(),
        _empresa(),
        sa.Column("codigo", sa.String(30), nullable=False),
        sa.Column("nombre", sa.String(100), nullable=False),
        sa.Column("tipo_articulo", sa.String(30), nullable=False),
        _cuenta("cuenta_cargo_id", False),
        _cuenta("cuenta_existencia_id", True),
        _cuenta("cuenta_variacion_id", True),
        _cuenta("cuenta_por_pagar_id", False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("empresa_id", "codigo"),
    )
    op.create_table(
        "cnt_centro_costo",
        *_auditoria(),
        _empresa(),
        sa.Column(
            "unidad_negocio_id",
            sa.Uuid(),
            sa.ForeignKey("mae_unidad_negocio.id"),
            nullable=False,
        ),
        sa.Column("codigo", sa.String(20), nullable=False),
        sa.Column("nombre", sa.String(150), nullable=False),
        sa.Column("responsable", sa.String(150), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("empresa_id", "codigo"),
    )
    op.create_table(
        "cnt_impuesto",
        *_auditoria(),
        _empresa(),
        sa.Column("codigo", sa.String(20), nullable=False),
        sa.Column("nombre", sa.String(100), nullable=False),
        sa.Column("tasa", sa.Numeric(7, 4), nullable=False),
        _cuenta("cuenta_id", True),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("empresa_id", "codigo"),
    )
    for tabla in ("cnt_cuenta", "cnt_perfil", "cnt_centro_costo", "cnt_impuesto"):
        op.create_index(f"ix_{tabla}_empresa_id", tabla, ["empresa_id"])


def downgrade() -> None:
    for tabla in ("cnt_impuesto", "cnt_centro_costo", "cnt_perfil", "cnt_cuenta"):
        op.drop_table(tabla)
