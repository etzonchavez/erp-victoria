"""Rutas de órdenes de compra y su formato PDF: /api/v1/compras/..."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.aprobaciones import presentacion
from app.modules.compras import asiento, pdf, service
from app.modules.compras import reporte as reporte_excel
from app.modules.compras.models import ESTADOS, Orden
from app.modules.compras.schemas import (
    ArticuloOpcion,
    AsientoPrevio,
    Comentario,
    FormatoDatos,
    FormatoSalida,
    OpcionesCompra,
    OrdenCrear,
    OrdenDatos,
    OrdenResumen,
    OrdenSalida,
    Ruta,
    SolicitudDisponible,
)
from app.modules.contabilidad import service as contabilidad
from app.modules.maestros import service as maestros
from app.modules.maestros.deps import acceso_empresa_de_ruta
from app.modules.seguridad import atributos
from app.modules.seguridad.deps import modulo_activo, requiere
from app.modules.seguridad.models import Usuario
from app.modules.solicitudes import service as solicitudes

router = APIRouter(dependencies=[Depends(acceso_empresa_de_ruta)])
MODULO = modulo_activo("compras")
DOC = service.DOCUMENTO


# ---------------------------------------------------------------- presentación


def _resumen(db: Session, o: Orden) -> dict:
    return {
        "id": o.id,
        "numero": o.numero,
        "fecha": o.fecha,
        "empresa_id": o.empresa_id,
        "unidad_negocio_id": o.unidad_negocio_id,
        "unidad_negocio": maestros.obtener_unidad_negocio(db, o.unidad_negocio_id).nombre,
        "comprador_id": o.comprador_id,
        "comprador": presentacion.nombre(db, Usuario, o.comprador_id),
        "proveedor_id": o.proveedor_id,
        "proveedor": maestros.obtener_proveedor(db, o.proveedor_id).razon_social,
        "moneda": o.moneda,
        "total": o.total,
        "total_funcional": o.total_funcional,
        "estado": o.estado,
        "solicitudes": sorted({ln.solicitud_numero for ln in o.lineas if ln.solicitud_numero}),
        "pendiente_de": presentacion.pasos_pendientes(service.historial(db, o), o.ronda)
        if o.estado == "en_aprobacion"
        else [],
    }


def _detalle(db: Session, usuario: Usuario, o: Orden) -> dict:
    lineas = []
    for ln in o.lineas:
        art = maestros.obtener_articulo(db, ln.articulo_id)
        cuenta = contabilidad.obtener_cuenta(db, ln.cuenta_id) if ln.cuenta_id else None
        lineas.append(
            {
                "numero": ln.numero,
                "solicitud_id": ln.solicitud_id,
                "solicitud_linea_id": ln.solicitud_linea_id,
                "solicitud_numero": ln.solicitud_numero,
                "articulo_id": art.id,
                "articulo": art.codigo,
                "descripcion": ln.descripcion,
                "cantidad": ln.cantidad,
                "unidad": ln.unidad,
                "unidad_base": art.unidad,
                "unidades": [art.unidad, *(u.unidad for u in art.unidades_alternas)],
                "precio": ln.precio,
                "subtotal": ln.subtotal,
                "impuesto_id": ln.impuesto_id,
                "tasa": ln.tasa,
                "impuesto_monto": ln.impuesto_monto,
                "total": ln.total,
                "cuenta": f"{cuenta.codigo} {cuenta.nombre}" if cuenta else None,
                "atributos": atributos.leer_valores(ln, DOC, "linea", db),
                "distribuciones": [
                    {
                        "centro_costo_id": d.centro_costo_id,
                        "centro_costo": contabilidad.obtener_centro(db, d.centro_costo_id).codigo,
                        "porcentaje": d.porcentaje,
                        "monto": d.monto,
                        "atributos": atributos.leer_valores(d, DOC, "distribucion", db),
                    }
                    for d in ln.distribuciones
                ],
            }
        )
    return {
        **_resumen(db, o),
        "contacto_id": o.contacto_id,
        "condicion_pago_id": o.condicion_pago_id,
        "condicion_pago": maestros.obtener_condicion(db, o.condicion_pago_id).nombre,
        "fecha_entrega": o.fecha_entrega,
        "lugar_entrega": o.lugar_entrega,
        "observaciones": o.observaciones,
        "subtotal": o.subtotal,
        "impuesto": o.impuesto,
        "tipo_cambio": o.tipo_cambio,
        "ronda": o.ronda,
        "enviada_en": o.enviada_en,
        "lineas": lineas,
        "atributos": atributos.leer_valores(o, DOC, "cabecera", db),
        "pasos": service.historial(db, o),
        "acciones": service.acciones(db, usuario, o),
    }


# ---------------------------------------------------------------- listas de apoyo


@router.get(
    "/empresas/{empresa_id}/opciones",
    response_model=OpcionesCompra,
    summary="Proveedores habilitados, condiciones, impuestos, unidades y centros",
)
def opciones(
    empresa_id: uuid.UUID,
    usuario: Usuario = Depends(requiere("compras.orden.crear")),
    db: Session = Depends(get_db),
):
    base = presentacion.opciones_empresa(db, usuario, empresa_id)
    defecto = service.impuesto_por_defecto(db, empresa_id)
    return {
        "unidades": base["unidades"],
        "centros": base["centros"],
        "proveedores": [
            {
                "id": p.id,
                "razon_social": p.razon_social,
                "documento": f"{p.tipo_documento} {p.numero_documento}",
                "moneda": p.moneda,
                "condicion_pago_id": p.condicion_pago_id,
                "contactos": [
                    {"id": c.id, "codigo": c.cargo or "", "nombre": c.nombre} for c in p.contactos
                ],
            }
            for p in maestros.buscar_proveedores(db, solo_activos=True, limite=500)
            if not maestros.proveedor_habilitado(db, p.id, empresa_id)
        ],
        "condiciones": [
            {"id": c.id, "codigo": c.codigo, "nombre": c.nombre}
            for c in maestros.listar_condiciones(db)
            if c.activo
        ],
        "impuestos": [
            {"id": i.id, "codigo": i.codigo, "nombre": i.nombre, "tasa": i.tasa}
            for i in contabilidad.listar_impuestos(db, empresa_id)
            if i.activo
        ],
        "impuesto_defecto": defecto.id if defecto else None,
        "monedas": [m.codigo for m in maestros.listar_monedas(db) if m.activo],
        "estados": [{"codigo": k, "nombre": v} for k, v in ESTADOS.items()],
    }


@router.get(
    "/empresas/{empresa_id}/solicitudes-disponibles",
    response_model=list[SolicitudDisponible],
    summary="Solicitudes aprobadas que aún no están en una orden",
)
def disponibles(
    empresa_id: uuid.UUID,
    usuario: Usuario = Depends(requiere("compras.orden.crear")),
    db: Session = Depends(get_db),
):
    resultado = []
    for s in solicitudes.disponibles(db, usuario, empresa_id):
        resultado.append(
            {
                "id": s.id,
                "numero": s.numero,
                "titulo": s.titulo,
                "solicitante": presentacion.nombre(db, Usuario, s.solicitante_id),
                "unidad_negocio": maestros.obtener_unidad_negocio(db, s.unidad_negocio_id).nombre,
                "fecha_requerida": s.fecha_requerida,
                "moneda": s.moneda,
                "total": s.total,
                "lineas": [
                    {
                        "id": ln.id,
                        "numero": ln.numero,
                        "articulo": maestros.obtener_articulo(db, ln.articulo_id).codigo,
                        "descripcion": ln.descripcion,
                        "cantidad": ln.cantidad,
                        "unidad": ln.unidad,
                        "precio": ln.precio,
                        "subtotal": ln.subtotal,
                        "centros": ", ".join(
                            contabilidad.obtener_centro(db, d.centro_costo_id).codigo
                            for d in ln.distribuciones
                        ),
                    }
                    for ln in s.lineas
                ],
            }
        )
    return resultado


@router.get(
    "/articulos", response_model=list[ArticuloOpcion], summary="Artículos para líneas directas"
)
def articulos(
    texto: str | None = None,
    _: Usuario = Depends(requiere("compras.orden.crear")),
    db: Session = Depends(get_db),
):
    return [
        {
            "id": a.id,
            "codigo": a.codigo,
            "descripcion": a.descripcion,
            "tipo": a.tipo,
            "unidad": a.unidad,
            "unidades": [{"unidad": x.unidad, "factor": x.factor} for x in a.unidades_alternas],
            "precio_referencial": a.precio_referencial,
            "moneda_precio": a.moneda_precio,
        }
        for a in maestros.buscar_articulos(db, texto=texto, solo_activos=True, limite=50)
    ]


# ---------------------------------------------------------------- formato PDF


def _formato(f) -> dict:
    return {
        "configuracion": pdf.configuracion(f),
        "tiene_logo": bool(f.logo),
        "secciones": [{"codigo": k, "nombre": v} for k, v in pdf.SECCIONES.items()],
        "columnas": [{"codigo": k, "nombre": v} for k, v in pdf.COLUMNAS.items()],
    }


@router.get("/empresas/{empresa_id}/formato", response_model=FormatoSalida, summary="Formato PDF")
def formato(
    empresa_id: uuid.UUID,
    _: Usuario = Depends(requiere("compras.formato.editar")),
    db: Session = Depends(get_db),
):
    return _formato(pdf.obtener_formato(db, empresa_id))


@router.put(
    "/empresas/{empresa_id}/formato", response_model=FormatoSalida, summary="Guardar formato"
)
def guardar_formato(
    empresa_id: uuid.UUID,
    datos: FormatoDatos,
    actor: Usuario = Depends(requiere("compras.formato.editar")),
    db: Session = Depends(get_db),
):
    return _formato(pdf.guardar_formato(db, actor, empresa_id, datos.configuracion))


@router.post(
    "/empresas/{empresa_id}/formato/logo", response_model=FormatoSalida, summary="Subir logo"
)
async def subir_logo(
    empresa_id: uuid.UUID,
    archivo: UploadFile = File(...),
    actor: Usuario = Depends(requiere("compras.formato.editar")),
    db: Session = Depends(get_db),
):
    contenido = await archivo.read(pdf.TAMANO_MAXIMO_LOGO + 1)
    return _formato(pdf.cambiar_logo(db, actor, empresa_id, contenido))


@router.delete(
    "/empresas/{empresa_id}/formato/logo", response_model=FormatoSalida, summary="Quitar logo"
)
def quitar_logo(
    empresa_id: uuid.UUID,
    actor: Usuario = Depends(requiere("compras.formato.editar")),
    db: Session = Depends(get_db),
):
    return _formato(pdf.cambiar_logo(db, actor, empresa_id, None))


def _respuesta_pdf(contenido: bytes, nombre: str) -> Response:
    return Response(
        contenido,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{nombre}.pdf"'},
    )


@router.post(
    "/empresas/{empresa_id}/formato/vista-previa",
    summary="PDF de ejemplo con el formato enviado (sin guardarlo)",
    response_class=Response,
)
def vista_previa(
    empresa_id: uuid.UUID,
    datos: FormatoDatos,
    _: Usuario = Depends(requiere("compras.formato.editar")),
    db: Session = Depends(get_db),
):
    return _respuesta_pdf(pdf.pdf_vista_previa(db, empresa_id, datos.configuracion), "vista-previa")


# ---------------------------------------------------------------- reporte


@router.get(
    "/empresas/{empresa_id}/reporte",
    summary="Reporte Excel de solicitudes y órdenes",
    response_class=Response,
)
def reporte(
    empresa_id: uuid.UUID,
    desde: date | None = None,
    hasta: date | None = None,
    estado: str | None = None,
    proveedor_id: uuid.UUID | None = None,
    unidad_negocio_id: uuid.UUID | None = None,
    incluir_sin_orden: bool = True,
    usuario: Usuario = Depends(requiere("compras.orden.ver")),
    db: Session = Depends(get_db),
):
    contenido = reporte_excel.excel(
        db,
        usuario,
        empresa_id,
        desde=desde,
        hasta=hasta,
        estado=estado,
        proveedor_id=proveedor_id,
        unidad_negocio_id=unidad_negocio_id,
        incluir_sin_orden=incluir_sin_orden,
    )
    return Response(
        contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="compras-{date.today()}.xlsx"'},
    )


# ---------------------------------------------------------------- órdenes


@router.get("/bandeja", response_model=list[OrdenResumen], summary="Pendientes de mi aprobación")
def bandeja(usuario: Usuario = Depends(MODULO), db: Session = Depends(get_db)):
    return [_resumen(db, o) for o in service.bandeja(db, usuario)]


@router.get("/ordenes", response_model=list[OrdenResumen], summary="Listar órdenes de compra")
def listar(
    empresa_id: uuid.UUID,
    alcance: str = "mias",
    estado: str | None = None,
    usuario: Usuario = Depends(MODULO),
    db: Session = Depends(get_db),
):
    return [_resumen(db, o) for o in service.listar(db, usuario, empresa_id, alcance, estado)]


@router.post("/ordenes", response_model=OrdenSalida, status_code=201, summary="Emitir orden")
def crear(
    datos: OrdenCrear,
    actor: Usuario = Depends(requiere("compras.orden.crear")),
    db: Session = Depends(get_db),
):
    return _detalle(db, actor, service.crear(db, actor, datos.model_dump(exclude_unset=True)))


@router.get("/ordenes/{orden_id}", response_model=OrdenSalida, summary="Detalle de la orden")
def detalle(orden_id: uuid.UUID, usuario: Usuario = Depends(MODULO), db: Session = Depends(get_db)):
    return _detalle(db, usuario, service.ver(db, usuario, orden_id))


@router.put("/ordenes/{orden_id}", response_model=OrdenSalida, summary="Editar orden")
def cambiar(
    orden_id: uuid.UUID,
    datos: OrdenDatos,
    actor: Usuario = Depends(requiere("compras.orden.crear")),
    db: Session = Depends(get_db),
):
    return _detalle(
        db, actor, service.cambiar(db, actor, orden_id, datos.model_dump(exclude_unset=True))
    )


@router.get("/ordenes/{orden_id}/ruta", response_model=Ruta, summary="Quién aprobaría si se envía")
def ruta(orden_id: uuid.UUID, usuario: Usuario = Depends(MODULO), db: Session = Depends(get_db)):
    return service.ruta(db, usuario, orden_id)


@router.get(
    "/ordenes/{orden_id}/asiento",
    response_model=AsientoPrevio,
    summary="Vista previa del asiento contable (no se contabiliza)",
)
def asiento_orden(
    orden_id: uuid.UUID, usuario: Usuario = Depends(MODULO), db: Session = Depends(get_db)
):
    return asiento.vista_previa(db, service.ver(db, usuario, orden_id))


@router.get("/ordenes/{orden_id}/pdf", summary="PDF de la orden", response_class=Response)
def pdf_orden(
    orden_id: uuid.UUID, usuario: Usuario = Depends(MODULO), db: Session = Depends(get_db)
):
    orden = service.ver(db, usuario, orden_id)
    return _respuesta_pdf(pdf.pdf_orden(db, orden), orden.numero)


@router.post(
    "/ordenes/{orden_id}/enviar", response_model=OrdenSalida, summary="Enviar a aprobación"
)
def enviar(
    orden_id: uuid.UUID,
    actor: Usuario = Depends(requiere("compras.orden.crear")),
    db: Session = Depends(get_db),
):
    return _detalle(db, actor, service.enviar(db, actor, orden_id))


@router.post(
    "/ordenes/{orden_id}/enviada", response_model=OrdenSalida, summary="Marcar enviada al proveedor"
)
def marcar_enviada(
    orden_id: uuid.UUID,
    actor: Usuario = Depends(requiere("compras.orden.crear")),
    db: Session = Depends(get_db),
):
    return _detalle(db, actor, service.marcar_enviada(db, actor, orden_id))


def _accion(nombre: str, resumen: str):
    def ruta_accion(
        orden_id: uuid.UUID,
        datos: Comentario,
        actor: Usuario = Depends(MODULO),
        db: Session = Depends(get_db),
    ):
        return _detalle(db, actor, service.actuar(db, actor, orden_id, nombre, datos.comentario))

    router.add_api_route(
        f"/ordenes/{{orden_id}}/{nombre}",
        ruta_accion,
        methods=["POST"],
        response_model=OrdenSalida,
        summary=resumen,
        name=f"orden_{nombre}",
    )


_accion("aprobar", "Aprobar mi paso")
_accion("rechazar", "Rechazar (libera las solicitudes)")
_accion("devolver", "Devolver al comprador para corregir")


@router.post("/ordenes/{orden_id}/anular", response_model=OrdenSalida, summary="Anular orden")
def anular(
    orden_id: uuid.UUID,
    datos: Comentario,
    actor: Usuario = Depends(MODULO),
    db: Session = Depends(get_db),
):
    return _detalle(db, actor, service.anular(db, actor, orden_id, datos.comentario))
