"""Entradas y salidas de la API de contabilidad base."""

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class Esquema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Opcion(BaseModel):
    codigo: str
    nombre: str


class CuentaResumen(Esquema):
    id: uuid.UUID
    codigo: str
    nombre: str


class CuentaSalida(Esquema):
    id: uuid.UUID
    codigo: str
    nombre: str
    padre_id: uuid.UUID | None
    nivel: int
    naturaleza: str
    imputable: bool
    plantilla: str
    activo: bool


class CuentaCrear(BaseModel):
    codigo: str = Field(min_length=1, max_length=20)
    nombre: str = Field(min_length=2, max_length=200)
    naturaleza: str | None = None  # solo para cuentas de primer nivel


class CuentaCambio(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=200)
    activo: bool | None = None


class PerfilSalida(Esquema):
    id: uuid.UUID
    codigo: str
    nombre: str
    tipo_articulo: str
    cuenta_cargo: CuentaResumen
    cuenta_existencia: CuentaResumen | None
    cuenta_variacion: CuentaResumen | None
    cuenta_por_pagar: CuentaResumen
    activo: bool


class PerfilCrear(BaseModel):
    codigo: str = Field(min_length=2, max_length=30)
    nombre: str = Field(min_length=2, max_length=100)
    tipo_articulo: str
    cuenta_cargo_id: uuid.UUID
    cuenta_existencia_id: uuid.UUID | None = None
    cuenta_variacion_id: uuid.UUID | None = None
    cuenta_por_pagar_id: uuid.UUID


class PerfilCambio(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=100)
    cuenta_cargo_id: uuid.UUID | None = None
    cuenta_existencia_id: uuid.UUID | None = None
    cuenta_variacion_id: uuid.UUID | None = None
    cuenta_por_pagar_id: uuid.UUID | None = None
    activo: bool | None = None


class CentroSalida(Esquema):
    id: uuid.UUID
    unidad_negocio_id: uuid.UUID
    codigo: str
    nombre: str
    responsable: str | None
    activo: bool


class CentroCrear(BaseModel):
    unidad_negocio_id: uuid.UUID
    codigo: str = Field(min_length=1, max_length=20)
    nombre: str = Field(min_length=2, max_length=150)
    responsable: str | None = Field(default=None, max_length=150)


class CentroCambio(BaseModel):
    unidad_negocio_id: uuid.UUID | None = None
    nombre: str | None = Field(default=None, min_length=2, max_length=150)
    responsable: str | None = Field(default=None, max_length=150)
    activo: bool | None = None


class ImpuestoSalida(Esquema):
    id: uuid.UUID
    codigo: str
    nombre: str
    tasa: Decimal
    cuenta: CuentaResumen | None
    activo: bool


class ImpuestoCrear(BaseModel):
    codigo: str = Field(min_length=2, max_length=20)
    nombre: str = Field(min_length=2, max_length=100)
    tasa: Decimal = Field(ge=0, le=100, max_digits=7, decimal_places=4)
    cuenta_id: uuid.UUID | None = None


class ImpuestoCambio(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=100)
    tasa: Decimal | None = Field(default=None, ge=0, le=100, max_digits=7, decimal_places=4)
    cuenta_id: uuid.UUID | None = None
    activo: bool | None = None


class PlantillaResultado(BaseModel):
    cuentas: int
