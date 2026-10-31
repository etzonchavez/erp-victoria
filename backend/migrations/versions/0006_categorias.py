"""categorías de artículo compartidas y su perfil contable por empresa

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-30

Las categorías de ejemplo las carga la API al iniciar. Para las empresas existentes, el
contador aplica los perfiles sugeridos desde Maestros → Categorías.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
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
        "mae_categoria",
        *_auditoria(),
        sa.Column("codigo", sa.String(20), nullable=False, unique=True),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("padre_id", sa.Uuid(), sa.ForeignKey("mae_categoria.id"), nullable=True),
        sa.Column("nivel", sa.Integer(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "cnt_categoria_perfil",
        *_auditoria(),
        sa.Column("empresa_id", sa.Uuid(), sa.ForeignKey("mae_empresa.id"), nullable=False),
        sa.Column("categoria_id", sa.Uuid(), sa.ForeignKey("mae_categoria.id"), nullable=False),
        sa.Column("perfil_id", sa.Uuid(), sa.ForeignKey("cnt_perfil.id"), nullable=False),
        sa.UniqueConstraint("empresa_id", "categoria_id"),
    )
    op.create_index(
        "ix_cnt_categoria_perfil_empresa_id", "cnt_categoria_perfil", ["empresa_id"]
    )


def downgrade() -> None:
    op.drop_table("cnt_categoria_perfil")
    op.drop_table("mae_categoria")
