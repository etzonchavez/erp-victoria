from sqlalchemy import select

from app.modules.seguridad import catalogo
from app.modules.seguridad.models import Permiso, Rol
from app.modules.seguridad.schemas import TipoRol
from app.modules.seguridad.service import sincronizar_roles_estandar
from tests.conftest import API, login


def roles(client, admin):
    return {r["codigo"]: r for r in client.get(f"{API}/roles", headers=admin).json()}


def test_el_erp_trae_un_rol_estandar_por_tipo_en_seguridad(client, admin):
    estandar = [r for r in roles(client, admin).values() if r["estandar"]]
    assert {r["tipo"] for r in estandar} == set(catalogo.TIPOS_ROL)
    assert all(r["codigo"].startswith("seguridad.") for r in estandar)


def test_roles_estandar_salen_primero_y_ordenados_por_tipo(client, admin):
    crear = {"codigo": "propio", "nombre": "AAA propio", "tipo": "administrador", "permisos": []}
    client.post(f"{API}/roles", headers=admin, json=crear)
    lista = client.get(f"{API}/roles", headers=admin).json()
    assert [r["tipo"] for r in lista[:4]] == list(catalogo.TIPOS_ROL)
    assert lista[-1]["codigo"] == "propio"


def test_rol_estandar_no_se_puede_editar(client, admin):
    auditor = roles(client, admin)["seguridad.auditor"]
    r = client.patch(f"{API}/roles/{auditor['id']}", headers=admin, json={"activo": False})
    assert r.status_code == 409
    assert r.json()["codigo"] == "rol_estandar"


def test_duplicar_crea_rol_propio_con_mismos_permisos_y_tipo(client, admin):
    auditor = roles(client, admin)["seguridad.auditor"]
    r = client.post(
        f"{API}/roles/{auditor['id']}/duplicar",
        headers=admin,
        json={"codigo": "auditor_externo", "nombre": "Auditor externo"},
    )
    assert r.status_code == 201, r.text
    copia = r.json()
    assert copia["estandar"] is False
    assert copia["tipo"] == "consulta"
    assert copia["permisos"] == auditor["permisos"]
    # La copia sí se puede ajustar
    r = client.patch(
        f"{API}/roles/{copia['id']}",
        headers=admin,
        json={"permisos": ["seguridad.auditoria.ver"]},
    )
    assert r.status_code == 200
    eventos = client.get(f"{API}/auditoria?entidad=rol", headers=admin).json()
    creado = next(e for e in eventos if e["accion"] == "crear")
    assert creado["detalle"]["duplicado_de"] == "seguridad.auditor"


def test_codigo_de_rol_propio_no_admite_punto(client, admin):
    auditor = roles(client, admin)["seguridad.auditor"]
    r = client.post(
        f"{API}/roles/{auditor['id']}/duplicar",
        headers=admin,
        json={"codigo": "seguridad.auditor", "nombre": "Copia"},
    )
    assert r.status_code == 422


def test_tipo_de_rol_es_obligatorio_y_valido(client, admin):
    base = {"codigo": "sin_tipo", "nombre": "Sin tipo", "permisos": []}
    assert client.post(f"{API}/roles", headers=admin, json=base).status_code == 422
    malo = {**base, "tipo": "jefe"}
    assert client.post(f"{API}/roles", headers=admin, json=malo).status_code == 422


def test_usuario_con_rol_estandar_auditor_solo_consulta(client, admin):
    auditor = roles(client, admin)["seguridad.auditor"]
    client.post(
        f"{API}/usuarios",
        headers=admin,
        json={
            "email": "auditor@empresa.pe",
            "nombre": "Auditor",
            "password": "Clave1234",
            "roles": [auditor["id"]],
        },
    )
    h = login(client, "auditor@empresa.pe", "Clave1234")
    assert client.get(f"{API}/auditoria", headers=h).status_code == 200
    assert (
        client.patch(f"{API}/modulos/maestros", headers=h, json={"activo": True}).status_code == 403
    )


def test_sincronizar_restaura_un_rol_estandar_alterado(db):
    with db() as s:
        rol = s.scalar(select(Rol).where(Rol.codigo == "seguridad.auditor"))
        rol.permisos = []
        rol.nombre = "Cambiado a mano"
        s.commit()
        sincronizar_roles_estandar(s)
        s.commit()
        assert rol.nombre == "Auditor"
        assert len(rol.permisos) == 4


def test_catalogo_es_consistente():
    assert set(TipoRol.__args__) == set(catalogo.TIPOS_ROL)
    codigos = {p.codigo for p in catalogo.PERMISOS}
    for r in catalogo.ROLES_ESTANDAR:
        assert r.tipo in catalogo.TIPOS_ROL, r.codigo
        assert set(r.permisos) <= codigos, r.codigo
        assert "." in r.codigo
        if r.tipo == "consulta":
            assert all(p.endswith(".ver") for p in r.permisos), r.codigo


def test_tipos_de_rol_disponibles_por_api(client, admin):
    tipos = client.get(f"{API}/tipos-rol", headers=admin).json()
    assert [t["codigo"] for t in tipos] == list(catalogo.TIPOS_ROL)


def test_permisos_del_catalogo_existen_en_bd(db):
    with db() as s:
        assert len(list(s.scalars(select(Permiso)))) == len(catalogo.PERMISOS)
