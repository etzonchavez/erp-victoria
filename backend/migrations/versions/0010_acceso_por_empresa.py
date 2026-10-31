"""acceso de cada usuario por empresa y unidad de negocio

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-31

Desde esta versión, un usuario que no es administrador solo ve las empresas que se le
asignan en Administración → Usuarios. Los usuarios existentes empiezan sin empresas.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
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


def _usuario() -> sa.Column:
    return sa.Column(
        "usuario_id",
        sa.Uuid(),
        sa.ForeignKey("seg_usuario.id", ondelete="CASCADE"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "mae_acceso_empresa",
        *_auditoria(),
        _usuario(),
        sa.Column("empresa_id", sa.Uuid(), sa.ForeignKey("mae_empresa.id"), nullable=False),
        sa.Column("todas_unidades", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("usuario_id", "empresa_id"),
    )
    op.create_table(
        "mae_acceso_unidad",
        *_auditoria(),
        _usuario(),
        sa.Column(
            "unidad_negocio_id",
            sa.Uuid(),
            sa.ForeignKey("mae_unidad_negocio.id"),
            nullable=False,
        ),
        sa.UniqueConstraint("usuario_id", "unidad_negocio_id"),
    )
    op.create_index("ix_mae_acceso_empresa_usuario_id", "mae_acceso_empresa", ["usuario_id"])
    op.create_index("ix_mae_acceso_unidad_usuario_id", "mae_acceso_unidad", ["usuario_id"])


def downgrade() -> None:
    op.drop_table("mae_acceso_unidad")
    op.drop_table("mae_acceso_empresa")
