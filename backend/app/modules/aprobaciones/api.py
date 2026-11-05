"""Reglas de aprobación de cualquier documento: /api/v1/aprobaciones/...

El permiso depende del documento: solicitudes.regla.* para solicitudes, compras.regla.* para
órdenes de compra.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import ErrorERP
from app.modules.aprobaciones import presentacion
from app.modules.aprobaciones import service as aprobaciones
from app.modules.aprobaciones.models import DOCUMENTOS, MAX_NIVELES, MODOS, TIPOS_APROBADOR
from app.modules.aprobaciones.schemas import (
    CatalogoAprobacion,
    OpcionesEmpresa,
    ReglaDatos,
    ReglaSalida,
)
from app.modules.maestros import service as maestros
from app.modules.maestros.deps import acceso_empresa_de_ruta
from app.modules.seguridad import service as seguridad
from app.modules.seguridad.deps import usuario_actual
from app.modules.seguridad.models import Usuario

router = APIRouter(dependencies=[Depends(acceso_empresa_de_ruta)])


def _permiso(db: Session, usuario: Usuario, documento: str, accion: str) -> None:
    if documento not in DOCUMENTOS:
        raise ErrorERP(422, "documento_invalido", "Documento inexistente")
    seguridad.verificar_permiso(db, usuario, f"{DOCUMENTOS[documento][1]}.{accion}")


@router.get("/catalogo", response_model=CatalogoAprobacion, summary="Documentos, modos y tipos")
def catalogo(usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    permisos = seguridad.permisos_de(db, usuario)
    return {
        "documentos": [
            {"codigo": k, "nombre": v[0]}
            for k, v in DOCUMENTOS.items()
            if f"{v[1]}.ver" in permisos
        ],
        "modos": [{"codigo": k, "nombre": v} for k, v in MODOS.items()],
        "tipos_aprobador": [{"codigo": k, "nombre": v} for k, v in TIPOS_APROBADOR.items()],
        "max_niveles": MAX_NIVELES,
    }


@router.get(
    "/empresas/{empresa_id}/opciones",
    response_model=OpcionesEmpresa,
    summary="Unidades, centros de costo, categorías y tipos para las condiciones",
)
def opciones(
    empresa_id: uuid.UUID,
    usuario: Usuario = Depends(usuario_actual),
    db: Session = Depends(get_db),
):
    return presentacion.opciones_empresa(db, usuario, empresa_id)


@router.get(
    "/empresas/{empresa_id}/reglas",
    response_model=list[ReglaSalida],
    summary="Reglas de aprobación de un documento en la empresa",
)
def reglas(
    empresa_id: uuid.UUID,
    documento: str,
    usuario: Usuario = Depends(usuario_actual),
    db: Session = Depends(get_db),
):
    _permiso(db, usuario, documento, "ver")
    return [
        presentacion.regla(db, r) for r in aprobaciones.listar_reglas(db, empresa_id, documento)
    ]


@router.post(
    "/empresas/{empresa_id}/reglas",
    response_model=ReglaSalida,
    status_code=201,
    summary="Crear regla de aprobación",
)
def crear_regla(
    empresa_id: uuid.UUID,
    documento: str,
    datos: ReglaDatos,
    actor: Usuario = Depends(usuario_actual),
    db: Session = Depends(get_db),
):
    _permiso(db, actor, documento, "editar")
    regla = aprobaciones.guardar_regla(
        db, actor, documento, datos.model_dump(), empresa_id=empresa_id
    )
    return presentacion.regla(db, regla)


@router.put("/reglas/{regla_id}", response_model=ReglaSalida, summary="Reemplazar una regla")
def cambiar_regla(
    regla_id: uuid.UUID,
    datos: ReglaDatos,
    actor: Usuario = Depends(usuario_actual),
    db: Session = Depends(get_db),
):
    regla = aprobaciones.obtener_regla(db, regla_id)
    _permiso(db, actor, regla.documento, "editar")
    maestros.verificar_acceso_empresa(db, actor, regla.empresa_id)
    regla = aprobaciones.guardar_regla(
        db, actor, regla.documento, datos.model_dump(), regla_id=regla_id
    )
    return presentacion.regla(db, regla)
