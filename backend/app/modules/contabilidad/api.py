"""Rutas de la contabilidad base: /api/v1/contabilidad/..."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.contabilidad import service
from app.modules.contabilidad.schemas import (
    ArticuloPerfilCambio,
    CategoriaPerfilCambio,
    CategoriaPerfilSalida,
    CentroCambio,
    CentroCrear,
    CentroSalida,
    CuentaCambio,
    CuentaCrear,
    CuentaSalida,
    EstadoContableEmpresa,
    ImpuestoCambio,
    ImpuestoCrear,
    ImpuestoSalida,
    Opcion,
    PerfilCambio,
    PerfilCrear,
    PerfilSalida,
    PlantillaResultado,
    SugeridosResultado,
)
from app.modules.maestros import service as maestros
from app.modules.seguridad.deps import requiere
from app.modules.seguridad.models import Usuario

router = APIRouter()


def _cambios(modelo) -> dict:
    """Campos enviados; en relaciones opcionales null significa "quitar la cuenta"."""
    return modelo.model_dump(exclude_unset=True)


@router.get("/tipos-articulo", response_model=list[Opcion], summary="Tipos de artículo")
def tipos_articulo(_: Usuario = Depends(requiere("contabilidad.perfil.ver"))):
    return [Opcion(codigo=c, nombre=n) for c, n in service.TIPOS_ARTICULO.items()]


@router.post(
    "/empresas/{empresa_id}/plantilla",
    response_model=PlantillaResultado,
    summary="Cargar la plantilla contable del país (solo si la empresa no tiene plan)",
)
def cargar_plantilla(
    empresa_id: uuid.UUID,
    actor: Usuario = Depends(requiere("contabilidad.cuenta.editar")),
    db: Session = Depends(get_db),
):
    empresa = maestros.obtener_empresa(db, empresa_id)
    return PlantillaResultado(cuentas=service.cargar_plantilla(db, actor, empresa))


# ---------------------------------------------------------------- plan de cuentas


@router.get("/empresas/{empresa_id}/cuentas", response_model=list[CuentaSalida], summary="Plan")
def cuentas(
    empresa_id: uuid.UUID,
    _: Usuario = Depends(requiere("contabilidad.cuenta.ver")),
    db: Session = Depends(get_db),
):
    return service.listar_cuentas(db, empresa_id)


@router.post(
    "/empresas/{empresa_id}/cuentas",
    response_model=CuentaSalida,
    status_code=201,
    summary="Crear cuenta o subcuenta",
)
def crear_cuenta(
    empresa_id: uuid.UUID,
    datos: CuentaCrear,
    actor: Usuario = Depends(requiere("contabilidad.cuenta.editar")),
    db: Session = Depends(get_db),
):
    return service.crear_cuenta(db, actor, empresa_id, datos.codigo, datos.nombre, datos.naturaleza)


@router.patch("/cuentas/{cuenta_id}", response_model=CuentaSalida, summary="Editar cuenta")
def cambiar_cuenta(
    cuenta_id: uuid.UUID,
    datos: CuentaCambio,
    actor: Usuario = Depends(requiere("contabilidad.cuenta.editar")),
    db: Session = Depends(get_db),
):
    return service.cambiar_cuenta(db, actor, cuenta_id, datos.model_dump(exclude_none=True))


# ---------------------------------------------------------------- perfiles


@router.get(
    "/empresas/{empresa_id}/perfiles", response_model=list[PerfilSalida], summary="Perfiles"
)
def perfiles(
    empresa_id: uuid.UUID,
    _: Usuario = Depends(requiere("contabilidad.perfil.ver")),
    db: Session = Depends(get_db),
):
    return service.listar_perfiles(db, empresa_id)


@router.post(
    "/empresas/{empresa_id}/perfiles",
    response_model=PerfilSalida,
    status_code=201,
    summary="Crear perfil contable",
)
def crear_perfil(
    empresa_id: uuid.UUID,
    datos: PerfilCrear,
    actor: Usuario = Depends(requiere("contabilidad.perfil.editar")),
    db: Session = Depends(get_db),
):
    return service.crear_perfil(db, actor, empresa_id, datos.model_dump())


@router.patch("/perfiles/{perfil_id}", response_model=PerfilSalida, summary="Editar perfil")
def cambiar_perfil(
    perfil_id: uuid.UUID,
    datos: PerfilCambio,
    actor: Usuario = Depends(requiere("contabilidad.perfil.editar")),
    db: Session = Depends(get_db),
):
    cambios = _cambios(datos)
    for campo in ("nombre", "activo", "cuenta_cargo_id", "cuenta_por_pagar_id"):
        if cambios.get(campo, "") is None:
            cambios.pop(campo)
    return service.cambiar_perfil(db, actor, perfil_id, cambios)


# ---------------------------------------------------------------- centros de costo


@router.get(
    "/empresas/{empresa_id}/centros-costo",
    response_model=list[CentroSalida],
    summary="Centros de costo",
)
def centros(
    empresa_id: uuid.UUID,
    _: Usuario = Depends(requiere("contabilidad.centro_costo.ver")),
    db: Session = Depends(get_db),
):
    return service.listar_centros(db, empresa_id)


@router.post(
    "/empresas/{empresa_id}/centros-costo",
    response_model=CentroSalida,
    status_code=201,
    summary="Crear centro de costo",
)
def crear_centro(
    empresa_id: uuid.UUID,
    datos: CentroCrear,
    actor: Usuario = Depends(requiere("contabilidad.centro_costo.editar")),
    db: Session = Depends(get_db),
):
    return service.crear_centro(db, actor, empresa_id, datos.model_dump())


@router.patch("/centros-costo/{centro_id}", response_model=CentroSalida, summary="Editar centro")
def cambiar_centro(
    centro_id: uuid.UUID,
    datos: CentroCambio,
    actor: Usuario = Depends(requiere("contabilidad.centro_costo.editar")),
    db: Session = Depends(get_db),
):
    cambios = _cambios(datos)
    for campo in ("nombre", "activo", "unidad_negocio_id"):
        if cambios.get(campo, "") is None:
            cambios.pop(campo)
    return service.cambiar_centro(db, actor, centro_id, cambios)


# ---------------------------------------------------------------- impuestos


@router.get(
    "/empresas/{empresa_id}/impuestos", response_model=list[ImpuestoSalida], summary="Impuestos"
)
def impuestos(
    empresa_id: uuid.UUID,
    _: Usuario = Depends(requiere("contabilidad.impuesto.ver")),
    db: Session = Depends(get_db),
):
    return service.listar_impuestos(db, empresa_id)


@router.post(
    "/empresas/{empresa_id}/impuestos",
    response_model=ImpuestoSalida,
    status_code=201,
    summary="Crear impuesto",
)
def crear_impuesto(
    empresa_id: uuid.UUID,
    datos: ImpuestoCrear,
    actor: Usuario = Depends(requiere("contabilidad.impuesto.editar")),
    db: Session = Depends(get_db),
):
    return service.crear_impuesto(db, actor, empresa_id, datos.model_dump())


@router.patch("/impuestos/{impuesto_id}", response_model=ImpuestoSalida, summary="Editar impuesto")
def cambiar_impuesto(
    impuesto_id: uuid.UUID,
    datos: ImpuestoCambio,
    actor: Usuario = Depends(requiere("contabilidad.impuesto.editar")),
    db: Session = Depends(get_db),
):
    cambios = _cambios(datos)
    for campo in ("nombre", "activo", "tasa"):
        if cambios.get(campo, "") is None:
            cambios.pop(campo)
    return service.cambiar_impuesto(db, actor, impuesto_id, cambios)


# ---------------------------------------------------------------- categorías de artículo


@router.get(
    "/empresas/{empresa_id}/categorias",
    response_model=list[CategoriaPerfilSalida],
    summary="Perfil propio y efectivo (heredado) de cada categoría en la empresa",
)
def categorias(
    empresa_id: uuid.UUID,
    _: Usuario = Depends(requiere("contabilidad.perfil.ver")),
    db: Session = Depends(get_db),
):
    return service.categorias_con_perfil(db, empresa_id)


@router.put(
    "/empresas/{empresa_id}/categorias/{categoria_id}/perfil",
    response_model=list[CategoriaPerfilSalida],
    summary="Asignar perfil a una categoría (null = heredar del padre)",
)
def asignar_perfil(
    empresa_id: uuid.UUID,
    categoria_id: uuid.UUID,
    datos: CategoriaPerfilCambio,
    actor: Usuario = Depends(requiere("contabilidad.perfil.editar")),
    db: Session = Depends(get_db),
):
    service.asignar_perfil_categoria(db, actor, empresa_id, categoria_id, datos.perfil_id)
    return service.categorias_con_perfil(db, empresa_id)


@router.post(
    "/empresas/{empresa_id}/sugeridos",
    response_model=SugeridosResultado,
    summary="Completar perfiles de la plantilla y perfiles sugeridos de las categorías de ejemplo",
)
def sugeridos(
    empresa_id: uuid.UUID,
    actor: Usuario = Depends(requiere("contabilidad.perfil.editar")),
    db: Session = Depends(get_db),
):
    empresa = maestros.obtener_empresa(db, empresa_id)
    return service.aplicar_sugeridos(db, actor, empresa)


# ---------------------------------------------------------------- artículos


@router.get(
    "/articulos/{articulo_id}/estado",
    response_model=list[EstadoContableEmpresa],
    summary="Perfil, cuentas e impuesto del artículo en cada empresa, y si se puede comprar",
)
def estado_articulo(
    articulo_id: uuid.UUID,
    _: Usuario = Depends(requiere("maestros.articulo.ver")),
    db: Session = Depends(get_db),
):
    # Usa el permiso de maestros: quien ve el artículo ve en qué empresas se puede comprar.
    return service.estado_contable(db, maestros.obtener_articulo(db, articulo_id))


@router.put(
    "/empresas/{empresa_id}/articulos/{articulo_id}/perfil",
    response_model=list[EstadoContableEmpresa],
    summary="Excepción contable del artículo en una empresa (null = usar la de su categoría)",
)
def excepcion_articulo(
    empresa_id: uuid.UUID,
    articulo_id: uuid.UUID,
    datos: ArticuloPerfilCambio,
    actor: Usuario = Depends(requiere("contabilidad.perfil.editar")),
    db: Session = Depends(get_db),
):
    service.asignar_perfil_articulo(db, actor, empresa_id, articulo_id, datos.perfil_id)
    return service.estado_contable(db, maestros.obtener_articulo(db, articulo_id))


@router.get(
    "/impuestos/codigos",
    response_model=list[str],
    summary="Códigos de impuesto usados en alguna empresa (para elegir el del artículo)",
)
def codigos_impuesto(
    _: Usuario = Depends(requiere("maestros.articulo.ver")), db: Session = Depends(get_db)
):
    return service.codigos_impuesto(db)
