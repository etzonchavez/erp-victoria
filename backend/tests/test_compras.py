# ruff: noqa: F811  (las fixtures importadas se reciben como argumentos)
"""Órdenes de compra: desde solicitudes completas o directas, aprobación y PDF."""

import pytest

from tests.conftest import API as API_SEG
from tests.test_maestros import RUC_BCP
from tests.test_solicitudes import (  # noqa: F401  (fixtures)
    MAE,
    accion,
    emp,
    gente,
    h,
    nivel,
    regla,
    solicitud,
    u,
    usuario,
)

CMP = "/api/v1/compras"
SOL = "/api/v1/solicitudes"


@pytest.fixture
def base(client, h, emp, gente):
    client.patch(f"{API_SEG}/modulos/compras", headers=h, json={"activo": True})
    prov = client.post(
        f"{MAE}/proveedores",
        headers=h,
        json={
            "tipo_documento": "RUC",
            "numero_documento": RUC_BCP,
            "razon_social": "Banco de Crédito",
        },
    )
    assert prov.status_code == 201, prov.text
    comprador = usuario(client, h, emp, "Compradora", ["ERP_COM_COMPRADOR"])
    # Solicitudes: aprueba Ana. Órdenes: aprueba Beto hasta 1000, luego también Carla.
    regla(client, h, emp, [nivel(u(gente["ana"]))])
    regla(
        client,
        h,
        emp,
        [nivel(u(gente["beto"])), nivel(u(gente["carla"]), desde=1000)],
        documento="orden_compra",
    )
    return {"prov": prov.json()["id"], "comp": comprador}


def aprobada(client, gente, emp, **kw) -> dict:
    s = solicitud(client, gente["sol"], emp, **kw).json()
    accion(client, gente["sol"], s, "enviar")
    r = accion(client, gente["ana"], s, "aprobar").json()
    assert r["estado"] == "aprobada", r
    return r


def orden(client, quien, emp, base, solicitudes=(), lineas=(), **extra):
    datos = {
        "empresa_id": emp["id"],
        "unidad_negocio_id": emp["un"],
        "proveedor_id": base["prov"],
        "solicitudes": [s["id"] for s in solicitudes],
        "lineas": list(lineas),
        **extra,
    }
    return client.post(f"{CMP}/ordenes", headers=quien["h"], json=datos)


def act(client, quien, o, nombre, comentario=None):
    return client.post(
        f"{CMP}/ordenes/{o['id']}/{nombre}", headers=quien["h"], json={"comentario": comentario}
    )


def directa(emp, cantidad=2, precio=100):
    return {
        "articulo_id": emp["art"],
        "cantidad": cantidad,
        "precio": precio,
        "distribuciones": [{"centro_costo_id": emp["centros"]["VEN"], "porcentaje": 100}],
    }


def test_orden_desde_dos_solicitudes_y_una_linea_directa(client, h, emp, gente, base):
    s1 = aprobada(client, gente, emp, precio=10, cantidad=5)
    s2 = aprobada(client, gente, emp, precio=20, cantidad=1)
    disp = client.get(
        f"{CMP}/empresas/{emp['id']}/solicitudes-disponibles", headers=base["comp"]["h"]
    )
    assert {d["numero"] for d in disp.json()} == {s1["numero"], s2["numero"]}
    r = orden(client, base["comp"], emp, base, [s1, s2], [directa(emp)])
    assert r.status_code == 201, r.text
    o = r.json()
    assert o["numero"].endswith("-000001") and o["estado"] == "borrador"
    assert [ln["solicitud_numero"] for ln in o["lineas"]] == [s1["numero"], s2["numero"], None]
    assert float(o["lineas"][0]["cantidad"]) == 5 and float(o["lineas"][0]["tasa"]) == 18
    # 50 + 20 + 200 = 270; IGV 48.60
    assert (o["subtotal"], o["impuesto"], o["total"]) == ("270.00", "48.60", "318.60")
    assert o["lineas"][0]["distribuciones"][0]["centro_costo"] == "ADM"
    # Las solicitudes ya no están disponibles y muestran su orden
    disp = client.get(
        f"{CMP}/empresas/{emp['id']}/solicitudes-disponibles", headers=base["comp"]["h"]
    )
    assert disp.json() == []
    s = client.get(f"{SOL}/{s1['id']}", headers=gente["sol"]["h"]).json()
    assert s["estado"] == "atendida" and s["orden_compra_numero"] == o["numero"]


def test_una_solicitud_no_entra_en_dos_ordenes(client, h, emp, gente, base):
    s1 = aprobada(client, gente, emp)
    assert orden(client, base["comp"], emp, base, [s1]).status_code == 201
    r = orden(client, base["comp"], emp, base, [s1])
    assert r.status_code == 409 and r.json()["codigo"] == "solicitud_no_disponible"


def test_solicitud_no_aprobada_no_entra(client, h, emp, gente, base):
    borrador = solicitud(client, gente["sol"], emp).json()
    r = orden(client, base["comp"], emp, base, [borrador])
    assert r.json()["codigo"] == "solicitud_no_disponible"


def test_precio_e_impuesto_de_la_linea_de_solicitud(client, h, emp, gente, base):
    s1 = aprobada(client, gente, emp, precio=10, cantidad=5)
    sl = client.get(
        f"{CMP}/empresas/{emp['id']}/solicitudes-disponibles", headers=base["comp"]["h"]
    ).json()[0]["lineas"][0]
    r = orden(
        client,
        base["comp"],
        emp,
        base,
        [s1],
        [{"solicitud_linea_id": sl["id"], "precio": 12, "impuesto_id": None}],
    ).json()
    assert float(r["lineas"][0]["precio"]) == 12 and float(r["total"]) == 60


def test_quitar_solicitud_al_editar_la_libera(client, h, emp, gente, base):
    s1, s2 = aprobada(client, gente, emp), aprobada(client, gente, emp)
    o = orden(client, base["comp"], emp, base, [s1, s2]).json()
    datos = {
        "unidad_negocio_id": emp["un"],
        "proveedor_id": base["prov"],
        "solicitudes": [s1["id"]],
    }
    r = client.put(f"{CMP}/ordenes/{o['id']}", headers=base["comp"]["h"], json=datos)
    assert r.status_code == 200 and r.json()["solicitudes"] == [s1["numero"]]
    assert client.get(f"{SOL}/{s2['id']}", headers=gente["sol"]["h"]).json()["estado"] == "aprobada"


def test_aprobacion_por_monto_y_envio_al_proveedor(client, h, emp, gente, base):
    o = orden(
        client, base["comp"], emp, base, lineas=[directa(emp, cantidad=10, precio=100)]
    ).json()
    ruta = client.get(f"{CMP}/ordenes/{o['id']}/ruta", headers=base["comp"]["h"]).json()
    assert [n["numero"] for n in ruta["niveles"]] == [1, 2]  # 1180 ≥ 1000
    r = act(client, base["comp"], o, "enviar").json()
    assert r["estado"] == "en_aprobacion" and r["pendiente_de"] == ["Beto"]
    assert r["lineas"][0]["cuenta"]
    bandeja = client.get(f"{CMP}/bandeja", headers=gente["beto"]["h"]).json()
    assert [b["numero"] for b in bandeja] == [o["numero"]]
    act(client, gente["beto"], o, "aprobar")
    r = act(client, gente["carla"], o, "aprobar").json()
    assert r["estado"] == "aprobada" and r["acciones"]["marcar_enviada"] is False
    propia = client.get(f"{CMP}/ordenes/{o['id']}", headers=base["comp"]["h"]).json()
    assert propia["acciones"]["marcar_enviada"]
    r = act(client, base["comp"], o, "enviada").json()
    assert r["estado"] == "enviada" and r["enviada_en"]


def test_monto_bajo_solo_un_nivel(client, h, emp, gente, base):
    o = orden(client, base["comp"], emp, base, lineas=[directa(emp, cantidad=1, precio=100)]).json()
    r = act(client, base["comp"], o, "enviar").json()
    assert act(client, gente["beto"], o, "aprobar").json()["estado"] == "aprobada"
    assert r["pendiente_de"] == ["Beto"]


def test_rechazo_libera_las_solicitudes(client, h, emp, gente, base):
    s1 = aprobada(client, gente, emp)
    o = orden(client, base["comp"], emp, base, [s1]).json()
    act(client, base["comp"], o, "enviar")
    r = act(client, gente["beto"], o, "rechazar", "Proveedor caro").json()
    assert r["estado"] == "rechazada"
    s = client.get(f"{SOL}/{s1['id']}", headers=gente["sol"]["h"]).json()
    assert s["estado"] == "aprobada" and s["orden_compra_numero"] is None


def test_anular_orden_enviada_requiere_permiso_y_libera(client, h, emp, gente, base):
    s1 = aprobada(client, gente, emp)
    o = orden(client, base["comp"], emp, base, [s1]).json()
    act(client, base["comp"], o, "enviar")
    act(client, gente["beto"], o, "aprobar")
    act(client, base["comp"], o, "enviada")
    assert act(client, base["comp"], o, "anular", "No llegó").status_code == 403
    jefe = usuario(client, h, emp, "JefaCompras", ["ERP_COM_ADMINISTRADOR"])
    assert act(client, jefe, o, "anular", "No llegó").json()["estado"] == "anulada"
    assert client.get(f"{SOL}/{s1['id']}", headers=gente["sol"]["h"]).json()["estado"] == "aprobada"


def test_proveedor_bloqueado_no_se_usa(client, h, emp, gente, base):
    client.put(
        f"{MAE}/proveedores/{base['prov']}/empresas/{emp['id']}",
        headers=h,
        json={"bloqueado": True, "motivo": "Deuda"},
    )
    r = orden(client, base["comp"], emp, base, lineas=[directa(emp)])
    assert r.json()["codigo"] == "proveedor_no_habilitado"


def test_sin_lineas(client, h, emp, gente, base):
    assert orden(client, base["comp"], emp, base).json()["codigo"] == "sin_lineas"


def test_reglas_de_orden_separadas_de_solicitudes(client, h, emp, gente, base):
    r = client.get(
        f"/api/v1/aprobaciones/empresas/{emp['id']}/reglas",
        headers=h,
        params={"documento": "orden_compra"},
    ).json()
    assert len(r) == 1 and len(r[0]["niveles"]) == 2
    consulta = usuario(client, h, emp, "SoloSol", ["ERP_SOL_CONFIGURADOR"])
    r = client.get(
        f"/api/v1/aprobaciones/empresas/{emp['id']}/reglas",
        headers=consulta["h"],
        params={"documento": "orden_compra"},
    )
    assert r.status_code == 403


# ---------------------------------------------------------------- PDF


def test_pdf_de_la_orden_y_formato(client, h, emp, gente, base):
    o = orden(client, base["comp"], emp, base, lineas=[directa(emp)]).json()
    r = client.get(f"{CMP}/ordenes/{o['id']}/pdf", headers=base["comp"]["h"])
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")
    f = client.get(f"{CMP}/empresas/{emp['id']}/formato", headers=h).json()
    config = {
        **f["configuracion"],
        "color": "#0f766e",
        "columnas": ["codigo", "descripcion", "total"],
    }
    r = client.put(f"{CMP}/empresas/{emp['id']}/formato", headers=h, json={"configuracion": config})
    assert r.json()["configuracion"]["color"] == "#0f766e"
    sin_desc = {**config, "columnas": ["codigo"]}
    r = client.put(
        f"{CMP}/empresas/{emp['id']}/formato", headers=h, json={"configuracion": sin_desc}
    )
    assert r.json()["codigo"] == "columnas_invalidas"
    r = client.post(
        f"{CMP}/empresas/{emp['id']}/formato/vista-previa",
        headers=h,
        json={"configuracion": config},
    )
    assert r.content.startswith(b"%PDF")
    assert (
        client.get(f"{CMP}/empresas/{emp['id']}/formato", headers=base["comp"]["h"]).status_code
        == 403
    )


def test_html_del_formato_respeta_secciones_y_columnas():
    from app.modules.compras import pdf

    config = pdf._normalizar(
        {
            "secciones": [
                {"codigo": "lineas", "activo": True},
                {"codigo": "proveedor", "activo": False},
            ],
            "columnas": ["descripcion", "total"],
            "titulo": "PEDIDO",
        }
    )
    assert config["secciones"][0] == {"codigo": "lineas", "activo": True}
    activas = [s["codigo"] for s in config["secciones"] if s["activo"]]
    assert activas == ["lineas"]  # las no enviadas quedan apagadas
    linea = {c: f"<{c}>" for c in pdf.COLUMNAS}
    datos = {
        "empresa": {"razon_social": "ACME", "identificacion": "RUC 1", "direccion": ""},
        "numero": "OC-1",
        "fecha": "01/01/2026",
        "estado": "borrador",
        "estado_nombre": "Borrador",
        "lineas": [linea],
        "atributos": [],
    }
    texto = pdf.html(config, datos, None)
    assert "PEDIDO" in texto and "BORRADOR" in texto  # marca de agua si no está aprobada
    assert "&lt;total&gt;" in texto and "&lt;codigo&gt;" not in texto  # columnas y escape
    assert "Proveedor" not in texto
