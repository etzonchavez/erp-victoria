"""Reporte Excel de solicitudes y órdenes de compra.

Una fila por línea de orden con su solicitud de origen; además, las líneas de solicitudes que
aún no están en una orden (sin datos de orden). Filtros: empresa, fechas, estado de la orden,
proveedor y unidad de negocio. Solo entran las unidades de negocio a las que el usuario accede.
"""

import io
import uuid
from datetime import date

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ErrorERP
from app.modules.compras.models import ESTADOS, Orden
from app.modules.contabilidad import service as contabilidad
from app.modules.maestros import service as maestros
from app.modules.seguridad.models import Usuario
from app.modules.solicitudes.models import ESTADOS as ESTADOS_SOL
from app.modules.solicitudes.models import Solicitud

COLUMNAS = [
    ("Orden", 16),
    ("Fecha orden", 12),
    ("Estado orden", 18),
    ("Proveedor", 32),
    ("Comprador", 22),
    ("Unidad de negocio", 20),
    ("Moneda", 8),
    ("Línea", 6),
    ("Código", 16),
    ("Descripción", 40),
    ("Cantidad", 11),
    ("Unidad", 8),
    ("Precio", 13),
    ("Subtotal", 14),
    ("Impuesto", 13),
    ("Total", 14),
    ("Centros de costo", 22),
    ("Solicitud", 16),
    ("Fecha solicitud", 13),
    ("Estado solicitud", 16),
    ("Solicitante", 22),
]
NUMERICAS = {"Cantidad", "Precio", "Subtotal", "Impuesto", "Total"}


def _acceso(db: Session, usuario: Usuario, unidad_id: uuid.UUID) -> bool:
    try:
        maestros.verificar_acceso_unidad(db, usuario, unidad_id)
    except ErrorERP:
        return False
    return True


def _nombre(db: Session, usuario_id) -> str:
    u = db.get(Usuario, usuario_id) if usuario_id else None
    return u.nombre if u else ""


def _centros(db: Session, distribuciones) -> str:
    return ", ".join(
        f"{contabilidad.obtener_centro(db, d.centro_costo_id).codigo} {float(d.porcentaje):g}%"
        for d in distribuciones
    )


def filas(
    db: Session,
    usuario: Usuario,
    empresa_id: uuid.UUID,
    desde: date | None = None,
    hasta: date | None = None,
    estado: str | None = None,
    proveedor_id: uuid.UUID | None = None,
    unidad_negocio_id: uuid.UUID | None = None,
    incluir_sin_orden: bool = True,
) -> list[list]:
    maestros.verificar_acceso_empresa(db, usuario, empresa_id)
    if estado and estado not in ESTADOS:
        raise ErrorERP(422, "estado_invalido", "Estado de orden inexistente")
    resultado: list[list] = []

    q = select(Orden).where(Orden.empresa_id == empresa_id)
    if desde:
        q = q.where(Orden.fecha >= desde)
    if hasta:
        q = q.where(Orden.fecha <= hasta)
    if estado:
        q = q.where(Orden.estado == estado)
    if proveedor_id:
        q = q.where(Orden.proveedor_id == proveedor_id)
    if unidad_negocio_id:
        q = q.where(Orden.unidad_negocio_id == unidad_negocio_id)
    for o in db.scalars(q.order_by(Orden.fecha, Orden.numero)):
        if not _acceso(db, usuario, o.unidad_negocio_id):
            continue
        prov = maestros.obtener_proveedor(db, o.proveedor_id).razon_social
        un = maestros.obtener_unidad_negocio(db, o.unidad_negocio_id).nombre
        for ln in o.lineas:
            sol = db.get(Solicitud, ln.solicitud_id) if ln.solicitud_id else None
            resultado.append(
                [
                    o.numero,
                    o.fecha,
                    ESTADOS[o.estado],
                    prov,
                    _nombre(db, o.comprador_id),
                    un,
                    o.moneda,
                    ln.numero,
                    maestros.obtener_articulo(db, ln.articulo_id).codigo,
                    ln.descripcion,
                    float(ln.cantidad),
                    ln.unidad,
                    float(ln.precio),
                    float(ln.subtotal),
                    float(ln.impuesto_monto),
                    float(ln.total),
                    _centros(db, ln.distribuciones),
                    sol.numero if sol else "Directa",
                    sol.fecha if sol else None,
                    ESTADOS_SOL[sol.estado] if sol else "",
                    _nombre(db, sol.solicitante_id) if sol else "",
                ]
            )

    # Solicitudes que aún no están en una orden (no aplican los filtros de orden/proveedor)
    if incluir_sin_orden and not estado and not proveedor_id:
        q = select(Solicitud).where(
            Solicitud.empresa_id == empresa_id,
            Solicitud.orden_compra_id.is_(None),
            Solicitud.estado.in_(["borrador", "en_aprobacion", "devuelta", "aprobada"]),
        )
        if desde:
            q = q.where(Solicitud.fecha >= desde)
        if hasta:
            q = q.where(Solicitud.fecha <= hasta)
        if unidad_negocio_id:
            q = q.where(Solicitud.unidad_negocio_id == unidad_negocio_id)
        for s in db.scalars(q.order_by(Solicitud.fecha, Solicitud.numero)):
            if not _acceso(db, usuario, s.unidad_negocio_id):
                continue
            un = maestros.obtener_unidad_negocio(db, s.unidad_negocio_id).nombre
            for ln in s.lineas:
                resultado.append(
                    [
                        "",
                        None,
                        "Sin orden",
                        "",
                        "",
                        un,
                        s.moneda,
                        ln.numero,
                        maestros.obtener_articulo(db, ln.articulo_id).codigo,
                        ln.descripcion,
                        float(ln.cantidad),
                        ln.unidad,
                        float(ln.precio),
                        float(ln.subtotal),
                        0.0,
                        float(ln.subtotal),
                        _centros(db, ln.distribuciones),
                        s.numero,
                        s.fecha,
                        ESTADOS_SOL[s.estado],
                        _nombre(db, s.solicitante_id),
                    ]
                )
    return resultado


def excel(db: Session, usuario: Usuario, empresa_id: uuid.UUID, **filtros) -> bytes:
    datos = filas(db, usuario, empresa_id, **filtros)
    empresa = maestros.obtener_empresa(db, empresa_id)
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Solicitudes y órdenes"
    hoja.append([f"Solicitudes y órdenes de compra · {empresa.razon_social}"])
    hoja["A1"].font = Font(bold=True, size=13)
    detalle = ", ".join(f"{k}: {v}" for k, v in filtros.items() if v not in (None, "", True))
    hoja.append(
        [f"Generado el {date.today():%d/%m/%Y}" + (f" · Filtros: {detalle}" if detalle else "")]
    )
    hoja.append([])
    hoja.append([c for c, _ in COLUMNAS])
    relleno = PatternFill("solid", fgColor="1F4FA3")
    for i, (_, ancho) in enumerate(COLUMNAS, start=1):
        celda = hoja.cell(row=4, column=i)
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = relleno
        celda.alignment = Alignment(vertical="center", wrap_text=True)
        hoja.column_dimensions[get_column_letter(i)].width = ancho
    for fila in datos:
        hoja.append(fila)
    for i, (nombre, _) in enumerate(COLUMNAS, start=1):
        formato = None
        if nombre in NUMERICAS:
            formato = "#,##0.00" if nombre != "Cantidad" else "#,##0.####"
        elif nombre.startswith("Fecha"):
            formato = "DD/MM/YYYY"
        if formato:
            for fila in hoja.iter_rows(min_row=5, min_col=i, max_col=i):
                fila[0].number_format = formato
    hoja.freeze_panes = "A5"
    if datos:
        hoja.auto_filter.ref = f"A4:{get_column_letter(len(COLUMNAS))}{4 + len(datos)}"
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()
