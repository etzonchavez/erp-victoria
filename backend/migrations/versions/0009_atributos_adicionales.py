"""atributos adicionales configurables de los documentos operativos (ADR-005)

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-30

Solo crea la configuración. Las 30 columnas de cada documento las agrega la migración
de cada módulo operativo con app.core.atributos.columnas_atributos().
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "seg_atributo",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("creado_por", sa.Uuid(), nullable=True),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actualizado_por", sa.Uuid(), nullable=True),
        sa.Column("documento", sa.String(30), nullable=False),
        sa.Column("nivel", sa.String(20), nullable=False),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("etiqueta", sa.String(60), nullable=True),
        sa.Column("ayuda", sa.String(200), nullable=True),
        sa.Column("valor_defecto", sa.String(240), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("copiar_documento", sa.String(30), nullable=True),
        sa.Column("copiar_numero", sa.Integer(), nullable=True),
        sa.UniqueConstraint("documento", "nivel", "tipo", "numero"),
    )
    op.create_table(
        "seg_atributo_valor",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "atributo_id",
            sa.Uuid(),
            sa.ForeignKey("seg_atributo.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("valor", sa.String(240), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.UniqueConstraint("atributo_id", "valor"),
    )
    op.create_index(
        "ix_seg_atributo_valor_atributo_id", "seg_atributo_valor", ["atributo_id"]
    )


def downgrade() -> None:
    op.drop_table("seg_atributo_valor")
    op.drop_table("seg_atributo")
