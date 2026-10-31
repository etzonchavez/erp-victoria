"""Entradas y salidas de la API de maestros."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class Esquema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PaisSalida(BaseModel):
    codigo: str
    nombre: str
    moneda: str
    nombre_identificacion_fiscal: str


# Empresas y unidades de negocio
class UnidadNegocioSalida(Esquema):
    id: uuid.UUID
    empresa_id: uuid.UUID
    codigo: str
    nombre: str
    activo: bool


class UnidadNegocioCrear(BaseModel):
    codigo: str = Field(min_length=1, max_length=20)
    nombre: str = Field(min_length=2, max_length=150)


class UnidadNegocioCambio(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=150)
    activo: bool | None = None


class EmpresaResumen(Esquema):
    id: uuid.UUID
    pais: str
    identificacion_fiscal: str
    razon_social: str
    moneda_funcional: str
    unidades: list[UnidadNegocioSalida]


class EmpresaSalida(Esquema):
    id: uuid.UUID
    pais: str
    identificacion_fiscal: str
    razon_social: str
    nombre_comercial: str | None
    direccion_fiscal: str | None
    moneda_funcional: str
    activo: bool
    unidades: list[UnidadNegocioSalida]
    creado_en: datetime


class EmpresaCrear(BaseModel):
    pais: str = Field(default="pe", min_length=2, max_length=2)
    identificacion_fiscal: str = Field(min_length=5, max_length=20)
    razon_social: str = Field(min_length=2, max_length=200)
    nombre_comercial: str | None = Field(default=None, max_length=150)
    direccion_fiscal: str | None = Field(default=None, max_length=300)
    moneda_funcional: str | None = Field(default=None, min_length=3, max_length=3)


class EmpresaCambio(BaseModel):
    razon_social: str | None = Field(default=None, min_length=2, max_length=200)
    nombre_comercial: str | None = Field(default=None, max_length=150)
    direccion_fiscal: str | None = Field(default=None, max_length=300)
    activo: bool | None = None


# Monedas y tipo de cambio
class MonedaSalida(Esquema):
    codigo: str
    nombre: str
    simbolo: str
    decimales: int
    activo: bool


class MonedaCrear(BaseModel):
    codigo: str = Field(min_length=3, max_length=3)
    nombre: str = Field(min_length=2, max_length=60)
    simbolo: str = Field(min_length=1, max_length=5)
    decimales: int = Field(default=2, ge=0, le=4)


class MonedaCambio(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=60)
    simbolo: str | None = Field(default=None, min_length=1, max_length=5)
    decimales: int | None = Field(default=None, ge=0, le=4)
    activo: bool | None = None


Tasa = Field(gt=0, max_digits=12, decimal_places=6)


class TipoCambioEntrada(BaseModel):
    moneda: str = Field(min_length=3, max_length=3)
    moneda_base: str = Field(default="PEN", min_length=3, max_length=3)
    fecha: date
    compra: Decimal = Tasa
    venta: Decimal = Tasa


class TipoCambioSalida(Esquema):
    id: uuid.UUID
    moneda: str
    moneda_base: str
    fecha: date
    compra: Decimal
    venta: Decimal
    fuente: str
    actualizado_en: datetime


# Unidades de medida
class UnidadSalida(Esquema):
    codigo: str
    nombre: str
    codigo_oficial: str
    tipo: str
    activo: bool


class UnidadCrear(BaseModel):
    codigo: str = Field(min_length=1, max_length=10)
    nombre: str = Field(min_length=2, max_length=80)
    codigo_oficial: str = Field(min_length=2, max_length=3)
    tipo: str


class UnidadCambio(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=80)
    codigo_oficial: str | None = Field(default=None, min_length=2, max_length=3)
    tipo: str | None = None
    activo: bool | None = None


class ConversionSalida(Esquema):
    id: uuid.UUID
    origen: str
    destino: str
    factor: Decimal


class ConversionCrear(BaseModel):
    origen: str = Field(min_length=1, max_length=10)
    destino: str = Field(min_length=1, max_length=10)
    factor: Decimal = Field(gt=0, max_digits=18, decimal_places=6)


# Categorías de artículo
class CategoriaSalida(Esquema):
    id: uuid.UUID
    codigo: str
    nombre: str
    padre_id: uuid.UUID | None
    nivel: int
    activo: bool


class CategoriaCrear(BaseModel):
    codigo: str = Field(min_length=1, max_length=20)
    nombre: str = Field(min_length=2, max_length=120)
    padre_id: uuid.UUID | None = None


class CategoriaCambio(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    padre_id: uuid.UUID | None = None  # enviar null para dejarla en el primer nivel
    activo: bool | None = None


# Condiciones de pago
class CondicionSalida(Esquema):
    id: uuid.UUID
    codigo: str
    nombre: str
    dias: int
    activo: bool


class CondicionCrear(BaseModel):
    codigo: str = Field(min_length=1, max_length=20)
    nombre: str = Field(min_length=2, max_length=80)
    dias: int = Field(ge=0, le=365)


class CondicionCambio(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=80)
    dias: int | None = Field(default=None, ge=0, le=365)
    activo: bool | None = None


# Proveedores
class TipoDocumentoSalida(BaseModel):
    codigo: str
    nombre: str
    codigo_oficial: str
    extranjero: bool


class ContactoSalida(Esquema):
    id: uuid.UUID
    nombre: str
    cargo: str | None
    correo: str | None
    telefono: str | None
    principal: bool


class ContactoCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=150)
    cargo: str | None = Field(default=None, max_length=100)
    correo: str | None = Field(default=None, max_length=200)
    telefono: str | None = Field(default=None, max_length=40)
    principal: bool = False


class ContactoCambio(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=150)
    cargo: str | None = Field(default=None, max_length=100)
    correo: str | None = Field(default=None, max_length=200)
    telefono: str | None = Field(default=None, max_length=40)
    principal: bool | None = None


class CuentaBancariaSalida(Esquema):
    id: uuid.UUID
    banco: str
    tipo: str
    moneda: str
    numero: str  # enmascarado sin el permiso maestros.proveedor.banco
    cci: str | None
    swift: str | None
    activo: bool
    enmascarada: bool = False


class CuentaBancariaCrear(BaseModel):
    banco: str = Field(min_length=2, max_length=100)
    tipo: str
    moneda: str = Field(min_length=3, max_length=3)
    numero: str = Field(min_length=5, max_length=40)
    cci: str | None = Field(default=None, max_length=30)
    swift: str | None = Field(default=None, max_length=15)


class CuentaBancariaCambio(BaseModel):
    activo: bool


class BloqueoSalida(Esquema):
    empresa_id: uuid.UUID
    motivo: str


class BloqueoCambio(BaseModel):
    bloqueado: bool
    motivo: str | None = Field(default=None, max_length=300)


class CategoriasCambio(BaseModel):
    categoria_ids: list[uuid.UUID]


class ProveedorResumen(Esquema):
    id: uuid.UUID
    tipo_documento: str
    numero_documento: str
    pais: str
    razon_social: str
    nombre_comercial: str | None
    moneda: str
    condicion_pago: CondicionSalida
    activo: bool
    bloqueos: list[BloqueoSalida]


class ProveedorSalida(ProveedorResumen):
    direccion: str | None
    correo: str | None
    telefono: str | None
    contactos: list[ContactoSalida]
    cuentas: list[CuentaBancariaSalida]
    categorias: list[CategoriaSalida]


class ProveedorCrear(BaseModel):
    tipo_documento: str = Field(min_length=2, max_length=5)
    numero_documento: str = Field(min_length=3, max_length=25)
    pais: str | None = Field(default=None, min_length=2, max_length=2)  # solo extranjeros
    razon_social: str = Field(min_length=2, max_length=200)
    nombre_comercial: str | None = Field(default=None, max_length=150)
    direccion: str | None = Field(default=None, max_length=300)
    correo: str | None = Field(default=None, max_length=200)
    telefono: str | None = Field(default=None, max_length=40)
    moneda: str | None = Field(default=None, min_length=3, max_length=3)
    condicion_pago_id: uuid.UUID | None = None


class ProveedorCambio(BaseModel):
    razon_social: str | None = Field(default=None, min_length=2, max_length=200)
    nombre_comercial: str | None = Field(default=None, max_length=150)
    direccion: str | None = Field(default=None, max_length=300)
    correo: str | None = Field(default=None, max_length=200)
    telefono: str | None = Field(default=None, max_length=40)
    moneda: str | None = Field(default=None, min_length=3, max_length=3)
    condicion_pago_id: uuid.UUID | None = None
    activo: bool | None = None
