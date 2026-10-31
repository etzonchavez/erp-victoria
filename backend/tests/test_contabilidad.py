from decimal import Decimal

import pytest

from app.localizacion import pais
from tests.conftest import API as API_SEG
from tests.test_maestros import RUC_BCP, crear_empresa, usuario_con_rol

API = "/api/v1/contabilidad"


@pytest.fixture
def h(client, admin):
    for modulo in ("maestros", "contabilidad"):
        r = client.patch(f"{API_SEG}/modulos/{modulo}", headers=admin, json={"activo": True})
        assert r.status_code == 200
    return admin


@pytest.fixture
def empresa(client, h):
    r = crear_empresa(client, h)
    assert r.status_code == 201, r.text
    return r.json()


def cuentas(client, h, empresa) -> dict[str, dict]:
    r = client.get(f"{API}/empresas/{empresa['id']}/cuentas", headers=h)
    return {c["codigo"]: c for c in r.json()}


def perfiles(client, h, empresa) -> dict[str, dict]:
    r = client.get(f"{API}/empresas/{empresa['id']}/perfiles", headers=h)
    return {p["codigo"]: p for p in r.json()}


# ---------------------------------------------------------------- plantilla


def test_al_crear_la_empresa_se_carga_la_plantilla_pcge(client, h, empresa):
    plan = pais("pe").plan_contable
    c = cuentas(client, h, empresa)
    assert len(c) == len(plan.CUENTAS)
    assert c["60"]["nivel"] == 1 and not c["60"]["imputable"]
    assert c["6011"]["padre_id"] == c["601"]["id"] and c["6011"]["imputable"]
    assert c["40111"]["naturaleza"] == "pasivo"
    assert c["20111"]["naturaleza"] == "activo"
    assert c["6011"]["naturaleza"] == "gasto"
    assert {x["plantilla"] for x in c.values()} == {"PCGE-2019"}


def test_perfiles_e_impuestos_precargados(client, h, empresa):
    p = perfiles(client, h, empresa)
    assert set(p) == {
        "MERCADERIA",
        "MATERIA_PRIMA",
        "SUMINISTRO_ALMACEN",
        "CONSUMO_DIRECTO",
        "SERVICIO",
        "ACTIVO_FIJO",
        "ACTIVO_MUEBLES",
        "ACTIVO_MAQUINARIA",
    }
    m = p["MERCADERIA"]
    assert (m["cuenta_cargo"]["codigo"], m["cuenta_existencia"]["codigo"]) == ("6011", "20111")
    assert m["cuenta_variacion"]["codigo"] == "6111"
    assert m["cuenta_por_pagar"]["codigo"] == "4212"
    assert p["SERVICIO"]["cuenta_existencia"] is None
    assert p["ACTIVO_FIJO"]["cuenta_por_pagar"]["codigo"] == "4654"
    imp = {
        i["codigo"]: i
        for i in client.get(f"{API}/empresas/{empresa['id']}/impuestos", headers=h).json()
    }
    assert Decimal(imp["IGV18"]["tasa"]) == 18
    assert imp["IGV18"]["cuenta"]["codigo"] == "40111"
    assert imp["EXO"]["cuenta"] is None


def test_la_plantilla_no_se_recarga_sobre_un_plan_existente(client, h, empresa):
    r = client.post(f"{API}/empresas/{empresa['id']}/plantilla", headers=h)
    assert r.status_code == 409
    assert r.json()["codigo"] == "plan_existente"


def test_empresa_creada_con_contabilidad_inactiva_tambien_recibe_su_plan(client, admin):
    client.patch(f"{API_SEG}/modulos/maestros", headers=admin, json={"activo": True})
    e = crear_empresa(client, admin).json()
    client.patch(f"{API_SEG}/modulos/contabilidad", headers=admin, json={"activo": True})
    assert len(cuentas(client, admin, e)) == len(pais("pe").plan_contable.CUENTAS)


def test_el_plan_es_por_empresa(client, h, empresa):
    otra = crear_empresa(client, h, ruc="20131312955").json()
    a, b = cuentas(client, h, empresa), cuentas(client, h, otra)
    assert set(a) == set(b)
    assert a["6011"]["id"] != b["6011"]["id"]


# ---------------------------------------------------------------- cuentas


def crear_cuenta(client, h, empresa, codigo, nombre="Cuenta de prueba", **extra):
    return client.post(
        f"{API}/empresas/{empresa['id']}/cuentas",
        headers=h,
        json={"codigo": codigo, "nombre": nombre, **extra},
    )


def test_subcuenta_hereda_y_el_padre_deja_de_ser_imputable(client, h, empresa):
    r = crear_cuenta(client, h, empresa, "26111", "Envases – Costo")
    assert r.status_code == 201, r.text
    c = cuentas(client, h, empresa)
    assert c["26111"]["padre_id"] == c["261"]["id"]
    assert c["26111"]["naturaleza"] == "activo" and c["26111"]["nivel"] == c["261"]["nivel"] + 1
    assert not c["261"]["imputable"]


def test_no_se_subdivide_una_cuenta_usada_por_un_perfil(client, h, empresa):
    r = crear_cuenta(client, h, empresa, "60111", "Mercaderías importadas")
    assert r.status_code == 409
    assert r.json()["codigo"] == "cuenta_en_uso"
    assert "MERCADERIA" in r.json()["mensaje"]


@pytest.mark.parametrize(
    ("codigo", "error"),
    [("6011", "cuenta_duplicada"), ("6A", "codigo_invalido"), ("6", "cuenta_intermedia")],
)
def test_validaciones_de_cuenta(client, h, empresa, codigo, error):
    assert crear_cuenta(client, h, empresa, codigo).json()["codigo"] == error


def test_cuenta_de_primer_nivel_toma_la_naturaleza_del_elemento(client, h, empresa):
    r = crear_cuenta(client, h, empresa, "70", "Ventas")
    assert r.json()["naturaleza"] == "ingreso" and r.json()["nivel"] == 1


def test_no_se_desactiva_una_cuenta_en_uso_o_con_subcuentas(client, h, empresa):
    c = cuentas(client, h, empresa)
    r = client.patch(f"{API}/cuentas/{c['40111']['id']}", headers=h, json={"activo": False})
    assert r.json()["codigo"] == "cuenta_en_uso"
    r = client.patch(f"{API}/cuentas/{c['26']['id']}", headers=h, json={"activo": False})
    assert r.json()["codigo"] == "tiene_subcuentas_activas"
    r = client.patch(f"{API}/cuentas/{c['261']['id']}", headers=h, json={"activo": False})
    assert r.status_code == 200 and not r.json()["activo"]


# ---------------------------------------------------------------- perfiles


def test_crear_perfil_valida_las_cuentas_por_tipo(client, h, empresa):
    c = cuentas(client, h, empresa)
    base = {
        "codigo": "util_oficina",
        "nombre": "Útiles de oficina",
        "tipo_articulo": "bien_no_inventariable",
        "cuenta_cargo_id": c["656"]["id"],
        "cuenta_por_pagar_id": c["4212"]["id"],
    }
    url = f"{API}/empresas/{empresa['id']}/perfiles"
    r = client.post(url, headers=h, json={**base, "cuenta_existencia_id": c["2524"]["id"]})
    assert r.json()["codigo"] == "cuenta_no_aplica"
    r = client.post(url, headers=h, json={**base, "cuenta_cargo_id": c["40111"]["id"]})
    assert r.json()["codigo"] == "naturaleza_incorrecta"
    r = client.post(url, headers=h, json={**base, "cuenta_cargo_id": c["65"]["id"]})
    assert r.json()["codigo"] == "cuenta_no_imputable"
    r = client.post(url, headers=h, json=base)
    assert r.status_code == 201 and r.json()["codigo"] == "UTIL_OFICINA"


def test_perfil_inventariable_requiere_existencia_y_variacion(client, h, empresa):
    c = cuentas(client, h, empresa)
    r = client.post(
        f"{API}/empresas/{empresa['id']}/perfiles",
        headers=h,
        json={
            "codigo": "ENVASES",
            "nombre": "Envases",
            "tipo_articulo": "bien_inventariable",
            "cuenta_cargo_id": c["6032"]["id"],
            "cuenta_por_pagar_id": c["4212"]["id"],
        },
    )
    assert r.json()["codigo"] == "cuenta_requerida"


def test_cambiar_cuenta_de_un_perfil_se_valida_y_audita(client, h, empresa):
    c, p = cuentas(client, h, empresa), perfiles(client, h, empresa)
    url = f"{API}/perfiles/{p['SERVICIO']['id']}"
    r = client.patch(url, headers=h, json={"cuenta_cargo_id": c["20111"]["id"]})
    assert r.json()["codigo"] == "naturaleza_incorrecta"
    crear_cuenta(client, h, empresa, "6321", "Asesoría y consultoría")
    nueva = cuentas(client, h, empresa)["6321"]
    r = client.patch(url, headers=h, json={"cuenta_cargo_id": nueva["id"]})
    assert r.status_code == 200 and r.json()["cuenta_cargo"]["codigo"] == "6321"
    eventos = client.get(f"{API_SEG}/auditoria?entidad=perfil_contable", headers=h).json()
    assert eventos and "cuenta_cargo_id" in eventos[0]["detalle"]


def test_perfil_no_usa_cuentas_de_otra_empresa(client, h, empresa):
    otra = crear_empresa(client, h, ruc="20131312955").json()
    ajena = cuentas(client, h, otra)["639"]
    p = perfiles(client, h, empresa)["SERVICIO"]
    r = client.patch(f"{API}/perfiles/{p['id']}", headers=h, json={"cuenta_cargo_id": ajena["id"]})
    assert r.json()["codigo"] == "cuenta_invalida"


# ---------------------------------------------------------------- centros de costo


def test_centros_de_costo_por_unidad_de_negocio(client, h, empresa):
    principal = empresa["unidades"][0]["id"]
    url = f"{API}/empresas/{empresa['id']}/centros-costo"
    r = client.post(
        url,
        headers=h,
        json={"unidad_negocio_id": principal, "codigo": "adm-01", "nombre": "Administración"},
    )
    assert r.status_code == 201 and r.json()["codigo"] == "ADM-01"
    r = client.post(
        url, headers=h, json={"unidad_negocio_id": principal, "codigo": "ADM-01", "nombre": "Otra"}
    )
    assert r.status_code == 409
    otra = crear_empresa(client, h, ruc="20131312955").json()
    r = client.post(
        url,
        headers=h,
        json={"unidad_negocio_id": otra["unidades"][0]["id"], "codigo": "X1", "nombre": "Ajena"},
    )
    assert r.json()["codigo"] == "unidad_otra_empresa"


# ---------------------------------------------------------------- impuestos


def test_impuesto_con_tasa_necesita_cuenta_de_pasivo_o_activo(client, h, empresa):
    c = cuentas(client, h, empresa)
    url = f"{API}/empresas/{empresa['id']}/impuestos"
    r = client.post(url, headers=h, json={"codigo": "ISC", "nombre": "ISC", "tasa": "10"})
    assert r.json()["codigo"] == "cuenta_requerida"
    r = client.post(
        url,
        headers=h,
        json={"codigo": "ISC", "nombre": "ISC", "tasa": "10", "cuenta_id": c["6011"]["id"]},
    )
    assert r.json()["codigo"] == "naturaleza_incorrecta"
    r = client.post(
        url,
        headers=h,
        json={"codigo": "IVAP", "nombre": "IVAP 4 %", "tasa": "4", "cuenta_id": c["40111"]["id"]},
    )
    assert r.status_code == 201


# ---------------------------------------------------------------- permisos


def test_analista_contable_solo_edita_centros_de_costo(client, h, empresa):
    u = usuario_con_rol(client, h, "ERP_CNT_CONFIGURADOR", [empresa])
    assert client.get(f"{API}/empresas/{empresa['id']}/cuentas", headers=u).status_code == 200
    assert crear_cuenta(client, u, empresa, "70", "Ventas").status_code == 403
    r = client.post(
        f"{API}/empresas/{empresa['id']}/centros-costo",
        headers=u,
        json={
            "unidad_negocio_id": empresa["unidades"][0]["id"],
            "codigo": "VEN",
            "nombre": "Ventas",
        },
    )
    assert r.status_code == 201


def test_contabilidad_inactiva_bloquea_su_api(client, admin):
    client.patch(f"{API_SEG}/modulos/maestros", headers=admin, json={"activo": True})
    e = crear_empresa(client, admin, ruc=RUC_BCP).json()
    r = client.get(f"{API}/empresas/{e['id']}/cuentas", headers=admin)
    assert r.json()["codigo"] == "modulo_inactivo"


def test_selector_de_empresas_accesibles(client, h, empresa):
    u = usuario_con_rol(client, h, "ERP_CNT_CONSULTA", [empresa])
    r = client.get("/api/v1/maestros/empresas/accesibles", headers=u)
    assert r.status_code == 200
    assert [e["identificacion_fiscal"] for e in r.json()] == [RUC_BCP]
