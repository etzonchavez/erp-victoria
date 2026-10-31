"""Atributos adicionales configurables de los documentos operativos (ADR-005).

Todo documento operativo (solicitud, orden de compra…) reserva 30 atributos por nivel
—cabecera, línea y distribución—: 10 de texto, 10 numéricos y 10 de fecha. El
administrador activa y nombra los que necesita (seguridad.atributos) y define a qué
atributo del documento siguiente se copia cada uno.

Uso en un módulo:

    class SolicitudLinea(ConAtributos, ConAuditoria, Base): ...

    # migración
    op.create_table("sol_linea", ..., *columnas_atributos())
"""

from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.orm import mapped_column

TIPOS = {"texto": "Texto", "numero": "Número", "fecha": "Fecha"}
NIVELES = {"cabecera": "Cabecera", "linea": "Línea", "distribucion": "Distribución"}
POR_TIPO = 10
LARGO_TEXTO = 240


def _tipo_columna(tipo: str):
    return {"texto": sa.String(LARGO_TEXTO), "numero": sa.Numeric(18, 4), "fecha": sa.Date()}[tipo]


def columna(tipo: str, numero: int) -> str:
    """Nombre de la columna de un atributo: ("texto", 3) → "atr_texto_03"."""
    if tipo not in TIPOS or not 1 <= numero <= POR_TIPO:
        raise ValueError(f"Atributo inexistente: {tipo} {numero}")
    return f"atr_{tipo}_{numero:02d}"


def todas_las_columnas() -> list[tuple[str, int, str]]:
    return [(t, n, columna(t, n)) for t in TIPOS for n in range(1, POR_TIPO + 1)]


# Mixin con las 30 columnas, generado para no escribirlas a mano.
ConAtributos = type(
    "ConAtributos",
    (),
    {
        "__doc__": "Agrega a la tabla los 30 atributos adicionales (ADR-005).",
        **{
            nombre: mapped_column(_tipo_columna(tipo), nullable=True)
            for tipo, _, nombre in todas_las_columnas()
        },
    },
)


def columnas_atributos() -> list[sa.Column]:
    """Columnas para crear la tabla en una migración de Alembic."""
    return [
        sa.Column(nombre, _tipo_columna(t), nullable=True) for t, _, nombre in todas_las_columnas()
    ]


@dataclass(frozen=True)
class Documento:
    codigo: str
    nombre: str
    modulo: str  # módulo dueño del documento (para la documentación y el menú)
    niveles: tuple[str, ...] = ("cabecera", "linea", "distribucion")


# Documentos operativos que llevan atributos. Cada módulo nuevo agrega aquí el suyo.
DOCUMENTOS: dict[str, Documento] = {
    d.codigo: d
    for d in (
        Documento("solicitud", "Solicitud de compra", "solicitudes"),
        Documento("orden_compra", "Orden de compra", "compras"),
    )
}

# Flujos entre documentos: los atributos del origen pueden copiarse al destino.
FLUJOS: list[tuple[str, str]] = [("solicitud", "orden_compra")]


def destinos(documento: str) -> list[str]:
    return [d for o, d in FLUJOS if o == documento]
