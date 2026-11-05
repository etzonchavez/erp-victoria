"""Rutas de solicitudes de compra y reglas de aprobación: /api/v1/solicitudes/..."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.aprobaciones import presentacion
from app.modules.contabilidad import service as contabilidad
from app.modules.maestros import service as maestros
from app.modules.maestros.deps import acceso_empresa_de_ruta
from app.modules.seguridad import atributos
from app.modules.seguridad.deps import modulo_activo, requiere
from app.modules.seguridad.models import Usuario
from app.modules.solicitudes import service
from app.modules.solicitudes.models import Solicitud
from app.modules.solicitudes.schemas import (
    ArticuloOpcion,
    Comentario,
    OpcionesEmpresa,
    Ruta,
    SolicitudCrear,
    SolicitudDatos,
    SolicitudResumen,
    SolicitudSalida,
)

router = APIRouter(dependencies=[Depends(acceso_empresa_de_ruta)])
MODULO = modulo_activo("solicitudes")
DOC = service.DOCUMENTO


# ---------------------------------------------------------------- presentación


def _pendiente_de(db: Session, sol: Solicitud) -> list[str]:
    if sol.estado != "en_aprobacion":
        return []
    return [
        p.descripcion
        for p in service.historial(db, sol)
        if p.ronda == sol.ronda and p.estado == "pendiente"
    ]


def _resumen(db: Session, sol: Solicitud) -> dict:
    return {
        "id": sol.id,
        "numero": sol.numero,
        "titulo": sol.titulo,
        "fecha": sol.fecha,
        "fecha_requerida": sol.fecha_requerida,
        "empresa_id": sol.empresa_id,
        "unidad_negocio_id": sol.unidad_negocio_id,
        "unidad_negocio": maestros.obtener_unidad_negocio(db, sol.unidad_negocio_id).nombre,
        "solicitante_id": sol.solicitante_id,
        "solicitante": presentacion.nombre(db, Usuario, sol.solicitante_id),
        "moneda": sol.moneda,
        "total": sol.total,
        "total_funcional": sol.total_funcional,
        "estado": sol.estado,
        "orden_compra_numero": sol.orden_compra_numero,
        "pendiente_de": _pendiente_de(db, sol),
    }


def _detalle(db: Session, usuario: Usuario, sol: Solicitud) -> dict:
    lineas = []
    for linea in sol.lineas:
        art = maestros.obtener_articulo(db, linea.articulo_id)
        cuenta = contabilidad.obtener_cuenta(db, linea.cuenta_id) if linea.cuenta_id else None
        lineas.append(
            {
                "numero": linea.numero,
                "articulo_id": art.id,
                "articulo": art.codigo,
                "descripcion": linea.descripcion,
                "cantidad": linea.cantidad,
                "unidad": linea.unidad,
                "cantidad_base": linea.cantidad_base,
                "unidad_base": art.unidad,
                "precio": linea.precio,
                "subtotal": linea.subtotal,
                "cuenta": f"{cuenta.codigo} {cuenta.nombre}" if cuenta else None,
                "atributos": atributos.leer_valores(linea, DOC, "linea", db),
                "distribuciones": [
                    {
                        "centro_costo_id": d.centro_costo_id,
                        "centro_costo": contabilidad.obtener_centro(db, d.centro_costo_id).codigo,
                        "porcentaje": d.porcentaje,
                        "monto": d.monto,
                        "atributos": atributos.leer_valores(d, DOC, "distribucion", db),
                    }
                    for d in linea.distribuciones
                ],
            }
        )
    return {
        **_resumen(db, sol),
        "justificacion": sol.justificacion,
        "tipo_cambio": sol.tipo_cambio,
        "ronda": sol.ronda,
        "lineas": lineas,
        "atributos": atributos.leer_valores(sol, DOC, "cabecera", db),
        "pasos": service.historial(db, sol),
        "acciones": service.acciones(db, usuario, sol),
    }


# ---------------------------------------------------------------- listas de apoyo


@router.get(
    "/empresas/{empresa_id}/opciones",
    response_model=OpcionesEmpresa,
    summary="Unidades, centros de costo, categorías y tipos para los formularios",
)
def opciones(
    empresa_id: uuid.UUID,
    usuario: Usuario = Depends(MODULO),
    db: Session = Depends(get_db),
):
    return presentacion.opciones_empresa(db, usuario, empresa_id)


@router.get(
    "/articulos",
    response_model=list[ArticuloOpcion],
    summary="Buscar artículos activos para las líneas",
)
def articulos(
    texto: str | None = None,
    _: Usuario = Depends(requiere("solicitudes.solicitud.crear")),
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


# ---------------------------------------------------------------- solicitudes


@router.get(
    "/bandeja", response_model=list[SolicitudResumen], summary="Pendientes de mi aprobación"
)
def bandeja(usuario: Usuario = Depends(MODULO), db: Session = Depends(get_db)):
    return [_resumen(db, s) for s in service.bandeja(db, usuario)]


@router.get("", response_model=list[SolicitudResumen], summary="Listar solicitudes")
def listar(
    empresa_id: uuid.UUID,
    alcance: str = "mias",
    estado: str | None = None,
    usuario: Usuario = Depends(MODULO),
    db: Session = Depends(get_db),
):
    return [_resumen(db, s) for s in service.listar(db, usuario, empresa_id, alcance, estado)]


@router.post("", response_model=SolicitudSalida, status_code=201, summary="Registrar solicitud")
def crear(
    datos: SolicitudCrear,
    actor: Usuario = Depends(requiere("solicitudes.solicitud.crear")),
    db: Session = Depends(get_db),
):
    sol = service.crear(db, actor, datos.model_dump())
    return _detalle(db, actor, sol)


@router.get("/{solicitud_id}", response_model=SolicitudSalida, summary="Detalle de solicitud")
def detalle(
    solicitud_id: uuid.UUID,
    usuario: Usuario = Depends(MODULO),
    db: Session = Depends(get_db),
):
    return _detalle(db, usuario, service.ver(db, usuario, solicitud_id))


@router.put("/{solicitud_id}", response_model=SolicitudSalida, summary="Editar solicitud")
def cambiar(
    solicitud_id: uuid.UUID,
    datos: SolicitudDatos,
    actor: Usuario = Depends(requiere("solicitudes.solicitud.crear")),
    db: Session = Depends(get_db),
):
    return _detalle(db, actor, service.cambiar(db, actor, solicitud_id, datos.model_dump()))


@router.get("/{solicitud_id}/ruta", response_model=Ruta, summary="Quién aprobaría si se envía")
def ruta(
    solicitud_id: uuid.UUID,
    usuario: Usuario = Depends(MODULO),
    db: Session = Depends(get_db),
):
    return service.ruta(db, usuario, solicitud_id)


@router.post(
    "/{solicitud_id}/enviar", response_model=SolicitudSalida, summary="Enviar a aprobación"
)
def enviar(
    solicitud_id: uuid.UUID,
    actor: Usuario = Depends(requiere("solicitudes.solicitud.crear")),
    db: Session = Depends(get_db),
):
    return _detalle(db, actor, service.enviar(db, actor, solicitud_id))


def _accion(nombre: str, resumen: str):
    def ruta_accion(
        solicitud_id: uuid.UUID,
        datos: Comentario,
        actor: Usuario = Depends(MODULO),
        db: Session = Depends(get_db),
    ):
        sol = service.actuar(db, actor, solicitud_id, nombre, datos.comentario)
        return _detalle(db, actor, sol)

    router.add_api_route(
        f"/{{solicitud_id}}/{nombre}",
        ruta_accion,
        methods=["POST"],
        response_model=SolicitudSalida,
        summary=resumen,
        name=nombre,
    )


_accion("aprobar", "Aprobar mi paso")
_accion("rechazar", "Rechazar (termina el flujo)")
_accion("devolver", "Devolver al solicitante para corregir")


@router.post("/{solicitud_id}/anular", response_model=SolicitudSalida, summary="Anular solicitud")
def anular(
    solicitud_id: uuid.UUID,
    datos: Comentario,
    actor: Usuario = Depends(MODULO),
    db: Session = Depends(get_db),
):
    return _detalle(db, actor, service.anular(db, actor, solicitud_id, datos.comentario))
