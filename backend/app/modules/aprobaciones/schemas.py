"""Entradas y salidas de la API de reglas de aprobación (comunes a todos los documentos)."""

import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class AprobadorDatos(BaseModel):
    tipo: str
    usuario_id: uuid.UUID | None = None
    rol_id: uuid.UUID | None = None
    unidad_negocio_id: uuid.UUID | None = None
    categoria_id: uuid.UUID | None = None
    centro_costo_id: uuid.UUID | None = None


class AprobadorSalida(AprobadorDatos):
    descripcion: str


class NivelDatos(BaseModel):
    monto_desde: Decimal = Decimal(0)
    modo: str = "serie"
    aprobadores: list[AprobadorDatos] = []


class NivelSalida(BaseModel):
    numero: int
    monto_desde: Decimal
    modo: str
    aprobadores: list[AprobadorSalida]


class ReglaDatos(BaseModel):
    nombre: str = Field(max_length=100)
    prioridad: int
    activo: bool = True
    unidad_negocio_id: uuid.UUID | None = None
    categoria_id: uuid.UUID | None = None
    tipo_articulo: str | None = None
    centro_costo_id: uuid.UUID | None = None
    niveles: list[NivelDatos]


class ReglaSalida(BaseModel):
    id: uuid.UUID
    empresa_id: uuid.UUID
    documento: str
    nombre: str
    prioridad: int
    activo: bool
    unidad_negocio_id: uuid.UUID | None
    categoria_id: uuid.UUID | None
    tipo_articulo: str | None
    centro_costo_id: uuid.UUID | None
    condiciones: str  # resumen legible
    niveles: list[NivelSalida]


class OpcionCodigo(BaseModel):
    codigo: str
    nombre: str


class CatalogoAprobacion(BaseModel):
    documentos: list[OpcionCodigo]
    modos: list[OpcionCodigo]
    tipos_aprobador: list[OpcionCodigo]
    max_niveles: int


class OpcionId(BaseModel):
    id: uuid.UUID
    codigo: str
    nombre: str


class OpcionesEmpresa(BaseModel):
    unidades: list[OpcionId]
    centros: list[OpcionId]
    categorias: list[OpcionId]
    tipos_articulo: list[OpcionCodigo]


class PasoSimulado(BaseModel):
    descripcion: str
    estado: str
    motivo: str | None


class NivelSimulado(BaseModel):
    numero: int
    modo: str
    monto_desde: Decimal
    pasos: list[PasoSimulado]


class Ruta(BaseModel):
    regla: str
    niveles: list[NivelSimulado]
