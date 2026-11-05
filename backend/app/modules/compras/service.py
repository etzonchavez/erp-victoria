"""Reglas de negocio de las órdenes de compra.

Ciclo de vida (ver models.ESTADOS):

    borrador ──enviar──▶ en_aprobacion ──aprobar (último)──▶ aprobada ──marcar──▶ enviada
       ▲                    │  │
       │                    │  └─rechazar──▶ rechazada (final; libera las solicitudes)
       └──── reenviar ── devuelta ◀─devolver
    borrador / devuelta ──anular (comprador)──▶ anulada
    aprobada / enviada ──anular (permiso compras.orden.anular)──▶ anulada

Decisiones de Et (4 nov 2026):
- La orden toma solicitudes aprobadas COMPLETAS: todas sus líneas, con la cantidad pedida.
  Desde que la orden se guarda, la solicitud ya no está disponible para otra orden.
- Una línea por línea de solicitud (no se suman artículos iguales).
- También se permiten líneas directas, sin solicitud.
- La orden pasa por su propia aprobación configurable (motor ADR-006, documento orden_compra).
"""

import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import ahora_utc
from app.core.errors import ErrorERP, no_encontrado
from app.modules.aprobaciones import service as aprobaciones
from app.modules.compras.models import (
    ANULABLES_CON_PERMISO,
    EDITABLES,
    ESTADOS,
    Correlativo,
    DistribucionOrden,
    LineaOrden,
    Orden,
)
from app.modules.contabilidad import service as contabilidad
from app.modules.contabilidad.models import Impuesto
from app.modules.maestros import service as maestros
from app.modules.seguridad import atributos
from app.modules.seguridad.models import Usuario
from app.modules.seguridad.service import auditar, permisos_de
from app.modules.solicitudes import service as solicitudes

DOCUMENTO = "orden_compra"
ORIGEN = "solicitud"
CENTAVO = Decimal("0.01")


def _redondear(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _puede(db: Session, usuario: Usuario, permiso: str) -> bool:
    return permiso in permisos_de(db, usuario)


def _acceso_unidad(db: Session, usuario: Usuario, unidad_id: uuid.UUID) -> bool:
    try:
        maestros.verificar_acceso_unidad(db, usuario, unidad_id)
    except ErrorERP:
        return False
    return True


# ---------------------------------------------------------------- consulta


def obtener(db: Session, orden_id: uuid.UUID) -> Orden:
    orden = db.get(Orden, orden_id)
    if not orden:
        raise no_encontrado("La orden de compra")
    return orden


def puede_ver(db: Session, usuario: Usuario, orden: Orden) -> bool:
    if usuario.es_administrador or orden.comprador_id == usuario.id:
        return True
    if _puede(db, usuario, "compras.orden.ver") and _acceso_unidad(
        db, usuario, orden.unidad_negocio_id
    ):
        return True
    return orden.id in aprobaciones.documentos_con_paso(db, usuario, DOCUMENTO)


def ver(db: Session, usuario: Usuario, orden_id: uuid.UUID) -> Orden:
    orden = obtener(db, orden_id)
    if not puede_ver(db, usuario, orden):
        raise ErrorERP(403, "sin_acceso_orden", "No tienes acceso a esta orden de compra")
    return orden


def listar(
    db: Session,
    usuario: Usuario,
    empresa_id: uuid.UUID,
    alcance: str = "mias",
    estado: str | None = None,
) -> list[Orden]:
    """alcance: mias (las que emití) o todas (requiere compras.orden.ver)."""
    maestros.verificar_acceso_empresa(db, usuario, empresa_id)
    q = select(Orden).where(Orden.empresa_id == empresa_id)
    if estado:
        q = q.where(Orden.estado == estado)
    if alcance == "mias":
        q = q.where(Orden.comprador_id == usuario.id)
    elif alcance == "todas":
        if not (usuario.es_administrador or _puede(db, usuario, "compras.orden.ver")):
            raise ErrorERP(403, "sin_permiso", "No tienes el permiso compras.orden.ver")
    else:
        raise ErrorERP(422, "alcance_invalido", "Alcance inexistente")
    resultado = list(db.scalars(q.order_by(Orden.creado_en.desc()).limit(500)))
    if alcance == "mias":
        return resultado
    return [o for o in resultado if _acceso_unidad(db, usuario, o.unidad_negocio_id)]


def bandeja(db: Session, usuario: Usuario) -> list[Orden]:
    ids = aprobaciones.documentos_pendientes(db, usuario, DOCUMENTO)
    if not ids:
        return []
    q = select(Orden).where(Orden.id.in_(ids), Orden.estado == "en_aprobacion")
    return [
        o for o in db.scalars(q.order_by(Orden.creado_en)) if acciones(db, usuario, o)["aprobar"]
    ]


def acciones(db: Session, usuario: Usuario, orden: Orden) -> dict:
    propia = orden.comprador_id == usuario.id
    editable = orden.estado in EDITABLES and propia
    turno = orden.estado == "en_aprobacion" and bool(
        aprobaciones.pasos_actuables(db, usuario, _contexto_basico(orden), orden.ronda)
    )
    anular = (orden.estado in EDITABLES and propia) or (
        orden.estado in ANULABLES_CON_PERMISO and _puede(db, usuario, "compras.orden.anular")
    )
    marcar = orden.estado == "aprobada" and _puede(db, usuario, "compras.orden.crear")
    return {
        "editar": editable,
        "enviar": editable,
        "aprobar": turno,
        "anular": anular,
        "marcar_enviada": marcar,
    }


# ---------------------------------------------------------------- registro


def _siguiente_numero(db: Session, empresa_id: uuid.UUID, fecha: date) -> str:
    corr = db.get(Correlativo, (empresa_id, fecha.year), with_for_update=True)
    if not corr:
        corr = Correlativo(empresa_id=empresa_id, anio=fecha.year, ultimo=0)
        db.add(corr)
    corr.ultimo += 1
    return f"OC-{fecha.year}-{corr.ultimo:06d}"


def _impuesto(db: Session, empresa_id: uuid.UUID, impuesto_id, donde: str) -> Impuesto | None:
    if not impuesto_id:
        return None
    imp = db.get(Impuesto, impuesto_id)
    if not imp or imp.empresa_id != empresa_id:
        raise ErrorERP(422, "impuesto_invalido", f"{donde}: el impuesto no es de esta empresa")
    if not imp.activo:
        raise ErrorERP(422, "impuesto_inactivo", f"{donde}: el impuesto {imp.codigo} está inactivo")
    return imp


def impuesto_por_defecto(db: Session, empresa_id: uuid.UUID) -> Impuesto | None:
    """El impuesto activo de mayor tasa (IGV 18 % en Perú)."""
    activos = [i for i in contabilidad.listar_impuestos(db, empresa_id) if i.activo]
    return max(activos, key=lambda i: i.tasa, default=None)


def _valores(db: Session, nivel: str, valores: dict | None) -> dict:
    if valores is None:
        return atributos.valores_por_defecto(db, DOCUMENTO, nivel)
    return atributos.validar_valores(db, DOCUMENTO, nivel, valores)


def _copiados(db: Session, origen_obj, nivel: str, valores: dict | None) -> dict:
    """Atributos de la línea/distribución: lo que envía el comprador o la copia de la solicitud."""
    if valores is not None:
        return atributos.validar_valores(db, DOCUMENTO, nivel, valores)
    leidos = {k: v for k, v in atributos.leer_valores(origen_obj, ORIGEN, nivel, db).items()}
    copia = atributos.copiar_valores(db, ORIGEN, DOCUMENTO, nivel, leidos)
    return {**atributos.valores_por_defecto(db, DOCUMENTO, nivel), **copia}


def _montos(linea: LineaOrden, precio: Decimal, imp: Impuesto | None) -> None:
    linea.precio = precio
    linea.subtotal = _redondear(linea.cantidad * precio)
    linea.impuesto_id = imp.id if imp else None
    linea.tasa = imp.tasa if imp else Decimal(0)
    linea.impuesto_monto = _redondear(linea.subtotal * linea.tasa / 100)
    linea.total = linea.subtotal + linea.impuesto_monto


def _repartir(linea: LineaOrden, items: list[tuple]) -> None:
    """items: (centro_id, porcentaje, atributos). El último centro recibe el redondeo."""
    asignado = Decimal(0)
    linea.distribuciones = []
    for j, (centro_id, porcentaje, valores) in enumerate(items, start=1):
        monto = (
            linea.subtotal - asignado
            if j == len(items)
            else _redondear(linea.subtotal * porcentaje / 100)
        )
        asignado += monto
        linea.distribuciones.append(
            DistribucionOrden(
                numero=j,
                centro_costo_id=centro_id,
                porcentaje=porcentaje,
                monto=monto,
                **valores,
            )
        )


def _distribucion_directa(db: Session, orden: Orden, items: list[dict], donde: str) -> list[tuple]:
    if not items:
        raise ErrorERP(422, "sin_distribucion", f"{donde}: indica al menos un centro de costo")
    suma = sum(Decimal(str(d["porcentaje"])) for d in items)
    if suma != 100:
        raise ErrorERP(
            422,
            "distribucion_incompleta",
            f"{donde}: los porcentajes suman {suma}, deben sumar 100",
        )
    vistos, resultado = set(), []
    for d in items:
        cc = contabilidad.obtener_centro(db, d["centro_costo_id"])
        if cc.empresa_id != orden.empresa_id or not cc.activo:
            raise ErrorERP(
                422, "centro_invalido", f"{donde}: centro de costo inactivo o de otra empresa"
            )
        if cc.id in vistos:
            raise ErrorERP(422, "centro_repetido", f"{donde}: el centro {cc.codigo} está repetido")
        vistos.add(cc.id)
        porcentaje = Decimal(str(d["porcentaje"]))
        if porcentaje <= 0:
            raise ErrorERP(
                422, "porcentaje_invalido", f"{donde}: cada porcentaje debe ser mayor que 0"
            )
        resultado.append((cc.id, porcentaje, _valores(db, "distribucion", d.get("atributos"))))
    return resultado


def _armar_lineas(db: Session, actor: Usuario, orden: Orden, datos: dict) -> None:
    """Reemplaza las líneas. Toma las solicitudes completas y agrega las líneas directas."""
    anteriores = {ln.solicitud_id for ln in orden.lineas if ln.solicitud_id}
    pedidas = list(dict.fromkeys(datos.get("solicitudes") or []))
    por_linea = {
        x["solicitud_linea_id"]: x for x in datos.get("lineas") or [] if x.get("solicitud_linea_id")
    }
    directas = [x for x in datos.get("lineas") or [] if not x.get("solicitud_linea_id")]
    if not pedidas and not directas:
        raise ErrorERP(422, "sin_lineas", "Agrega al menos una solicitud o una línea directa")
    defecto = impuesto_por_defecto(db, orden.empresa_id)

    orden.lineas.clear()
    db.flush()
    numero, usadas = 0, set()
    for sol_id in pedidas:
        sol = solicitudes.obtener(db, sol_id)
        if sol.empresa_id != orden.empresa_id:
            raise ErrorERP(
                422, "solicitud_otra_empresa", f"La solicitud {sol.numero} es de otra empresa"
            )
        if not _acceso_unidad(db, actor, sol.unidad_negocio_id):
            raise ErrorERP(
                403, "sin_acceso_unidad", f"No tienes acceso a la solicitud {sol.numero}"
            )
        solicitudes.tomar_para_orden(db, actor, sol.id, orden.id, orden.numero)
        for sl in sol.lineas:
            numero += 1
            usadas.add(sl.id)
            extra = por_linea.get(sl.id, {})
            donde = f"Línea {numero} ({sol.numero})"
            precio = Decimal(
                str(extra.get("precio", sl.precio if sol.moneda == orden.moneda else 0))
            )
            if precio < 0:
                raise ErrorERP(422, "precio_invalido", f"{donde}: el precio no puede ser negativo")
            imp = _impuesto(
                db,
                orden.empresa_id,
                extra.get("impuesto_id", defecto.id if defecto else None),
                donde,
            )
            linea = LineaOrden(
                numero=numero,
                solicitud_id=sol.id,
                solicitud_linea_id=sl.id,
                solicitud_numero=sol.numero,
                articulo_id=sl.articulo_id,
                descripcion=sl.descripcion,
                cantidad=sl.cantidad,
                unidad=sl.unidad,
                cantidad_base=sl.cantidad_base,
                perfil_id=sl.perfil_id,
                cuenta_id=sl.cuenta_id,
                **_copiados(db, sl, "linea", extra.get("atributos")),
            )
            _montos(linea, precio, imp)
            _repartir(
                linea,
                [
                    (d.centro_costo_id, d.porcentaje, _copiados(db, d, "distribucion", None))
                    for d in sl.distribuciones
                ],
            )
            orden.lineas.append(linea)
    sobrantes = set(por_linea) - usadas
    if sobrantes:
        raise ErrorERP(
            422, "linea_sin_solicitud", "Hay líneas de solicitudes que no están en la orden"
        )
    for datos_linea in directas:
        numero += 1
        donde = f"Línea {numero}"
        art = maestros.obtener_articulo(db, datos_linea["articulo_id"])
        if not art.activo:
            raise ErrorERP(
                422, "articulo_inactivo", f"{donde}: el artículo {art.codigo} está inactivo"
            )
        cantidad = Decimal(str(datos_linea["cantidad"]))
        if cantidad <= 0:
            raise ErrorERP(422, "cantidad_invalida", f"{donde}: la cantidad debe ser mayor que 0")
        unidad = (datos_linea.get("unidad") or art.unidad).upper()
        try:
            base = maestros.convertir_a_unidad_base(db, art, cantidad, unidad)
        except ErrorERP as e:
            raise ErrorERP(422, "unidad_invalida", f"{donde}: {e.mensaje}") from None
        precio = Decimal(str(datos_linea.get("precio") or 0))
        if precio < 0:
            raise ErrorERP(422, "precio_invalido", f"{donde}: el precio no puede ser negativo")
        imp_id = (
            datos_linea["impuesto_id"]
            if "impuesto_id" in datos_linea
            else (defecto.id if defecto else None)
        )
        imp = _impuesto(db, orden.empresa_id, imp_id, donde)
        linea = LineaOrden(
            numero=numero,
            articulo_id=art.id,
            descripcion=(datos_linea.get("descripcion") or art.descripcion).strip()[:240],
            cantidad=cantidad,
            unidad=unidad,
            cantidad_base=base,
            **_valores(db, "linea", datos_linea.get("atributos")),
        )
        _montos(linea, precio, imp)
        _repartir(
            linea, _distribucion_directa(db, orden, datos_linea.get("distribuciones") or [], donde)
        )
        orden.lineas.append(linea)

    for sol_id in anteriores - set(pedidas):
        solicitudes.liberar_de_orden(db, actor, sol_id, f"Se quitó de la orden {orden.numero}")
    orden.subtotal = sum((ln.subtotal for ln in orden.lineas), Decimal(0))
    orden.impuesto = sum((ln.impuesto_monto for ln in orden.lineas), Decimal(0))
    orden.total = orden.subtotal + orden.impuesto


def _cabecera(db: Session, actor: Usuario, orden: Orden, datos: dict) -> None:
    un = maestros.obtener_unidad_negocio(db, datos["unidad_negocio_id"])
    if un.empresa_id != orden.empresa_id or not un.activo:
        raise ErrorERP(
            422, "unidad_invalida", "La unidad de negocio está inactiva o es de otra empresa"
        )
    maestros.verificar_acceso_unidad(db, actor, un.id)
    prov = maestros.obtener_proveedor(db, datos["proveedor_id"])
    motivo = maestros.proveedor_habilitado(db, prov.id, orden.empresa_id)
    if motivo:
        raise ErrorERP(422, "proveedor_no_habilitado", f"{prov.razon_social}: {motivo}")
    contacto_id = datos.get("contacto_id")
    if contacto_id and contacto_id not in {c.id for c in prov.contactos}:
        raise ErrorERP(422, "contacto_invalido", "El contacto no es de este proveedor")
    if not contacto_id:
        contacto_id = next((c.id for c in prov.contactos if c.principal), None)
    condicion = maestros.obtener_condicion(
        db, datos.get("condicion_pago_id") or prov.condicion_pago_id
    )
    if not condicion.activo:
        raise ErrorERP(
            422, "condicion_inactiva", f"La condición de pago {condicion.nombre} está inactiva"
        )
    moneda = maestros.obtener_moneda(db, datos.get("moneda") or prov.moneda)
    if not moneda.activo:
        raise ErrorERP(422, "moneda_inactiva", f"La moneda {moneda.codigo} no está activa")
    if datos.get("fecha_entrega") and datos["fecha_entrega"] < orden.fecha:
        raise ErrorERP(
            422, "fecha_invalida", "La fecha de entrega no puede ser anterior a la orden"
        )
    orden.unidad_negocio_id = un.id
    orden.proveedor_id, orden.contacto_id = prov.id, contacto_id
    orden.condicion_pago_id, orden.moneda = condicion.id, moneda.codigo
    orden.fecha_entrega = datos.get("fecha_entrega")
    orden.lugar_entrega = (datos.get("lugar_entrega") or "").strip() or None
    orden.observaciones = (datos.get("observaciones") or "").strip() or None
    for columna, valor in _valores(db, "cabecera", datos.get("atributos")).items():
        setattr(orden, columna, valor)


def _resumen(orden: Orden) -> dict:
    return {
        "numero": orden.numero,
        "proveedor_id": str(orden.proveedor_id),
        "moneda": orden.moneda,
        "total": str(orden.total),
        "lineas": len(orden.lineas),
        "solicitudes": sorted({ln.solicitud_numero for ln in orden.lineas if ln.solicitud_numero}),
    }


def _tipo_cambio(db: Session, orden: Orden) -> tuple[Decimal, Decimal]:
    empresa = maestros.obtener_empresa(db, orden.empresa_id)
    if orden.moneda == empresa.moneda_funcional:
        return Decimal(1), orden.total
    tc = maestros.tipo_cambio_vigente(
        db, orden.moneda, date.today(), empresa.moneda_funcional
    ).venta
    return tc, _redondear(orden.total * tc)


def crear(db: Session, actor: Usuario, datos: dict) -> Orden:
    empresa = maestros.obtener_empresa(db, datos["empresa_id"])
    if not empresa.activo:
        raise ErrorERP(422, "empresa_inactiva", "La empresa está inactiva")
    maestros.verificar_acceso_empresa(db, actor, empresa.id)
    hoy = date.today()
    orden = Orden(
        id=uuid.uuid4(),
        empresa_id=empresa.id,
        comprador_id=actor.id,
        fecha=hoy,
        estado="borrador",
        creado_por=actor.id,
        actualizado_por=actor.id,
    )
    _cabecera(db, actor, orden, datos)
    orden.numero = _siguiente_numero(db, empresa.id, hoy)
    db.add(orden)
    db.flush()
    _armar_lineas(db, actor, orden, datos)
    orden.tipo_cambio, orden.total_funcional = _tipo_cambio(db, orden)
    db.flush()
    auditar(db, actor, "crear", "orden_compra", orden.id, _resumen(orden))
    db.commit()
    return orden


def cambiar(db: Session, actor: Usuario, orden_id: uuid.UUID, datos: dict) -> Orden:
    orden = obtener(db, orden_id)
    if orden.comprador_id != actor.id:
        raise ErrorERP(403, "no_es_comprador", "Solo quien emitió la orden puede editarla")
    if orden.estado not in EDITABLES:
        raise ErrorERP(
            409, "no_editable", f"La orden está {ESTADOS[orden.estado].lower()}: ya no se edita"
        )
    antes = _resumen(orden)
    _cabecera(db, actor, orden, datos)
    _armar_lineas(db, actor, orden, datos)
    orden.tipo_cambio, orden.total_funcional = _tipo_cambio(db, orden)
    orden.actualizado_por = actor.id
    db.flush()
    auditar(
        db, actor, "editar", "orden_compra", orden.id, {"antes": antes, "despues": _resumen(orden)}
    )
    db.commit()
    return orden


# ---------------------------------------------------------------- aprobación


def _contexto_basico(orden: Orden) -> aprobaciones.Contexto:
    return aprobaciones.Contexto(
        documento=DOCUMENTO,
        documento_id=orden.id,
        empresa_id=orden.empresa_id,
        unidad_negocio_id=orden.unidad_negocio_id,
        solicitante_id=orden.comprador_id,
        monto=orden.total_funcional,
    )


def _contexto(db: Session, orden: Orden, monto: Decimal) -> aprobaciones.Contexto:
    ctx = _contexto_basico(orden)
    ctx.monto = monto
    for linea in orden.lineas:
        art = maestros.obtener_articulo(db, linea.articulo_id)
        ctx.tipos.add(art.tipo)
        ctx.categorias.update(c.id for c in maestros.ancestros_categoria(db, art.categoria))
        for d in linea.distribuciones:
            if d.centro_costo_id not in ctx.centros:
                ctx.centros.append(d.centro_costo_id)
    return ctx


def ruta(db: Session, usuario: Usuario, orden_id: uuid.UUID) -> dict:
    orden = ver(db, usuario, orden_id)
    _, monto = _tipo_cambio(db, orden)
    return aprobaciones.simular(db, _contexto(db, orden, monto))


def _fijar_cuentas(db: Session, orden: Orden) -> None:
    for linea in orden.lineas:
        if linea.cuenta_id:
            continue
        art = maestros.obtener_articulo(db, linea.articulo_id)
        perfil, _ = contabilidad.perfil_de_articulo(db, orden.empresa_id, art)
        if not perfil or not perfil.activo:
            raise ErrorERP(
                422,
                "articulo_sin_perfil",
                f"Línea {linea.numero}: el artículo {art.codigo} no tiene perfil contable en esta "
                "empresa. Pide a Contabilidad que asigne uno a su categoría.",
            )
        linea.perfil_id, linea.cuenta_id = perfil.id, perfil.cuenta_cargo_id


def enviar(db: Session, actor: Usuario, orden_id: uuid.UUID) -> Orden:
    orden = obtener(db, orden_id)
    if orden.comprador_id != actor.id:
        raise ErrorERP(403, "no_es_comprador", "Solo quien emitió la orden puede enviarla")
    if orden.estado not in EDITABLES:
        raise ErrorERP(409, "no_enviable", f"La orden está {ESTADOS[orden.estado].lower()}")
    motivo = maestros.proveedor_habilitado(db, orden.proveedor_id, orden.empresa_id)
    if motivo:
        raise ErrorERP(422, "proveedor_no_habilitado", motivo)
    _fijar_cuentas(db, orden)
    orden.tipo_cambio, orden.total_funcional = _tipo_cambio(db, orden)
    orden.ronda += 1
    resultado = aprobaciones.iniciar(db, _contexto(db, orden, orden.total_funcional), orden.ronda)
    orden.estado = "aprobada" if resultado == "aprobado" else "en_aprobacion"
    orden.actualizado_por = actor.id
    auditar(
        db,
        actor,
        "enviar",
        "orden_compra",
        orden.id,
        {
            "numero": orden.numero,
            "ronda": orden.ronda,
            "total_funcional": str(orden.total_funcional),
            "estado": orden.estado,
        },
    )
    db.commit()
    return orden


def _liberar_solicitudes(db: Session, actor: Usuario, orden: Orden, motivo: str) -> None:
    for sol_id in {ln.solicitud_id for ln in orden.lineas if ln.solicitud_id}:
        solicitudes.liberar_de_orden(db, actor, sol_id, motivo)


def actuar(
    db: Session, actor: Usuario, orden_id: uuid.UUID, accion: str, comentario: str | None
) -> Orden:
    orden = obtener(db, orden_id)
    if orden.estado != "en_aprobacion":
        raise ErrorERP(409, "no_en_aprobacion", f"La orden está {ESTADOS[orden.estado].lower()}")
    resultado = aprobaciones.actuar(
        db, actor, _contexto_basico(orden), orden.ronda, accion, comentario
    )
    orden.estado = {
        "en_aprobacion": "en_aprobacion",
        "aprobado": "aprobada",
        "rechazado": "rechazada",
        "devuelto": "devuelta",
    }[resultado]
    if orden.estado == "rechazada":
        _liberar_solicitudes(db, actor, orden, f"Orden {orden.numero} rechazada")
    auditar(
        db,
        actor,
        accion,
        "orden_compra",
        orden.id,
        {"numero": orden.numero, "comentario": comentario, "estado": orden.estado},
    )
    db.commit()
    return orden


def marcar_enviada(db: Session, actor: Usuario, orden_id: uuid.UUID) -> Orden:
    orden = obtener(db, orden_id)
    if not acciones(db, actor, orden)["marcar_enviada"]:
        raise ErrorERP(409, "no_se_puede_enviar", "Solo una orden aprobada se envía al proveedor")
    orden.estado, orden.enviada_en, orden.enviada_por = "enviada", ahora_utc(), actor.id
    auditar(db, actor, "enviar_proveedor", "orden_compra", orden.id, {"numero": orden.numero})
    db.commit()
    return orden


def anular(db: Session, actor: Usuario, orden_id: uuid.UUID, comentario: str | None) -> Orden:
    orden = obtener(db, orden_id)
    if not acciones(db, actor, orden)["anular"]:
        if orden.estado == "en_aprobacion":
            raise ErrorERP(
                409,
                "en_aprobacion",
                "No se anula mientras está en aprobación: pide que la devuelvan",
            )
        raise ErrorERP(403, "no_anulable", "No puedes anular esta orden")
    comentario = (comentario or "").strip()
    if len(comentario) < 3:
        raise ErrorERP(422, "comentario_requerido", "Escribe el motivo de la anulación")
    aprobaciones.cancelar_ronda(db, _contexto_basico(orden), orden.ronda)
    antes = orden.estado
    orden.estado, orden.actualizado_por = "anulada", actor.id
    _liberar_solicitudes(db, actor, orden, f"Orden {orden.numero} anulada")
    auditar(
        db,
        actor,
        "anular",
        "orden_compra",
        orden.id,
        {"numero": orden.numero, "estado_anterior": antes, "motivo": comentario},
    )
    db.commit()
    return orden


def historial(db: Session, orden: Orden) -> list:
    return aprobaciones.pasos_de(db, DOCUMENTO, orden.id)
