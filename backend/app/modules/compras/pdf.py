"""PDF de la orden de compra con formato configurable por empresa (ADR-007).

El formato (cmp_formato.configuracion) decide: título, color, tamaño de página, columnas de
los bloques de datos, qué secciones se imprimen y en qué orden, qué columnas llevan las líneas,
términos y condiciones, pie de página y logo. El PDF se arma como HTML y lo convierte
WeasyPrint, así el diseño se ajusta con CSS sin tocar la lógica.
"""

import base64
import copy
import uuid
from datetime import date
from decimal import Decimal
from html import escape

from sqlalchemy.orm import Session

from app.core.errors import ErrorERP
from app.modules.compras.models import ESTADOS, Formato, Orden
from app.modules.contabilidad import service as contabilidad
from app.modules.maestros import service as maestros
from app.modules.seguridad import atributos
from app.modules.seguridad.models import Usuario
from app.modules.seguridad.service import (
    TAMANO_MAXIMO_LOGO,
    auditar,
    obtener_personalizacion,
    tipo_de_imagen,
)

SECCIONES = {
    "proveedor": "Proveedor",
    "entrega": "Entrega",
    "condiciones": "Condiciones comerciales",
    "lineas": "Detalle de la orden",
    "totales": "Totales",
    "atributos": "Datos adicionales",
    "observaciones": "Observaciones",
    "terminos": "Términos y condiciones",
    "firmas": "Aprobaciones",
}
BLOQUES_DATOS = {"proveedor", "entrega", "condiciones", "atributos"}  # van en rejilla
COLUMNAS = {
    "numero": "N.°",
    "codigo": "Código",
    "descripcion": "Descripción",
    "cantidad": "Cantidad",
    "unidad": "Unidad",
    "precio": "Precio unit.",
    "impuesto": "Impuesto",
    "subtotal": "Subtotal",
    "total": "Total",
    "centro_costo": "Centro de costo",
    "solicitud": "Solicitud",
}
NUMERICAS = {"cantidad", "precio", "subtotal", "total"}
TAMANOS = {"A4": "A4", "carta": "letter"}

FORMATO_BASE: dict = {
    "titulo": "ORDEN DE COMPRA",
    "color": "#1f4fa3",
    "tamano": "A4",
    "columnas_datos": 2,
    "mostrar_logo": True,
    "secciones": [{"codigo": c, "activo": True} for c in SECCIONES],
    "columnas": ["numero", "codigo", "descripcion", "cantidad", "unidad", "precio", "total"],
    "terminos": (
        "1. Indique el número de esta orden en su factura y guía de remisión.\n"
        "2. La mercadería se recibe solo en el lugar y fecha de entrega indicados.\n"
        "3. Los precios no incluyen impuestos salvo que se indique."
    ),
    "pie": "",
}


# ---------------------------------------------------------------- configuración


def _normalizar(config: dict | None) -> dict:
    """Completa con el formato base y descarta valores desconocidos."""
    base = copy.deepcopy(FORMATO_BASE)
    config = config or {}
    for clave in ("titulo", "terminos", "pie"):
        if isinstance(config.get(clave), str):
            base[clave] = config[clave][:4000]
    color = str(config.get("color") or "")
    if len(color) == 7 and color.startswith("#"):
        try:
            int(color[1:], 16)
            base["color"] = color
        except ValueError:
            pass
    if config.get("tamano") in TAMANOS:
        base["tamano"] = config["tamano"]
    if config.get("columnas_datos") in (1, 2, 3):
        base["columnas_datos"] = config["columnas_datos"]
    if isinstance(config.get("mostrar_logo"), bool):
        base["mostrar_logo"] = config["mostrar_logo"]
    if isinstance(config.get("secciones"), list):
        vistas, secciones = set(), []
        for s in config["secciones"]:
            if isinstance(s, dict) and s.get("codigo") in SECCIONES and s["codigo"] not in vistas:
                vistas.add(s["codigo"])
                secciones.append({"codigo": s["codigo"], "activo": bool(s.get("activo", True))})
        secciones += [{"codigo": c, "activo": False} for c in SECCIONES if c not in vistas]
        base["secciones"] = secciones
    if isinstance(config.get("columnas"), list):
        columnas = [c for c in dict.fromkeys(config["columnas"]) if c in COLUMNAS]
        if "descripcion" not in columnas:
            raise ErrorERP(422, "columnas_invalidas", "La descripción siempre se imprime")
        base["columnas"] = columnas
    return base


def obtener_formato(db: Session, empresa_id: uuid.UUID) -> Formato:
    maestros.obtener_empresa(db, empresa_id)
    formato = db.get(Formato, empresa_id)
    if not formato:
        formato = Formato(empresa_id=empresa_id, configuracion=copy.deepcopy(FORMATO_BASE))
        db.add(formato)
        db.commit()
    return formato


def configuracion(formato: Formato) -> dict:
    return _normalizar(formato.configuracion)


def guardar_formato(db: Session, actor: Usuario, empresa_id: uuid.UUID, config: dict) -> Formato:
    formato = obtener_formato(db, empresa_id)
    nueva = _normalizar(config)
    formato.configuracion, formato.actualizado_por = nueva, actor.id
    auditar(db, actor, "editar", "formato_oc", empresa_id, {"configuracion": nueva})
    db.commit()
    return formato


def cambiar_logo(
    db: Session, actor: Usuario, empresa_id: uuid.UUID, datos: bytes | None
) -> Formato:
    formato = obtener_formato(db, empresa_id)
    if datos:
        if len(datos) > TAMANO_MAXIMO_LOGO:
            raise ErrorERP(413, "logo_muy_grande", "El logo no puede superar 2 MB")
        tipo = tipo_de_imagen(datos)
        if not tipo:
            raise ErrorERP(415, "logo_formato", "El logo debe ser una imagen PNG, JPG o WebP")
        formato.logo, formato.logo_tipo = datos, tipo
    else:
        formato.logo, formato.logo_tipo = None, None
    formato.actualizado_por = actor.id
    auditar(
        db,
        actor,
        "editar",
        "formato_oc",
        empresa_id,
        {"logo": f"{formato.logo_tipo}, {len(datos) // 1024} KB" if datos else "quitado"},
    )
    db.commit()
    return formato


def _logo(db: Session, formato: Formato) -> str | None:
    """Logo propio del formato; si no hay, el logo de la marca del ERP."""
    datos, tipo = formato.logo, formato.logo_tipo
    if not datos:
        marca = obtener_personalizacion(db)
        datos, tipo = marca.logo, marca.logo_tipo
    if not datos:
        return None
    return f"data:{tipo};base64,{base64.b64encode(datos).decode()}"


# ---------------------------------------------------------------- datos


def _num(valor, decimales: int = 2) -> str:
    """2 decimales; con decimales=4 muestra hasta 4 sin ceros de más (precios unitarios)."""
    texto = f"{Decimal(str(valor)):,.{decimales}f}"
    if decimales > 2:
        entero, dec = texto.split(".")
        texto = f"{entero}.{dec.rstrip('0').ljust(2, '0')}"
    return texto


def _cantidad(valor) -> str:
    texto = f"{Decimal(str(valor)):,.4f}".rstrip("0").rstrip(".")
    return texto


def _fecha(valor: date | None) -> str:
    return valor.strftime("%d/%m/%Y") if valor else "—"


def datos_orden(db: Session, orden: Orden) -> dict:
    empresa = maestros.obtener_empresa(db, orden.empresa_id)
    prov = maestros.obtener_proveedor(db, orden.proveedor_id)
    contacto = next((c for c in prov.contactos if c.id == orden.contacto_id), None)
    comprador = db.get(Usuario, orden.comprador_id)
    nombres = atributos.nombres_activos(db, "orden_compra", "cabecera")
    pasos = [p for p in _pasos(db, orden) if p.ronda == orden.ronda and p.estado == "aprobado"]
    return {
        "empresa": {
            "razon_social": empresa.razon_social,
            "identificacion": f"RUC {empresa.identificacion_fiscal}",
            "direccion": empresa.direccion_fiscal or "",
        },
        "numero": orden.numero,
        "fecha": _fecha(orden.fecha),
        "estado": orden.estado,
        "estado_nombre": ESTADOS[orden.estado],
        "proveedor": [
            ("Razón social", prov.razon_social),
            (prov.tipo_documento, prov.numero_documento),
            ("Dirección", prov.direccion or "—"),
            ("Contacto", contacto.nombre if contacto else "—"),
            ("Correo", (contacto.correo if contacto and contacto.correo else prov.correo) or "—"),
            (
                "Teléfono",
                (contacto.telefono if contacto and contacto.telefono else prov.telefono) or "—",
            ),
        ],
        "entrega": [
            ("Fecha de entrega", _fecha(orden.fecha_entrega)),
            ("Lugar", orden.lugar_entrega or "—"),
            (
                "Unidad de negocio",
                maestros.obtener_unidad_negocio(db, orden.unidad_negocio_id).nombre,
            ),
        ],
        "condiciones": [
            ("Condición de pago", maestros.obtener_condicion(db, orden.condicion_pago_id).nombre),
            ("Moneda", orden.moneda),
            ("Comprador", comprador.nombre if comprador else "—"),
        ],
        "atributos": [
            (nombre, str(getattr(orden, col)))
            for col, nombre in nombres.items()
            if getattr(orden, col) is not None
        ],
        "lineas": [
            {
                "numero": str(ln.numero),
                "codigo": maestros.obtener_articulo(db, ln.articulo_id).codigo,
                "descripcion": ln.descripcion,
                "cantidad": _cantidad(ln.cantidad),
                "unidad": ln.unidad,
                "precio": _num(ln.precio, 4),
                "impuesto": f"{_num(ln.tasa)} %" if ln.impuesto_id else "—",
                "subtotal": _num(ln.subtotal),
                "total": _num(ln.total),
                "centro_costo": ", ".join(
                    f"{contabilidad.obtener_centro(db, d.centro_costo_id).codigo} "
                    f"{_num(d.porcentaje)}%"
                    for d in ln.distribuciones
                ),
                "solicitud": ln.solicitud_numero or "Directa",
            }
            for ln in orden.lineas
        ],
        "totales": {
            "moneda": orden.moneda,
            "subtotal": _num(orden.subtotal),
            "impuesto": _num(orden.impuesto),
            "total": _num(orden.total),
        },
        "observaciones": orden.observaciones or "",
        "firmas": [
            {
                "nombre": p.actuado_por_nombre or p.descripcion,
                "cargo": f"Aprobó · nivel {p.nivel}",
                "fecha": p.actuado_en.strftime("%d/%m/%Y %H:%M") if p.actuado_en else "",
            }
            for p in pasos
        ]
        + [
            {
                "nombre": comprador.nombre if comprador else "—",
                "cargo": "Emitió",
                "fecha": _fecha(orden.fecha),
            }
        ],
    }


def _pasos(db: Session, orden: Orden):
    from app.modules.compras import service  # evita import circular

    return service.historial(db, orden)


def datos_ejemplo(db: Session, empresa_id: uuid.UUID) -> dict:
    empresa = maestros.obtener_empresa(db, empresa_id)
    return {
        "empresa": {
            "razon_social": empresa.razon_social,
            "identificacion": f"RUC {empresa.identificacion_fiscal}",
            "direccion": empresa.direccion_fiscal or "",
        },
        "numero": "OC-2026-000000",
        "fecha": _fecha(date.today()),
        "estado": "aprobada",
        "estado_nombre": "Vista previa",
        "proveedor": [
            ("Razón social", "Proveedor de ejemplo S.A.C."),
            ("RUC", "20100000001"),
            ("Dirección", "Av. Industrial 123, Lima"),
            ("Contacto", "María Torres"),
            ("Correo", "ventas@proveedor.pe"),
            ("Teléfono", "01 555 0000"),
        ],
        "entrega": [
            ("Fecha de entrega", _fecha(date.today())),
            ("Lugar", "Almacén central"),
            ("Unidad de negocio", "Principal"),
        ],
        "condiciones": [
            ("Condición de pago", "Crédito 30 días"),
            ("Moneda", empresa.moneda_funcional),
            ("Comprador", "Comprador de ejemplo"),
        ],
        "atributos": [("N.° de proyecto", "PRY-001")],
        "lineas": [
            {
                "numero": "1",
                "codigo": "SUM-OFI-0001",
                "descripcion": "Papel bond A4 80 g",
                "cantidad": "20",
                "unidad": "PAQ",
                "precio": "18.50",
                "impuesto": "18.00 %",
                "subtotal": "370.00",
                "total": "436.60",
                "centro_costo": "ADM 100.00%",
                "solicitud": "SC-2026-000001",
            },
            {
                "numero": "2",
                "codigo": "SRV-MAN-0001",
                "descripcion": "Mantenimiento preventivo de montacargas",
                "cantidad": "1",
                "unidad": "SRV",
                "precio": "1,200.00",
                "impuesto": "18.00 %",
                "subtotal": "1,200.00",
                "total": "1,416.00",
                "centro_costo": "OPE 100.00%",
                "solicitud": "Directa",
            },
        ],
        "totales": {
            "moneda": empresa.moneda_funcional,
            "subtotal": "1,570.00",
            "impuesto": "282.60",
            "total": "1,852.60",
        },
        "observaciones": "Entregar en horario de 8:00 a 16:00.",
        "firmas": [
            {"nombre": "Jefe de área", "cargo": "Aprobó · nivel 1", "fecha": _fecha(date.today())},
            {"nombre": "Comprador de ejemplo", "cargo": "Emitió", "fecha": _fecha(date.today())},
        ],
    }


# ---------------------------------------------------------------- dibujo


def _e(texto) -> str:
    return escape(str(texto)).replace("\n", "<br>")


def _bloque(titulo: str, filas: list[tuple]) -> str:
    cuerpo = "".join(f"<tr><th>{_e(k)}</th><td>{_e(v)}</td></tr>" for k, v in filas)
    return (
        f'<section class="bloque"><h2>{_e(titulo)}</h2>'
        f'<table class="datos">{cuerpo}</table></section>'
    )


def html(config: dict, datos: dict, logo: str | None) -> str:
    c = config
    color = c["color"]
    partes: list[str] = []
    rejilla: list[str] = []

    def cerrar_rejilla():
        if rejilla:
            partes.append(f'<div class="rejilla">{"".join(rejilla)}</div>')
            rejilla.clear()

    for s in c["secciones"]:
        if not s["activo"]:
            continue
        cod, titulo = s["codigo"], SECCIONES[s["codigo"]]
        if cod in BLOQUES_DATOS:
            if cod == "atributos" and not datos["atributos"]:
                continue
            rejilla.append(_bloque(titulo, datos[cod]))
            continue
        cerrar_rejilla()
        if cod == "lineas":
            cab = "".join(
                f'<th class="col-{col} {"num" if col in NUMERICAS else ""}">{COLUMNAS[col]}</th>'
                for col in c["columnas"]
            )
            filas = "".join(
                "<tr>"
                + "".join(
                    f'<td class="col-{col} {"num" if col in NUMERICAS else ""}">{_e(ln[col])}</td>'
                    for col in c["columnas"]
                )
                + "</tr>"
                for ln in datos["lineas"]
            )
            partes.append(
                f'<section><h2>{titulo}</h2><table class="lineas"><thead><tr>{cab}</tr></thead>'
                f"<tbody>{filas}</tbody></table></section>"
            )
        elif cod == "totales":
            t = datos["totales"]
            partes.append(
                '<table class="totales">'
                f"<tr><th>Subtotal</th><td>{t['moneda']} {t['subtotal']}</td></tr>"
                f"<tr><th>Impuestos</th><td>{t['moneda']} {t['impuesto']}</td></tr>"
                f"<tr class='total'><th>Total</th><td>{t['moneda']} {t['total']}</td></tr></table>"
            )
        elif cod == "observaciones" and datos["observaciones"]:
            partes.append(
                f"<section><h2>{titulo}</h2><p>{_e(datos['observaciones'])}</p></section>"
            )
        elif cod == "terminos" and c["terminos"].strip():
            partes.append(
                f'<section class="terminos"><h2>{titulo}</h2><p>{_e(c["terminos"])}</p></section>'
            )
        elif cod == "firmas":
            firmas = "".join(
                f'<div class="firma"><div class="raya"></div><strong>{_e(f["nombre"])}</strong>'
                f"<span>{_e(f['cargo'])}</span><span>{_e(f['fecha'])}</span></div>"
                for f in datos["firmas"]
            )
            partes.append(f'<section><h2>{titulo}</h2><div class="firmas">{firmas}</div></section>')
    cerrar_rejilla()

    marca_agua = (
        ""
        if datos["estado"] in ("aprobada", "enviada")
        else f'<div class="marca-agua">{_e(datos["estado_nombre"].upper())}</div>'
    )
    logo_html = f'<img class="logo" src="{logo}">' if logo and c["mostrar_logo"] else ""
    pie = " ".join(c["pie"].split()).replace("\\", "").replace('"', "'")
    e = datos["empresa"]
    css = (
        CSS.replace("__TAMANO__", TAMANOS[c["tamano"]])
        .replace("__COLOR__", color)
        .replace("__COLUMNAS__", str(c["columnas_datos"]))
        .replace("__PIE__", pie)
        .replace("__NUMERO__", escape(datos["numero"]))
    )
    return (
        f'<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><style>{css}</style>'
        f"</head><body>{marca_agua}"
        f'<header><div class="empresa">{logo_html}<strong>{_e(e["razon_social"])}</strong>'
        f"<div>{_e(e['identificacion'])}</div><div>{_e(e['direccion'])}</div></div>"
        f'<div class="numero"><h1>{_e(c["titulo"])}</h1><div class="n">{_e(datos["numero"])}</div>'
        f"<div>Fecha: {_e(datos['fecha'])}</div></div></header>"
        f"{''.join(partes)}</body></html>"
    )


CSS = """
@page { size: __TAMANO__; margin: 16mm 14mm 18mm;
  @bottom-left { content: "__PIE__"; font: 8pt "DejaVu Sans", Arial, sans-serif;
    color: #6b7280; }
  @bottom-right { content: "__NUMERO__ · Página " counter(page) " de " counter(pages);
    font: 8pt "DejaVu Sans", Arial, sans-serif; color: #6b7280; } }
body { font-family: "DejaVu Sans", Arial, sans-serif; font-size: 9pt; color: #1f2937; }
header { display: flex; justify-content: space-between; align-items: flex-start;
  border-bottom: 3px solid __COLOR__; padding-bottom: 10px; margin-bottom: 14px; }
.logo { max-height: 60px; max-width: 200px; margin-bottom: 6px; display: block; }
.empresa strong { font-size: 11pt; } .empresa div { color: #4b5563; }
.numero { text-align: right; } .numero h1 { margin: 0; color: __COLOR__; font-size: 15pt; }
.numero .n { font-size: 12pt; font-weight: bold; }
h2 { font-size: 9pt; text-transform: uppercase; letter-spacing: .04em; color: __COLOR__;
  margin: 14px 0 6px; }
.rejilla { display: grid; grid-template-columns: repeat(__COLUMNAS__, 1fr); gap: 0 18px; }
table { width: 100%; border-collapse: collapse; }
.datos th { text-align: left; color: #6b7280; font-weight: normal; width: 38%;
  padding: 2px 6px 2px 0; vertical-align: top; }
.datos td { padding: 2px 0; }
.lineas th { background: __COLOR__; color: #fff; text-align: left; padding: 5px 6px;
  font-weight: 600; }
.lineas td { border-bottom: 1px solid #e5e7eb; padding: 5px 6px; vertical-align: top; }
.lineas tr:nth-child(even) td { background: #f8fafc; }
.num { text-align: right; white-space: nowrap; }
.lineas th, .col-codigo, .col-numero, .col-unidad, .col-solicitud { white-space: nowrap; }
.totales { width: 45%; margin: 8px 0 0 auto; }
.totales th { text-align: left; padding: 3px 6px; color: #4b5563; font-weight: normal; }
.totales td { text-align: right; padding: 3px 6px; }
.totales .total th, .totales .total td { border-top: 2px solid __COLOR__; font-weight: bold;
  font-size: 11pt; }
.terminos p { color: #4b5563; font-size: 8pt; }
.firmas { display: flex; flex-wrap: wrap; gap: 18px; margin-top: 26px; }
.firma { width: 150px; display: flex; flex-direction: column; font-size: 8pt; }
.firma .raya { border-top: 1px solid #9ca3af; margin-bottom: 4px; }
.firma span { color: #6b7280; }
.marca-agua { position: fixed; top: 40%; left: 0; right: 0; text-align: center; font-size: 60pt;
  color: rgba(220, 38, 38, .12); transform: rotate(-25deg); font-weight: bold; }
"""


def generar(config: dict, datos: dict, logo: str | None) -> bytes:
    from weasyprint import HTML  # carga diferida: solo al generar

    return HTML(string=html(config, datos, logo)).write_pdf()


def pdf_orden(db: Session, orden: Orden) -> bytes:
    formato = obtener_formato(db, orden.empresa_id)
    return generar(configuracion(formato), datos_orden(db, orden), _logo(db, formato))


def pdf_vista_previa(db: Session, empresa_id: uuid.UUID, config: dict | None) -> bytes:
    formato = obtener_formato(db, empresa_id)
    return generar(
        _normalizar(config or formato.configuracion),
        datos_ejemplo(db, empresa_id),
        _logo(db, formato),
    )
