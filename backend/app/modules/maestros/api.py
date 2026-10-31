"""Rutas del módulo de maestros: /api/v1/maestros/..."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.localizacion import PAISES
from app.modules.maestros import service
from app.modules.maestros.schemas import (
    CategoriaCambio,
    CategoriaCrear,
    CategoriaSalida,
    ConversionCrear,
    ConversionSalida,
    EmpresaCambio,
    EmpresaCrear,
    EmpresaResumen,
    EmpresaSalida,
    MonedaCambio,
    MonedaCrear,
    MonedaSalida,
    PaisSalida,
    TipoCambioEntrada,
    TipoCambioSalida,
    UnidadCambio,
    UnidadCrear,
    UnidadNegocioCambio,
    UnidadNegocioCrear,
    UnidadNegocioSalida,
    UnidadSalida,
)
from app.modules.seguridad.deps import requiere, usuario_actual
from app.modules.seguridad.models import Usuario

router = APIRouter()


def _sin_nulos(modelo) -> dict:
    return modelo.model_dump(exclude_unset=True, exclude_none=True)


# ---------------------------------------------------------------- países


@router.get("/paises", response_model=list[PaisSalida], summary="Países disponibles")
def paises(_: Usuario = Depends(requiere("maestros.empresa.ver"))):
    return [
        PaisSalida(
            codigo=p.codigo,
            nombre=p.nombre,
            moneda=p.moneda,
            nombre_identificacion_fiscal=p.nombre_identificacion_fiscal,
        )
        for p in PAISES.values()
    ]


# ---------------------------------------------------------------- empresas


@router.get("/empresas", response_model=list[EmpresaSalida], summary="Listar empresas")
def empresas(_: Usuario = Depends(requiere("maestros.empresa.ver")), db: Session = Depends(get_db)):
    return service.listar_empresas(db)


@router.get(
    "/empresas/accesibles",
    response_model=list[EmpresaResumen],
    summary="Empresas activas con las que el usuario puede trabajar (selector de empresa)",
)
def empresas_accesibles(_: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    # Hoy todas las activas; con el acceso por empresa (pendiente) se filtrará por usuario.
    return service.listar_empresas(db, solo_activas=True)


@router.post("/empresas", response_model=EmpresaSalida, status_code=201, summary="Crear empresa")
def crear_empresa(
    datos: EmpresaCrear,
    actor: Usuario = Depends(requiere("maestros.empresa.editar")),
    db: Session = Depends(get_db),
):
    return service.crear_empresa(db, actor, datos.model_dump())


@router.get("/empresas/{empresa_id}", response_model=EmpresaSalida, summary="Ver empresa")
def empresa(
    empresa_id: uuid.UUID,
    _: Usuario = Depends(requiere("maestros.empresa.ver")),
    db: Session = Depends(get_db),
):
    return service.obtener_empresa(db, empresa_id)


@router.patch("/empresas/{empresa_id}", response_model=EmpresaSalida, summary="Editar empresa")
def cambiar_empresa(
    empresa_id: uuid.UUID,
    datos: EmpresaCambio,
    actor: Usuario = Depends(requiere("maestros.empresa.editar")),
    db: Session = Depends(get_db),
):
    return service.cambiar_empresa(db, actor, empresa_id, datos.model_dump(exclude_unset=True))


@router.post(
    "/empresas/{empresa_id}/unidades-negocio",
    response_model=UnidadNegocioSalida,
    status_code=201,
    summary="Crear unidad de negocio",
)
def crear_unidad_negocio(
    empresa_id: uuid.UUID,
    datos: UnidadNegocioCrear,
    actor: Usuario = Depends(requiere("maestros.empresa.editar")),
    db: Session = Depends(get_db),
):
    return service.crear_unidad_negocio(db, actor, empresa_id, datos.codigo, datos.nombre)


@router.patch(
    "/unidades-negocio/{unidad_id}",
    response_model=UnidadNegocioSalida,
    summary="Editar unidad de negocio",
)
def cambiar_unidad_negocio(
    unidad_id: uuid.UUID,
    datos: UnidadNegocioCambio,
    actor: Usuario = Depends(requiere("maestros.empresa.editar")),
    db: Session = Depends(get_db),
):
    return service.cambiar_unidad_negocio(db, actor, unidad_id, _sin_nulos(datos))


# ---------------------------------------------------------------- monedas


@router.get("/monedas", response_model=list[MonedaSalida], summary="Listar monedas")
def monedas(_: Usuario = Depends(requiere("maestros.moneda.ver")), db: Session = Depends(get_db)):
    return service.listar_monedas(db)


@router.post("/monedas", response_model=MonedaSalida, status_code=201, summary="Agregar moneda")
def crear_moneda(
    datos: MonedaCrear,
    actor: Usuario = Depends(requiere("maestros.moneda.editar")),
    db: Session = Depends(get_db),
):
    return service.crear_moneda(db, actor, datos.model_dump())


@router.patch("/monedas/{codigo}", response_model=MonedaSalida, summary="Editar o activar moneda")
def cambiar_moneda(
    codigo: str,
    datos: MonedaCambio,
    actor: Usuario = Depends(requiere("maestros.moneda.editar")),
    db: Session = Depends(get_db),
):
    return service.cambiar_moneda(db, actor, codigo, _sin_nulos(datos))


# ---------------------------------------------------------------- tipo de cambio


@router.get("/tipos-cambio", response_model=list[TipoCambioSalida], summary="Historial")
def tipos_cambio(
    moneda: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    limite: int = Query(default=60, ge=1, le=400),
    _: Usuario = Depends(requiere("maestros.moneda.ver")),
    db: Session = Depends(get_db),
):
    return service.listar_tipos_cambio(db, moneda, desde, hasta, limite)


@router.get(
    "/tipos-cambio/vigente",
    response_model=TipoCambioSalida,
    summary="Tipo de cambio vigente en una fecha (último registrado en esa fecha o antes)",
)
def tipo_cambio_vigente(
    moneda: str,
    fecha: date | None = None,
    moneda_base: str = "PEN",
    _: Usuario = Depends(requiere("maestros.moneda.ver")),
    db: Session = Depends(get_db),
):
    return service.tipo_cambio_vigente(db, moneda, fecha or date.today(), moneda_base)


@router.put(
    "/tipos-cambio",
    response_model=TipoCambioSalida,
    summary="Registrar o corregir el tipo de cambio de una fecha",
)
def registrar_tipo_cambio(
    datos: TipoCambioEntrada,
    actor: Usuario = Depends(requiere("maestros.tipo_cambio.registrar")),
    db: Session = Depends(get_db),
):
    return service.registrar_tipo_cambio(db, actor, datos.model_dump())


# ---------------------------------------------------------------- unidades de medida


@router.get("/unidades-medida", response_model=list[UnidadSalida], summary="Listar unidades")
def unidades(_: Usuario = Depends(requiere("maestros.unidad.ver")), db: Session = Depends(get_db)):
    return service.listar_unidades(db)


@router.post(
    "/unidades-medida", response_model=UnidadSalida, status_code=201, summary="Crear unidad"
)
def crear_unidad(
    datos: UnidadCrear,
    actor: Usuario = Depends(requiere("maestros.unidad.editar")),
    db: Session = Depends(get_db),
):
    return service.crear_unidad(db, actor, datos.model_dump())


@router.patch("/unidades-medida/{codigo}", response_model=UnidadSalida, summary="Editar unidad")
def cambiar_unidad(
    codigo: str,
    datos: UnidadCambio,
    actor: Usuario = Depends(requiere("maestros.unidad.editar")),
    db: Session = Depends(get_db),
):
    return service.cambiar_unidad(db, actor, codigo, _sin_nulos(datos))


@router.get("/conversiones", response_model=list[ConversionSalida], summary="Conversiones")
def conversiones(
    _: Usuario = Depends(requiere("maestros.unidad.ver")), db: Session = Depends(get_db)
):
    return service.listar_conversiones(db)


@router.post(
    "/conversiones", response_model=ConversionSalida, status_code=201, summary="Crear conversión"
)
def crear_conversion(
    datos: ConversionCrear,
    actor: Usuario = Depends(requiere("maestros.unidad.editar")),
    db: Session = Depends(get_db),
):
    return service.crear_conversion(db, actor, datos.origen, datos.destino, datos.factor)


@router.delete("/conversiones/{conversion_id}", status_code=204, summary="Eliminar conversión")
def eliminar_conversion(
    conversion_id: uuid.UUID,
    actor: Usuario = Depends(requiere("maestros.unidad.editar")),
    db: Session = Depends(get_db),
):
    service.eliminar_conversion(db, actor, conversion_id)
    return Response(status_code=204)


# ---------------------------------------------------------------- categorías


@router.get(
    "/categorias", response_model=list[CategoriaSalida], summary="Árbol de categorías (en orden)"
)
def categorias(
    _: Usuario = Depends(requiere("maestros.categoria.ver")), db: Session = Depends(get_db)
):
    return service.listar_categorias(db)


@router.post(
    "/categorias", response_model=CategoriaSalida, status_code=201, summary="Crear categoría"
)
def crear_categoria(
    datos: CategoriaCrear,
    actor: Usuario = Depends(requiere("maestros.categoria.editar")),
    db: Session = Depends(get_db),
):
    return service.crear_categoria(db, actor, datos.codigo, datos.nombre, datos.padre_id)


@router.patch(
    "/categorias/{categoria_id}",
    response_model=CategoriaSalida,
    summary="Renombrar, mover o desactivar categoría",
)
def cambiar_categoria(
    categoria_id: uuid.UUID,
    datos: CategoriaCambio,
    actor: Usuario = Depends(requiere("maestros.categoria.editar")),
    db: Session = Depends(get_db),
):
    cambios = datos.model_dump(exclude_unset=True)
    for campo in ("nombre", "activo"):
        if cambios.get(campo, "") is None:
            cambios.pop(campo)
    return service.cambiar_categoria(db, actor, categoria_id, cambios)
