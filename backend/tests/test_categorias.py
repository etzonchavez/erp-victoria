import uuid

import pytest

from app.modules.contabilidad import service as contabilidad
from tests.conftest import API as API_SEG
from tests.test_maestros import crear_empresa, usuario_con_rol

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


def categorias(client, h) -> dict[str, dict]:
    return {c["codigo"]: c for c in client.get(f"{MAE}/categorias", headers=h).json()}


def perfiles_cat(client, h, empresa) -> dict[str, dict]:
    cats = {c["id"]: c["codigo"] for c in client.get(f"{MAE}/categorias", headers=h).json()}
    filas = client.get(f"{CNT}/empresas/{empresa['id']}/categorias", headers=h).json()
    return {cats[f["categoria_id"]]: f for f in filas}


def crear(client, h, codigo, nombre="Categoría", padre=None):
    return client.post(
        f"{MAE}/categorias", headers=h, json={"codigo": codigo, "nombre": nombre, "padre_id": padre}
    )


# ---------------------------------------------------------------- árbol (maestros)


def test_arbol_de_ejemplo_en_orden(client, h):
    lista = client.get(f"{MAE}/categorias", headers=h).json()
    codigos = [c["codigo"] for c in lista]
    # cada rama completa antes de la siguiente categoría raíz
    assert codigos.index("SRV") < codigos.index("SRV-CON") < codigos.index("SUM")
    c = categorias(client, h)
    assert c["SUM-OFI"]["padre_id"] == c["SUM"]["id"] and c["SUM-OFI"]["nivel"] == 2


def test_maximo_tres_niveles(client, h):
    c = categorias(client, h)
    n3 = crear(client, h, "SUM-OFI-PAP", "Papelería", c["SUM-OFI"]["id"])
    assert n3.status_code == 201 and n3.json()["nivel"] == 3
    r = crear(client, h, "SUM-OFI-PAP-A4", "Papel A4", n3.json()["id"])
    assert r.json()["codigo"] == "nivel_maximo"


def test_codigo_unico_y_valido(client, h):
    assert crear(client, h, "sum").json()["codigo"] == "categoria_duplicada"
    assert crear(client, h, "con espacio").json()["codigo"] == "codigo_invalido"


def test_mover_rama_actualiza_niveles_y_evita_ciclos(client, h):
    c = categorias(client, h)
    n3 = crear(client, h, "SRV-MAN-AC", "Aire acondicionado", c["SRV-MAN"]["id"]).json()
    url = f"{MAE}/categorias/{c['SRV']['id']}"
    r = client.patch(url, headers=h, json={"padre_id": c["SRV-MAN"]["id"]})
    assert r.json()["codigo"] == "ciclo"
    # SRV-MAN (2 niveles de alto) bajo SUM-OFI (nivel 2) quedaría en 4 niveles
    r = client.patch(
        f"{MAE}/categorias/{c['SRV-MAN']['id']}", headers=h, json={"padre_id": c["SUM-OFI"]["id"]}
    )
    assert r.json()["codigo"] == "nivel_maximo"
    r = client.patch(f"{MAE}/categorias/{c['SRV-MAN']['id']}", headers=h, json={"padre_id": None})
    assert r.status_code == 200 and r.json()["nivel"] == 1
    assert categorias(client, h)["SRV-MAN-AC"]["nivel"] == 2
    assert n3["nivel"] == 3


def test_desactivar_requiere_subcategorias_inactivas(client, h):
    c = categorias(client, h)
    r = client.patch(f"{MAE}/categorias/{c['AF']['id']}", headers=h, json={"activo": False})
    assert r.json()["codigo"] == "tiene_subcategorias_activas"
    for hija in ("AF-TI", "AF-MUE", "AF-MAQ"):
        client.patch(f"{MAE}/categorias/{c[hija]['id']}", headers=h, json={"activo": False})
    r = client.patch(f"{MAE}/categorias/{c['AF']['id']}", headers=h, json={"activo": False})
    assert r.status_code == 200
    r = client.patch(f"{MAE}/categorias/{c['AF-TI']['id']}", headers=h, json={"activo": True})
    assert r.json()["codigo"] == "padre_inactivo"


# ---------------------------------------------------------------- perfil por empresa


def test_empresa_nueva_recibe_perfiles_sugeridos_y_herencia(client, h, empresa):
    p = perfiles_cat(client, h, empresa)
    assert p["SUM"]["perfil_propio"]["codigo"] == "SUMINISTRO_ALMACEN"
    assert p["SUM-REP"]["perfil_propio"] is None
    assert p["SUM-REP"]["perfil_efectivo"]["codigo"] == "SUMINISTRO_ALMACEN"
    assert p["SUM-REP"]["heredado_de"]["codigo"] == "SUM"
    assert p["SUM-OFI"]["perfil_efectivo"]["codigo"] == "CONSUMO_DIRECTO"
    assert p["SUM-OFI"]["heredado_de"] is None
    assert p["AF-MUE"]["perfil_efectivo"]["codigo"] == "ACTIVO_MUEBLES"


def test_categoria_nueva_hereda_del_padre(client, h, empresa):
    c = categorias(client, h)
    nueva = crear(client, h, "SRV-SEG", "Seguridad y vigilancia", c["SRV"]["id"]).json()
    p = perfiles_cat(client, h, empresa)["SRV-SEG"]
    assert p["perfil_efectivo"]["codigo"] == "SERVICIO"
    assert p["heredado_de"]["codigo"] == "SRV"
    raiz = crear(client, h, "OTR", "Otros").json()
    assert perfiles_cat(client, h, empresa)["OTR"]["perfil_efectivo"] is None
    assert nueva["nivel"] == 2 and raiz["nivel"] == 1


def test_asignar_y_quitar_perfil(client, h, empresa, db):
    c = categorias(client, h)
    perf = {
        x["codigo"]: x
        for x in client.get(f"{CNT}/empresas/{empresa['id']}/perfiles", headers=h).json()
    }
    url = f"{CNT}/empresas/{empresa['id']}/categorias/{c['SUM-REP']['id']}/perfil"
    r = client.put(url, headers=h, json={"perfil_id": perf["CONSUMO_DIRECTO"]["id"]})
    assert r.status_code == 200
    with db() as s:
        perfil, origen = contabilidad.perfil_de_categoria(
            s, uuid.UUID(empresa["id"]), uuid.UUID(c["SUM-REP"]["id"])
        )
        assert perfil.codigo == "CONSUMO_DIRECTO" and origen.codigo == "SUM-REP"
    client.put(url, headers=h, json={"perfil_id": None})
    with db() as s:
        perfil, origen = contabilidad.perfil_de_categoria(
            s, uuid.UUID(empresa["id"]), uuid.UUID(c["SUM-REP"]["id"])
        )
        assert perfil.codigo == "SUMINISTRO_ALMACEN" and origen.codigo == "SUM"
    eventos = client.get(f"{API_SEG}/auditoria?entidad=categoria_perfil", headers=h).json()
    assert eventos[0]["detalle"]["perfil"] == {"antes": "CONSUMO_DIRECTO", "despues": "heredado"}


def test_cada_empresa_tiene_su_propio_perfil(client, h, empresa):
    otra = crear_empresa(client, h, ruc="20131312955").json()
    c = categorias(client, h)
    perf_otra = {
        x["codigo"]: x["id"]
        for x in client.get(f"{CNT}/empresas/{otra['id']}/perfiles", headers=h).json()
    }
    client.put(
        f"{CNT}/empresas/{otra['id']}/categorias/{c['MER']['id']}/perfil",
        headers=h,
        json={"perfil_id": perf_otra["MATERIA_PRIMA"]},
    )
    assert perfiles_cat(client, h, otra)["MER"]["perfil_efectivo"]["codigo"] == "MATERIA_PRIMA"
    assert perfiles_cat(client, h, empresa)["MER"]["perfil_efectivo"]["codigo"] == "MERCADERIA"
    r = client.put(
        f"{CNT}/empresas/{empresa['id']}/categorias/{c['MER']['id']}/perfil",
        headers=h,
        json={"perfil_id": perf_otra["MATERIA_PRIMA"]},
    )
    assert r.json()["codigo"] == "perfil_otra_empresa"


def test_sugeridos_completa_sin_pisar(client, h, empresa):
    c = categorias(client, h)
    url = f"{CNT}/empresas/{empresa['id']}/categorias/{c['MER']['id']}/perfil"
    perf = {
        x["codigo"]: x["id"]
        for x in client.get(f"{CNT}/empresas/{empresa['id']}/perfiles", headers=h).json()
    }
    client.put(url, headers=h, json={"perfil_id": perf["MATERIA_PRIMA"]})
    r = client.post(f"{CNT}/empresas/{empresa['id']}/sugeridos", headers=h)
    assert r.json() == {"perfiles": 0, "categorias": 0}
    assert perfiles_cat(client, h, empresa)["MER"]["perfil_propio"]["codigo"] == "MATERIA_PRIMA"


# ---------------------------------------------------------------- permisos


def test_maestros_ordena_el_arbol_pero_no_asigna_perfiles(client, h, empresa):
    u = usuario_con_rol(client, h, "ERP_MAE_CONFIGURADOR")
    assert crear(client, u, "EPP", "Equipos de protección").status_code == 201
    c = categorias(client, h)
    r = client.put(
        f"{CNT}/empresas/{empresa['id']}/categorias/{c['EPP']['id']}/perfil",
        headers=u,
        json={"perfil_id": None},
    )
    assert r.status_code == 403


def test_contador_asigna_perfiles_pero_no_crea_categorias(client, h, empresa):
    u = usuario_con_rol(client, h, "ERP_CNT_ADMINISTRADOR")
    assert crear(client, u, "XYZ", "No permitido").status_code == 403
    c = categorias(client, h)
    r = client.put(
        f"{CNT}/empresas/{empresa['id']}/categorias/{c['SUM-REP']['id']}/perfil",
        headers=u,
        json={"perfil_id": None},
    )
    assert r.status_code == 200
