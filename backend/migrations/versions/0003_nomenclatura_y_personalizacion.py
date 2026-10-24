"""nomenclatura ERP_MOD_FUNCION en roles y personalización de la empresa

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-24
"""

import re
from collections import Counter
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Copia fija de esta versión: una migración no debe depender del código que cambia.
ABREVIATURAS = {"seguridad": "SEG", "maestros": "MAE", "solicitudes": "SOL", "compras": "COM"}
ESTANDAR = {
    "seguridad.administrador": "ERP_SEG_ADMINISTRADOR",
    "seguridad.configurador": "ERP_SEG_CONFIGURADOR",
    "seguridad.gestor_usuarios": "ERP_SEG_GESTOR_USUARIOS",
    "seguridad.auditor": "ERP_SEG_AUDITOR",
}


def upgrade() -> None:
    conn = op.get_bind()

    # Abreviatura de cada módulo
    op.add_column("seg_modulo", sa.Column("abreviatura", sa.String(length=3), nullable=True))
    for codigo, abr in ABREVIATURAS.items():
        conn.execute(
            sa.text("UPDATE seg_modulo SET abreviatura = :a WHERE codigo = :c"),
            {"a": abr, "c": codigo},
        )
    conn.execute(
        sa.text("UPDATE seg_modulo SET abreviatura = UPPER(SUBSTR(codigo, 1, 3)) "
                "WHERE abreviatura IS NULL")
    )
    op.alter_column("seg_modulo", "abreviatura", nullable=False)

    # Módulo de cada rol y renombre a ERP_<MÓDULO>_<FUNCIÓN>
    op.add_column("seg_rol", sa.Column("modulo", sa.String(length=50), nullable=True))
    roles = conn.execute(sa.text("SELECT id, codigo, estandar FROM seg_rol")).all()
    usados = {r.codigo for r in roles}
    for rol in roles:
        permisos = conn.execute(
            sa.text("SELECT permiso_codigo FROM seg_rol_permiso WHERE rol_id = :id"),
            {"id": rol.id},
        ).scalars()
        conteo = Counter(p.split(".")[0] for p in permisos)
        modulo = rol.codigo.split(".")[0] if rol.estandar else None
        modulo = modulo or (conteo.most_common(1)[0][0] if conteo else "seguridad")
        if rol.codigo in ESTANDAR:
            nuevo = ESTANDAR[rol.codigo]
        else:
            funcion = re.sub(r"[^A-Z0-9]+", "_", rol.codigo.upper()).strip("_") or "ROL"
            base = f"ERP_{ABREVIATURAS.get(modulo, 'SEG')}_{funcion}"[:46]
            nuevo, n = base, 2
            while nuevo in usados:
                nuevo, n = f"{base}_{n}", n + 1
        usados.add(nuevo)
        conn.execute(
            sa.text("UPDATE seg_rol SET codigo = :c, modulo = :m WHERE id = :id"),
            {"c": nuevo, "m": modulo, "id": rol.id},
        )
    op.alter_column("seg_rol", "modulo", nullable=False)
    op.create_foreign_key("fk_seg_rol_modulo", "seg_rol", "seg_modulo", ["modulo"], ["codigo"])

    # Personalización de la empresa (una sola fila)
    op.create_table(
        "seg_personalizacion",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre_empresa", sa.String(length=150), nullable=True),
        sa.Column("logo", sa.LargeBinary(), nullable=True),
        sa.Column("logo_tipo", sa.String(length=30), nullable=True),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actualizado_por", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("seg_personalizacion")
    op.drop_constraint("fk_seg_rol_modulo", "seg_rol", type_="foreignkey")
    op.drop_column("seg_rol", "modulo")
    op.drop_column("seg_modulo", "abreviatura")
