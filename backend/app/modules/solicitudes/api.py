"""Rutas de solicitudes de compra y reglas de aprobación: /api/v1/solicitudes/..."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import ErrorERP
from app.modules.aprobaciones import service as aprobaciones
from app.modules.aprobaciones.models import MAX_NIVELES, MODOS, TIPOS_APROBADOR, Regla
from app.modules.contabilidad import service as contabilidad
from app.modules.maestros import datos_base
from app.modules.maestros import service as maestros
from app.modules.maestros.deps import acceso_empresa_de_ruta
from app.modules.seguridad import atributos
from app.modules.seguridad import service as seguridad
from app.modules.seguridad.deps import requiere, usuario_actual
from app.modules.seguridad.models import Rol, Usuario
from app.modules.solicitudes import service
from app.modules.solicitudes.models import ESTADOS, Solicitud
from app.modules.solicitudes.schemas import (
    ArticuloOpcion,
    CatalogoAprobacion,
    Comentario,
    OpcionesEmpresa,
    ReglaDatos,
    ReglaSalida,
    Ruta,
    SolicitudCrear,
    SolicitudDatos,
    SolicitudResumen,
    SolicitudSalida,
)

router = APIRouter(dependencies=[Depends(acceso_empresa_de_ruta)])
DOC = service.DOCUMENTO


def modulo_activo(usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Para las rutas sin permiso propio (aprobar, bandeja): basta con el módulo activo."""
    if "solicitudes" not in seguridad.modulos_activos(db):
        raise ErrorERP(403, "modulo_inactivo", "El módulo solicitudes no está activo")
    return usuario


# ---------------------------------------------------------------- presentación


def _nombre(db: Session, modelo, id_, campo="nombre") -> str:
    obj = db.get(modelo, id_) if id_ else None
    return getattr(obj, campo) if obj else "—"


def _condiciones(db: Session, c) -> list[str]:
    partes = []
    if c.unidad_negocio_id:
        partes.append(f"Unidad {maestros.obtener_unidad_negocio(db, c.unidad_negocio_id).nombre}")
    if c.categoria_id:
        cat = maestros.obtener_categoria(db, c.categoria_id)
        partes.append(f"Categoría {cat.codigo}")
    if getattr(c, "tipo_articulo", None):
        partes.append(datos_base.TIPOS_ARTICULO.get(c.tipo_articulo, c.tipo_articulo))
    if c.centro_costo_id:
        partes.append(f"Centro {contabilidad.obtener_centro(db, c.centro_costo_id).codigo}")
    return partes


def _aprobador(db: Session, a) -> dict:
    if a.tipo == "usuario":
        base = _nombre(db, Usuario, a.usuario_id)
    elif a.tipo == "rol":
        base = f"Rol {_nombre(db, Rol, a.rol_id)}"
    else:
        base = TIPOS_APROBADOR[a.tipo]
    condiciones = _condiciones(db, a)
    return {
        "tipo": a.tipo,
        "usuario_id": a.usuario_id,
        "rol_id": a.rol_id,
        "unidad_negocio_id": a.unidad_negocio_id,
        "categoria_id": a.categoria_id,
        "centro_costo_id": a.centro_costo_id,
        "descripcion": base + (f" · solo si {', '.join(condiciones)}" if condiciones else ""),
    }


def _regla(db: Session, r: Regla) -> dict:
    condiciones = _condiciones(db, r)
    return {
        "id": r.id,
        "empresa_id": r.empresa_id,
        "nombre": r.nombre,
        "prioridad": r.prioridad,
        "activo": r.activo,
        "unidad_negocio_id": r.unidad_negocio_id,
        "categoria_id": r.categoria_id,
        "tipo_articulo": r.tipo_articulo,
        "centro_costo_id": r.centro_costo_id,
        "condiciones": " · ".join(condiciones) if condiciones else "Todas las solicitudes",
        "niveles": [
            {
                "numero": n.numero,
                "monto_desde": n.monto_desde,
                "modo": n.modo,
                "aprobadores": [_aprobador(db, a) for a in n.aprobadores],
            }
            for n in r.niveles
        ],
    }


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
        "solicitante": _nombre(db, Usuario, sol.solicitante_id),
        "moneda": sol.moneda,
        "total": sol.total,
        "total_funcional": sol.total_funcional,
        "estado": sol.estado,
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


# ---------------------------------------------------------------- catálogo y reglas


@router.get("/catalogo", response_model=CatalogoAprobacion, summary="Modos, tipos y estados")
def catalogo(_: Usuario = Depends(modulo_activo)):
    return {
        "modos": [{"codigo": k, "nombre": v} for k, v in MODOS.items()],
        "tipos_aprobador": [{"codigo": k, "nombre": v} for k, v in TIPOS_APROBADOR.items()],
        "estados": [{"codigo": k, "nombre": v} for k, v in ESTADOS.items()],
        "max_niveles": MAX_NIVELES,
    }


@router.get(
    "/empresas/{empresa_id}/reglas",
    response_model=list[ReglaSalida],
    summary="Reglas de aprobación de solicitudes de la empresa",
)
def reglas(
    empresa_id: uuid.UUID,
    _: Usuario = Depends(requiere("solicitudes.regla.ver")),
    db: Session = Depends(get_db),
):
    return [_regla(db, r) for r in aprobaciones.listar_reglas(db, empresa_id, DOC)]


@router.post(
    "/empresas/{empresa_id}/reglas",
    response_model=ReglaSalida,
    status_code=201,
    summary="Crear regla de aprobación",
)
def crear_regla(
    empresa_id: uuid.UUID,
    datos: ReglaDatos,
    actor: Usuario = Depends(requiere("solicitudes.regla.editar")),
    db: Session = Depends(get_db),
):
    regla = aprobaciones.guardar_regla(db, actor, DOC, datos.model_dump(), empresa_id=empresa_id)
    return _regla(db, regla)


@router.put("/reglas/{regla_id}", response_model=ReglaSalida, summary="Reemplazar una regla")
def cambiar_regla(
    regla_id: uuid.UUID,
    datos: ReglaDatos,
    actor: Usuario = Depends(requiere("solicitudes.regla.editar")),
    db: Session = Depends(get_db),
):
    maestros.verificar_acceso_empresa(
        db, actor, aprobaciones.obtener_regla(db, regla_id).empresa_id
    )
    regla = aprobaciones.guardar_regla(db, actor, DOC, datos.model_dump(), regla_id=regla_id)
    return _regla(db, regla)


@router.get(
    "/empresas/{empresa_id}/opciones",
    response_model=OpcionesEmpresa,
    summary="Unidades, centros de costo, categorías y tipos para los formularios",
)
def opciones(
    empresa_id: uuid.UUID,
    usuario: Usuario = Depends(modulo_activo),
    db: Session = Depends(get_db),
):
    empresa = maestros.obtener_empresa(db, empresa_id)
    return {
        "unidades": [
            {"id": un.id, "codigo": un.codigo, "nombre": un.nombre}
            for un in maestros.unidades_permitidas(db, usuario, empresa)
            if un.activo
        ],
        "centros": [
            {"id": c.id, "codigo": c.codigo, "nombre": c.nombre}
            for c in contabilidad.listar_centros(db, empresa_id)
            if c.activo
        ],
        "categorias": [
            {"id": c.id, "codigo": c.codigo, "nombre": "· " * (c.nivel - 1) + c.nombre}
            for c in maestros.listar_categorias(db)
            if c.activo
        ],
        "tipos_articulo": [
            {"codigo": k, "nombre": v} for k, v in datos_base.TIPOS_ARTICULO.items()
        ],
    }


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
def bandeja(usuario: Usuario = Depends(modulo_activo), db: Session = Depends(get_db)):
    return [_resumen(db, s) for s in service.bandeja(db, usuario)]


@router.get("", response_model=list[SolicitudResumen], summary="Listar solicitudes")
def listar(
    empresa_id: uuid.UUID,
    alcance: str = "mias",
    estado: str | None = None,
    usuario: Usuario = Depends(modulo_activo),
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
    usuario: Usuario = Depends(modulo_activo),
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
    usuario: Usuario = Depends(modulo_activo),
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
        actor: Usuario = Depends(modulo_activo),
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
    actor: Usuario = Depends(modulo_activo),
    db: Session = Depends(get_db),
):
    return _detalle(db, actor, service.anular(db, actor, solicitud_id, datos.comentario))
