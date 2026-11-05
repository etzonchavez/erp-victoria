"""órdenes de compra con aprobación y formato PDF configurable

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-04

- cmp_*: orden (cabecera, línea y distribución con atributos ADR-005), correlativo y formato
  PDF por empresa.
- sol_solicitud.orden_compra_id / _numero: la orden que atiende la solicitud.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.atributos import columnas_atributos

revision: str = "0012"
down_revision: str | None = "0011"
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


def _fk(nombre: str, tabla: str, nulo: bool = True, **kw) -> sa.Column:
    return sa.Column(nombre, sa.Uuid(), sa.ForeignKey(f"{tabla}.id", **kw), nullable=nulo)


def upgrade() -> None:
    with op.batch_alter_table("sol_solicitud") as t:
        t.add_column(sa.Column("orden_compra_id", sa.Uuid(), nullable=True))
        t.add_column(sa.Column("orden_compra_numero", sa.String(20), nullable=True))

    op.create_table(
        "cmp_correlativo",
        sa.Column("empresa_id", sa.Uuid(), sa.ForeignKey("mae_empresa.id"), primary_key=True),
        sa.Column("anio", sa.Integer(), primary_key=True),
        sa.Column("ultimo", sa.Integer(), nullable=False),
    )
    op.create_table(
        "cmp_orden",
        *_auditoria(),
        _fk("empresa_id", "mae_empresa", nulo=False),
        _fk("unidad_negocio_id", "mae_unidad_negocio", nulo=False),
        sa.Column("numero", sa.String(20), nullable=False),
        _fk("comprador_id", "seg_usuario", nulo=False),
        _fk("proveedor_id", "mae_proveedor", nulo=False),
        _fk("contacto_id", "mae_proveedor_contacto"),
        _fk("condicion_pago_id", "mae_condicion_pago", nulo=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("fecha_entrega", sa.Date(), nullable=True),
        sa.Column("lugar_entrega", sa.String(300), nullable=True),
        sa.Column("observaciones", sa.Text(), nullable=True),
        sa.Column("moneda", sa.String(3), sa.ForeignKey("mae_moneda.codigo"), nullable=False),
        sa.Column("subtotal", sa.Numeric(18, 2), nullable=False),
        sa.Column("impuesto", sa.Numeric(18, 2), nullable=False),
        sa.Column("total", sa.Numeric(18, 2), nullable=False),
        sa.Column("tipo_cambio", sa.Numeric(12, 6), nullable=False),
        sa.Column("total_funcional", sa.Numeric(18, 2), nullable=False),
        sa.Column("estado", sa.String(25), nullable=False),
        sa.Column("ronda", sa.Integer(), nullable=False),
        sa.Column("enviada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enviada_por", sa.Uuid(), nullable=True),
        *columnas_atributos(),
        sa.UniqueConstraint("empresa_id", "numero"),
    )
    for col in ("empresa_id", "comprador_id", "proveedor_id", "estado"):
        op.create_index(f"ix_cmp_orden_{col}", "cmp_orden", [col])
    op.create_table(
        "cmp_linea",
        *_auditoria(),
        _fk("orden_id", "cmp_orden", nulo=False, ondelete="CASCADE"),
        sa.Column("numero", sa.Integer(), nullable=False),
        _fk("solicitud_id", "sol_solicitud"),
        _fk("solicitud_linea_id", "sol_linea"),
        sa.Column("solicitud_numero", sa.String(20), nullable=True),
        _fk("articulo_id", "mae_articulo", nulo=False),
        sa.Column("descripcion", sa.String(240), nullable=False),
        sa.Column("cantidad", sa.Numeric(18, 4), nullable=False),
        sa.Column(
            "unidad", sa.String(10), sa.ForeignKey("mae_unidad_medida.codigo"), nullable=False
        ),
        sa.Column("cantidad_base", sa.Numeric(18, 4), nullable=False),
        sa.Column("precio", sa.Numeric(18, 4), nullable=False),
        sa.Column("subtotal", sa.Numeric(18, 2), nullable=False),
        _fk("impuesto_id", "cnt_impuesto"),
        sa.Column("tasa", sa.Numeric(7, 4), nullable=False),
        sa.Column("impuesto_monto", sa.Numeric(18, 2), nullable=False),
        sa.Column("total", sa.Numeric(18, 2), nullable=False),
        _fk("perfil_id", "cnt_perfil"),
        _fk("cuenta_id", "cnt_cuenta"),
        *columnas_atributos(),
    )
    op.create_index("ix_cmp_linea_orden_id", "cmp_linea", ["orden_id"])
    op.create_index("ix_cmp_linea_solicitud_id", "cmp_linea", ["solicitud_id"])
    op.create_table(
        "cmp_distribucion",
        *_auditoria(),
        _fk("linea_id", "cmp_linea", nulo=False, ondelete="CASCADE"),
        sa.Column("numero", sa.Integer(), nullable=False),
        _fk("centro_costo_id", "cnt_centro_costo", nulo=False),
        sa.Column("porcentaje", sa.Numeric(7, 4), nullable=False),
        sa.Column("monto", sa.Numeric(18, 2), nullable=False),
        *columnas_atributos(),
    )
    op.create_index("ix_cmp_distribucion_linea_id", "cmp_distribucion", ["linea_id"])
    op.create_table(
        "cmp_formato",
        sa.Column("empresa_id", sa.Uuid(), sa.ForeignKey("mae_empresa.id"), primary_key=True),
        sa.Column("configuracion", sa.JSON(), nullable=False),
        sa.Column("logo", sa.LargeBinary(), nullable=True),
        sa.Column("logo_tipo", sa.String(30), nullable=True),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actualizado_por", sa.Uuid(), nullable=True),
    )


def downgrade() -> None:
    for tabla in ("cmp_formato", "cmp_distribucion", "cmp_linea", "cmp_orden", "cmp_correlativo"):
        op.drop_table(tabla)
    with op.batch_alter_table("sol_solicitud") as t:
        t.drop_column("orden_compra_numero")
        t.drop_column("orden_compra_id")
