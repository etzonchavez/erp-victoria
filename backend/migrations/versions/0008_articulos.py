"""artículos compartidos, unidades alternativas y excepción contable por empresa

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
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
        "mae_articulo",
        *_auditoria(),
        sa.Column("codigo", sa.String(30), nullable=False, unique=True),
        sa.Column("descripcion", sa.String(240), nullable=False),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("categoria_id", sa.Uuid(), sa.ForeignKey("mae_categoria.id"), nullable=False),
        sa.Column(
            "unidad", sa.String(10), sa.ForeignKey("mae_unidad_medida.codigo"), nullable=False
        ),
        sa.Column("impuesto", sa.String(20), nullable=False),
        sa.Column("marca", sa.String(100), nullable=True),
        sa.Column("modelo", sa.String(100), nullable=True),
        sa.Column("especificacion", sa.Text(), nullable=True),
        sa.Column("precio_referencial", sa.Numeric(18, 4), nullable=True),
        sa.Column("moneda_precio", sa.String(3), sa.ForeignKey("mae_moneda.codigo"), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_mae_articulo_descripcion", "mae_articulo", ["descripcion"])
    op.create_index("ix_mae_articulo_categoria_id", "mae_articulo", ["categoria_id"])
    op.create_table(
        "mae_articulo_unidad",
        *_auditoria(),
        sa.Column("articulo_id", sa.Uuid(), sa.ForeignKey("mae_articulo.id"), nullable=False),
        sa.Column(
            "unidad", sa.String(10), sa.ForeignKey("mae_unidad_medida.codigo"), nullable=False
        ),
        sa.Column("factor", sa.Numeric(18, 6), nullable=False),
        sa.UniqueConstraint("articulo_id", "unidad"),
    )
    op.create_index("ix_mae_articulo_unidad_articulo_id", "mae_articulo_unidad", ["articulo_id"])
    op.create_table(
        "cnt_articulo_perfil",
        *_auditoria(),
        sa.Column("empresa_id", sa.Uuid(), sa.ForeignKey("mae_empresa.id"), nullable=False),
        sa.Column("articulo_id", sa.Uuid(), sa.ForeignKey("mae_articulo.id"), nullable=False),
        sa.Column("perfil_id", sa.Uuid(), sa.ForeignKey("cnt_perfil.id"), nullable=False),
        sa.UniqueConstraint("empresa_id", "articulo_id"),
    )
    op.create_index("ix_cnt_articulo_perfil_empresa_id", "cnt_articulo_perfil", ["empresa_id"])
    op.create_index("ix_cnt_articulo_perfil_articulo_id", "cnt_articulo_perfil", ["articulo_id"])


def downgrade() -> None:
    for tabla in ("cnt_articulo_perfil", "mae_articulo_unidad", "mae_articulo"):
        op.drop_table(tabla)
