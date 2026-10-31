"""Rutas de la carga desde Excel: /api/v1/importacion/..."""

import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.importacion import service
from app.modules.seguridad.deps import usuario_actual
from app.modules.seguridad.models import Usuario

router = APIRouter()

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class TipoSalida(BaseModel):
    codigo: str
    nombre: str
    permiso: str
    por_empresa: bool


class FilaSalida(BaseModel):
    fila: int
    clave: str
    error: str | None


class ResultadoSalida(BaseModel):
    tipo: str
    total: int
    validas: int
    errores: int
    cargado: bool
    filas: list[FilaSalida]


@router.get("/tipos", response_model=list[TipoSalida], summary="Qué se puede cargar")
def tipos(_: Usuario = Depends(usuario_actual)):
    return [
        TipoSalida(codigo=t.codigo, nombre=t.nombre, permiso=t.permiso, por_empresa=t.por_empresa)
        for t in service.TIPOS.values()
    ]


@router.get("/{tipo}/plantilla", summary="Descargar la plantilla de Excel")
def plantilla(tipo: str, _: Usuario = Depends(usuario_actual)):
    return Response(
        service.plantilla(tipo),
        media_type=XLSX,
        headers={"Content-Disposition": f'attachment; filename="victoria-{tipo}.xlsx"'},
    )


async def _procesar(tipo, archivo, empresa_id, actor, db, confirmar):
    contenido = await archivo.read(service.MAX_BYTES + 1)
    return service.procesar(db, actor, tipo, contenido, empresa_id, confirmar)


@router.post(
    "/{tipo}/validar",
    response_model=ResultadoSalida,
    summary="Vista previa: valida todas las filas sin guardar nada",
)
async def validar(
    tipo: str,
    archivo: UploadFile = File(...),
    empresa_id: uuid.UUID | None = Form(default=None),
    actor: Usuario = Depends(usuario_actual),
    db: Session = Depends(get_db),
):
    return await _procesar(tipo, archivo, empresa_id, actor, db, confirmar=False)


@router.post(
    "/{tipo}/cargar",
    response_model=ResultadoSalida,
    summary="Carga todo o nada: si una fila tiene error no se guarda ninguna",
)
async def cargar(
    tipo: str,
    archivo: UploadFile = File(...),
    empresa_id: uuid.UUID | None = Form(default=None),
    actor: Usuario = Depends(usuario_actual),
    db: Session = Depends(get_db),
):
    return await _procesar(tipo, archivo, empresa_id, actor, db, confirmar=True)
