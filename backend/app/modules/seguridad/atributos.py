"""Configuración, validación y copia de los atributos adicionales (ADR-005).

Los módulos operativos usan:

- validar_valores(db, "solicitud", "linea", {"atr_texto_01": "P-104"}) al guardar;
- valores_por_defecto(db, "solicitud", "cabecera") al crear un documento;
- copiar_valores(db, "solicitud", "orden_compra", "linea", valores) al generar el siguiente.
"""

from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import atributos as nucleo
from app.core.errors import ErrorERP
from app.modules.seguridad.models import Atributo, AtributoValor, Usuario
from app.modules.seguridad.service import auditar

MAX_VALORES_LISTA = 200


def _validar_ranura(documento: str, nivel: str, tipo: str, numero: int) -> None:
    doc = nucleo.DOCUMENTOS.get(documento)
    if not doc:
        raise ErrorERP(
            422, "documento_invalido", f"Documento no válido: {', '.join(nucleo.DOCUMENTOS)}"
        )
    if nivel not in doc.niveles:
        raise ErrorERP(422, "nivel_invalido", f"{doc.nombre} no tiene el nivel {nivel}")
    if tipo not in nucleo.TIPOS or not 1 <= numero <= nucleo.POR_TIPO:
        raise ErrorERP(
            422, "atributo_invalido", f"Hay {nucleo.POR_TIPO} atributos de texto, número y fecha"
        )


def _convertir(tipo: str, valor, etiqueta: str):
    """Convierte un valor al tipo del atributo; None si viene vacío."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None
    try:
        if tipo == "texto":
            texto = str(valor).strip()
            if len(texto) > nucleo.LARGO_TEXTO:
                raise ValueError
            return texto
        if tipo == "numero":
            numero = Decimal(str(valor))
            if not numero.is_finite() or abs(numero) >= Decimal("1e14"):
                raise ValueError
            return numero.quantize(Decimal("0.0001"))
        return valor if isinstance(valor, date) else date.fromisoformat(str(valor))
    except (ValueError, InvalidOperation):
        detalle = {
            "texto": f"hasta {nucleo.LARGO_TEXTO} caracteres",
            "numero": "un número",
            "fecha": "una fecha AAAA-MM-DD",
        }[tipo]
        raise ErrorERP(422, "valor_invalido", f"{etiqueta}: debe ser {detalle}") from None


def _filas(db: Session, documento: str | None = None) -> dict[tuple, Atributo]:
    q = select(Atributo)
    if documento:
        q = q.where(Atributo.documento == documento)
    return {(a.documento, a.nivel, a.tipo, a.numero): a for a in db.scalars(q)}


def listar(db: Session, documento: str | None = None, solo_activos: bool = False) -> list[dict]:
    """Las 30 ranuras de cada documento y nivel, configuradas o no."""
    filas = _filas(db, documento)
    resultado = []
    for doc in nucleo.DOCUMENTOS.values():
        if documento and doc.codigo != documento:
            continue
        for nivel in doc.niveles:
            for tipo, numero, columna in nucleo.todas_las_columnas():
                a = filas.get((doc.codigo, nivel, tipo, numero))
                if solo_activos and not (a and a.activo):
                    continue
                resultado.append(
                    {
                        "documento": doc.codigo,
                        "nivel": nivel,
                        "tipo": tipo,
                        "numero": numero,
                        "columna": columna,
                        "activo": bool(a and a.activo),
                        "etiqueta": a.etiqueta if a else None,
                        "ayuda": a.ayuda if a else None,
                        "valor_defecto": a.valor_defecto if a else None,
                        "valores": [v.valor for v in a.valores] if a else [],
                        "copiar_documento": a.copiar_documento if a else None,
                        "copiar_numero": a.copiar_numero if a else None,
                    }
                )
    return resultado


def definir(
    db: Session,
    actor: Usuario,
    documento: str,
    nivel: str,
    tipo: str,
    numero: int,
    datos: dict,
) -> Atributo:
    """Activa, configura o desactiva un atributo."""
    _validar_ranura(documento, nivel, tipo, numero)
    filas = _filas(db)
    atributo = filas.get((documento, nivel, tipo, numero))
    activo = bool(datos.get("activo"))
    etiqueta = (datos.get("etiqueta") or "").strip() or None
    if activo and (not etiqueta or len(etiqueta) < 2):
        raise ErrorERP(422, "etiqueta_requerida", "Un atributo activo necesita un nombre")
    if activo:
        repetido = next(
            (
                a
                for k, a in filas.items()
                if k[:2] == (documento, nivel)
                and k != (documento, nivel, tipo, numero)
                and a.activo
                and (a.etiqueta or "").lower() == etiqueta.lower()
            ),
            None,
        )
        if repetido:
            raise ErrorERP(
                409,
                "etiqueta_repetida",
                f"Ya hay un atributo activo llamado {etiqueta} en este nivel",
            )

    # lista de valores (solo texto)
    valores = [v.strip() for v in datos.get("valores") or [] if v and v.strip()]
    if valores and tipo != "texto":
        raise ErrorERP(
            422, "lista_solo_texto", "Solo los atributos de texto tienen lista de valores"
        )
    if len(set(v.lower() for v in valores)) != len(valores):
        raise ErrorERP(422, "valor_repetido", "La lista de valores tiene elementos repetidos")
    if len(valores) > MAX_VALORES_LISTA or any(len(v) > nucleo.LARGO_TEXTO for v in valores):
        raise ErrorERP(
            422, "lista_invalida", f"Hasta {MAX_VALORES_LISTA} valores de 240 caracteres"
        )

    nombre = etiqueta or f"{nucleo.TIPOS[tipo]} {numero}"
    defecto = _convertir(tipo, datos.get("valor_defecto"), f"{nombre} (valor por defecto)")
    if defecto is not None and valores and defecto not in valores:
        raise ErrorERP(422, "defecto_fuera_de_lista", "El valor por defecto debe estar en la lista")

    # copia al documento siguiente
    copiar_doc, copiar_num = datos.get("copiar_documento"), datos.get("copiar_numero")
    if bool(copiar_doc) != bool(copiar_num):
        raise ErrorERP(422, "copia_incompleta", "Indica el documento y el atributo de destino")
    if copiar_doc:
        if copiar_doc not in nucleo.destinos(documento):
            raise ErrorERP(
                422, "copia_invalida", f"{documento} no genera documentos de tipo {copiar_doc}"
            )
        if (
            nivel not in nucleo.DOCUMENTOS[copiar_doc].niveles
            or not 1 <= copiar_num <= nucleo.POR_TIPO
        ):
            raise ErrorERP(422, "copia_invalida", "El atributo de destino no existe")
        destino = filas.get((copiar_doc, nivel, tipo, copiar_num))
        if not destino or not destino.activo:
            raise ErrorERP(
                422,
                "destino_inactivo",
                f"Activa primero {nucleo.TIPOS[tipo].lower()} {copiar_num} de "
                f"{nucleo.DOCUMENTOS[copiar_doc].nombre.lower()} ({nucleo.NIVELES[nivel].lower()})",
            )
        ocupado = next(
            (
                a
                for k, a in filas.items()
                if a.copiar_documento == copiar_doc
                and a.copiar_numero == copiar_num
                and k[1:3] == (nivel, tipo)
                and k != (documento, nivel, tipo, numero)
            ),
            None,
        )
        if ocupado:
            raise ErrorERP(
                409,
                "destino_ocupado",
                f"Ese atributo de destino ya recibe a {ocupado.etiqueta or 'otro atributo'}",
            )

    # no desactivar un atributo que recibe copias
    if not activo and atributo and atributo.activo:
        origen = next(
            (
                a
                for k, a in filas.items()
                if a.activo
                and a.copiar_documento == documento
                and a.copiar_numero == numero
                and k[1:3] == (nivel, tipo)
            ),
            None,
        )
        if origen:
            raise ErrorERP(
                409,
                "destino_en_uso",
                f"{atributo.etiqueta} recibe la copia de {origen.etiqueta} "
                f"({nucleo.DOCUMENTOS[origen.documento].nombre.lower()}); quita esa copia primero",
            )

    antes = _resumen(atributo)
    if not atributo:
        atributo = Atributo(
            documento=documento, nivel=nivel, tipo=tipo, numero=numero, creado_por=actor.id
        )
        db.add(atributo)
    atributo.activo = activo
    atributo.etiqueta = etiqueta
    atributo.ayuda = (datos.get("ayuda") or "").strip() or None
    atributo.valor_defecto = None if defecto is None else str(defecto)
    atributo.copiar_documento = copiar_doc or None
    atributo.copiar_numero = copiar_num or None
    atributo.valores = [AtributoValor(valor=v, orden=i) for i, v in enumerate(valores)]
    atributo.actualizado_por = actor.id
    db.flush()
    despues = _resumen(atributo)
    if antes != despues:
        auditar(
            db,
            actor,
            "configurar",
            "atributo",
            atributo.id,
            {
                "atributo": nucleo.columna(tipo, numero),
                "documento": documento,
                "nivel": nivel,
                "antes": antes,
                "despues": despues,
            },
        )
    db.commit()
    return atributo


def _resumen(a: Atributo | None) -> dict | None:
    if not a:
        return None
    return {
        "activo": a.activo,
        "etiqueta": a.etiqueta,
        "valor_defecto": a.valor_defecto,
        "valores": len(a.valores),
        "copiar_a": f"{a.copiar_documento} {a.copiar_numero}" if a.copiar_documento else None,
    }


def _activos(db: Session, documento: str, nivel: str) -> dict[str, Atributo]:
    q = select(Atributo).where(
        Atributo.documento == documento, Atributo.nivel == nivel, Atributo.activo.is_(True)
    )
    return {nucleo.columna(a.tipo, a.numero): a for a in db.scalars(q)}


def validar_valores(db: Session, documento: str, nivel: str, valores: dict | None) -> dict:
    """Valida y convierte los atributos enviados; devuelve {columna: valor} listos para guardar."""
    activos = _activos(db, documento, nivel)
    resultado = {}
    for columna, valor in (valores or {}).items():
        a = activos.get(columna)
        if not a:
            if valor in (None, ""):
                continue
            raise ErrorERP(
                422, "atributo_inactivo", f"El atributo {columna} no está activo en este documento"
            )
        convertido = _convertir(a.tipo, valor, a.etiqueta)
        lista = [v.valor for v in a.valores]
        if convertido is not None and lista and convertido not in lista:
            raise ErrorERP(422, "valor_fuera_de_lista", f"{a.etiqueta}: elige un valor de la lista")
        resultado[columna] = convertido
    return resultado


def valores_por_defecto(db: Session, documento: str, nivel: str) -> dict:
    return {
        columna: _convertir(a.tipo, a.valor_defecto, a.etiqueta)
        for columna, a in _activos(db, documento, nivel).items()
        if a.valor_defecto is not None
    }


def copiar_valores(db: Session, origen: str, destino: str, nivel: str, valores: dict) -> dict:
    """Valores para el documento destino según el mapeo configurado; ignora vacíos."""
    destinos_activos = _activos(db, destino, nivel)
    copia = {}
    for columna, a in _activos(db, origen, nivel).items():
        if a.copiar_documento != destino or valores.get(columna) is None:
            continue
        col_destino = nucleo.columna(a.tipo, a.copiar_numero)
        if col_destino in destinos_activos:
            copia[col_destino] = valores[columna]
    return copia


def leer_valores(objeto, documento: str, nivel: str, db: Session) -> dict:
    """Atributos activos de un documento guardado, para devolverlos en la API."""
    return {columna: getattr(objeto, columna) for columna in _activos(db, documento, nivel)}


__all__ = [
    "copiar_valores",
    "definir",
    "leer_valores",
    "listar",
    "validar_valores",
    "valores_por_defecto",
]
