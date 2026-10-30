"""Datos que se precargan en toda instalación nueva. Se cargan solo si no existen,
así una versión nueva puede agregar datos sin pisar los cambios del cliente."""

from decimal import Decimal

# (código ISO 4217, nombre, símbolo, decimales, activa por defecto)
MONEDAS = [
    ("PEN", "Sol peruano", "S/", 2, True),
    ("USD", "Dólar estadounidense", "US$", 2, True),
    ("EUR", "Euro", "€", 2, False),
    ("COP", "Peso colombiano", "COL$", 2, False),
    ("PAB", "Balboa panameño", "B/.", 2, False),
    ("CLP", "Peso chileno", "CLP$", 0, False),
]

# (código interno, nombre, código oficial SUNAT Catálogo N.° 03 = UN/ECE Rec. 20, tipo)
UNIDADES = [
    ("UND", "Unidad", "NIU", "cantidad"),
    ("SRV", "Servicio", "ZZ", "servicio"),
    ("DOC", "Docena", "DZN", "cantidad"),
    ("CJA", "Caja", "BX", "cantidad"),
    ("PAQ", "Paquete", "PK", "cantidad"),
    ("JGO", "Juego", "SET", "cantidad"),
    ("MLL", "Millar", "MIL", "cantidad"),
    ("KG", "Kilogramo", "KGM", "peso"),
    ("G", "Gramo", "GRM", "peso"),
    ("TN", "Tonelada", "TNE", "peso"),
    ("L", "Litro", "LTR", "volumen"),
    ("ML", "Mililitro", "MLT", "volumen"),
    ("GAL", "Galón", "GLL", "volumen"),
    ("M3", "Metro cúbico", "MTQ", "volumen"),
    ("M", "Metro", "MTR", "longitud"),
    ("CM", "Centímetro", "CMT", "longitud"),
    ("M2", "Metro cuadrado", "MTK", "area"),
    ("H", "Hora", "HUR", "tiempo"),
    ("DIA", "Día", "DAY", "tiempo"),
    ("MES", "Mes", "MON", "tiempo"),
]

TIPOS_UNIDAD = ["cantidad", "servicio", "peso", "volumen", "longitud", "area", "tiempo"]

# (origen, destino, factor): 1 origen = factor destino
CONVERSIONES = [
    ("DOC", "UND", Decimal("12")),
    ("MLL", "UND", Decimal("1000")),
    ("KG", "G", Decimal("1000")),
    ("TN", "KG", Decimal("1000")),
    ("L", "ML", Decimal("1000")),
    ("GAL", "L", Decimal("3.785412")),
    ("M3", "L", Decimal("1000")),
    ("M", "CM", Decimal("100")),
    ("DIA", "H", Decimal("24")),
]
