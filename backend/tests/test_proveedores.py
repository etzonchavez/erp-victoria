import uuid

import pytest

from app.modules.maestros import service
from tests.conftest import API as API_SEG
from tests.test_maestros import RUC_BCP, RUC_SUNAT, crear_empresa, usuario_con_rol

MAE = "/api/v1/maestros"
CCI = "00219300123456789012"


@pytest.fixture
def h(client, admin):
    client.patch(f"{API_SEG}/modulos/maestros", headers=admin, json={"activo": True})
    return admin


def crear(client, h, **datos):
    base = {
        "tipo_documento": "RUC",
        "numero_documento": RUC_BCP,
        "razon_social": "Banco de Crédito",
    }
    return client.post(f"{MAE}/proveedores", headers=h, json={**base, **datos})


@pytest.fixture
def prov(client, h):
    r = crear(client, h)
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------- documento


@pytest.mark.parametrize(
    ("datos", "codigo"),
    [
        ({"numero_documento": "20100047219"}, "documento_invalido"),
        ({"tipo_documento": "DNI", "numero_documento": "1234567"}, "documento_invalido"),
        ({"tipo_documento": "CE", "numero_documento": "123456"}, "tipo_documento_invalido"),
        ({"tipo_documento": "EXT", "numero_documento": "94-1234567"}, "pais_invalido"),
        (
            {"tipo_documento": "EXT", "numero_documento": "94-1234567", "pais": "pe"},
            "pais_invalido",
        ),
        ({"tipo_documento": "EXT", "numero_documento": "@@@", "pais": "us"}, "documento_invalido"),
        ({"correo": "no-es-correo"}, "correo_invalido"),
    ],
)
def test_validaciones_de_documento(client, h, datos, codigo):
    assert crear(client, h, **datos).json()["codigo"] == codigo


def test_proveedor_local_por_defecto_en_soles_y_contado(client, h, prov):
    assert prov["pais"] == "pe" and prov["moneda"] == "PEN"
    assert prov["condicion_pago"]["codigo"] == "CONTADO"


def test_proveedor_del_exterior_en_dolares(client, h):
    r = crear(
        client,
        h,
        tipo_documento="EXT",
        numero_documento="94-1234567",
        pais="US",
        razon_social="ACME Inc.",
    )
    assert r.status_code == 201
    assert (r.json()["pais"], r.json()["moneda"]) == ("us", "USD")


def test_dni_y_duplicados(client, h, prov):
    assert (
        crear(
            client, h, tipo_documento="DNI", numero_documento="45678912", razon_social="Juan Pérez"
        ).status_code
        == 201
    )
    r = crear(client, h, numero_documento=f" {RUC_BCP} ")
    assert r.status_code == 409 and "Banco de Crédito" in r.json()["mensaje"]


def test_busqueda_por_nombre_o_documento(client, h, prov):
    crear(client, h, numero_documento=RUC_SUNAT, razon_social="SUNAT")

    def nombres(q):
        r = client.get(f"{MAE}/proveedores?buscar={q}", headers=h)
        return [p["razon_social"] for p in r.json()]

    assert nombres("crédito") == ["Banco de Crédito"]
    assert nombres("2013131") == ["SUNAT"]


def test_documento_no_cambia(client, h, prov):
    r = client.patch(
        f"{MAE}/proveedores/{prov['id']}",
        headers=h,
        json={"razon_social": "BCP", "numero_documento": RUC_SUNAT},
    )
    assert r.json()["razon_social"] == "BCP" and r.json()["numero_documento"] == RUC_BCP


# ---------------------------------------------------------------- contactos


def test_siempre_hay_un_contacto_principal(client, h, prov):
    url = f"{MAE}/proveedores/{prov['id']}/contactos"
    a = client.post(url, headers=h, json={"nombre": "Ana Ruiz", "correo": "ana@bcp.pe"}).json()
    assert a["principal"]
    b = client.post(url, headers=h, json={"nombre": "Luis Soto", "principal": True}).json()
    ficha = client.get(f"{MAE}/proveedores/{prov['id']}", headers=h).json()
    assert {c["nombre"]: c["principal"] for c in ficha["contactos"]} == {
        "Ana Ruiz": False,
        "Luis Soto": True,
    }
    r = client.patch(f"{MAE}/contactos/{b['id']}", headers=h, json={"principal": False})
    assert r.json()["codigo"] == "principal_requerido"
    client.delete(f"{MAE}/contactos/{b['id']}", headers=h)
    ficha = client.get(f"{MAE}/proveedores/{prov['id']}", headers=h).json()
    assert ficha["contactos"][0]["principal"]


# ---------------------------------------------------------------- cuentas bancarias


def cuenta(client, h, prov, **datos):
    base = {
        "banco": "BCP",
        "tipo": "corriente",
        "moneda": "PEN",
        "numero": "193-1234567-0-12",
        "cci": CCI,
    }
    return client.post(
        f"{MAE}/proveedores/{prov['id']}/cuentas-bancarias", headers=h, json={**base, **datos}
    )


def test_cuenta_local_requiere_cci_valido(client, h, prov):
    assert cuenta(client, h, prov, cci=None).json()["codigo"] == "cci_requerido"
    assert cuenta(client, h, prov, cci="123").json()["codigo"] == "cci_invalido"
    r = cuenta(client, h, prov)
    assert r.status_code == 201 and r.json()["numero"] == "1931234567012"
    assert cuenta(client, h, prov).json()["codigo"] == "cuenta_duplicada"


def test_cuenta_del_exterior_requiere_swift(client, h):
    ext = crear(
        client,
        h,
        tipo_documento="EXT",
        numero_documento="94-1234567",
        pais="us",
        razon_social="ACME",
    ).json()
    base = {"banco": "Chase", "tipo": "corriente", "moneda": "USD", "numero": "123456789"}
    url = f"{MAE}/proveedores/{ext['id']}/cuentas-bancarias"
    assert client.post(url, headers=h, json=base).json()["codigo"] == "swift_requerido"
    assert client.post(url, headers=h, json={**base, "swift": "CHASUS33"}).status_code == 201


def test_cuentas_enmascaradas_sin_permiso_bancario(client, h, prov):
    cuenta(client, h, prov)
    analista = usuario_con_rol(client, h, "ERP_MAE_ANALISTA")
    ficha = client.get(f"{MAE}/proveedores/{prov['id']}", headers=analista).json()
    c = ficha["cuentas"][0]
    assert c["enmascarada"] and c["numero"] == "•••• 7012" and c["cci"] == "•••• 9012"
    assert cuenta(client, analista, prov, numero="999999999").status_code == 403
    completa = client.get(f"{MAE}/proveedores/{prov['id']}", headers=h).json()["cuentas"][0]
    assert completa["cci"] == CCI and not completa["enmascarada"]


def test_cambios_de_cuenta_quedan_auditados_sin_el_numero_completo(client, h, prov):
    c = cuenta(client, h, prov).json()
    client.patch(f"{MAE}/cuentas-bancarias/{c['id']}", headers=h, json={"activo": False})
    eventos = client.get(f"{API_SEG}/auditoria?entidad=proveedor_cuenta", headers=h).json()
    assert [e["accion"] for e in eventos] == ["desactivar", "crear"]
    assert all("1931234567012" not in str(e["detalle"]) for e in eventos)


# ---------------------------------------------------------------- categorías y bloqueo


def test_categorias_que_provee(client, h, prov):
    cats = {c["codigo"]: c["id"] for c in client.get(f"{MAE}/categorias", headers=h).json()}
    r = client.put(
        f"{MAE}/proveedores/{prov['id']}/categorias",
        headers=h,
        json={"categoria_ids": [cats["SRV-CON"], cats["SUM-OFI"], cats["SRV-CON"]]},
    )
    assert [c["codigo"] for c in r.json()["categorias"]] == ["SRV-CON", "SUM-OFI"]


def test_bloqueo_por_empresa(client, h, prov, db):
    a = crear_empresa(client, h).json()
    b = crear_empresa(client, h, ruc=RUC_SUNAT).json()
    url = f"{MAE}/proveedores/{prov['id']}/empresas/{a['id']}"
    assert (
        client.put(url, headers=h, json={"bloqueado": True}).json()["codigo"] == "motivo_requerido"
    )
    r = client.put(url, headers=h, json={"bloqueado": True, "motivo": "Deuda tributaria"})
    assert r.json()["bloqueos"] == [{"empresa_id": a["id"], "motivo": "Deuda tributaria"}]
    with db() as s:
        assert "Deuda tributaria" in service.proveedor_habilitado(
            s, uuid.UUID(prov["id"]), uuid.UUID(a["id"])
        )
        assert service.proveedor_habilitado(s, uuid.UUID(prov["id"]), uuid.UUID(b["id"])) is None
    client.put(url, headers=h, json={"bloqueado": False})
    with db() as s:
        assert service.proveedor_habilitado(s, uuid.UUID(prov["id"]), uuid.UUID(a["id"])) is None


# ---------------------------------------------------------------- condiciones de pago


def test_condiciones_de_pago(client, h, prov):
    conds = {c["codigo"]: c for c in client.get(f"{MAE}/condiciones-pago", headers=h).json()}
    assert [conds[c]["dias"] for c in ("CONTADO", "30D", "60D")] == [0, 30, 60]
    r = client.patch(
        f"{MAE}/condiciones-pago/{conds['CONTADO']['id']}", headers=h, json={"activo": False}
    )
    assert r.json()["codigo"] == "condicion_en_uso"
    r = client.post(
        f"{MAE}/condiciones-pago",
        headers=h,
        json={"codigo": "90d", "nombre": "Crédito 90 días", "dias": 90},
    )
    assert r.status_code == 201 and r.json()["codigo"] == "90D"
    r = client.patch(
        f"{MAE}/proveedores/{prov['id']}", headers=h, json={"condicion_pago_id": r.json()["id"]}
    )
    assert r.json()["condicion_pago"]["dias"] == 90


def test_consulta_no_registra_proveedores(client, h):
    u = usuario_con_rol(client, h, "ERP_MAE_CONSULTA")
    assert client.get(f"{MAE}/proveedores", headers=u).status_code == 200
    assert crear(client, u).status_code == 403
