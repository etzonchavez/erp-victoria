from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.localizacion.pe import validar_ruc
from app.modules.maestros import service
from tests.conftest import API as API_SEG
from tests.conftest import login

API = "/api/v1/maestros"
RUC_BCP = "20100047218"
RUC_SUNAT = "20131312955"


@pytest.fixture
def activo(client, admin):
    """Maestros viene desactivado: el administrador lo activa."""
    r = client.patch(f"{API_SEG}/modulos/maestros", headers=admin, json={"activo": True})
    assert r.status_code == 200
    return admin


def crear_empresa(client, h, ruc=RUC_BCP, **extra):
    return client.post(
        f"{API}/empresas",
        headers=h,
        json={"identificacion_fiscal": ruc, "razon_social": "ACME S.A.C.", **extra},
    )


def usuario_con_rol(client, admin, rol: str) -> dict:
    roles = {r["codigo"]: r["id"] for r in client.get(f"{API_SEG}/roles", headers=admin).json()}
    email = f"{rol.lower()}@empresa.pe"
    r = client.post(
        f"{API_SEG}/usuarios",
        headers=admin,
        json={"email": email, "nombre": "Usuario", "password": "Clave1234", "roles": [roles[rol]]},
    )
    assert r.status_code == 201, r.text
    return login(client, email, "Clave1234")


# ---------------------------------------------------------------- RUC


@pytest.mark.parametrize(
    ("ruc", "valido"),
    [
        (RUC_BCP, True),
        (RUC_SUNAT, True),
        ("20100047219", False),  # dígito verificador
        ("2010004721", False),  # largo
        ("30100047218", False),  # prefijo
        ("2010004721A", False),
    ],
)
def test_validacion_de_ruc(ruc, valido):
    assert (validar_ruc(ruc) is None) == valido


# ---------------------------------------------------------------- empresas


def test_modulo_inactivo_bloquea_maestros(client, admin):
    r = client.get(f"{API}/empresas", headers=admin)
    assert r.status_code == 403
    assert r.json()["codigo"] == "modulo_inactivo"


def test_crear_empresa_con_unidad_principal_y_moneda_del_pais(client, activo):
    r = crear_empresa(client, activo)
    assert r.status_code == 201, r.text
    e = r.json()
    assert e["pais"] == "pe" and e["moneda_funcional"] == "PEN"
    assert [u["codigo"] for u in e["unidades"]] == ["PRINCIPAL"]


def test_ruc_invalido_o_duplicado(client, activo):
    r = crear_empresa(client, activo, ruc="20100047219")
    assert r.status_code == 422
    assert r.json()["codigo"] == "identificacion_fiscal_invalida"
    assert crear_empresa(client, activo).status_code == 201
    r = crear_empresa(client, activo, ruc=f" {RUC_BCP} ")
    assert r.status_code == 409


def test_multiempresa(client, activo):
    crear_empresa(client, activo)
    crear_empresa(client, activo, ruc=RUC_SUNAT, moneda_funcional="USD")
    empresas = client.get(f"{API}/empresas", headers=activo).json()
    assert len(empresas) == 2
    assert {e["moneda_funcional"] for e in empresas} == {"PEN", "USD"}


def test_pais_no_disponible(client, activo):
    r = crear_empresa(client, activo, pais="co")
    assert r.status_code == 422
    assert r.json()["codigo"] == "pais_no_disponible"


def test_ruc_y_moneda_funcional_no_cambian(client, activo):
    e = crear_empresa(client, activo).json()
    r = client.patch(
        f"{API}/empresas/{e['id']}",
        headers=activo,
        json={"razon_social": "ACME Perú S.A.C.", "identificacion_fiscal": RUC_SUNAT},
    )
    assert r.status_code == 200
    assert r.json()["razon_social"] == "ACME Perú S.A.C."
    assert r.json()["identificacion_fiscal"] == RUC_BCP


def test_unidades_de_negocio(client, activo):
    e = crear_empresa(client, activo).json()
    url = f"{API}/empresas/{e['id']}/unidades-negocio"
    r = client.post(url, headers=activo, json={"codigo": "lima", "nombre": "Sede Lima"})
    assert r.status_code == 201 and r.json()["codigo"] == "LIMA"
    assert (
        client.post(url, headers=activo, json={"codigo": "LIMA", "nombre": "Otra"}).status_code
        == 409
    )
    assert (
        client.post(url, headers=activo, json={"codigo": "LI MA", "nombre": "Mal"}).status_code
        == 422
    )


def test_no_se_desactiva_la_ultima_unidad_de_negocio(client, activo):
    e = crear_empresa(client, activo).json()
    principal = e["unidades"][0]["id"]
    r = client.patch(f"{API}/unidades-negocio/{principal}", headers=activo, json={"activo": False})
    assert r.status_code == 409
    assert r.json()["codigo"] == "ultima_unidad_negocio"


# ---------------------------------------------------------------- monedas


def test_monedas_precargadas(client, activo):
    monedas = {m["codigo"]: m for m in client.get(f"{API}/monedas", headers=activo).json()}
    assert {"PEN", "USD", "EUR", "COP", "PAB", "CLP"} <= set(monedas)
    assert monedas["PEN"]["activo"] and monedas["USD"]["activo"]
    assert not monedas["EUR"]["activo"]
    assert monedas["CLP"]["decimales"] == 0


def test_moneda_funcional_no_se_desactiva(client, activo):
    crear_empresa(client, activo)
    r = client.patch(f"{API}/monedas/PEN", headers=activo, json={"activo": False})
    assert r.status_code == 409
    assert r.json()["codigo"] == "moneda_en_uso"


def test_agregar_moneda_iso(client, activo):
    assert (
        client.post(
            f"{API}/monedas",
            headers=activo,
            json={"codigo": "brl", "nombre": "Real brasileño", "simbolo": "R$"},
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"{API}/monedas",
            headers=activo,
            json={"codigo": "B1L", "nombre": "Mal", "simbolo": "X"},
        ).status_code
        == 422
    )


# ---------------------------------------------------------------- tipo de cambio


def tc(client, h, fecha, compra="3.700", venta="3.720", moneda="USD"):
    return client.put(
        f"{API}/tipos-cambio",
        headers=h,
        json={"moneda": moneda, "fecha": fecha.isoformat(), "compra": compra, "venta": venta},
    )


def test_registrar_y_corregir_tipo_de_cambio(client, activo):
    hoy = date.today()
    assert tc(client, activo, hoy).status_code == 200
    r = tc(client, activo, hoy, venta="3.725")
    assert Decimal(r.json()["venta"]) == Decimal("3.725")
    assert len(client.get(f"{API}/tipos-cambio?moneda=USD", headers=activo).json()) == 1


def test_tipo_de_cambio_vigente_usa_el_ultimo_anterior(client, activo):
    hoy = date.today()
    tc(client, activo, hoy - timedelta(days=3), venta="3.700", compra="3.690")
    tc(client, activo, hoy - timedelta(days=1), venta="3.750", compra="3.740")
    r = client.get(
        f"{API}/tipos-cambio/vigente?moneda=USD&fecha={(hoy - timedelta(days=2)).isoformat()}",
        headers=activo,
    )
    assert Decimal(r.json()["venta"]) == Decimal("3.700")
    r = client.get(f"{API}/tipos-cambio/vigente?moneda=USD", headers=activo)
    assert Decimal(r.json()["venta"]) == Decimal("3.750")
    r = client.get(f"{API}/tipos-cambio/vigente?moneda=USD&fecha=2000-01-01", headers=activo)
    assert r.status_code == 404 and r.json()["codigo"] == "sin_tipo_cambio"


@pytest.mark.parametrize(
    ("dias", "compra", "venta", "moneda", "codigo"),
    [
        (-1, "3.7", "3.72", "USD", "fecha_futura"),
        (0, "3.8", "3.7", "USD", "venta_menor_compra"),
        (0, "1", "1", "PEN", "misma_moneda"),
        (0, "4.0", "4.1", "EUR", "moneda_inactiva"),
    ],
)
def test_validaciones_de_tipo_de_cambio(client, activo, dias, compra, venta, moneda, codigo):
    r = tc(client, activo, date.today() - timedelta(days=dias), compra, venta, moneda)
    assert r.status_code == 422
    assert r.json()["codigo"] == codigo


def test_analista_registra_tipo_de_cambio_pero_no_crea_empresas(client, activo):
    h = usuario_con_rol(client, activo, "ERP_MAE_ANALISTA")
    assert tc(client, h, date.today()).status_code == 200
    assert crear_empresa(client, h).status_code == 403


def test_consulta_solo_lee(client, activo):
    h = usuario_con_rol(client, activo, "ERP_MAE_CONSULTA")
    assert client.get(f"{API}/monedas", headers=h).status_code == 200
    assert tc(client, h, date.today()).status_code == 403


# ---------------------------------------------------------------- unidades de medida


def test_unidades_sunat_precargadas(client, activo):
    unidades = {u["codigo"]: u for u in client.get(f"{API}/unidades-medida", headers=activo).json()}
    assert unidades["UND"]["codigo_oficial"] == "NIU"
    assert unidades["SRV"]["codigo_oficial"] == "ZZ"
    assert unidades["KG"]["codigo_oficial"] == "KGM"


def test_crear_unidad_y_validar_tipo(client, activo):
    r = client.post(
        f"{API}/unidades-medida",
        headers=activo,
        json={"codigo": "bls", "nombre": "Bolsa", "codigo_oficial": "bg", "tipo": "cantidad"},
    )
    assert (
        r.status_code == 201 and r.json()["codigo"] == "BLS" and r.json()["codigo_oficial"] == "BG"
    )
    r = client.post(
        f"{API}/unidades-medida",
        headers=activo,
        json={"codigo": "XX", "nombre": "Mal", "codigo_oficial": "XX", "tipo": "color"},
    )
    assert r.json()["codigo"] == "tipo_invalido"


def test_conversiones(client, activo, db):
    r = client.post(
        f"{API}/conversiones", headers=activo, json={"origen": "KG", "destino": "L", "factor": "1"}
    )
    assert r.json()["codigo"] == "tipos_distintos"
    r = client.post(
        f"{API}/conversiones",
        headers=activo,
        json={"origen": "G", "destino": "KG", "factor": "0.001"},
    )
    assert r.status_code == 409  # ya existe KG → G
    with db() as s:
        assert service.convertir(s, Decimal("2"), "KG", "G") == Decimal("2000")
        assert service.convertir(s, Decimal("500"), "G", "KG") == Decimal("0.5")
        assert service.convertir(s, Decimal("3"), "DOC", "UND") == Decimal("36")


def test_maestros_quedan_auditados(client, activo):
    crear_empresa(client, activo)
    tc(client, activo, date.today())
    eventos = client.get(f"{API_SEG}/auditoria", headers=activo).json()
    entidades = {e["entidad"] for e in eventos}
    assert {"empresa", "tipo_cambio"} <= entidades
