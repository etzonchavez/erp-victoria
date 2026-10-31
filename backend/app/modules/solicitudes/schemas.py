"""Entradas y salidas de la API de solicitudes y reglas de aprobación."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

Atributos = dict[str, str | float | int | None]


# ---------------------------------------------------------------- reglas de aprobación


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
    modos: list[OpcionCodigo]
    tipos_aprobador: list[OpcionCodigo]
    estados: list[OpcionCodigo]
    max_niveles: int


# ---------------------------------------------------------------- solicitudes


class DistribucionDatos(BaseModel):
    centro_costo_id: uuid.UUID
    porcentaje: Decimal = Field(gt=0, le=100)
    atributos: Atributos | None = None


class LineaDatos(BaseModel):
    articulo_id: uuid.UUID
    descripcion: str | None = Field(default=None, max_length=240)
    cantidad: Decimal
    unidad: str | None = None
    precio: Decimal = Decimal(0)
    distribuciones: list[DistribucionDatos] = []
    atributos: Atributos | None = None


class SolicitudDatos(BaseModel):
    unidad_negocio_id: uuid.UUID
    titulo: str = Field(max_length=150)
    justificacion: str | None = Field(default=None, max_length=2000)
    fecha_requerida: date | None = None
    moneda: str | None = None
    lineas: list[LineaDatos] = []
    atributos: Atributos | None = None


class SolicitudCrear(SolicitudDatos):
    empresa_id: uuid.UUID


class Comentario(BaseModel):
    comentario: str | None = Field(default=None, max_length=500)


class DistribucionSalida(BaseModel):
    centro_costo_id: uuid.UUID
    centro_costo: str
    porcentaje: Decimal
    monto: Decimal
    atributos: dict


class LineaSalida(BaseModel):
    numero: int
    articulo_id: uuid.UUID
    articulo: str
    descripcion: str
    cantidad: Decimal
    unidad: str
    cantidad_base: Decimal
    unidad_base: str
    precio: Decimal
    subtotal: Decimal
    cuenta: str | None
    distribuciones: list[DistribucionSalida]
    atributos: dict


class PasoSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ronda: int
    regla_nombre: str
    nivel: int
    modo: str
    orden: int
    descripcion: str
    estado: str
    motivo: str | None
    actuado_por_nombre: str | None
    actuado_en: datetime | None
    comentario: str | None


class Acciones(BaseModel):
    editar: bool
    enviar: bool
    aprobar: bool
    anular: bool


class SolicitudResumen(BaseModel):
    id: uuid.UUID
    numero: str
    titulo: str
    fecha: date
    fecha_requerida: date | None
    empresa_id: uuid.UUID
    unidad_negocio_id: uuid.UUID
    unidad_negocio: str
    solicitante_id: uuid.UUID
    solicitante: str
    moneda: str
    total: Decimal
    total_funcional: Decimal
    estado: str
    pendiente_de: list[str]  # quién tiene la aprobación en sus manos ahora


class SolicitudSalida(SolicitudResumen):
    justificacion: str | None
    tipo_cambio: Decimal
    ronda: int
    lineas: list[LineaSalida]
    atributos: dict
    pasos: list[PasoSalida]
    acciones: Acciones


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


# ---------------------------------------------------------------- listas de apoyo


class OpcionId(BaseModel):
    id: uuid.UUID
    codigo: str
    nombre: str


class OpcionesEmpresa(BaseModel):
    unidades: list[OpcionId]
    centros: list[OpcionId]
    categorias: list[OpcionId]
    tipos_articulo: list[OpcionCodigo]


class UnidadAlterna(BaseModel):
    unidad: str
    factor: Decimal


class ArticuloOpcion(BaseModel):
    id: uuid.UUID
    codigo: str
    descripcion: str
    tipo: str
    unidad: str
    unidades: list[UnidadAlterna]
    precio_referencial: Decimal | None
    moneda_precio: str | None
