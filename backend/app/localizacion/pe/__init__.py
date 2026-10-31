"""Localización Perú: RUC, unidades de medida SUNAT (Catálogo N.° 03)."""

PESOS_RUC = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
PREFIJOS_RUC = ("10", "15", "16", "17", "20")


def validar_ruc(ruc: str) -> str | None:
    """Valida el RUC de SUNAT: 11 dígitos, prefijo de tipo de contribuyente y dígito verificador."""
    if len(ruc) != 11 or not ruc.isdigit():
        return "El RUC debe tener 11 dígitos"
    if not ruc.startswith(PREFIJOS_RUC):
        return "El RUC debe empezar con 10, 15, 16, 17 o 20"
    suma = sum(int(d) * p for d, p in zip(ruc[:10], PESOS_RUC, strict=True))
    verificador = 11 - suma % 11
    verificador = {10: 0, 11: 1}.get(verificador, verificador)
    if verificador != int(ruc[10]):
        return "El RUC no es válido (dígito verificador incorrecto)"
    return None


def validar_dni(dni: str) -> str | None:
    if len(dni) != 8 or not dni.isdigit():
        return "El DNI debe tener 8 dígitos"
    return None


def validar_cci(cci: str) -> str | None:
    """Código de Cuenta Interbancario: 20 dígitos."""
    if len(cci) != 20 or not cci.isdigit():
        return "El CCI debe tener 20 dígitos"
    return None


# Tipos de documento de identidad de un proveedor domiciliado en Perú.
# (código, nombre, código SUNAT Catálogo N.° 06, validador)
TIPOS_DOCUMENTO = [
    ("RUC", "RUC", "6", validar_ruc),
    ("DNI", "DNI", "1", validar_dni),
]
