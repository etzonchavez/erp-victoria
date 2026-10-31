"""Localización por país (ADR-002).

El núcleo es neutro: cada país aporta aquí su identificación fiscal, moneda,
catálogos oficiales y, más adelante, impuestos, plan de cuentas y comprobantes.
Agregar un país = agregar un paquete y registrarlo en PAISES; el núcleo no cambia.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.localizacion import pe
from app.localizacion.pe import plan_contable as pe_plan


@dataclass(frozen=True)
class Pais:
    codigo: str  # ISO 3166-1 alfa-2 en minúsculas
    nombre: str
    moneda: str  # ISO 4217
    nombre_identificacion_fiscal: str  # RUC, NIT, RUT…
    validar_identificacion_fiscal: Callable[[str], str | None]  # motivo del error o None
    zona_horaria: str
    # Módulo con PLANTILLA, NATURALEZA_POR_ELEMENTO, CUENTAS, PERFILES, IMPUESTOS
    plan_contable: Any = None
    # Documentos de terceros locales: (código, nombre, código oficial, validador)
    tipos_documento: tuple = ()
    validar_cuenta_interbancaria: Callable[[str], str | None] | None = None


PAISES: dict[str, Pais] = {
    "pe": Pais(
        codigo="pe",
        nombre="Perú",
        moneda="PEN",
        nombre_identificacion_fiscal="RUC",
        validar_identificacion_fiscal=pe.validar_ruc,
        zona_horaria="America/Lima",
        plan_contable=pe_plan,
        tipos_documento=tuple(pe.TIPOS_DOCUMENTO),
        validar_cuenta_interbancaria=pe.validar_cci,
    ),
}


def pais(codigo: str) -> Pais | None:
    return PAISES.get(codigo.lower())


# Proveedor del exterior (no domiciliado): se identifica con su número tributario de origen.
TIPO_EXTRANJERO = ("EXT", "Identificación tributaria del exterior", "0")
