from sqlalchemy import select

from app.modules.seguridad import catalogo
from app.modules.seguridad.models import Permiso, Rol
from app.modules.seguridad.schemas import TipoRol
from app.modules.seguridad.service import sincronizar_roles_estandar
from tests.conftest import API, login


def roles(client, admin):
    return {r["codigo"]: r for r in client.get(f"{API}/roles", headers=admin).json()}


def test_cada_modulo_trae_un_rol_estandar_por_tipo(client, admin):
    estandar = [r for r in roles(client, admin).values() if r["estandar"]]
    for modulo in ("seguridad", "maestros"):
        delmodulo = [r for r in estandar if r["modulo"] == modulo]
        assert sorted(r["tipo"] for r in delmodulo) == sorted(catalogo.TIPOS_ROL), modulo
        prefijo = catalogo.prefijo_rol(modulo)
        assert all(r["codigo"].startswith(prefijo) for r in delmodulo)


def test_roles_estandar_salen_primero_y_ordenados_por_tipo(client, admin):
    crear = {
        "codigo": "ERP_SEG_PROPIO",
        "modulo": "seguridad",
        "nombre": "AAA propio",
        "tipo": "administrador",
        "permisos": [],
    }
    client.post(f"{API}/roles", headers=admin, json=crear)
    lista = client.get(f"{API}/roles", headers=admin).json()
    estandar = [r for r in lista if r["estandar"]]
    assert lista[: len(estandar)] == estandar  # los estándar primero
    orden = list(catalogo.TIPOS_ROL)
    tipos = [orden.index(r["tipo"]) for r in estandar]
    assert tipos == sorted(tipos)  # agrupados por tipo
    assert lista[-1]["codigo"] == "ERP_SEG_PROPIO"


def test_rol_estandar_no_se_puede_editar(client, admin):
    auditor = roles(client, admin)["ERP_SEG_AUDITOR"]
    r = client.patch(f"{API}/roles/{auditor['id']}", headers=admin, json={"activo": False})
    assert r.status_code == 409
    assert r.json()["codigo"] == "rol_estandar"


def test_duplicar_crea_rol_propio_con_mismos_permisos_y_tipo(client, admin):
    auditor = roles(client, admin)["ERP_SEG_AUDITOR"]
    r = client.post(
        f"{API}/roles/{auditor['id']}/duplicar",
        headers=admin,
        json={"codigo": "ERP_SEG_AUDITOR_EXTERNO", "nombre": "Auditor externo"},
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
    assert creado["detalle"]["duplicado_de"] == "ERP_SEG_AUDITOR"


def test_codigo_duplicado_de_rol_estandar_es_rechazado(client, admin):
    auditor = roles(client, admin)["ERP_SEG_AUDITOR"]
    r = client.post(
        f"{API}/roles/{auditor['id']}/duplicar",
        headers=admin,
        json={"codigo": "ERP_SEG_AUDITOR", "nombre": "Copia"},
    )
    assert r.status_code == 409


def test_tipo_de_rol_es_obligatorio_y_valido(client, admin):
    base = {
        "codigo": "ERP_SEG_SIN_TIPO",
        "modulo": "seguridad",
        "nombre": "Sin tipo",
        "permisos": [],
    }
    assert client.post(f"{API}/roles", headers=admin, json=base).status_code == 422
    malo = {**base, "tipo": "jefe"}
    assert client.post(f"{API}/roles", headers=admin, json=malo).status_code == 422


def test_usuario_con_rol_estandar_auditor_solo_consulta(client, admin):
    auditor = roles(client, admin)["ERP_SEG_AUDITOR"]
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
        rol = s.scalar(select(Rol).where(Rol.codigo == "ERP_SEG_AUDITOR"))
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
        assert catalogo.validar_codigo_rol(r.codigo, r.modulo) is None, r.codigo
        if r.tipo == "consulta":
            assert all(p.endswith(".ver") for p in r.permisos), r.codigo


def test_tipos_de_rol_disponibles_por_api(client, admin):
    tipos = client.get(f"{API}/tipos-rol", headers=admin).json()
    assert [t["codigo"] for t in tipos] == list(catalogo.TIPOS_ROL)


def test_permisos_del_catalogo_existen_en_bd(db):
    with db() as s:
        assert len(list(s.scalars(select(Permiso)))) == len(catalogo.PERMISOS)


# ------------------------------------------------- nomenclatura ERP_<MÓDULO>_<FUNCIÓN>


def nuevo_rol(client, admin, codigo, modulo="seguridad"):
    return client.post(
        f"{API}/roles",
        headers=admin,
        json={
            "codigo": codigo,
            "modulo": modulo,
            "nombre": "Prueba",
            "tipo": "operativo",
            "permisos": [],
        },
    )


def test_codigo_valido_por_modulo(client, admin):
    assert nuevo_rol(client, admin, "ERP_COM_ANALISTA", "compras").status_code == 201
    assert nuevo_rol(client, admin, "ERP_SEG_GESTOR_2", "seguridad").status_code == 201


def test_codigo_en_minusculas_se_normaliza(client, admin):
    r = nuevo_rol(client, admin, "erp_com_comprador", "compras")
    assert r.status_code == 201
    assert r.json()["codigo"] == "ERP_COM_COMPRADOR"


def test_codigo_fuera_de_nomenclatura_es_rechazado(client, admin):
    for codigo in ["COMPRADOR_SENIOR", "ERP_COMPRAS_ANALISTA", "ERP_COM_", "ERP_COM_ANALISTA-1"]:
        r = nuevo_rol(client, admin, codigo, "compras")
        assert r.status_code == 422, codigo
        assert r.json()["codigo"] in ("codigo_rol_invalido", "validacion"), codigo


def test_prefijo_debe_coincidir_con_el_modulo(client, admin):
    r = nuevo_rol(client, admin, "ERP_SEG_ANALISTA", "compras")
    assert r.status_code == 422
    assert "ERP_COM_" in r.json()["mensaje"]


def test_modulo_inexistente_es_rechazado(client, admin):
    r = nuevo_rol(client, admin, "ERP_XYZ_ANALISTA", "ventas")
    assert r.status_code == 422
    assert r.json()["codigo"] == "modulo_inexistente"


def test_duplicar_a_otro_modulo_exige_su_prefijo(client, admin):
    auditor = roles(client, admin)["ERP_SEG_AUDITOR"]
    r = client.post(
        f"{API}/roles/{auditor['id']}/duplicar",
        headers=admin,
        json={
            "codigo": "ERP_SEG_AUDITOR_COMPRAS",
            "nombre": "Auditor de compras",
            "modulo": "compras",
        },
    )
    assert r.status_code == 422
    r = client.post(
        f"{API}/roles/{auditor['id']}/duplicar",
        headers=admin,
        json={"codigo": "ERP_COM_AUDITOR", "nombre": "Auditor de compras", "modulo": "compras"},
    )
    assert r.status_code == 201
    assert r.json()["modulo"] == "compras"


def test_rol_propio_que_choca_con_un_estandar_nuevo_se_renombra(db):
    with db() as s:
        rol = s.scalar(select(Rol).where(Rol.codigo == "ERP_SEG_AUDITOR"))
        rol.estandar = False  # simula un rol del cliente creado antes que el estándar
        s.commit()
        sincronizar_roles_estandar(s)
        s.commit()
        codigos = set(s.scalars(select(Rol.codigo)))
        assert {"ERP_SEG_AUDITOR", "ERP_SEG_AUDITOR_CLIENTE"} <= codigos
