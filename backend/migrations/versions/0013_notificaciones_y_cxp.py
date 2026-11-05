"""notificaciones, momento de reconocimiento del cargo y aviso de pasos

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-05

- seg_notificacion: avisos de la campana (por aprobar, aprobado, rechazado, devuelto, enviada).
- apr_paso.notificado: el aviso "por aprobar" se envía una sola vez por paso.
- cnt_config_cxp: por empresa, cuándo se reconoce el cargo por tipo de artículo (al recibir o
  al facturar) y la cuenta puente de recepción (4211 facturas no emitidas).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "seg_notificacion",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "usuario_id",
            sa.Uuid(),
            sa.ForeignKey("seg_usuario.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("titulo", sa.String(150), nullable=False),
        sa.Column("mensaje", sa.String(300), nullable=False),
        sa.Column("enlace", sa.String(200), nullable=False),
        sa.Column("documento", sa.String(30), nullable=True),
        sa.Column("documento_id", sa.Uuid(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("leida_en", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_seg_notificacion_usuario_id", "seg_notificacion", ["usuario_id"])
    op.create_index("ix_seg_notificacion_creado_en", "seg_notificacion", ["creado_en"])
    with op.batch_alter_table("apr_paso") as t:
        t.add_column(
            sa.Column("notificado", sa.Boolean(), nullable=False, server_default=sa.true())
        )
    op.create_table(
        "cnt_config_cxp",
        sa.Column("empresa_id", sa.Uuid(), sa.ForeignKey("mae_empresa.id"), primary_key=True),
        sa.Column("momentos", sa.JSON(), nullable=False),
        sa.Column(
            "cuenta_recepcion_id", sa.Uuid(), sa.ForeignKey("cnt_cuenta.id"), nullable=True
        ),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actualizado_por", sa.Uuid(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("cnt_config_cxp")
    with op.batch_alter_table("apr_paso") as t:
        t.drop_column("notificado")
    op.drop_table("seg_notificacion")
