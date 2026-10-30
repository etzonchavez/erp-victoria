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
