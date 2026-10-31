"""solicitudes de compra y reglas de aprobación configurables

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-31

- seg_usuario.jefe_id: jefe inmediato (aprobador "jefe del solicitante").
- cnt_centro_costo.responsable_id: usuario responsable (aprobador "responsable del centro").
- apr_*: reglas de aprobación (hasta 3 niveles, serie o paralelo) y pasos de cada envío.
- sol_*: solicitud con cabecera, línea y distribución, cada una con atributos (ADR-005).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.atributos import columnas_atributos

revision: str = "0011"
down_revision: str | None = "0010"
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


def _condiciones() -> list[sa.Column]:
    return [
        _fk("unidad_negocio_id", "mae_unidad_negocio"),
        _fk("categoria_id", "mae_categoria"),
        _fk("centro_costo_id", "cnt_centro_costo"),
    ]


def upgrade() -> None:
    with op.batch_alter_table("seg_usuario") as t:
        t.add_column(_fk("jefe_id", "seg_usuario"))
    with op.batch_alter_table("cnt_centro_costo") as t:
        t.add_column(_fk("responsable_id", "seg_usuario"))

    op.create_table(
        "apr_regla",
        *_auditoria(),
        _fk("empresa_id", "mae_empresa", nulo=False),
        sa.Column("documento", sa.String(30), nullable=False),
        sa.Column("nombre", sa.String(100), nullable=False),
        sa.Column("prioridad", sa.Integer(), nullable=False),
        sa.Column("tipo_articulo", sa.String(30), nullable=True),
        *_condiciones(),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("empresa_id", "documento", "prioridad"),
    )
    op.create_index("ix_apr_regla_empresa_id", "apr_regla", ["empresa_id"])
    op.create_table(
        "apr_nivel",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("regla_id", "apr_regla", nulo=False, ondelete="CASCADE"),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("monto_desde", sa.Numeric(18, 2), nullable=False),
        sa.Column("modo", sa.String(25), nullable=False),
        sa.UniqueConstraint("regla_id", "numero"),
    )
    op.create_index("ix_apr_nivel_regla_id", "apr_nivel", ["regla_id"])
    op.create_table(
        "apr_aprobador",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("nivel_id", "apr_nivel", nulo=False, ondelete="CASCADE"),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        _fk("usuario_id", "seg_usuario"),
        _fk("rol_id", "seg_rol"),
        *_condiciones(),
    )
    op.create_index("ix_apr_aprobador_nivel_id", "apr_aprobador", ["nivel_id"])
    op.create_table(
        "apr_paso",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("documento", sa.String(30), nullable=False),
        sa.Column("documento_id", sa.Uuid(), nullable=False),
        sa.Column("ronda", sa.Integer(), nullable=False),
        sa.Column("regla_id", sa.Uuid(), nullable=True),
        sa.Column("regla_nombre", sa.String(100), nullable=False),
        sa.Column("nivel", sa.Integer(), nullable=False),
        sa.Column("modo", sa.String(25), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=True),
        sa.Column("rol_id", sa.Uuid(), nullable=True),
        sa.Column("descripcion", sa.String(200), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False),
        sa.Column("motivo", sa.String(200), nullable=True),
        sa.Column("actuado_por", sa.Uuid(), nullable=True),
        sa.Column("actuado_por_nombre", sa.String(150), nullable=True),
        sa.Column("actuado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("comentario", sa.String(500), nullable=True),
    )
    for col in ("documento_id", "usuario_id", "rol_id", "estado"):
        op.create_index(f"ix_apr_paso_{col}", "apr_paso", [col])

    op.create_table(
        "sol_correlativo",
        sa.Column("empresa_id", sa.Uuid(), sa.ForeignKey("mae_empresa.id"), primary_key=True),
        sa.Column("anio", sa.Integer(), primary_key=True),
        sa.Column("ultimo", sa.Integer(), nullable=False),
    )
    op.create_table(
        "sol_solicitud",
        *_auditoria(),
        _fk("empresa_id", "mae_empresa", nulo=False),
        _fk("unidad_negocio_id", "mae_unidad_negocio", nulo=False),
        sa.Column("numero", sa.String(20), nullable=False),
        _fk("solicitante_id", "seg_usuario", nulo=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("fecha_requerida", sa.Date(), nullable=True),
        sa.Column("titulo", sa.String(150), nullable=False),
        sa.Column("justificacion", sa.Text(), nullable=True),
        sa.Column("moneda", sa.String(3), sa.ForeignKey("mae_moneda.codigo"), nullable=False),
        sa.Column("total", sa.Numeric(18, 2), nullable=False),
        sa.Column("tipo_cambio", sa.Numeric(12, 6), nullable=False),
        sa.Column("total_funcional", sa.Numeric(18, 2), nullable=False),
        sa.Column("estado", sa.String(25), nullable=False),
        sa.Column("ronda", sa.Integer(), nullable=False),
        *columnas_atributos(),
        sa.UniqueConstraint("empresa_id", "numero"),
    )
    for col in ("empresa_id", "solicitante_id", "estado"):
        op.create_index(f"ix_sol_solicitud_{col}", "sol_solicitud", [col])
    op.create_table(
        "sol_linea",
        *_auditoria(),
        _fk("solicitud_id", "sol_solicitud", nulo=False, ondelete="CASCADE"),
        sa.Column("numero", sa.Integer(), nullable=False),
        _fk("articulo_id", "mae_articulo", nulo=False),
        sa.Column("descripcion", sa.String(240), nullable=False),
        sa.Column("cantidad", sa.Numeric(18, 4), nullable=False),
        sa.Column(
            "unidad", sa.String(10), sa.ForeignKey("mae_unidad_medida.codigo"), nullable=False
        ),
        sa.Column("cantidad_base", sa.Numeric(18, 4), nullable=False),
        sa.Column("precio", sa.Numeric(18, 4), nullable=False),
        sa.Column("subtotal", sa.Numeric(18, 2), nullable=False),
        _fk("perfil_id", "cnt_perfil"),
        _fk("cuenta_id", "cnt_cuenta"),
        *columnas_atributos(),
    )
    op.create_index("ix_sol_linea_solicitud_id", "sol_linea", ["solicitud_id"])
    op.create_table(
        "sol_distribucion",
        *_auditoria(),
        _fk("linea_id", "sol_linea", nulo=False, ondelete="CASCADE"),
        sa.Column("numero", sa.Integer(), nullable=False),
        _fk("centro_costo_id", "cnt_centro_costo", nulo=False),
        sa.Column("porcentaje", sa.Numeric(7, 4), nullable=False),
        sa.Column("monto", sa.Numeric(18, 2), nullable=False),
        *columnas_atributos(),
    )
    op.create_index("ix_sol_distribucion_linea_id", "sol_distribucion", ["linea_id"])


def downgrade() -> None:
    for tabla in (
        "sol_distribucion",
        "sol_linea",
        "sol_solicitud",
        "sol_correlativo",
        "apr_paso",
        "apr_aprobador",
        "apr_nivel",
        "apr_regla",
    ):
        op.drop_table(tabla)
    with op.batch_alter_table("cnt_centro_costo") as t:
        t.drop_column("responsable_id")
    with op.batch_alter_table("seg_usuario") as t:
        t.drop_column("jefe_id")
