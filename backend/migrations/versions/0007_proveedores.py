"""proveedores compartidos, contactos, cuentas bancarias, bloqueos y condiciones de pago

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
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


def _proveedor() -> sa.Column:
    return sa.Column("proveedor_id", sa.Uuid(), sa.ForeignKey("mae_proveedor.id"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "mae_condicion_pago",
        *_auditoria(),
        sa.Column("codigo", sa.String(20), nullable=False, unique=True),
        sa.Column("nombre", sa.String(80), nullable=False),
        sa.Column("dias", sa.Integer(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "mae_proveedor",
        *_auditoria(),
        sa.Column("tipo_documento", sa.String(5), nullable=False),
        sa.Column("numero_documento", sa.String(20), nullable=False),
        sa.Column("pais", sa.String(2), nullable=False),
        sa.Column("razon_social", sa.String(200), nullable=False),
        sa.Column("nombre_comercial", sa.String(150), nullable=True),
        sa.Column("direccion", sa.String(300), nullable=True),
        sa.Column("correo", sa.String(200), nullable=True),
        sa.Column("telefono", sa.String(40), nullable=True),
        sa.Column("moneda", sa.String(3), sa.ForeignKey("mae_moneda.codigo"), nullable=False),
        sa.Column(
            "condicion_pago_id",
            sa.Uuid(),
            sa.ForeignKey("mae_condicion_pago.id"),
            nullable=False,
        ),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("pais", "tipo_documento", "numero_documento"),
    )
    op.create_index("ix_mae_proveedor_numero_documento", "mae_proveedor", ["numero_documento"])
    op.create_index("ix_mae_proveedor_razon_social", "mae_proveedor", ["razon_social"])
    op.create_table(
        "mae_proveedor_categoria",
        sa.Column(
            "proveedor_id",
            sa.Uuid(),
            sa.ForeignKey("mae_proveedor.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("categoria_id", sa.Uuid(), sa.ForeignKey("mae_categoria.id"), primary_key=True),
    )
    op.create_table(
        "mae_proveedor_contacto",
        *_auditoria(),
        _proveedor(),
        sa.Column("nombre", sa.String(150), nullable=False),
        sa.Column("cargo", sa.String(100), nullable=True),
        sa.Column("correo", sa.String(200), nullable=True),
        sa.Column("telefono", sa.String(40), nullable=True),
        sa.Column("principal", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "mae_proveedor_cuenta",
        *_auditoria(),
        _proveedor(),
        sa.Column("banco", sa.String(100), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("moneda", sa.String(3), sa.ForeignKey("mae_moneda.codigo"), nullable=False),
        sa.Column("numero", sa.String(34), nullable=False),
        sa.Column("cci", sa.String(20), nullable=True),
        sa.Column("swift", sa.String(11), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "mae_proveedor_bloqueo",
        *_auditoria(),
        _proveedor(),
        sa.Column("empresa_id", sa.Uuid(), sa.ForeignKey("mae_empresa.id"), nullable=False),
        sa.Column("motivo", sa.String(300), nullable=False),
        sa.UniqueConstraint("proveedor_id", "empresa_id"),
    )
    for tabla in ("mae_proveedor_contacto", "mae_proveedor_cuenta", "mae_proveedor_bloqueo"):
        op.create_index(f"ix_{tabla}_proveedor_id", tabla, ["proveedor_id"])


def downgrade() -> None:
    for tabla in (
        "mae_proveedor_bloqueo",
        "mae_proveedor_cuenta",
        "mae_proveedor_contacto",
        "mae_proveedor_categoria",
        "mae_proveedor",
        "mae_condicion_pago",
    ):
        op.drop_table(tabla)
