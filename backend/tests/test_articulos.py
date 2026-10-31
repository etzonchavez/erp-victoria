import uuid
from decimal import Decimal

import pytest

from app.modules.contabilidad import service as contabilidad
from app.modules.maestros import service as maestros
from app.modules.maestros.models import Articulo
from tests.conftest import API as API_SEG
from tests.test_maestros import RUC_SUNAT, crear_empresa, usuario_con_rol

MAE = "/api/v1/maestros"
CNT = "/api/v1/contabilidad"


@pytest.fixture
def h(client, admin):
    for modulo in ("maestros", "contabilidad"):
        client.patch(f"{API_SEG}/modulos/{modulo}", headers=admin, json={"activo": True})
    return admin


@pytest.fixture
def empresa(client, h):
    return crear_empresa(client, h).json()


@pytest.fixture
def cats(client, h) -> dict[str, str]:
    return {c["codigo"]: c["id"] for c in client.get(f"{MAE}/categorias", headers=h).json()}


def crear(client, h, cats, cat="SUM-OFI", tipo="bien_no_inventariable", **datos):
    base = {
        "descripcion": "Papel bond A4 80 g",
        "tipo": tipo,
        "categoria_id": cats[cat],
        "unidad": "PAQ",
    }
    return client.post(f"{MAE}/articulos", headers=h, json={**base, **datos})


def estado(client, h, art) -> dict[str, dict]:
    filas = client.get(f"{CNT}/articulos/{art['id']}/estado", headers=h).json()
    return {f["razon_social"]: f for f in filas}


def perfiles(client, h, empresa) -> dict[str, str]:
    r = client.get(f"{CNT}/empresas/{empresa['id']}/perfiles", headers=h)
    return {p["codigo"]: p["id"] for p in r.json()}


# ---------------------------------------------------------------- código


def test_codigo_automatico_por_categoria(client, h, empresa, cats):
    a = crear(client, h, cats).json()
    b = crear(client, h, cats, descripcion="Lapicero azul", unidad="UND").json()
    assert (a["codigo"], b["codigo"]) == ("SUM-OFI-0001", "SUM-OFI-0002")
    r = client.get(f"{MAE}/articulos/siguiente-codigo?categoria_id={cats['SUM-OFI']}", headers=h)
    assert r.json()["codigo"] == "SUM-OFI-0003"


def test_codigo_manual_para_migraciones(client, h, empresa, cats):
    r = crear(client, h, cats, codigo="pap-a4-001")
    assert r.json()["codigo"] == "PAP-A4-001"
    assert crear(client, h, cats, codigo="PAP-A4-001").json()["codigo"] == "articulo_duplicado"
    assert crear(client, h, cats, codigo="CON ESPACIO").json()["codigo"] == "codigo_invalido"


# ---------------------------------------------------------------- tipo vs perfil


def test_tipo_debe_coincidir_con_el_perfil_de_la_categoria(client, h, empresa, cats):
    r = crear(client, h, cats, tipo="servicio")
    assert r.status_code == 422 and r.json()["codigo"] == "tipo_no_coincide"
    assert "Consumo directo" in r.json()["mensaje"]


def test_sin_perfil_se_guarda_y_advierte(client, h, empresa, cats):
    nueva = client.post(
        f"{MAE}/categorias", headers=h, json={"codigo": "OTR", "nombre": "Otros"}
    ).json()
    cats["OTR"] = nueva["id"]
    r = crear(client, h, cats, cat="OTR", tipo="servicio", unidad="SRV")
    assert r.status_code == 201
    fila = estado(client, h, r.json())["ACME S.A.C."]
    assert fila["perfil"] is None and "Sin perfil" in fila["problema"]


def test_estado_contable_muestra_cuentas_e_impuesto(client, h, empresa, cats):
    art = crear(client, h, cats, cat="SUM-REP", tipo="bien_inventariable", unidad="UND").json()
    fila = estado(client, h, art)["ACME S.A.C."]
    assert fila["problema"] is None
    assert fila["perfil"]["codigo"] == "SUMINISTRO_ALMACEN" and fila["origen"] == "Categoría SUM"
    assert fila["perfil"]["cuenta_cargo"]["codigo"] == "6032"
    assert fila["impuesto"]["codigo"] == "IGV18" and Decimal(fila["impuesto"]["tasa"]) == 18


def test_cambiar_categoria_valida_el_tipo(client, h, empresa, cats):
    art = crear(client, h, cats).json()
    r = client.patch(
        f"{MAE}/articulos/{art['id']}", headers=h, json={"categoria_id": cats["SRV-CON"]}
    )
    assert r.json()["codigo"] == "tipo_no_coincide"
    r = client.patch(
        f"{MAE}/articulos/{art['id']}",
        headers=h,
        json={"categoria_id": cats["SRV-CON"], "tipo": "servicio"},
    )
    assert r.status_code == 200 and r.json()["categoria"]["codigo"] == "SRV-CON"


def test_contabilidad_no_cambia_un_perfil_que_rompa_articulos(client, h, empresa, cats):
    crear(client, h, cats)  # Útiles de oficina: consumo directo
    p = perfiles(client, h, empresa)
    r = client.put(
        f"{CNT}/empresas/{empresa['id']}/categorias/{cats['SUM-OFI']}/perfil",
        headers=h,
        json={"perfil_id": p["SERVICIO"]},
    )
    assert r.status_code == 409 and r.json()["codigo"] == "articulos_de_otro_tipo"
    assert "SUM-OFI-0001" in r.json()["mensaje"]
    # sin perfil propio heredaría Suministros de almacén (inventariable): también se rechaza
    r = client.put(
        f"{CNT}/empresas/{empresa['id']}/categorias/{cats['SUM-OFI']}/perfil",
        headers=h,
        json={"perfil_id": None},
    )
    assert r.json()["codigo"] == "articulos_de_otro_tipo"


# ---------------------------------------------------------------- excepción contable


def test_excepcion_contable_por_empresa(client, h, empresa, cats):
    otra = crear_empresa(client, h, ruc=RUC_SUNAT).json()
    art = crear(
        client, h, cats, cat="AF-TI", tipo="activo_fijo", descripcion="Proyector", unidad="UND"
    ).json()
    p = perfiles(client, h, empresa)
    url = f"{CNT}/empresas/{empresa['id']}/articulos/{art['id']}/perfil"
    r = client.put(url, headers=h, json={"perfil_id": p["SERVICIO"]})
    assert r.json()["codigo"] == "tipo_no_coincide"
    r = client.put(url, headers=h, json={"perfil_id": p["ACTIVO_MUEBLES"]})
    filas = {f["empresa_id"]: f for f in r.json()}
    assert (
        filas[empresa["id"]]["excepcion"]
        and filas[empresa["id"]]["perfil"]["codigo"] == "ACTIVO_MUEBLES"
    )
    assert filas[empresa["id"]]["origen"] == "Excepción del artículo"
    assert not filas[otra["id"]]["excepcion"]
    r = client.put(url, headers=h, json={"perfil_id": None})
    assert {f["razon_social"]: f for f in r.json()}["ACME S.A.C."]["perfil"][
        "codigo"
    ] == "ACTIVO_FIJO"


def test_maestros_no_define_excepciones(client, h, empresa, cats):
    art = crear(client, h, cats).json()
    u = usuario_con_rol(client, h, "ERP_MAE_ANALISTA")
    r = client.put(
        f"{CNT}/empresas/{empresa['id']}/articulos/{art['id']}/perfil",
        headers=u,
        json={"perfil_id": None},
    )
    assert r.status_code == 403
    assert client.get(f"{CNT}/articulos/{art['id']}/estado", headers=u).status_code == 200


# ---------------------------------------------------------------- datos y unidades


def test_precio_referencial_requiere_moneda(client, h, empresa, cats):
    assert (
        crear(client, h, cats, precio_referencial="15.50").json()["codigo"] == "precio_incompleto"
    )
    r = crear(
        client,
        h,
        cats,
        precio_referencial="15.50",
        moneda_precio="PEN",
        marca="Atlas",
        modelo="A4-80",
    )
    assert r.status_code == 201 and Decimal(r.json()["precio_referencial"]) == Decimal("15.5")


def test_impuesto_debe_existir(client, h, empresa, cats):
    assert crear(client, h, cats, impuesto="IVA21").json()["codigo"] == "impuesto_inexistente"
    assert crear(client, h, cats, impuesto="exo").json()["impuesto"] == "EXO"


def test_unidades_alternativas_y_conversion(client, h, empresa, cats, db):
    art = crear(client, h, cats, descripcion="Lapicero azul", unidad="UND").json()
    url = f"{MAE}/articulos/{art['id']}/unidades"
    r = client.put(url, headers=h, json={"unidades": [{"unidad": "UND", "factor": "1"}]})
    assert r.json()["codigo"] == "unidad_base"
    r = client.put(
        url,
        headers=h,
        json={"unidades": [{"unidad": "CJA", "factor": "12"}, {"unidad": "PAQ", "factor": "6"}]},
    )
    assert [u["unidad"] for u in r.json()["unidades_alternas"]] == ["CJA", "PAQ"]
    with db() as s:
        a = s.get(Articulo, uuid.UUID(art["id"]))
        assert maestros.convertir_a_unidad_base(s, a, Decimal("2"), "CJA") == 24
        assert (
            maestros.convertir_a_unidad_base(s, a, Decimal("2"), "DOC") == 24
        )  # conversión general
    r = client.patch(f"{MAE}/articulos/{art['id']}", headers=h, json={"unidad": "CJA"})
    assert r.json()["codigo"] == "unidad_repetida"


def test_busqueda_por_texto_categoria_y_tipo(client, h, empresa, cats):
    crear(client, h, cats)
    crear(
        client,
        h,
        cats,
        cat="SRV-MAN",
        tipo="servicio",
        descripcion="Mantenimiento de aire acondicionado",
        unidad="SRV",
    )

    def codigos(q):
        return [a["codigo"] for a in client.get(f"{MAE}/articulos?{q}", headers=h).json()]

    assert codigos("buscar=aire") == ["SRV-MAN-0001"]
    assert codigos(f"categoria_id={cats['SRV']}") == ["SRV-MAN-0001"]  # incluye subcategorías
    assert codigos("tipo=bien_no_inventariable") == ["SUM-OFI-0001"]


def test_perfil_de_articulo_para_compras(client, h, empresa, cats, db):
    art = crear(client, h, cats).json()
    with db() as s:
        a = s.get(Articulo, uuid.UUID(art["id"]))
        perfil, origen = contabilidad.perfil_de_articulo(s, uuid.UUID(empresa["id"]), a)
        assert perfil.cuenta_cargo.codigo == "656" and origen == "Categoría SUM-OFI"


def test_consulta_no_registra_articulos(client, h, empresa, cats):
    u = usuario_con_rol(client, h, "ERP_MAE_CONSULTA")
    assert client.get(f"{MAE}/articulos", headers=u).status_code == 200
    assert crear(client, u, cats).status_code == 403
