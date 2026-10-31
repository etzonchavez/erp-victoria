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

# Árbol de categorías de ejemplo para empezar rápido: (código, nombre, código del padre).
# El cliente las renombra, desactiva o agrega las suyas.
CATEGORIAS = [
    ("MER", "Mercaderías", None),
    ("MP", "Materias primas", None),
    ("SUM", "Suministros", None),
    ("SUM-REP", "Repuestos", "SUM"),
    ("SUM-OFI", "Útiles de oficina", "SUM"),
    ("SUM-LIM", "Artículos de limpieza", "SUM"),
    ("SRV", "Servicios", None),
    ("SRV-MAN", "Mantenimiento y reparaciones", "SRV"),
    ("SRV-CON", "Asesoría y consultoría", "SRV"),
    ("SRV-TRA", "Transporte y fletes", "SRV"),
    ("AF", "Activo fijo", None),
    ("AF-TI", "Equipos de cómputo", "AF"),
    ("AF-MUE", "Muebles y enseres", "AF"),
    ("AF-MAQ", "Maquinaria y equipo", "AF"),
]

# (código, nombre, días)
CONDICIONES_PAGO = [
    ("CONTADO", "Contado", 0),
    ("15D", "Crédito 15 días", 15),
    ("30D", "Crédito 30 días", 30),
    ("45D", "Crédito 45 días", 45),
    ("60D", "Crédito 60 días", 60),
]

TIPOS_CUENTA_BANCARIA = {
    "corriente": "Cuenta corriente",
    "ahorros": "Cuenta de ahorros",
    "detracciones": "Cuenta de detracciones",
}
