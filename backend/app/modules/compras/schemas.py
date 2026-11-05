"""Entradas y salidas de la API de órdenes de compra."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.modules.aprobaciones.schemas import OpcionCodigo, OpcionId
from app.modules.solicitudes.schemas import (  # noqa: F401  (reexporta)
    ArticuloOpcion,
    Atributos,
    Comentario,
    DistribucionDatos,
    PasoSalida,
    Ruta,
)


class LineaOrdenDatos(BaseModel):
    """Con solicitud_linea_id: ajusta precio, impuesto o atributos de una línea de solicitud.
    Sin él: línea directa (artículo, cantidad, unidad, distribución)."""

    solicitud_linea_id: uuid.UUID | None = None
    articulo_id: uuid.UUID | None = None
    descripcion: str | None = Field(default=None, max_length=240)
    cantidad: Decimal | None = None
    unidad: str | None = None
    precio: Decimal | None = None
    impuesto_id: uuid.UUID | None = None
    distribuciones: list[DistribucionDatos] = []
    atributos: Atributos | None = None


class OrdenDatos(BaseModel):
    unidad_negocio_id: uuid.UUID
    proveedor_id: uuid.UUID
    contacto_id: uuid.UUID | None = None
    condicion_pago_id: uuid.UUID | None = None
    moneda: str | None = None
    fecha_entrega: date | None = None
    lugar_entrega: str | None = Field(default=None, max_length=300)
    observaciones: str | None = Field(default=None, max_length=2000)
    solicitudes: list[uuid.UUID] = []
    lineas: list[LineaOrdenDatos] = []
    atributos: Atributos | None = None


class OrdenCrear(OrdenDatos):
    empresa_id: uuid.UUID


class DistribucionOrdenSalida(BaseModel):
    centro_costo_id: uuid.UUID
    centro_costo: str
    porcentaje: Decimal
    monto: Decimal
    atributos: dict


class LineaOrdenSalida(BaseModel):
    numero: int
    solicitud_id: uuid.UUID | None
    solicitud_linea_id: uuid.UUID | None
    solicitud_numero: str | None
    articulo_id: uuid.UUID
    articulo: str
    descripcion: str
    cantidad: Decimal
    unidad: str
    unidad_base: str
    unidades: list[str]
    precio: Decimal
    subtotal: Decimal
    impuesto_id: uuid.UUID | None
    tasa: Decimal
    impuesto_monto: Decimal
    total: Decimal
    cuenta: str | None
    distribuciones: list[DistribucionOrdenSalida]
    atributos: dict


class AccionesOrden(BaseModel):
    editar: bool
    enviar: bool
    aprobar: bool
    anular: bool
    marcar_enviada: bool


class OrdenResumen(BaseModel):
    id: uuid.UUID
    numero: str
    fecha: date
    empresa_id: uuid.UUID
    unidad_negocio_id: uuid.UUID
    unidad_negocio: str
    comprador_id: uuid.UUID
    comprador: str
    proveedor_id: uuid.UUID
    proveedor: str
    moneda: str
    total: Decimal
    total_funcional: Decimal
    estado: str
    solicitudes: list[str]
    pendiente_de: list[str]


class OrdenSalida(OrdenResumen):
    contacto_id: uuid.UUID | None
    condicion_pago_id: uuid.UUID
    condicion_pago: str
    fecha_entrega: date | None
    lugar_entrega: str | None
    observaciones: str | None
    subtotal: Decimal
    impuesto: Decimal
    tipo_cambio: Decimal
    ronda: int
    enviada_en: datetime | None
    lineas: list[LineaOrdenSalida]
    atributos: dict
    pasos: list[PasoSalida]
    acciones: AccionesOrden


class LineaDisponible(BaseModel):
    id: uuid.UUID
    numero: int
    articulo: str
    descripcion: str
    cantidad: Decimal
    unidad: str
    precio: Decimal
    subtotal: Decimal
    centros: str


class SolicitudDisponible(BaseModel):
    id: uuid.UUID
    numero: str
    titulo: str
    solicitante: str
    unidad_negocio: str
    fecha_requerida: date | None
    moneda: str
    total: Decimal
    lineas: list[LineaDisponible]


class ProveedorOpcion(BaseModel):
    id: uuid.UUID
    razon_social: str
    documento: str
    moneda: str
    condicion_pago_id: uuid.UUID
    contactos: list[OpcionId]


class ImpuestoOpcion(BaseModel):
    id: uuid.UUID
    codigo: str
    nombre: str
    tasa: Decimal


class OpcionesCompra(BaseModel):
    unidades: list[OpcionId]
    centros: list[OpcionId]
    proveedores: list[ProveedorOpcion]
    condiciones: list[OpcionId]
    impuestos: list[ImpuestoOpcion]
    impuesto_defecto: uuid.UUID | None
    monedas: list[str]
    estados: list[OpcionCodigo]


class FormatoSalida(BaseModel):
    configuracion: dict
    tiene_logo: bool
    secciones: list[OpcionCodigo]
    columnas: list[OpcionCodigo]


class FormatoDatos(BaseModel):
    configuracion: dict


class FilaAsiento(BaseModel):
    cuenta: str
    nombre: str
    centro_costo: str | None
    glosa: str
    debe: Decimal
    haber: Decimal


class Asiento(BaseModel):
    momento: str
    titulo: str
    filas: list[FilaAsiento]
    debe: Decimal
    haber: Decimal
    cuadra: bool


class MomentoTipo(BaseModel):
    tipo_articulo: str
    momento: str


class AsientoPrevio(BaseModel):
    moneda: str
    moneda_funcional: str
    tipo_cambio: Decimal
    asientos: list[Asiento]
    avisos: list[str]
    momentos: list[MomentoTipo]
