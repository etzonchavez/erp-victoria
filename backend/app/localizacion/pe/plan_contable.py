"""Plantilla contable de Perú: PCGE Modificado 2019, versión reducida para compras.

Códigos de los elementos 1 a 4 verificados con el catálogo oficial del MEF.
Los del elemento 6 siguen la práctica contable y están POR VALIDAR con un contador
(ver docs/modulos/contabilidad.md). Cada empresa puede editar su plan después.

El PCGE 2026 (Resolución N.° 002-2026-EF/30, vigente desde el 1 de enero de 2028)
se agregará como otra plantilla sin cambiar esta.
"""

from decimal import Decimal

PLANTILLA = "PCGE-2019"

# Naturaleza según el primer dígito (elemento) del PCGE.
NATURALEZA_POR_ELEMENTO = {
    "1": "activo",
    "2": "activo",
    "3": "activo",
    "4": "pasivo",
    "5": "patrimonio",
    "6": "gasto",
    "7": "ingreso",
    "8": "resultado",
    "9": "analitica",
    "0": "orden",
}

# (código, nombre). El padre se deduce del prefijo; las cuentas sin hijas son imputables.
CUENTAS: list[tuple[str, str]] = [
    ("16", "Cuentas por cobrar diversas – Terceros"),
    ("167", "Tributos por acreditar"),
    ("1673", "IGV por acreditar en compras"),
    ("20", "Mercaderías"),
    ("201", "Mercaderías"),
    ("2011", "Mercaderías"),
    ("20111", "Mercaderías – Costo"),
    ("24", "Materias primas"),
    ("241", "Materias primas"),
    ("2411", "Materias primas"),
    ("24111", "Materias primas – Costo"),
    ("25", "Materiales auxiliares, suministros y repuestos"),
    ("252", "Suministros"),
    ("2524", "Otros suministros"),
    ("26", "Envases y embalajes"),
    ("261", "Envases"),
    ("28", "Inventarios por recibir"),
    ("281", "Mercaderías"),
    ("33", "Propiedad, planta y equipo"),
    ("333", "Maquinaria y equipo de explotación"),
    ("3331", "Maquinaria y equipo de explotación"),
    ("33311", "Maquinaria y equipo de explotación – Costo"),
    ("335", "Muebles y enseres"),
    ("3351", "Muebles"),
    ("33511", "Muebles – Costo"),
    ("336", "Equipos diversos"),
    ("3361", "Equipo para procesamiento de información"),
    ("33611", "Equipo para procesamiento de información – Costo"),
    ("40", "Tributos, contraprestaciones y aportes al sistema de pensiones y de salud por pagar"),
    ("401", "Gobierno central"),
    ("4011", "Impuesto general a las ventas"),
    ("40111", "IGV – Cuenta propia"),
    ("42", "Cuentas por pagar comerciales – Terceros"),
    ("421", "Facturas, boletas y otros comprobantes por pagar"),
    ("4212", "Emitidas"),
    ("46", "Cuentas por pagar diversas – Terceros"),
    ("465", "Pasivos por compra de activo inmovilizado"),
    ("4654", "Propiedad, planta y equipo"),
    ("60", "Compras"),
    ("601", "Mercaderías"),
    ("6011", "Mercaderías"),
    ("602", "Materias primas"),
    ("6021", "Materias primas"),
    ("603", "Materiales auxiliares, suministros y repuestos"),
    ("6032", "Suministros"),
    ("61", "Variación de inventarios"),
    ("611", "Mercaderías"),
    ("6111", "Mercaderías"),
    ("612", "Materias primas"),
    ("6121", "Materias primas"),
    ("613", "Materiales auxiliares, suministros y repuestos"),
    ("6132", "Suministros"),
    ("63", "Gastos de servicios prestados por terceros"),
    ("639", "Otros servicios prestados por terceros"),
    ("65", "Otros gastos de gestión"),
    ("656", "Suministros"),
]

# (código, nombre, tipo de artículo, cargo, existencia, variación, por pagar)
PERFILES: list[tuple[str, str, str, str, str | None, str | None, str]] = [
    ("MERCADERIA", "Mercaderías", "bien_inventariable", "6011", "20111", "6111", "4212"),
    ("MATERIA_PRIMA", "Materias primas", "bien_inventariable", "6021", "24111", "6121", "4212"),
    (
        "SUMINISTRO_ALMACEN",
        "Suministros de almacén",
        "bien_inventariable",
        "6032",
        "2524",
        "6132",
        "4212",
    ),
    ("CONSUMO_DIRECTO", "Consumo directo", "bien_no_inventariable", "656", None, None, "4212"),
    ("SERVICIO", "Servicios de terceros", "servicio", "639", None, None, "4212"),
    ("ACTIVO_FIJO", "Activo fijo – equipos de cómputo", "activo_fijo", "33611", None, None, "4654"),
    ("ACTIVO_MUEBLES", "Activo fijo – muebles", "activo_fijo", "33511", None, None, "4654"),
    ("ACTIVO_MAQUINARIA", "Activo fijo – maquinaria", "activo_fijo", "33311", None, None, "4654"),
]

# Perfil sugerido para las categorías de ejemplo (código de categoría → código de perfil).
# Las subcategorías que no aparecen heredan el perfil de su categoría padre.
CATEGORIAS_PERFIL: dict[str, str] = {
    "MER": "MERCADERIA",
    "MP": "MATERIA_PRIMA",
    "SUM": "SUMINISTRO_ALMACEN",
    "SUM-OFI": "CONSUMO_DIRECTO",
    "SUM-LIM": "CONSUMO_DIRECTO",
    "SRV": "SERVICIO",
    "AF": "ACTIVO_FIJO",
    "AF-MUE": "ACTIVO_MUEBLES",
    "AF-MAQ": "ACTIVO_MAQUINARIA",
}

# (código, nombre, tasa %, cuenta)
IMPUESTOS: list[tuple[str, str, Decimal, str | None]] = [
    ("IGV18", "IGV 18 %", Decimal("18"), "40111"),
    ("EXO", "Exonerado", Decimal("0"), None),
    ("INA", "Inafecto", Decimal("0"), None),
]
