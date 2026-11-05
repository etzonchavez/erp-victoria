"""Reglas de negocio de las solicitudes de compra.

Ciclo de vida (ver models.ESTADOS):

    borrador ──enviar──▶ en_aprobacion ──aprobar (último)──▶ aprobada
       ▲                    │  │
       │                    │  └─rechazar──▶ rechazada (final)
       └──── reenviar ── devuelta ◀─devolver
    borrador / devuelta / aprobada ──anular──▶ anulada
    aprobada ──Compras la incluye en una OC──▶ atendida ──OC rechazada o anulada──▶ aprobada

Si la regla no tiene niveles para el monto, la solicitud se aprueba al enviarla.
"""

import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ErrorERP, no_encontrado
from app.modules.aprobaciones import service as aprobaciones
from app.modules.contabilidad import service as contabilidad
from app.modules.maestros import service as maestros
from app.modules.seguridad import atributos, notificaciones
from app.modules.seguridad.models import Usuario
from app.modules.seguridad.service import auditar, permisos_de
from app.modules.solicitudes.models import (
    EDITABLES,
    ESTADOS,
    Correlativo,
    Distribucion,
    Linea,
    Solicitud,
)

DOCUMENTO = "solicitud"
CENTAVO = Decimal("0.01")


def _redondear(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _puede(db: Session, usuario: Usuario, permiso: str) -> bool:
    return permiso in permisos_de(db, usuario)


# ---------------------------------------------------------------- consulta


def obtener(db: Session, solicitud_id: uuid.UUID) -> Solicitud:
    sol = db.get(Solicitud, solicitud_id)
    if not sol:
        raise no_encontrado("La solicitud")
    return sol


def _tiene_acceso_unidad(db: Session, usuario: Usuario, unidad_id: uuid.UUID) -> bool:
    try:
        maestros.verificar_acceso_unidad(db, usuario, unidad_id)
    except ErrorERP:
        return False
    return True


def puede_ver(db: Session, usuario: Usuario, sol: Solicitud) -> bool:
    if usuario.es_administrador or sol.solicitante_id == usuario.id:
        return True
    if _puede(db, usuario, "solicitudes.solicitud.ver") and _tiene_acceso_unidad(
        db, usuario, sol.unidad_negocio_id
    ):
        return True
    return sol.id in aprobaciones.documentos_con_paso(db, usuario, DOCUMENTO)


def ver(db: Session, usuario: Usuario, solicitud_id: uuid.UUID) -> Solicitud:
    sol = obtener(db, solicitud_id)
    if not puede_ver(db, usuario, sol):
        raise ErrorERP(403, "sin_acceso_solicitud", "No tienes acceso a esta solicitud")
    return sol


def listar(
    db: Session,
    usuario: Usuario,
    empresa_id: uuid.UUID,
    alcance: str = "mias",
    estado: str | None = None,
) -> list[Solicitud]:
    """alcance: mias (las que registré), todas (requiere ver) o por_aprobar (mi bandeja)."""
    maestros.verificar_acceso_empresa(db, usuario, empresa_id)
    q = select(Solicitud).where(Solicitud.empresa_id == empresa_id)
    if estado:
        q = q.where(Solicitud.estado == estado)
    if alcance == "mias":
        q = q.where(Solicitud.solicitante_id == usuario.id)
    elif alcance == "por_aprobar":
        ids = aprobaciones.documentos_pendientes(db, usuario, DOCUMENTO)
        q = q.where(Solicitud.id.in_(ids), Solicitud.estado == "en_aprobacion")
    elif alcance == "todas":
        if not (usuario.es_administrador or _puede(db, usuario, "solicitudes.solicitud.ver")):
            raise ErrorERP(403, "sin_permiso", "No tienes el permiso solicitudes.solicitud.ver")
    else:
        raise ErrorERP(422, "alcance_invalido", "Alcance inexistente")
    resultado = list(db.scalars(q.order_by(Solicitud.creado_en.desc()).limit(500)))
    if alcance == "mias":
        return resultado
    if alcance == "por_aprobar":
        return [s for s in resultado if acciones(db, usuario, s)["aprobar"]]
    return [s for s in resultado if _tiene_acceso_unidad(db, usuario, s.unidad_negocio_id)]


def bandeja(db: Session, usuario: Usuario) -> list[Solicitud]:
    """Solicitudes que esperan una aprobación del usuario, en todas sus empresas."""
    ids = aprobaciones.documentos_pendientes(db, usuario, DOCUMENTO)
    if not ids:
        return []
    q = select(Solicitud).where(Solicitud.id.in_(ids), Solicitud.estado == "en_aprobacion")
    return [
        s
        for s in db.scalars(q.order_by(Solicitud.creado_en))
        if acciones(db, usuario, s)["aprobar"]
    ]


def acciones(db: Session, usuario: Usuario, sol: Solicitud) -> dict:
    """Qué puede hacer el usuario con la solicitud (para mostrar los botones correctos)."""
    propia = sol.solicitante_id == usuario.id
    editable = sol.estado in EDITABLES and propia
    turno = sol.estado == "en_aprobacion" and bool(
        aprobaciones.pasos_actuables(db, usuario, _contexto_basico(sol), sol.ronda)
    )
    anular = (sol.estado in EDITABLES and propia) or (
        sol.estado == "aprobada" and _puede(db, usuario, "solicitudes.solicitud.anular")
    )
    return {"editar": editable, "enviar": editable, "aprobar": turno, "anular": anular}


# ---------------------------------------------------------------- registro


def _siguiente_numero(db: Session, empresa_id: uuid.UUID, fecha: date) -> str:
    corr = db.get(Correlativo, (empresa_id, fecha.year), with_for_update=True)
    if not corr:
        corr = Correlativo(empresa_id=empresa_id, anio=fecha.year, ultimo=0)
        db.add(corr)
    corr.ultimo += 1
    return f"SC-{fecha.year}-{corr.ultimo:06d}"


def _tipo_cambio(db: Session, moneda: str, base: str, fecha: date) -> Decimal:
    if moneda == base:
        return Decimal(1)
    return maestros.tipo_cambio_vigente(db, moneda, fecha, base).venta


def _armar_lineas(db: Session, sol: Solicitud, lineas: list[dict]) -> None:
    if not lineas:
        raise ErrorERP(422, "sin_lineas", "Agrega al menos una línea")
    sol.lineas.clear()
    db.flush()
    total = Decimal(0)
    for i, datos in enumerate(lineas, start=1):
        donde = f"Línea {i}"
        art = maestros.obtener_articulo(db, datos["articulo_id"])
        if not art.activo:
            raise ErrorERP(
                422, "articulo_inactivo", f"{donde}: el artículo {art.codigo} está inactivo"
            )
        cantidad = Decimal(str(datos["cantidad"]))
        if cantidad <= 0:
            raise ErrorERP(422, "cantidad_invalida", f"{donde}: la cantidad debe ser mayor que 0")
        unidad = (datos.get("unidad") or art.unidad).upper()
        try:
            base = maestros.convertir_a_unidad_base(db, art, cantidad, unidad)
        except ErrorERP as e:
            raise ErrorERP(422, "unidad_invalida", f"{donde}: {e.mensaje}") from None
        precio = Decimal(str(datos.get("precio") or 0))
        if precio < 0:
            raise ErrorERP(422, "precio_invalido", f"{donde}: el precio no puede ser negativo")
        subtotal = _redondear(cantidad * precio)
        total += subtotal
        linea = Linea(
            numero=i,
            articulo_id=art.id,
            descripcion=(datos.get("descripcion") or art.descripcion).strip()[:240],
            cantidad=cantidad,
            unidad=unidad,
            cantidad_base=base,
            precio=precio,
            subtotal=subtotal,
            **_valores(db, "linea", datos.get("atributos")),
        )
        linea.distribuciones = _distribuciones(
            db, sol, datos.get("distribuciones") or [], subtotal, donde
        )
        sol.lineas.append(linea)
    sol.total = _redondear(total)


def _distribuciones(
    db: Session, sol: Solicitud, items: list[dict], subtotal: Decimal, donde: str
) -> list[Distribucion]:
    if not items:
        raise ErrorERP(422, "sin_distribucion", f"{donde}: indica al menos un centro de costo")
    suma = sum(Decimal(str(d["porcentaje"])) for d in items)
    if suma != 100:
        raise ErrorERP(
            422,
            "distribucion_incompleta",
            f"{donde}: los porcentajes suman {suma}, deben sumar 100",
        )
    vistos, resultado, asignado = set(), [], Decimal(0)
    for j, d in enumerate(items, start=1):
        cc = contabilidad.obtener_centro(db, d["centro_costo_id"])
        if cc.empresa_id != sol.empresa_id:
            raise ErrorERP(
                422, "centro_otra_empresa", f"{donde}: el centro de costo es de otra empresa"
            )
        if not cc.activo:
            raise ErrorERP(
                422, "centro_inactivo", f"{donde}: el centro de costo {cc.codigo} está inactivo"
            )
        if cc.id in vistos:
            raise ErrorERP(422, "centro_repetido", f"{donde}: el centro {cc.codigo} está repetido")
        vistos.add(cc.id)
        porcentaje = Decimal(str(d["porcentaje"]))
        if porcentaje <= 0:
            raise ErrorERP(
                422, "porcentaje_invalido", f"{donde}: cada porcentaje debe ser mayor que 0"
            )
        # El último centro recibe el resto para que los montos cuadren al céntimo
        monto = subtotal - asignado if j == len(items) else _redondear(subtotal * porcentaje / 100)
        asignado += monto
        resultado.append(
            Distribucion(
                numero=j,
                centro_costo_id=cc.id,
                porcentaje=porcentaje,
                monto=monto,
                **_valores(db, "distribucion", d.get("atributos")),
            )
        )
    return resultado


def _valores(db: Session, nivel: str, valores: dict | None) -> dict:
    if valores is None:
        return atributos.valores_por_defecto(db, DOCUMENTO, nivel)
    return atributos.validar_valores(db, DOCUMENTO, nivel, valores)


def _cabecera(db: Session, actor: Usuario, sol: Solicitud, datos: dict) -> None:
    un = maestros.obtener_unidad_negocio(db, datos["unidad_negocio_id"])
    if un.empresa_id != sol.empresa_id:
        raise ErrorERP(422, "unidad_otra_empresa", "La unidad de negocio es de otra empresa")
    if not un.activo:
        raise ErrorERP(422, "unidad_inactiva", f"La unidad de negocio {un.nombre} está inactiva")
    maestros.verificar_acceso_unidad(db, actor, un.id)
    moneda = maestros.obtener_moneda(db, datos.get("moneda") or sol.moneda)
    if not moneda.activo:
        raise ErrorERP(422, "moneda_inactiva", f"La moneda {moneda.codigo} no está activa")
    titulo = (datos.get("titulo") or "").strip()
    if len(titulo) < 3:
        raise ErrorERP(422, "titulo_requerido", "Escribe un título que resuma qué se necesita")
    if datos.get("fecha_requerida") and datos["fecha_requerida"] < sol.fecha:
        raise ErrorERP(
            422, "fecha_invalida", "La fecha requerida no puede ser anterior a la de la solicitud"
        )
    sol.unidad_negocio_id = un.id
    sol.moneda = moneda.codigo
    sol.titulo = titulo
    sol.justificacion = (datos.get("justificacion") or "").strip() or None
    sol.fecha_requerida = datos.get("fecha_requerida")
    for columna, valor in _valores(db, "cabecera", datos.get("atributos")).items():
        setattr(sol, columna, valor)


def _resumen(sol: Solicitud) -> dict:
    return {
        "numero": sol.numero,
        "titulo": sol.titulo,
        "moneda": sol.moneda,
        "total": str(sol.total),
        "lineas": len(sol.lineas),
    }


def crear(db: Session, actor: Usuario, datos: dict) -> Solicitud:
    empresa = maestros.obtener_empresa(db, datos["empresa_id"])
    if not empresa.activo:
        raise ErrorERP(422, "empresa_inactiva", "La empresa está inactiva")
    maestros.verificar_acceso_empresa(db, actor, empresa.id)
    hoy = date.today()
    sol = Solicitud(
        empresa_id=empresa.id,
        solicitante_id=actor.id,
        fecha=hoy,
        moneda=empresa.moneda_funcional,
        estado="borrador",
        creado_por=actor.id,
        actualizado_por=actor.id,
    )
    _cabecera(db, actor, sol, datos)
    sol.numero = _siguiente_numero(db, empresa.id, hoy)
    db.add(sol)
    _armar_lineas(db, sol, datos.get("lineas") or [])
    db.flush()
    auditar(db, actor, "crear", "solicitud", sol.id, _resumen(sol))
    db.commit()
    return sol


def cambiar(db: Session, actor: Usuario, solicitud_id: uuid.UUID, datos: dict) -> Solicitud:
    sol = obtener(db, solicitud_id)
    if sol.solicitante_id != actor.id:
        raise ErrorERP(403, "no_es_solicitante", "Solo quien registró la solicitud puede editarla")
    if sol.estado not in EDITABLES:
        raise ErrorERP(
            409, "no_editable", f"La solicitud está {ESTADOS[sol.estado].lower()}: ya no se edita"
        )
    antes = _resumen(sol)
    _cabecera(db, actor, sol, datos)
    _armar_lineas(db, sol, datos.get("lineas") or [])
    sol.actualizado_por = actor.id
    db.flush()
    auditar(db, actor, "editar", "solicitud", sol.id, {"antes": antes, "despues": _resumen(sol)})
    db.commit()
    return sol


# ---------------------------------------------------------------- aprobación


def _contexto_basico(sol: Solicitud) -> aprobaciones.Contexto:
    return aprobaciones.Contexto(
        documento=DOCUMENTO,
        documento_id=sol.id,
        empresa_id=sol.empresa_id,
        unidad_negocio_id=sol.unidad_negocio_id,
        solicitante_id=sol.solicitante_id,
        monto=sol.total_funcional,
        referencia=f"solicitud {sol.numero} · {sol.titulo}",
        enlace=f"solicitudes?id={sol.id}",
    )


def _contexto(db: Session, sol: Solicitud, monto: Decimal) -> aprobaciones.Contexto:
    ctx = _contexto_basico(sol)
    ctx.monto = monto
    for linea in sol.lineas:
        art = maestros.obtener_articulo(db, linea.articulo_id)
        ctx.tipos.add(art.tipo)
        ctx.categorias.update(c.id for c in maestros.ancestros_categoria(db, art.categoria))
        for d in linea.distribuciones:
            if d.centro_costo_id not in ctx.centros:
                ctx.centros.append(d.centro_costo_id)
    return ctx


def _monto_funcional(db: Session, sol: Solicitud) -> tuple[Decimal, Decimal]:
    empresa = maestros.obtener_empresa(db, sol.empresa_id)
    tc = _tipo_cambio(db, sol.moneda, empresa.moneda_funcional, date.today())
    return tc, _redondear(sol.total * tc)


def ruta(db: Session, usuario: Usuario, solicitud_id: uuid.UUID) -> dict:
    """Quién aprobaría la solicitud si se envía ahora (vista previa)."""
    sol = ver(db, usuario, solicitud_id)
    _, monto = _monto_funcional(db, sol)
    return aprobaciones.simular(db, _contexto(db, sol, monto))


def _fijar_cuentas(db: Session, sol: Solicitud) -> None:
    for linea in sol.lineas:
        art = maestros.obtener_articulo(db, linea.articulo_id)
        perfil, _ = contabilidad.perfil_de_articulo(db, sol.empresa_id, art)
        if not perfil or not perfil.activo:
            raise ErrorERP(
                422,
                "articulo_sin_perfil",
                f"Línea {linea.numero}: el artículo {art.codigo} no tiene perfil contable en esta "
                "empresa. Pide a Contabilidad que asigne uno a su categoría.",
            )
        linea.perfil_id, linea.cuenta_id = perfil.id, perfil.cuenta_cargo_id


def enviar(db: Session, actor: Usuario, solicitud_id: uuid.UUID) -> Solicitud:
    sol = obtener(db, solicitud_id)
    if sol.solicitante_id != actor.id:
        raise ErrorERP(403, "no_es_solicitante", "Solo quien registró la solicitud puede enviarla")
    if sol.estado not in EDITABLES:
        raise ErrorERP(409, "no_enviable", f"La solicitud está {ESTADOS[sol.estado].lower()}")
    maestros.verificar_acceso_unidad(db, actor, sol.unidad_negocio_id)
    _fijar_cuentas(db, sol)
    sol.tipo_cambio, sol.total_funcional = _monto_funcional(db, sol)
    sol.ronda += 1
    resultado = aprobaciones.iniciar(db, _contexto(db, sol, sol.total_funcional), sol.ronda)
    sol.estado = "aprobada" if resultado == "aprobado" else "en_aprobacion"
    sol.actualizado_por = actor.id
    auditar(
        db,
        actor,
        "enviar",
        "solicitud",
        sol.id,
        {
            "numero": sol.numero,
            "ronda": sol.ronda,
            "total_funcional": str(sol.total_funcional),
            "estado": sol.estado,
        },
    )
    db.commit()
    return sol


def actuar(
    db: Session, actor: Usuario, solicitud_id: uuid.UUID, accion: str, comentario: str | None
) -> Solicitud:
    sol = obtener(db, solicitud_id)
    if sol.estado != "en_aprobacion":
        raise ErrorERP(409, "no_en_aprobacion", f"La solicitud está {ESTADOS[sol.estado].lower()}")
    resultado = aprobaciones.actuar(db, actor, _contexto_basico(sol), sol.ronda, accion, comentario)
    sol.estado = {
        "en_aprobacion": "en_aprobacion",
        "aprobado": "aprobada",
        "rechazado": "rechazada",
        "devuelto": "devuelta",
    }[resultado]
    _avisar_resultado(db, actor, sol, comentario)
    auditar(
        db,
        actor,
        accion,
        "solicitud",
        sol.id,
        {"numero": sol.numero, "comentario": comentario, "estado": sol.estado},
    )
    db.commit()
    return sol


AVISOS = {
    "aprobada": ("aprobado", "Tu solicitud {n} fue aprobada", "Ya está lista para Compras."),
    "rechazada": ("rechazado", "Tu solicitud {n} fue rechazada", "{a}: {c}"),
    "devuelta": ("devuelto", "Tu solicitud {n} fue devuelta", "{a} pide corregir: {c}"),
}


def _avisar_resultado(db: Session, actor: Usuario, sol: Solicitud, comentario: str | None) -> None:
    if sol.estado not in AVISOS:
        return
    tipo, titulo, mensaje = AVISOS[sol.estado]
    notificaciones.notificar(
        db,
        [sol.solicitante_id],
        tipo,
        titulo.format(n=sol.numero),
        mensaje.format(a=actor.nombre, c=comentario or "sin comentario"),
        f"solicitudes?id={sol.id}",
        DOCUMENTO,
        sol.id,
    )


def anular(
    db: Session, actor: Usuario, solicitud_id: uuid.UUID, comentario: str | None
) -> Solicitud:
    sol = obtener(db, solicitud_id)
    if not acciones(db, actor, sol)["anular"]:
        if sol.estado == "en_aprobacion":
            raise ErrorERP(
                409,
                "en_aprobacion",
                "No se anula mientras está en aprobación: pide que la devuelvan",
            )
        raise ErrorERP(403, "no_anulable", "No puedes anular esta solicitud")
    comentario = (comentario or "").strip()
    if len(comentario) < 3:
        raise ErrorERP(422, "comentario_requerido", "Escribe el motivo de la anulación")
    aprobaciones.cancelar_ronda(db, _contexto_basico(sol), sol.ronda)
    antes = sol.estado
    sol.estado = "anulada"
    sol.actualizado_por = actor.id
    auditar(
        db,
        actor,
        "anular",
        "solicitud",
        sol.id,
        {"numero": sol.numero, "estado_anterior": antes, "motivo": comentario},
    )
    db.commit()
    return sol


def historial(db: Session, sol: Solicitud) -> list:
    return aprobaciones.pasos_de(db, DOCUMENTO, sol.id)


# ---------------------------------------------------------------- uso desde Compras


def disponibles(db: Session, usuario: Usuario, empresa_id: uuid.UUID) -> list[Solicitud]:
    """Solicitudes aprobadas que aún no están en una orden de compra."""
    maestros.verificar_acceso_empresa(db, usuario, empresa_id)
    q = select(Solicitud).where(Solicitud.empresa_id == empresa_id, Solicitud.estado == "aprobada")
    return [
        s
        for s in db.scalars(q.order_by(Solicitud.creado_en))
        if _tiene_acceso_unidad(db, usuario, s.unidad_negocio_id)
    ]


def tomar_para_orden(
    db: Session, actor: Usuario, solicitud_id: uuid.UUID, orden_id: uuid.UUID, numero: str
) -> Solicitud:
    """La orden de compra toma la solicitud completa: deja de estar disponible."""
    sol = db.get(Solicitud, solicitud_id, with_for_update=True)
    if not sol:
        raise no_encontrado("La solicitud")
    if sol.orden_compra_id == orden_id:
        return sol
    if sol.estado != "aprobada":
        detalle = f" en la orden {sol.orden_compra_numero}" if sol.orden_compra_numero else ""
        raise ErrorERP(
            409,
            "solicitud_no_disponible",
            f"La solicitud {sol.numero} no está disponible: está "
            f"{ESTADOS[sol.estado].lower()}{detalle}",
        )
    sol.estado, sol.orden_compra_id, sol.orden_compra_numero = "atendida", orden_id, numero
    auditar(db, actor, "atender", "solicitud", sol.id, {"numero": sol.numero, "orden": numero})
    return sol


def liberar_de_orden(db: Session, actor: Usuario, solicitud_id: uuid.UUID, motivo: str) -> None:
    """La orden se rechazó, se anuló o la quitó: la solicitud vuelve a estar aprobada."""
    sol = obtener(db, solicitud_id)
    if sol.estado != "atendida":
        return
    numero = sol.orden_compra_numero
    sol.estado, sol.orden_compra_id, sol.orden_compra_numero = "aprobada", None, None
    auditar(
        db,
        actor,
        "liberar",
        "solicitud",
        sol.id,
        {"numero": sol.numero, "orden": numero, "motivo": motivo},
    )
