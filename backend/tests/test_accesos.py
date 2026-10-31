from tests.conftest import API as API_SEG
from tests.conftest import login
from tests.test_maestros import RUC_SUNAT, crear_empresa

MAE = "/api/v1/maestros"
CNT = "/api/v1/contabilidad"


def preparar(client, admin):
    for modulo in ("maestros", "contabilidad"):
        client.patch(f"{API_SEG}/modulos/{modulo}", headers=admin, json={"activo": True})
    a = crear_empresa(client, admin).json()
    b = crear_empresa(client, admin, ruc=RUC_SUNAT, razon_social="Beta S.A.C.").json()
    r = client.post(
        f"{MAE}/empresas/{a['id']}/unidades-negocio",
        headers=admin,
        json={"codigo": "LIMA", "nombre": "Sede Lima"},
    )
    lima = r.json()
    roles = {r["codigo"]: r["id"] for r in client.get(f"{API_SEG}/roles", headers=admin).json()}
    u = client.post(
        f"{API_SEG}/usuarios",
        headers=admin,
        json={
            "email": "contador@grupo.pe",
            "nombre": "Contador",
            "password": "Clave1234",
            "roles": [roles["ERP_CNT_ADMINISTRADOR"], roles["ERP_MAE_CONSULTA"]],
        },
    ).json()
    return a, b, lima, u, login(client, "contador@grupo.pe", "Clave1234")


def asignar(client, admin, usuario, accesos):
    return client.put(
        f"{MAE}/usuarios/{usuario['id']}/accesos", headers=admin, json={"accesos": accesos}
    )


def test_sin_asignacion_no_ve_ninguna_empresa(client, admin):
    a, _, _, _, h = preparar(client, admin)
    assert client.get(f"{MAE}/empresas/accesibles", headers=h).json() == []
    r = client.get(f"{CNT}/empresas/{a['id']}/cuentas", headers=h)
    assert r.status_code == 403 and r.json()["codigo"] == "sin_acceso_empresa"


def test_el_administrador_ve_todas(client, admin):
    preparar(client, admin)
    assert len(client.get(f"{MAE}/empresas/accesibles", headers=admin).json()) == 2


def test_acceso_a_una_empresa(client, admin):
    a, b, _, u, h = preparar(client, admin)
    assert asignar(client, admin, u, [{"empresa_id": a["id"]}]).status_code == 200
    assert [e["id"] for e in client.get(f"{MAE}/empresas/accesibles", headers=h).json()] == [
        a["id"]
    ]
    assert client.get(f"{CNT}/empresas/{a['id']}/cuentas", headers=h).status_code == 200
    assert client.get(f"{CNT}/empresas/{b['id']}/cuentas", headers=h).status_code == 403
    # tampoco por el identificador de un objeto de la otra empresa
    cuenta_b = client.get(f"{CNT}/empresas/{b['id']}/cuentas", headers=admin).json()[0]
    r = client.patch(
        f"{CNT}/cuentas/{cuenta_b['id']}", headers=h, json={"nombre": "Cambio indebido"}
    )
    assert r.status_code == 403
    # la lista de empresas de Maestros también se filtra
    assert [e["id"] for e in client.get(f"{MAE}/empresas", headers=h).json()] == [a["id"]]


def test_acceso_a_algunas_unidades(client, admin):
    a, _, lima, u, h = preparar(client, admin)
    r = asignar(
        client,
        admin,
        u,
        [{"empresa_id": a["id"], "todas_unidades": False, "unidades": [lima["id"]]}],
    )
    assert r.json() == [{"empresa_id": a["id"], "todas_unidades": False, "unidades": [lima["id"]]}]
    unidades = client.get(f"{MAE}/empresas/accesibles", headers=h).json()[0]["unidades"]
    assert [x["codigo"] for x in unidades] == ["LIMA"]


def test_validaciones_de_asignacion(client, admin):
    a, b, lima, u, _ = preparar(client, admin)
    r = asignar(client, admin, u, [{"empresa_id": a["id"], "todas_unidades": False}])
    assert r.json()["codigo"] == "unidades_requeridas"
    r = asignar(
        client,
        admin,
        u,
        [{"empresa_id": b["id"], "todas_unidades": False, "unidades": [lima["id"]]}],
    )
    assert r.json()["codigo"] == "unidad_otra_empresa"
    r = asignar(client, admin, u, [{"empresa_id": a["id"]}, {"empresa_id": a["id"]}])
    assert r.json()["codigo"] == "empresa_repetida"


def test_resumen_y_auditoria(client, admin):
    a, _, _, u, _ = preparar(client, admin)
    asignar(client, admin, u, [{"empresa_id": a["id"]}])
    assert client.get(f"{MAE}/accesos/resumen", headers=admin).json() == {u["id"]: 1}
    eventos = client.get(f"{API_SEG}/auditoria?entidad=usuario", headers=admin).json()
    assert eventos[0]["accion"] == "asignar_accesos"
    assert eventos[0]["detalle"]["despues"] == ["ACME S.A.C.: todas"]


def test_quien_crea_una_empresa_obtiene_acceso(client, admin):
    client.patch(f"{API_SEG}/modulos/maestros", headers=admin, json={"activo": True})
    roles = {r["codigo"]: r["id"] for r in client.get(f"{API_SEG}/roles", headers=admin).json()}
    client.post(
        f"{API_SEG}/usuarios",
        headers=admin,
        json={
            "email": "conf@grupo.pe",
            "nombre": "Conf",
            "password": "Clave1234",
            "roles": [roles["ERP_MAE_CONFIGURADOR"]],
        },
    )
    h = login(client, "conf@grupo.pe", "Clave1234")
    e = crear_empresa(client, h).json()
    assert [x["id"] for x in client.get(f"{MAE}/empresas/accesibles", headers=h).json()] == [
        e["id"]
    ]


def test_solo_quien_edita_usuarios_asigna_accesos(client, admin):
    a, _, _, u, h = preparar(client, admin)
    assert asignar(client, h, u, [{"empresa_id": a["id"]}]).status_code == 403
