"""Reglas de negocio de maestros. Otros módulos usan solo estas funciones."""

import re
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ErrorERP, no_encontrado
from app.core.eventos import emitir
from app.localizacion import PAISES, TIPO_EXTRANJERO, pais
from app.modules.maestros import datos_base
from app.modules.maestros.models import (
    Articulo,
    BloqueoProveedor,
    Categoria,
    CondicionPago,
    ContactoProveedor,
    ConversionUnidad,
    CuentaBancariaProveedor,
    Empresa,
    Moneda,
    Proveedor,
    TipoCambio,
    UnidadArticulo,
    UnidadMedida,
    UnidadNegocio,
)
from app.modules.seguridad.models import Usuario
from app.modules.seguridad.service import auditar

CODIGO_UN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,19}$")
CODIGO_UNIDAD = re.compile(r"^[A-Z0-9]{1,10}$")
CODIGO_OFICIAL = re.compile(r"^[A-Z0-9]{2,3}$")
CODIGO_MONEDA = re.compile(r"^[A-Z]{3}$")
CODIGO_CATEGORIA = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,19}$")
NIVELES_CATEGORIA = 3


def _cambios(obj, cambios: dict, campos: tuple[str, ...]) -> dict:
    """Aplica los cambios y devuelve el detalle antes/después para la auditoría."""
    detalle = {}
    for campo in campos:
        if campo in cambios and getattr(obj, campo) != cambios[campo]:
            antes, despues = getattr(obj, campo), cambios[campo]
            detalle[campo] = {"antes": _json(antes), "despues": _json(despues)}
            setattr(obj, campo, despues)
    return detalle


def _json(valor):
    return str(valor) if isinstance(valor, Decimal | date | uuid.UUID) else valor


# ---------------------------------------------------------------- arranque


def preparar(db: Session) -> None:
    """Precarga monedas, unidades y conversiones que aún no existen."""
    monedas = set(db.scalars(select(Moneda.codigo)))
    for codigo, nombre, simbolo, decimales, activo in datos_base.MONEDAS:
        if codigo not in monedas:
            db.add(
                Moneda(
                    codigo=codigo,
                    nombre=nombre,
                    simbolo=simbolo,
                    decimales=decimales,
                    activo=activo,
                )
            )
    unidades = set(db.scalars(select(UnidadMedida.codigo)))
    for codigo, nombre, oficial, tipo in datos_base.UNIDADES:
        if codigo not in unidades:
            db.add(UnidadMedida(codigo=codigo, nombre=nombre, codigo_oficial=oficial, tipo=tipo))
    db.flush()
    conversiones = {(c.origen, c.destino) for c in db.scalars(select(ConversionUnidad))}
    for origen, destino, factor in datos_base.CONVERSIONES:
        if (origen, destino) not in conversiones:
            db.add(ConversionUnidad(origen=origen, destino=destino, factor=factor))
    condiciones = set(db.scalars(select(CondicionPago.codigo)))
    for codigo, nombre, dias in datos_base.CONDICIONES_PAGO:
        if codigo not in condiciones:
            db.add(CondicionPago(codigo=codigo, nombre=nombre, dias=dias))
    categorias = {c.codigo: c for c in db.scalars(select(Categoria))}
    for codigo, nombre, padre in datos_base.CATEGORIAS:
        if codigo not in categorias:
            p = categorias.get(padre) if padre else None
            cat = Categoria(
                id=uuid.uuid4(),
                codigo=codigo,
                nombre=nombre,
                padre_id=p.id if p else None,
                nivel=p.nivel + 1 if p else 1,
            )
            db.add(cat)
            categorias[codigo] = cat
    db.commit()


# ---------------------------------------------------------------- empresas


def listar_empresas(db: Session, solo_activas: bool = False) -> list[Empresa]:
    q = select(Empresa).order_by(Empresa.razon_social)
    if solo_activas:
        q = q.where(Empresa.activo.is_(True))
    return list(db.scalars(q))


def obtener_empresa(db: Session, empresa_id: uuid.UUID) -> Empresa:
    empresa = db.get(Empresa, empresa_id)
    if not empresa:
        raise no_encontrado("La empresa")
    return empresa


def crear_empresa(db: Session, actor: Usuario, datos: dict) -> Empresa:
    p = pais(datos["pais"])
    if not p:
        disponibles = ", ".join(x.nombre for x in PAISES.values())
        raise ErrorERP(422, "pais_no_disponible", f"País no disponible. Disponibles: {disponibles}")
    identificacion = re.sub(r"\s", "", datos["identificacion_fiscal"])
    motivo = p.validar_identificacion_fiscal(identificacion)
    if motivo:
        raise ErrorERP(422, "identificacion_fiscal_invalida", motivo)
    if db.scalar(
        select(Empresa.id).where(
            Empresa.pais == p.codigo, Empresa.identificacion_fiscal == identificacion
        )
    ):
        raise ErrorERP(
            409,
            "empresa_duplicada",
            f"Ya existe una empresa con {p.nombre_identificacion_fiscal} {identificacion}",
        )
    moneda = obtener_moneda(db, datos.get("moneda_funcional") or p.moneda)
    moneda.activo = True
    empresa = Empresa(
        pais=p.codigo,
        identificacion_fiscal=identificacion,
        razon_social=datos["razon_social"].strip(),
        nombre_comercial=(datos.get("nombre_comercial") or "").strip() or None,
        direccion_fiscal=(datos.get("direccion_fiscal") or "").strip() or None,
        moneda_funcional=moneda.codigo,
        creado_por=actor.id,
        actualizado_por=actor.id,
    )
    db.add(empresa)
    db.flush()
    # Toda empresa nace con una unidad de negocio para poder operar de inmediato.
    principal = UnidadNegocio(
        empresa_id=empresa.id,
        codigo="PRINCIPAL",
        nombre="Principal",
        creado_por=actor.id,
        actualizado_por=actor.id,
    )
    db.add(principal)
    db.flush()
    db.refresh(empresa)
    # Otros módulos preparan sus datos (ej. contabilidad carga el plan de cuentas del país).
    emitir("empresa_creada", db, actor, empresa)
    auditar(
        db,
        actor,
        "crear",
        "empresa",
        empresa.id,
        {
            "pais": p.codigo,
            p.nombre_identificacion_fiscal.lower(): identificacion,
            "razon_social": empresa.razon_social,
            "moneda_funcional": moneda.codigo,
        },
    )
    db.commit()
    db.refresh(empresa)
    return empresa


def cambiar_empresa(db: Session, actor: Usuario, empresa_id: uuid.UUID, cambios: dict) -> Empresa:
    """País, identificación fiscal y moneda funcional no cambian: afectan la contabilidad."""
    empresa = obtener_empresa(db, empresa_id)
    for campo in ("nombre_comercial", "direccion_fiscal"):
        if campo in cambios and cambios[campo] is not None:
            cambios[campo] = cambios[campo].strip() or None
    if "razon_social" in cambios and cambios["razon_social"]:
        cambios["razon_social"] = cambios["razon_social"].strip()
    detalle = _cambios(
        empresa, cambios, ("razon_social", "nombre_comercial", "direccion_fiscal", "activo")
    )
    if detalle:
        empresa.actualizado_por = actor.id
        auditar(db, actor, "editar", "empresa", empresa.id, detalle)
        db.commit()
    return empresa


# ---------------------------------------------------------------- unidades de negocio


def obtener_unidad_negocio(db: Session, unidad_id: uuid.UUID) -> UnidadNegocio:
    un = db.get(UnidadNegocio, unidad_id)
    if not un:
        raise no_encontrado("La unidad de negocio")
    return un


def crear_unidad_negocio(
    db: Session, actor: Usuario, empresa_id: uuid.UUID, codigo: str, nombre: str
) -> UnidadNegocio:
    empresa = obtener_empresa(db, empresa_id)
    codigo = codigo.strip().upper()
    if not CODIGO_UN.match(codigo):
        raise ErrorERP(
            422,
            "codigo_invalido",
            "El código usa mayúsculas, números, guion o guion bajo (hasta 20 caracteres)",
        )
    if any(u.codigo == codigo for u in empresa.unidades):
        raise ErrorERP(
            409, "unidad_negocio_duplicada", f"La empresa ya tiene la unidad de negocio {codigo}"
        )
    un = UnidadNegocio(
        empresa_id=empresa.id,
        codigo=codigo,
        nombre=nombre.strip(),
        creado_por=actor.id,
        actualizado_por=actor.id,
    )
    db.add(un)
    db.flush()
    auditar(
        db,
        actor,
        "crear",
        "unidad_negocio",
        un.id,
        {"empresa": empresa.razon_social, "codigo": codigo, "nombre": un.nombre},
    )
    db.commit()
    db.refresh(empresa)
    return un


def cambiar_unidad_negocio(
    db: Session, actor: Usuario, unidad_id: uuid.UUID, cambios: dict
) -> UnidadNegocio:
    un = obtener_unidad_negocio(db, unidad_id)
    if cambios.get("activo") is False and un.activo:
        otras = [u for u in un.empresa.unidades if u.activo and u.id != un.id]
        if not otras:
            raise ErrorERP(
                409,
                "ultima_unidad_negocio",
                "La empresa debe tener al menos una unidad de negocio activa",
            )
    if cambios.get("nombre"):
        cambios["nombre"] = cambios["nombre"].strip()
    detalle = _cambios(un, cambios, ("nombre", "activo"))
    if detalle:
        un.actualizado_por = actor.id
        auditar(db, actor, "editar", "unidad_negocio", un.id, detalle)
        db.commit()
    return un


# ---------------------------------------------------------------- monedas


def listar_monedas(db: Session) -> list[Moneda]:
    return list(db.scalars(select(Moneda).order_by(Moneda.activo.desc(), Moneda.codigo)))


def obtener_moneda(db: Session, codigo: str) -> Moneda:
    moneda = db.scalar(select(Moneda).where(Moneda.codigo == codigo.upper()))
    if not moneda:
        raise no_encontrado(f"La moneda {codigo.upper()}")
    return moneda


def crear_moneda(db: Session, actor: Usuario, datos: dict) -> Moneda:
    codigo = datos["codigo"].strip().upper()
    if not CODIGO_MONEDA.match(codigo):
        raise ErrorERP(
            422, "codigo_invalido", "El código de moneda es ISO 4217: 3 letras (ej. USD)"
        )
    if db.scalar(select(Moneda.id).where(Moneda.codigo == codigo)):
        raise ErrorERP(409, "moneda_duplicada", f"La moneda {codigo} ya existe")
    moneda = Moneda(
        codigo=codigo,
        nombre=datos["nombre"].strip(),
        simbolo=datos["simbolo"].strip(),
        decimales=datos["decimales"],
        activo=True,
        creado_por=actor.id,
        actualizado_por=actor.id,
    )
    db.add(moneda)
    db.flush()
    auditar(db, actor, "crear", "moneda", codigo, {"nombre": moneda.nombre})
    db.commit()
    return moneda


def cambiar_moneda(db: Session, actor: Usuario, codigo: str, cambios: dict) -> Moneda:
    moneda = obtener_moneda(db, codigo)
    if cambios.get("activo") is False and moneda.activo:
        usada = db.scalar(
            select(Empresa.razon_social).where(
                Empresa.moneda_funcional == moneda.codigo, Empresa.activo.is_(True)
            )
        )
        if usada:
            raise ErrorERP(
                409,
                "moneda_en_uso",
                f"{moneda.codigo} es la moneda funcional de {usada}; no se puede desactivar",
            )
    detalle = _cambios(moneda, cambios, ("nombre", "simbolo", "decimales", "activo"))
    if detalle:
        moneda.actualizado_por = actor.id
        auditar(db, actor, "editar", "moneda", moneda.codigo, detalle)
        db.commit()
    return moneda


# ---------------------------------------------------------------- tipo de cambio


def registrar_tipo_cambio(db: Session, actor: Usuario, datos: dict) -> TipoCambio:
    """Crea o corrige el tipo de cambio de una fecha (uno por moneda, base y fecha)."""
    moneda = obtener_moneda(db, datos["moneda"])
    base = obtener_moneda(db, datos.get("moneda_base") or "PEN")
    if moneda.codigo == base.codigo:
        raise ErrorERP(422, "misma_moneda", "La moneda y la moneda base deben ser distintas")
    if not moneda.activo or not base.activo:
        raise ErrorERP(422, "moneda_inactiva", "Activa la moneda antes de registrar su cambio")
    fecha, compra, venta = datos["fecha"], datos["compra"], datos["venta"]
    if fecha > date.today():
        raise ErrorERP(422, "fecha_futura", "No se registra tipo de cambio de fechas futuras")
    if venta < compra:
        raise ErrorERP(
            422, "venta_menor_compra", "El precio de venta no puede ser menor al de compra"
        )
    tc = db.scalar(
        select(TipoCambio).where(
            TipoCambio.moneda == moneda.codigo,
            TipoCambio.moneda_base == base.codigo,
            TipoCambio.fecha == fecha,
        )
    )
    accion = "editar" if tc else "crear"
    detalle = {"moneda": f"{moneda.codigo}/{base.codigo}", "fecha": fecha.isoformat()}
    if tc:
        detalle |= _cambios(tc, {"compra": compra, "venta": venta}, ("compra", "venta"))
        tc.fuente = datos.get("fuente", "manual")
        tc.actualizado_por = actor.id
    else:
        tc = TipoCambio(
            moneda=moneda.codigo,
            moneda_base=base.codigo,
            fecha=fecha,
            compra=compra,
            venta=venta,
            fuente=datos.get("fuente", "manual"),
            creado_por=actor.id,
            actualizado_por=actor.id,
        )
        db.add(tc)
        db.flush()
        detalle |= {"compra": str(compra), "venta": str(venta)}
    auditar(db, actor, accion, "tipo_cambio", tc.id, detalle)
    db.commit()
    return tc


def listar_tipos_cambio(
    db: Session,
    moneda: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    limite: int = 60,
) -> list[TipoCambio]:
    q = select(TipoCambio).order_by(TipoCambio.fecha.desc(), TipoCambio.moneda)
    if moneda:
        q = q.where(TipoCambio.moneda == moneda.upper())
    if desde:
        q = q.where(TipoCambio.fecha >= desde)
    if hasta:
        q = q.where(TipoCambio.fecha <= hasta)
    return list(db.scalars(q.limit(min(limite, 400))))


def tipo_cambio_vigente(db: Session, moneda: str, fecha: date, base: str = "PEN") -> TipoCambio:
    """El último tipo de cambio registrado en la fecha o antes (fines de semana y feriados)."""
    tc = db.scalar(
        select(TipoCambio)
        .where(
            TipoCambio.moneda == moneda.upper(),
            TipoCambio.moneda_base == base.upper(),
            TipoCambio.fecha <= fecha,
        )
        .order_by(TipoCambio.fecha.desc())
        .limit(1)
    )
    if not tc:
        raise ErrorERP(
            404,
            "sin_tipo_cambio",
            f"No hay tipo de cambio {moneda.upper()}/{base.upper()} al {fecha.isoformat()}",
        )
    return tc


# ---------------------------------------------------------------- unidades de medida


def listar_unidades(db: Session) -> list[UnidadMedida]:
    return list(db.scalars(select(UnidadMedida).order_by(UnidadMedida.tipo, UnidadMedida.codigo)))


def obtener_unidad(db: Session, codigo: str) -> UnidadMedida:
    unidad = db.scalar(select(UnidadMedida).where(UnidadMedida.codigo == codigo.upper()))
    if not unidad:
        raise no_encontrado(f"La unidad {codigo.upper()}")
    return unidad


def _validar_unidad(datos: dict) -> None:
    if "codigo_oficial" in datos and not CODIGO_OFICIAL.match(datos["codigo_oficial"]):
        raise ErrorERP(
            422, "codigo_oficial_invalido", "El código oficial tiene 2 o 3 caracteres (ej. NIU)"
        )
    if "tipo" in datos and datos["tipo"] not in datos_base.TIPOS_UNIDAD:
        raise ErrorERP(
            422, "tipo_invalido", f"Tipo no válido. Usa: {', '.join(datos_base.TIPOS_UNIDAD)}"
        )


def crear_unidad(db: Session, actor: Usuario, datos: dict) -> UnidadMedida:
    datos = {**datos, "codigo": datos["codigo"].strip().upper()}
    datos["codigo_oficial"] = datos["codigo_oficial"].strip().upper()
    if not CODIGO_UNIDAD.match(datos["codigo"]):
        raise ErrorERP(422, "codigo_invalido", "El código usa mayúsculas y números (hasta 10)")
    _validar_unidad(datos)
    if db.scalar(select(UnidadMedida.id).where(UnidadMedida.codigo == datos["codigo"])):
        raise ErrorERP(409, "unidad_duplicada", f"La unidad {datos['codigo']} ya existe")
    unidad = UnidadMedida(
        codigo=datos["codigo"],
        nombre=datos["nombre"].strip(),
        codigo_oficial=datos["codigo_oficial"],
        tipo=datos["tipo"],
        creado_por=actor.id,
        actualizado_por=actor.id,
    )
    db.add(unidad)
    db.flush()
    auditar(
        db,
        actor,
        "crear",
        "unidad_medida",
        unidad.codigo,
        {"nombre": unidad.nombre, "codigo_oficial": unidad.codigo_oficial, "tipo": unidad.tipo},
    )
    db.commit()
    return unidad


def cambiar_unidad(db: Session, actor: Usuario, codigo: str, cambios: dict) -> UnidadMedida:
    unidad = obtener_unidad(db, codigo)
    if cambios.get("codigo_oficial"):
        cambios["codigo_oficial"] = cambios["codigo_oficial"].strip().upper()
    _validar_unidad({k: v for k, v in cambios.items() if v is not None})
    detalle = _cambios(unidad, cambios, ("nombre", "codigo_oficial", "tipo", "activo"))
    if detalle:
        unidad.actualizado_por = actor.id
        auditar(db, actor, "editar", "unidad_medida", unidad.codigo, detalle)
        db.commit()
    return unidad


def listar_conversiones(db: Session) -> list[ConversionUnidad]:
    return list(
        db.scalars(
            select(ConversionUnidad).order_by(ConversionUnidad.origen, ConversionUnidad.destino)
        )
    )


def crear_conversion(
    db: Session, actor: Usuario, origen: str, destino: str, factor: Decimal
) -> ConversionUnidad:
    uo, ud = obtener_unidad(db, origen), obtener_unidad(db, destino)
    if uo.codigo == ud.codigo:
        raise ErrorERP(422, "misma_unidad", "La unidad de origen y destino deben ser distintas")
    if uo.tipo != ud.tipo:
        raise ErrorERP(
            422,
            "tipos_distintos",
            f"No se convierte {uo.tipo} en {ud.tipo} ({uo.codigo} → {ud.codigo})",
        )
    if factor <= 0:
        raise ErrorERP(422, "factor_invalido", "El factor debe ser mayor que cero")
    existe = db.scalar(
        select(ConversionUnidad).where(
            ((ConversionUnidad.origen == uo.codigo) & (ConversionUnidad.destino == ud.codigo))
            | ((ConversionUnidad.origen == ud.codigo) & (ConversionUnidad.destino == uo.codigo))
        )
    )
    if existe:
        raise ErrorERP(
            409,
            "conversion_duplicada",
            f"Ya existe la conversión {existe.origen} → {existe.destino}",
        )
    conv = ConversionUnidad(
        origen=uo.codigo,
        destino=ud.codigo,
        factor=factor,
        creado_por=actor.id,
        actualizado_por=actor.id,
    )
    db.add(conv)
    db.flush()
    auditar(
        db,
        actor,
        "crear",
        "conversion_unidad",
        conv.id,
        {"conversion": f"1 {uo.codigo} = {factor} {ud.codigo}"},
    )
    db.commit()
    return conv


def eliminar_conversion(db: Session, actor: Usuario, conversion_id: uuid.UUID) -> None:
    conv = db.get(ConversionUnidad, conversion_id)
    if not conv:
        raise no_encontrado("La conversión")
    auditar(
        db,
        actor,
        "eliminar",
        "conversion_unidad",
        conv.id,
        {"conversion": f"1 {conv.origen} = {conv.factor} {conv.destino}"},
    )
    db.delete(conv)
    db.commit()


def convertir(db: Session, cantidad: Decimal, origen: str, destino: str) -> Decimal:
    """Convierte una cantidad usando la conversión directa o su inversa."""
    origen, destino = origen.upper(), destino.upper()
    if origen == destino:
        return cantidad
    for conv in db.scalars(
        select(ConversionUnidad).where(
            ConversionUnidad.origen.in_([origen, destino]),
            ConversionUnidad.destino.in_([origen, destino]),
        )
    ):
        if conv.origen == origen:
            return cantidad * conv.factor
        return cantidad / conv.factor
    raise ErrorERP(422, "sin_conversion", f"No hay conversión entre {origen} y {destino}")


# ---------------------------------------------------------------- categorías de artículo


def listar_categorias(db: Session) -> list[Categoria]:
    """Ordenadas como árbol: cada categoría seguida de sus subcategorías."""
    todas = list(db.scalars(select(Categoria).order_by(Categoria.codigo)))
    hijas: dict[uuid.UUID | None, list[Categoria]] = {}
    for c in todas:
        hijas.setdefault(c.padre_id, []).append(c)
    orden: list[Categoria] = []

    def recorrer(padre_id: uuid.UUID | None) -> None:
        for c in hijas.get(padre_id, []):
            orden.append(c)
            recorrer(c.id)

    recorrer(None)
    return orden


def obtener_categoria(db: Session, categoria_id: uuid.UUID) -> Categoria:
    cat = db.get(Categoria, categoria_id)
    if not cat:
        raise no_encontrado("La categoría")
    return cat


def ancestros_categoria(db: Session, categoria: Categoria) -> list[Categoria]:
    """La categoría y sus padres, de la más específica a la raíz."""
    cadena = [categoria]
    while cadena[-1].padre_id:
        cadena.append(db.get(Categoria, cadena[-1].padre_id))
    return cadena


def _descendientes(db: Session, categoria: Categoria) -> list[Categoria]:
    todas = list(db.scalars(select(Categoria)))
    resultado, pendientes = [], [categoria.id]
    while pendientes:
        actual = pendientes.pop()
        for c in todas:
            if c.padre_id == actual:
                resultado.append(c)
                pendientes.append(c.id)
    return resultado


def _altura(db: Session, categoria: Categoria) -> int:
    """Niveles que ocupa la rama: 1 si no tiene subcategorías."""
    desc = _descendientes(db, categoria)
    return 1 + (max(c.nivel for c in desc) - categoria.nivel if desc else 0)


def crear_categoria(
    db: Session, actor: Usuario, codigo: str, nombre: str, padre_id: uuid.UUID | None
) -> Categoria:
    codigo = codigo.strip().upper()
    if not CODIGO_CATEGORIA.match(codigo):
        raise ErrorERP(
            422,
            "codigo_invalido",
            "El código usa mayúsculas, números, guion o guion bajo (hasta 20 caracteres)",
        )
    if db.scalar(select(Categoria.id).where(Categoria.codigo == codigo)):
        raise ErrorERP(409, "categoria_duplicada", f"Ya existe la categoría {codigo}")
    padre = obtener_categoria(db, padre_id) if padre_id else None
    if padre and not padre.activo:
        raise ErrorERP(422, "padre_inactivo", f"La categoría {padre.codigo} está inactiva")
    nivel = padre.nivel + 1 if padre else 1
    if nivel > NIVELES_CATEGORIA:
        raise ErrorERP(
            422, "nivel_maximo", f"Las categorías tienen como máximo {NIVELES_CATEGORIA} niveles"
        )
    cat = Categoria(
        codigo=codigo,
        nombre=nombre.strip(),
        padre_id=padre.id if padre else None,
        nivel=nivel,
        creado_por=actor.id,
        actualizado_por=actor.id,
    )
    db.add(cat)
    db.flush()
    auditar(
        db,
        actor,
        "crear",
        "categoria",
        cat.id,
        {"codigo": codigo, "nombre": cat.nombre, "padre": padre.codigo if padre else None},
    )
    db.commit()
    return cat


def cambiar_categoria(
    db: Session, actor: Usuario, categoria_id: uuid.UUID, cambios: dict
) -> Categoria:
    """Nombre, padre (mover la rama) y estado. El código no cambia."""
    cat = obtener_categoria(db, categoria_id)
    detalle: dict = {}
    if "padre_id" in cambios and cambios["padre_id"] != cat.padre_id:
        nuevo = obtener_categoria(db, cambios["padre_id"]) if cambios["padre_id"] else None
        if nuevo and (nuevo.id == cat.id or nuevo in _descendientes(db, cat)):
            raise ErrorERP(
                422,
                "ciclo",
                "Una categoría no puede quedar dentro de sí misma o de sus subcategorías",
            )
        if nuevo and not nuevo.activo:
            raise ErrorERP(422, "padre_inactivo", f"La categoría {nuevo.codigo} está inactiva")
        nivel = nuevo.nivel + 1 if nuevo else 1
        if nivel - 1 + _altura(db, cat) > NIVELES_CATEGORIA:
            raise ErrorERP(
                422,
                "nivel_maximo",
                f"Al moverla, la rama superaría los {NIVELES_CATEGORIA} niveles",
            )
        anterior = db.get(Categoria, cat.padre_id) if cat.padre_id else None
        delta = nivel - cat.nivel
        for d in _descendientes(db, cat):
            d.nivel += delta
        cat.padre_id, cat.nivel = (nuevo.id if nuevo else None), nivel
        detalle["padre"] = {
            "antes": anterior.codigo if anterior else None,
            "despues": nuevo.codigo if nuevo else None,
        }
    if cambios.get("activo") is False and cat.activo:
        activas = [d.codigo for d in _descendientes(db, cat) if d.activo]
        if activas:
            raise ErrorERP(
                409,
                "tiene_subcategorias_activas",
                f"Desactiva primero sus subcategorías: {', '.join(activas)}",
            )
    if cambios.get("activo") is True and not cat.activo and cat.padre_id:
        padre = db.get(Categoria, cat.padre_id)
        if not padre.activo:
            raise ErrorERP(422, "padre_inactivo", f"Activa primero la categoría {padre.codigo}")
    if cambios.get("nombre"):
        cambios["nombre"] = cambios["nombre"].strip()
    detalle |= _cambios(cat, cambios, ("nombre", "activo"))
    if detalle:
        cat.actualizado_por = actor.id
        auditar(db, actor, "editar", "categoria", cat.id, {"codigo": cat.codigo, **detalle})
        db.commit()
    return cat


# ---------------------------------------------------------------- condiciones de pago

CODIGO_CONDICION = re.compile(r"^[A-Z0-9_-]{1,20}$")


def listar_condiciones(db: Session) -> list[CondicionPago]:
    return list(
        db.scalars(select(CondicionPago).order_by(CondicionPago.dias, CondicionPago.codigo))
    )


def obtener_condicion(db: Session, condicion_id: uuid.UUID) -> CondicionPago:
    c = db.get(CondicionPago, condicion_id)
    if not c:
        raise no_encontrado("La condición de pago")
    return c


def crear_condicion(
    db: Session, actor: Usuario, codigo: str, nombre: str, dias: int
) -> CondicionPago:
    codigo = codigo.strip().upper()
    if not CODIGO_CONDICION.match(codigo):
        raise ErrorERP(422, "codigo_invalido", "El código usa mayúsculas, números, - o _")
    if db.scalar(select(CondicionPago.id).where(CondicionPago.codigo == codigo)):
        raise ErrorERP(409, "condicion_duplicada", f"Ya existe la condición de pago {codigo}")
    c = CondicionPago(
        codigo=codigo,
        nombre=nombre.strip(),
        dias=dias,
        creado_por=actor.id,
        actualizado_por=actor.id,
    )
    db.add(c)
    db.flush()
    auditar(db, actor, "crear", "condicion_pago", c.id, {"codigo": codigo, "dias": dias})
    db.commit()
    return c


def cambiar_condicion(
    db: Session, actor: Usuario, condicion_id: uuid.UUID, cambios: dict
) -> CondicionPago:
    c = obtener_condicion(db, condicion_id)
    if cambios.get("activo") is False and c.activo:
        en_uso = db.scalar(
            select(func.count())
            .select_from(Proveedor)
            .where(Proveedor.condicion_pago_id == c.id, Proveedor.activo.is_(True))
        )
        if en_uso:
            raise ErrorERP(
                409,
                "condicion_en_uso",
                f"{en_uso} proveedor(es) activo(s) usan {c.nombre}; cámbiales la condición primero",
            )
    if cambios.get("nombre"):
        cambios["nombre"] = cambios["nombre"].strip()
    detalle = _cambios(c, cambios, ("nombre", "dias", "activo"))
    if detalle:
        c.actualizado_por = actor.id
        auditar(db, actor, "editar", "condicion_pago", c.id, {"codigo": c.codigo, **detalle})
        db.commit()
    return c


# ---------------------------------------------------------------- proveedores

DOCUMENTO_EXTRANJERO = re.compile(r"^[A-Z0-9][A-Z0-9.-]{2,19}$")
CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SWIFT = re.compile(r"^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$")
PAIS_LOCAL = "pe"  # país donde opera hoy Victoria ERP (los demás proveedores son del exterior)


def tipos_documento() -> list[dict]:
    p = pais(PAIS_LOCAL)
    locales = [
        {"codigo": c, "nombre": n, "codigo_oficial": o, "extranjero": False}
        for c, n, o, _ in p.tipos_documento
    ]
    codigo, nombre, oficial = TIPO_EXTRANJERO
    return locales + [
        {"codigo": codigo, "nombre": nombre, "codigo_oficial": oficial, "extranjero": True}
    ]


def _validar_documento(tipo: str, numero: str, pais_proveedor: str) -> tuple[str, str]:
    """Devuelve (número normalizado, país). Valida según el tipo de documento."""
    numero = re.sub(r"\s", "", numero).upper()
    if tipo == TIPO_EXTRANJERO[0]:
        pais_proveedor = (pais_proveedor or "").lower()
        if not re.fullmatch(r"[a-z]{2}", pais_proveedor) or pais_proveedor == PAIS_LOCAL:
            raise ErrorERP(
                422,
                "pais_invalido",
                "Un proveedor del exterior necesita su país (código de 2 letras distinto de PE)",
            )
        if not DOCUMENTO_EXTRANJERO.match(numero):
            raise ErrorERP(
                422,
                "documento_invalido",
                "La identificación tributaria del exterior tiene de 3 a 20 letras, números, . o -",
            )
        return numero, pais_proveedor
    local = {c: v for c, _, _, v in pais(PAIS_LOCAL).tipos_documento}
    if tipo not in local:
        raise ErrorERP(
            422,
            "tipo_documento_invalido",
            f"Tipo de documento no válido: {', '.join([*local, 'EXT'])}",
        )
    motivo = local[tipo](numero)
    if motivo:
        raise ErrorERP(422, "documento_invalido", motivo)
    return numero, PAIS_LOCAL


def _validar_correo(correo: str | None) -> str | None:
    correo = (correo or "").strip().lower() or None
    if correo and not CORREO.match(correo):
        raise ErrorERP(422, "correo_invalido", f"El correo {correo} no es válido")
    return correo


def _texto(valor: str | None) -> str | None:
    return (valor or "").strip() or None


def buscar_proveedores(
    db: Session, texto: str | None = None, solo_activos: bool = False, limite: int = 200
) -> list[Proveedor]:
    q = select(Proveedor).order_by(Proveedor.razon_social)
    if texto:
        patron = f"%{texto.strip()}%"
        q = q.where(
            Proveedor.razon_social.ilike(patron)
            | Proveedor.nombre_comercial.ilike(patron)
            | Proveedor.numero_documento.ilike(patron)
        )
    if solo_activos:
        q = q.where(Proveedor.activo.is_(True))
    return list(db.scalars(q.limit(min(limite, 500))))


def obtener_proveedor(db: Session, proveedor_id: uuid.UUID) -> Proveedor:
    p = db.get(Proveedor, proveedor_id)
    if not p:
        raise no_encontrado("El proveedor")
    return p


def crear_proveedor(db: Session, actor: Usuario, datos: dict) -> Proveedor:
    tipo = datos["tipo_documento"].upper()
    numero, pais_proveedor = _validar_documento(tipo, datos["numero_documento"], datos.get("pais"))
    existente = db.scalar(
        select(Proveedor).where(
            Proveedor.pais == pais_proveedor,
            Proveedor.tipo_documento == tipo,
            Proveedor.numero_documento == numero,
        )
    )
    if existente:
        raise ErrorERP(
            409,
            "proveedor_duplicado",
            f"El proveedor {tipo} {numero} ya existe: {existente.razon_social}",
        )
    extranjero = tipo == TIPO_EXTRANJERO[0]
    moneda = obtener_moneda(db, datos.get("moneda") or ("USD" if extranjero else "PEN"))
    if not moneda.activo:
        raise ErrorERP(422, "moneda_inactiva", f"La moneda {moneda.codigo} está inactiva")
    condicion = (
        obtener_condicion(db, datos["condicion_pago_id"])
        if datos.get("condicion_pago_id")
        else db.scalar(select(CondicionPago).where(CondicionPago.codigo == "CONTADO"))
    )
    if not condicion or not condicion.activo:
        raise ErrorERP(422, "condicion_inactiva", "Elige una condición de pago activa")
    prov = Proveedor(
        tipo_documento=tipo,
        numero_documento=numero,
        pais=pais_proveedor,
        razon_social=datos["razon_social"].strip(),
        nombre_comercial=_texto(datos.get("nombre_comercial")),
        direccion=_texto(datos.get("direccion")),
        correo=_validar_correo(datos.get("correo")),
        telefono=_texto(datos.get("telefono")),
        moneda=moneda.codigo,
        condicion_pago_id=condicion.id,
        creado_por=actor.id,
        actualizado_por=actor.id,
    )
    db.add(prov)
    db.flush()
    auditar(
        db,
        actor,
        "crear",
        "proveedor",
        prov.id,
        {
            "documento": f"{tipo} {numero}",
            "pais": pais_proveedor,
            "razon_social": prov.razon_social,
        },
    )
    db.commit()
    db.refresh(prov)
    return prov


def cambiar_proveedor(
    db: Session, actor: Usuario, proveedor_id: uuid.UUID, cambios: dict
) -> Proveedor:
    """El documento y el país no cambian: identifican al proveedor ante el fisco."""
    prov = obtener_proveedor(db, proveedor_id)
    if "correo" in cambios:
        cambios["correo"] = _validar_correo(cambios["correo"])
    for campo in ("nombre_comercial", "direccion", "telefono"):
        if campo in cambios:
            cambios[campo] = _texto(cambios[campo])
    if cambios.get("razon_social"):
        cambios["razon_social"] = cambios["razon_social"].strip()
    if "moneda" in cambios:
        moneda = obtener_moneda(db, cambios["moneda"])
        if not moneda.activo:
            raise ErrorERP(422, "moneda_inactiva", f"La moneda {moneda.codigo} está inactiva")
        cambios["moneda"] = moneda.codigo
    if (
        "condicion_pago_id" in cambios
        and not obtener_condicion(db, cambios["condicion_pago_id"]).activo
    ):
        raise ErrorERP(422, "condicion_inactiva", "Elige una condición de pago activa")
    campos = (
        "razon_social",
        "nombre_comercial",
        "direccion",
        "correo",
        "telefono",
        "moneda",
        "condicion_pago_id",
        "activo",
    )
    detalle = _cambios(prov, cambios, campos)
    if detalle:
        prov.actualizado_por = actor.id
        auditar(
            db,
            actor,
            "editar",
            "proveedor",
            prov.id,
            {"documento": prov.numero_documento, **detalle},
        )
        db.commit()
        db.refresh(prov)
    return prov


# contactos


def _quitar_principal(prov: Proveedor, excepto: ContactoProveedor | None = None) -> None:
    for c in prov.contactos:
        if c is not excepto:
            c.principal = False


def crear_contacto(
    db: Session, actor: Usuario, proveedor_id: uuid.UUID, datos: dict
) -> ContactoProveedor:
    prov = obtener_proveedor(db, proveedor_id)
    contacto = ContactoProveedor(
        proveedor_id=prov.id,
        nombre=datos["nombre"].strip(),
        cargo=_texto(datos.get("cargo")),
        correo=_validar_correo(datos.get("correo")),
        telefono=_texto(datos.get("telefono")),
        # El primer contacto es el principal: recibe las órdenes de compra.
        principal=bool(datos.get("principal")) or not prov.contactos,
        creado_por=actor.id,
        actualizado_por=actor.id,
    )
    if contacto.principal:
        _quitar_principal(prov)
    prov.contactos.append(contacto)
    db.flush()
    auditar(
        db,
        actor,
        "crear",
        "proveedor_contacto",
        contacto.id,
        {
            "proveedor": prov.razon_social,
            "nombre": contacto.nombre,
            "principal": contacto.principal,
        },
    )
    db.commit()
    return contacto


def _obtener_contacto(db: Session, contacto_id: uuid.UUID) -> ContactoProveedor:
    c = db.get(ContactoProveedor, contacto_id)
    if not c:
        raise no_encontrado("El contacto")
    return c


def cambiar_contacto(
    db: Session, actor: Usuario, contacto_id: uuid.UUID, cambios: dict
) -> ContactoProveedor:
    contacto = _obtener_contacto(db, contacto_id)
    prov = obtener_proveedor(db, contacto.proveedor_id)
    if "correo" in cambios:
        cambios["correo"] = _validar_correo(cambios["correo"])
    for campo in ("cargo", "telefono"):
        if campo in cambios:
            cambios[campo] = _texto(cambios[campo])
    if cambios.get("nombre"):
        cambios["nombre"] = cambios["nombre"].strip()
    if cambios.get("principal") is False and contacto.principal:
        raise ErrorERP(
            422, "principal_requerido", "Marca otro contacto como principal en lugar de quitarlo"
        )
    if cambios.get("principal") is True:
        _quitar_principal(prov, excepto=contacto)
    detalle = _cambios(contacto, cambios, ("nombre", "cargo", "correo", "telefono", "principal"))
    if detalle:
        contacto.actualizado_por = actor.id
        auditar(
            db,
            actor,
            "editar",
            "proveedor_contacto",
            contacto.id,
            {"proveedor": prov.razon_social, **detalle},
        )
        db.commit()
    return contacto


def eliminar_contacto(db: Session, actor: Usuario, contacto_id: uuid.UUID) -> None:
    contacto = _obtener_contacto(db, contacto_id)
    prov = obtener_proveedor(db, contacto.proveedor_id)
    prov.contactos.remove(contacto)
    if contacto.principal and prov.contactos:
        prov.contactos[0].principal = True
    auditar(
        db,
        actor,
        "eliminar",
        "proveedor_contacto",
        contacto.id,
        {"proveedor": prov.razon_social, "nombre": contacto.nombre},
    )
    db.commit()


# cuentas bancarias (permiso especial: un cambio de cuenta es una vía común de fraude)


def crear_cuenta_bancaria(
    db: Session, actor: Usuario, proveedor_id: uuid.UUID, datos: dict
) -> CuentaBancariaProveedor:
    prov = obtener_proveedor(db, proveedor_id)
    if datos["tipo"] not in datos_base.TIPOS_CUENTA_BANCARIA:
        raise ErrorERP(
            422,
            "tipo_invalido",
            f"Tipo de cuenta no válido: {', '.join(datos_base.TIPOS_CUENTA_BANCARIA)}",
        )
    moneda = obtener_moneda(db, datos["moneda"])
    numero = re.sub(r"[\s-]", "", datos["numero"]).upper()
    if not re.fullmatch(r"[A-Z0-9]{5,34}", numero):
        raise ErrorERP(
            422, "numero_invalido", "El número de cuenta tiene de 5 a 34 letras o dígitos"
        )
    cci = re.sub(r"[\s-]", "", datos.get("cci") or "") or None
    swift = re.sub(r"\s", "", datos.get("swift") or "").upper() or None
    local = pais(PAIS_LOCAL)
    if prov.pais == PAIS_LOCAL:
        if not cci:
            raise ErrorERP(422, "cci_requerido", "Las cuentas en Perú necesitan el CCI")
        motivo = local.validar_cuenta_interbancaria(cci)
        if motivo:
            raise ErrorERP(422, "cci_invalido", motivo)
    elif not swift:
        raise ErrorERP(
            422, "swift_requerido", "Las cuentas del exterior necesitan el código SWIFT/BIC"
        )
    if swift and not SWIFT.match(swift):
        raise ErrorERP(422, "swift_invalido", "El SWIFT/BIC tiene 8 u 11 caracteres (ej. BCPLPEPL)")
    if any(c.numero == numero and c.activo for c in prov.cuentas):
        raise ErrorERP(409, "cuenta_duplicada", "Esa cuenta ya está registrada")
    cuenta = CuentaBancariaProveedor(
        proveedor_id=prov.id,
        banco=datos["banco"].strip(),
        tipo=datos["tipo"],
        moneda=moneda.codigo,
        numero=numero,
        cci=cci,
        swift=swift,
        creado_por=actor.id,
        actualizado_por=actor.id,
    )
    prov.cuentas.append(cuenta)
    db.flush()
    auditar(
        db,
        actor,
        "crear",
        "proveedor_cuenta",
        cuenta.id,
        {
            "proveedor": prov.razon_social,
            "banco": cuenta.banco,
            "moneda": cuenta.moneda,
            "cuenta": enmascarar(numero),
        },
    )
    db.commit()
    return cuenta


def cambiar_cuenta_bancaria(
    db: Session, actor: Usuario, cuenta_id: uuid.UUID, activo: bool
) -> CuentaBancariaProveedor:
    """Las cuentas no se editan: se desactiva la anterior y se registra la nueva."""
    cuenta = db.get(CuentaBancariaProveedor, cuenta_id)
    if not cuenta:
        raise no_encontrado("La cuenta bancaria")
    if cuenta.activo != activo:
        cuenta.activo, cuenta.actualizado_por = activo, actor.id
        prov = obtener_proveedor(db, cuenta.proveedor_id)
        auditar(
            db,
            actor,
            "activar" if activo else "desactivar",
            "proveedor_cuenta",
            cuenta.id,
            {"proveedor": prov.razon_social, "cuenta": enmascarar(cuenta.numero)},
        )
        db.commit()
    return cuenta


def enmascarar(valor: str | None) -> str | None:
    return f"•••• {valor[-4:]}" if valor else None


# categorías que provee y bloqueo por empresa


def asignar_categorias(
    db: Session, actor: Usuario, proveedor_id: uuid.UUID, categoria_ids: list[uuid.UUID]
) -> Proveedor:
    prov = obtener_proveedor(db, proveedor_id)
    nuevas = [obtener_categoria(db, c) for c in dict.fromkeys(categoria_ids)]
    antes = sorted(c.codigo for c in prov.categorias)
    despues = sorted(c.codigo for c in nuevas)
    if antes != despues:
        prov.categorias = nuevas
        prov.actualizado_por = actor.id
        auditar(
            db,
            actor,
            "editar",
            "proveedor",
            prov.id,
            {"categorias": {"antes": antes, "despues": despues}},
        )
        db.commit()
        db.refresh(prov)
    return prov


def bloquear_proveedor(
    db: Session,
    actor: Usuario,
    proveedor_id: uuid.UUID,
    empresa_id: uuid.UUID,
    bloqueado: bool,
    motivo: str | None,
) -> Proveedor:
    prov = obtener_proveedor(db, proveedor_id)
    empresa = obtener_empresa(db, empresa_id)
    actual = next((b for b in prov.bloqueos if b.empresa_id == empresa.id), None)
    if bloqueado and not actual:
        motivo = _texto(motivo)
        if not motivo:
            raise ErrorERP(422, "motivo_requerido", "Indica el motivo del bloqueo")
        prov.bloqueos.append(
            BloqueoProveedor(
                proveedor_id=prov.id,
                empresa_id=empresa.id,
                motivo=motivo,
                creado_por=actor.id,
                actualizado_por=actor.id,
            )
        )
    elif not bloqueado and actual:
        prov.bloqueos.remove(actual)
    else:
        return prov
    auditar(
        db,
        actor,
        "bloquear" if bloqueado else "desbloquear",
        "proveedor",
        prov.id,
        {"empresa": empresa.razon_social, "motivo": motivo if bloqueado else actual.motivo},
    )
    db.commit()
    db.refresh(prov)
    return prov


def proveedor_habilitado(db: Session, proveedor_id: uuid.UUID, empresa_id: uuid.UUID) -> str | None:
    """None si la empresa puede comprarle; si no, el motivo. Lo usarán las órdenes de compra."""
    prov = obtener_proveedor(db, proveedor_id)
    if not prov.activo:
        return "El proveedor está inactivo"
    bloqueo = next((b for b in prov.bloqueos if b.empresa_id == empresa_id), None)
    return f"Proveedor bloqueado para esta empresa: {bloqueo.motivo}" if bloqueo else None


# ---------------------------------------------------------------- artículos

CODIGO_ARTICULO = re.compile(r"^[A-Z0-9][A-Z0-9_.-]{0,29}$")


def siguiente_codigo(db: Session, categoria_id: uuid.UUID) -> str:
    """Siguiente correlativo de la categoría: SUM-OFI-0001, SUM-OFI-0002…"""
    cat = obtener_categoria(db, categoria_id)
    prefijo = f"{cat.codigo}-"
    usados = db.scalars(select(Articulo.codigo).where(Articulo.codigo.startswith(prefijo)))
    numeros = [int(c[len(prefijo) :]) for c in usados if c[len(prefijo) :].isdigit()]
    return f"{prefijo}{max(numeros, default=0) + 1:04d}"


def buscar_articulos(
    db: Session,
    texto: str | None = None,
    categoria_id: uuid.UUID | None = None,
    tipo: str | None = None,
    solo_activos: bool = False,
    limite: int = 200,
) -> list[Articulo]:
    q = select(Articulo).order_by(Articulo.codigo)
    if texto:
        patron = f"%{texto.strip()}%"
        q = q.where(
            Articulo.codigo.ilike(patron)
            | Articulo.descripcion.ilike(patron)
            | Articulo.marca.ilike(patron)
            | Articulo.modelo.ilike(patron)
        )
    if categoria_id:
        # La categoría y todas sus subcategorías
        cat = obtener_categoria(db, categoria_id)
        ids = [cat.id, *(d.id for d in _descendientes(db, cat))]
        q = q.where(Articulo.categoria_id.in_(ids))
    if tipo:
        q = q.where(Articulo.tipo == tipo)
    if solo_activos:
        q = q.where(Articulo.activo.is_(True))
    return list(db.scalars(q.limit(min(limite, 500))))


def obtener_articulo(db: Session, articulo_id: uuid.UUID) -> Articulo:
    a = db.get(Articulo, articulo_id)
    if not a:
        raise no_encontrado("El artículo")
    return a


def articulos_de_categorias(db: Session, categoria_ids: list[uuid.UUID]) -> list[Articulo]:
    if not categoria_ids:
        return []
    return list(db.scalars(select(Articulo).where(Articulo.categoria_id.in_(categoria_ids))))


def subcategorias(db: Session, categoria_id: uuid.UUID) -> list[Categoria]:
    """La categoría y todas sus descendientes."""
    cat = obtener_categoria(db, categoria_id)
    return [cat, *_descendientes(db, cat)]


def _validar_datos_articulo(db: Session, datos: dict, actual: Articulo | None = None) -> None:
    if "tipo" in datos and datos["tipo"] not in datos_base.TIPOS_ARTICULO:
        raise ErrorERP(
            422, "tipo_invalido", f"Tipo no válido: {', '.join(datos_base.TIPOS_ARTICULO)}"
        )
    if "categoria_id" in datos:
        cat = obtener_categoria(db, datos["categoria_id"])
        if not cat.activo and (not actual or actual.categoria_id != cat.id):
            raise ErrorERP(422, "categoria_inactiva", f"La categoría {cat.codigo} está inactiva")
    if "unidad" in datos:
        unidad = obtener_unidad(db, datos["unidad"])
        if not unidad.activo and (not actual or actual.unidad != unidad.codigo):
            raise ErrorERP(422, "unidad_inactiva", f"La unidad {unidad.codigo} está inactiva")
        datos["unidad"] = unidad.codigo
    precio = datos.get("precio_referencial", actual.precio_referencial if actual else None)
    moneda = datos.get("moneda_precio", actual.moneda_precio if actual else None)
    if (precio is None) != (moneda is None):
        raise ErrorERP(
            422, "precio_incompleto", "El precio referencial necesita monto y moneda (o ninguno)"
        )
    if precio is not None and precio < 0:
        raise ErrorERP(422, "precio_invalido", "El precio referencial no puede ser negativo")
    if datos.get("moneda_precio"):
        datos["moneda_precio"] = obtener_moneda(db, datos["moneda_precio"]).codigo


def crear_articulo(db: Session, actor: Usuario, datos: dict) -> Articulo:
    _validar_datos_articulo(db, datos)
    codigo = (datos.get("codigo") or "").strip().upper() or siguiente_codigo(
        db, datos["categoria_id"]
    )
    if not CODIGO_ARTICULO.match(codigo):
        raise ErrorERP(
            422,
            "codigo_invalido",
            "El código usa mayúsculas, números, punto, guion o guion bajo (hasta 30)",
        )
    if db.scalar(select(Articulo.id).where(Articulo.codigo == codigo)):
        raise ErrorERP(409, "articulo_duplicado", f"Ya existe el artículo {codigo}")
    art = Articulo(
        codigo=codigo,
        descripcion=datos["descripcion"].strip(),
        tipo=datos["tipo"],
        categoria_id=datos["categoria_id"],
        unidad=datos["unidad"],
        impuesto=(datos.get("impuesto") or "IGV18").strip().upper(),
        marca=_texto(datos.get("marca")),
        modelo=_texto(datos.get("modelo")),
        especificacion=_texto(datos.get("especificacion")),
        precio_referencial=datos.get("precio_referencial"),
        moneda_precio=datos.get("moneda_precio"),
        creado_por=actor.id,
        actualizado_por=actor.id,
    )
    db.add(art)
    db.flush()
    db.refresh(art)
    # Contabilidad verifica que el tipo coincida con el perfil de cada empresa que lo tenga.
    emitir("validar_articulo", db, art)
    auditar(
        db,
        actor,
        "crear",
        "articulo",
        art.id,
        {"codigo": codigo, "descripcion": art.descripcion, "tipo": art.tipo},
    )
    db.commit()
    return art


def cambiar_articulo(
    db: Session, actor: Usuario, articulo_id: uuid.UUID, cambios: dict
) -> Articulo:
    art = obtener_articulo(db, articulo_id)
    _validar_datos_articulo(db, cambios, art)
    for campo in ("marca", "modelo", "especificacion"):
        if campo in cambios:
            cambios[campo] = _texto(cambios[campo])
    if cambios.get("descripcion"):
        cambios["descripcion"] = cambios["descripcion"].strip()
    if cambios.get("impuesto"):
        cambios["impuesto"] = cambios["impuesto"].strip().upper()
    if cambios.get("unidad") and any(u.unidad == cambios["unidad"] for u in art.unidades_alternas):
        raise ErrorERP(
            422,
            "unidad_repetida",
            f"{cambios['unidad']} es una unidad alternativa del artículo; quítala primero",
        )
    campos = (
        "descripcion",
        "tipo",
        "categoria_id",
        "unidad",
        "impuesto",
        "marca",
        "modelo",
        "especificacion",
        "precio_referencial",
        "moneda_precio",
        "activo",
    )
    detalle = _cambios(art, cambios, campos)
    if detalle:
        db.flush()
        db.expire(art, ["categoria"])
        if {"tipo", "categoria_id"} & set(detalle):
            emitir("validar_articulo", db, art)
        art.actualizado_por = actor.id
        auditar(db, actor, "editar", "articulo", art.id, {"codigo": art.codigo, **detalle})
        db.commit()
    return art


def fijar_unidades_articulo(
    db: Session, actor: Usuario, articulo_id: uuid.UUID, unidades: list[dict]
) -> Articulo:
    """Reemplaza las unidades alternativas: [{"unidad": "CJA", "factor": 12}]."""
    art = obtener_articulo(db, articulo_id)
    vistas: set[str] = set()
    nuevas: list[UnidadArticulo] = []
    for u in unidades:
        unidad = obtener_unidad(db, u["unidad"])
        if unidad.codigo == art.unidad:
            raise ErrorERP(422, "unidad_base", f"{unidad.codigo} ya es la unidad base del artículo")
        if unidad.codigo in vistas:
            raise ErrorERP(422, "unidad_repetida", f"{unidad.codigo} está repetida")
        if u["factor"] <= 0:
            raise ErrorERP(422, "factor_invalido", "El factor debe ser mayor que cero")
        vistas.add(unidad.codigo)
        nuevas.append(
            UnidadArticulo(
                articulo_id=art.id,
                unidad=unidad.codigo,
                factor=u["factor"],
                creado_por=actor.id,
                actualizado_por=actor.id,
            )
        )
    antes = sorted(f"1 {u.unidad} = {u.factor:g} {art.unidad}" for u in art.unidades_alternas)
    despues = sorted(f"1 {u.unidad} = {u.factor:g} {art.unidad}" for u in nuevas)
    if antes != despues:
        art.unidades_alternas = nuevas
        art.actualizado_por = actor.id
        auditar(
            db,
            actor,
            "editar",
            "articulo",
            art.id,
            {"codigo": art.codigo, "unidades": {"antes": antes, "despues": despues}},
        )
        db.commit()
        db.refresh(art)
    return art


def convertir_a_unidad_base(
    db: Session, articulo: Articulo, cantidad: Decimal, unidad: str
) -> Decimal:
    """Pasa a la unidad base: primero unidades propias del artículo, luego las generales."""
    unidad = unidad.upper()
    propia = next((u for u in articulo.unidades_alternas if u.unidad == unidad), None)
    if propia:
        return cantidad * propia.factor
    return convertir(db, cantidad, unidad, articulo.unidad)
