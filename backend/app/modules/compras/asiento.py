"""Vista previa del asiento contable de una orden de compra (ADR-004: no se contabiliza).

Según la configuración de Contabilidad (cuándo se reconoce el cargo por tipo de artículo):

- Al recibir:   Debe gasto/compra por centro · Haber cuenta puente (4211 no emitidas)
  y al facturar: Debe cuenta puente + IGV       · Haber cuenta por pagar del perfil (4212).
- Al facturar:  Debe gasto/compra por centro + IGV · Haber cuenta por pagar del perfil (4212).

Para bienes inventariables se agrega el asiento de destino (Debe existencias · Haber variación)
en el mismo momento en que se reconoce la compra.
"""

from collections import OrderedDict
from decimal import Decimal

from sqlalchemy.orm import Session

from app.modules.compras.models import Orden
from app.modules.contabilidad import service as contabilidad
from app.modules.contabilidad.models import Cuenta, Impuesto, Perfil
from app.modules.maestros import service as maestros

TITULOS = {
    "recepcion": "Al recibir la mercadería o el servicio",
    "facturacion": "Al registrar la factura",
}


class _Asiento:
    def __init__(self) -> None:
        self.filas: OrderedDict[tuple, dict] = OrderedDict()

    def agregar(
        self, cuenta: Cuenta | None, lado: str, monto: Decimal, glosa: str, centro: str = ""
    ):
        if not monto:
            return
        clave = (cuenta.id if cuenta else None, centro, lado, glosa)
        fila = self.filas.setdefault(
            clave,
            {
                "cuenta": cuenta.codigo if cuenta else "—",
                "nombre": cuenta.nombre if cuenta else "Falta configurar la cuenta",
                "centro_costo": centro or None,
                "glosa": glosa,
                "debe": Decimal(0),
                "haber": Decimal(0),
            },
        )
        fila[lado] += monto

    def lista(self) -> list[dict]:
        orden = sorted(self.filas.values(), key=lambda f: (f["debe"] == 0, f["cuenta"]))
        return orden


def vista_previa(db: Session, orden: Orden) -> dict:
    config = contabilidad.obtener_config_cxp(db, orden.empresa_id)
    momentos = contabilidad.momentos_cxp(config)
    puente = db.get(Cuenta, config.cuenta_recepcion_id) if config.cuenta_recepcion_id else None
    asientos = {"recepcion": _Asiento(), "facturacion": _Asiento()}
    avisos: list[str] = []

    for ln in orden.lineas:
        art = maestros.obtener_articulo(db, ln.articulo_id)
        perfil = db.get(Perfil, ln.perfil_id) if ln.perfil_id else None
        if not perfil:
            perfil, _ = contabilidad.perfil_de_articulo(db, orden.empresa_id, art)
        if not perfil:
            avisos.append(f"Línea {ln.numero}: el artículo {art.codigo} no tiene perfil contable")
            continue
        cargo = db.get(Cuenta, ln.cuenta_id) if ln.cuenta_id else perfil.cuenta_cargo
        por_pagar = db.get(Cuenta, perfil.cuenta_por_pagar_id)
        imp = db.get(Impuesto, ln.impuesto_id) if ln.impuesto_id else None
        momento = momentos.get(art.tipo, "facturacion")
        glosa = f"{art.codigo} · línea {ln.numero}"
        reconoce = asientos[momento]

        for d in ln.distribuciones:
            centro = contabilidad.obtener_centro(db, d.centro_costo_id).codigo
            reconoce.agregar(cargo, "debe", d.monto, glosa, centro)
        if perfil.cuenta_existencia and perfil.cuenta_variacion:
            reconoce.agregar(perfil.cuenta_existencia, "debe", ln.subtotal, f"Destino · {glosa}")
            reconoce.agregar(perfil.cuenta_variacion, "haber", ln.subtotal, f"Destino · {glosa}")

        factura = asientos["facturacion"]
        if momento == "recepcion":
            if not puente:
                avisos.append(
                    "Falta la cuenta puente de recepción en Configuración › Cuentas por pagar"
                )
            reconoce.agregar(puente, "haber", ln.subtotal, "Recepción por facturar")
            factura.agregar(puente, "debe", ln.subtotal, "Recepción por facturar")
        if ln.impuesto_monto:
            if imp and not imp.cuenta:
                avisos.append(f"El impuesto {imp.codigo} no tiene cuenta contable")
            factura.agregar(
                imp.cuenta if imp else None,
                "debe",
                ln.impuesto_monto,
                imp.nombre if imp else "Impuesto",
            )
        factura.agregar(por_pagar, "haber", ln.total, "Proveedor")

    tc = orden.tipo_cambio or Decimal(1)
    resultado = []
    for momento, asiento in asientos.items():
        filas = asiento.lista()
        if not filas:
            continue
        debe = sum((f["debe"] for f in filas), Decimal(0))
        haber = sum((f["haber"] for f in filas), Decimal(0))
        resultado.append(
            {
                "momento": momento,
                "titulo": TITULOS[momento],
                "filas": filas,
                "debe": debe,
                "haber": haber,
                "cuadra": debe == haber,
            }
        )
    empresa = maestros.obtener_empresa(db, orden.empresa_id)
    return {
        "moneda": orden.moneda,
        "moneda_funcional": empresa.moneda_funcional,
        "tipo_cambio": tc,
        "asientos": resultado,
        "avisos": list(dict.fromkeys(avisos)),
        "momentos": [{"tipo_articulo": t, "momento": m} for t, m in momentos.items()],
    }
