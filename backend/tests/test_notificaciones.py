# ruff: noqa: F811  (las fixtures importadas se reciben como argumentos)
"""Notificaciones, momento de reconocimiento del cargo, asiento previo y reporte Excel."""

import io

from openpyxl import load_workbook

from tests.conftest import API as API_SEG
from tests.test_compras import CMP, act, base, directa, orden  # noqa: F401
from tests.test_solicitudes import (  # noqa: F401
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

CNT = "/api/v1/contabilidad"


def avisos(client, quien):
    return client.get(f"{API_SEG}/notificaciones", headers=quien["h"]).json()


def test_avisos_de_aprobacion_y_resultado(client, h, emp, gente):
    g = gente
    regla(client, h, emp, [nivel(u(g["ana"]), u(g["beto"]))])
    s = solicitud(client, g["sol"], emp).json()
    accion(client, g["sol"], s, "enviar")
    a = avisos(client, g["ana"])
    assert a["no_leidas"] == 1 and a["items"][0]["tipo"] == "por_aprobar"
    assert s["numero"] in a["items"][0]["titulo"]
    assert a["items"][0]["enlace"] == f"solicitudes?id={s['id']}"
    assert avisos(client, g["beto"])["no_leidas"] == 0  # en serie: aún no es su turno
    accion(client, g["ana"], s, "aprobar")
    assert avisos(client, g["beto"])["no_leidas"] == 1
    accion(client, g["beto"], s, "devolver", "Falta cotización")
    r = avisos(client, g["sol"])
    assert r["items"][0]["tipo"] == "devuelto" and "Falta cotización" in r["items"][0]["mensaje"]


def test_marcar_leidas(client, h, emp, gente):
    g = gente
    regla(client, h, emp, [nivel(u(g["ana"]))])
    for _ in range(2):
        s = solicitud(client, g["sol"], emp).json()
        accion(client, g["sol"], s, "enviar")
    a = avisos(client, g["ana"])
    assert a["no_leidas"] == 2
    r = client.post(f"{API_SEG}/notificaciones/{a['items'][0]['id']}/leida", headers=g["ana"]["h"])
    assert r.json()["leida_en"]
    assert avisos(client, g["ana"])["no_leidas"] == 1
    client.post(f"{API_SEG}/notificaciones/leidas", headers=g["ana"]["h"])
    assert avisos(client, g["ana"])["no_leidas"] == 0
    otro = client.post(
        f"{API_SEG}/notificaciones/{a['items'][0]['id']}/leida", headers=g["beto"]["h"]
    )
    assert otro.status_code == 404


def test_rol_avisa_a_sus_usuarios_con_acceso(client, h, emp, gente):
    g = gente
    gerente = usuario(client, h, emp, "Gerente", ["ERP_SOL_CONSULTA"])
    roles = {r["codigo"]: r["id"] for r in client.get(f"{API_SEG}/roles", headers=h).json()}
    regla(client, h, emp, [nivel({"tipo": "rol", "rol_id": roles["ERP_SOL_CONSULTA"]})])
    s = solicitud(client, g["sol"], emp).json()
    accion(client, g["sol"], s, "enviar")
    assert avisos(client, gerente)["no_leidas"] == 1


def test_orden_enviada_avisa_al_solicitante(client, h, emp, gente, base):
    g = gente
    s = solicitud(client, g["sol"], emp).json()
    accion(client, g["sol"], s, "enviar")
    accion(client, g["ana"], s, "aprobar")
    o = orden(client, base["comp"], emp, base, [s]).json()
    act(client, base["comp"], o, "enviar")
    act(client, g["beto"], o, "aprobar")
    assert avisos(client, base["comp"])["items"][0]["tipo"] == "aprobado"
    act(client, base["comp"], o, "enviada")
    tipos = [n["tipo"] for n in avisos(client, g["sol"])["items"]]
    assert tipos[0] == "enviada"


# ---------------------------------------------------------------- reconocimiento y asiento


def test_configuracion_de_reconocimiento(client, h, emp):
    r = client.get(f"{CNT}/empresas/{emp['id']}/reconocimiento", headers=h).json()
    momentos = {m["tipo_articulo"]: m["momento"] for m in r["momentos"]}
    assert momentos["servicio"] == "facturacion" and momentos["bien_inventariable"] == "recepcion"
    assert r["cuenta_recepcion"].startswith("4211")
    r = client.put(
        f"{CNT}/empresas/{emp['id']}/reconocimiento",
        headers=h,
        json={"momentos": {"servicio": "recepcion"}, "cuenta_recepcion_id": None},
    )
    assert r.json()["codigo"] == "cuenta_recepcion_requerida"
    r = client.put(
        f"{CNT}/empresas/{emp['id']}/reconocimiento",
        headers=h,
        json={"momentos": {"servicio": "otro"}},
    )
    assert r.json()["codigo"] == "momento_invalido"


def test_asiento_previo_segun_momento(client, h, emp, gente, base):
    # El artículo de prueba es no inventariable: se reconoce al recibir (por defecto)
    o = orden(client, base["comp"], emp, base, lineas=[directa(emp, cantidad=2, precio=100)]).json()
    a = client.get(f"{CMP}/ordenes/{o['id']}/asiento", headers=base["comp"]["h"]).json()
    assert [x["momento"] for x in a["asientos"]] == ["recepcion", "facturacion"]
    assert all(x["cuadra"] for x in a["asientos"])
    recep = {f["cuenta"]: f for f in a["asientos"][0]["filas"]}
    assert float(recep["4211"]["haber"]) == 200
    fact = {f["cuenta"]: f for f in a["asientos"][1]["filas"]}
    assert float(fact["4211"]["debe"]) == 200 and float(fact["40111"]["debe"]) == 36
    assert float(fact["4212"]["haber"]) == 236
    # Al facturar: un solo asiento
    cfg = client.get(f"{CNT}/empresas/{emp['id']}/reconocimiento", headers=h).json()
    client.put(
        f"{CNT}/empresas/{emp['id']}/reconocimiento",
        headers=h,
        json={
            "momentos": {"bien_no_inventariable": "facturacion"},
            "cuenta_recepcion_id": cfg["cuenta_recepcion_id"],
        },
    )
    a = client.get(f"{CMP}/ordenes/{o['id']}/asiento", headers=base["comp"]["h"]).json()
    assert [x["momento"] for x in a["asientos"]] == ["facturacion"]
    filas = a["asientos"][0]["filas"]
    assert sum(float(f["debe"]) for f in filas) == 236 and a["asientos"][0]["cuadra"]


# ---------------------------------------------------------------- reporte


def test_reporte_excel(client, h, emp, gente, base):
    g = gente
    s = solicitud(client, g["sol"], emp).json()  # sin orden
    o = orden(client, base["comp"], emp, base, lineas=[directa(emp)]).json()
    r = client.get(f"{CMP}/empresas/{emp['id']}/reporte", headers=h)
    assert r.status_code == 200
    hoja = load_workbook(io.BytesIO(r.content)).active
    filas = [[c.value for c in fila] for fila in hoja.iter_rows(min_row=5)]
    assert [f[0] for f in filas] == [o["numero"], None]
    assert filas[1][17] == s["numero"] and filas[1][2] == "Sin orden"
    r = client.get(f"{CMP}/empresas/{emp['id']}/reporte", headers=h, params={"estado": "aprobada"})
    assert list(load_workbook(io.BytesIO(r.content)).active.iter_rows(min_row=5)) == []
    assert (
        client.get(f"{CMP}/empresas/{emp['id']}/reporte", headers=g["sol"]["h"]).status_code == 403
    )
