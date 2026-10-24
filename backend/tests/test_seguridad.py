from tests.conftest import API, login


def crear_rol(client, admin, codigo, permisos):
    r = client.post(
        f"{API}/roles",
        headers=admin,
        json={"codigo": codigo, "nombre": codigo, "permisos": permisos},
    )
    assert r.status_code == 201, r.text
    return r.json()


def crear_usuario(client, admin, email, roles=(), password="Clave1234"):
    r = client.post(
        f"{API}/usuarios",
        headers=admin,
        json={
            "email": email,
            "nombre": "Usuario Prueba",
            "password": password,
            "roles": list(roles),
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------- autenticación


def test_login_correcto_devuelve_token(client):
    r = client.post(
        f"{API}/auth/login", json={"email": "ADMIN@erp-victoria.local", "password": "Admin123!"}
    )
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"


def test_login_incorrecto_responde_401_con_formato_estandar(client):
    r = client.post(
        f"{API}/auth/login", json={"email": "admin@erp-victoria.local", "password": "x"}
    )
    assert r.status_code == 401
    assert r.json() == {
        "codigo": "credenciales_invalidas",
        "mensaje": "Correo o contraseña incorrectos",
    }


def test_sin_token_no_hay_acceso(client):
    r = client.get(f"{API}/usuarios")
    assert r.status_code == 401
    assert r.json()["codigo"] == "no_autenticado"


def test_token_invalido_no_hay_acceso(client):
    r = client.get(f"{API}/usuarios", headers={"Authorization": "Bearer basura"})
    assert r.status_code == 401


def test_sesion_del_admin_trae_todos_los_permisos(client, admin):
    d = client.get(f"{API}/auth/sesion", headers=admin).json()
    assert d["usuario"]["es_administrador"] is True
    assert "seguridad.usuario.crear" in d["permisos"]
    assert [m["codigo"] for m in d["modulos"]] == ["seguridad"]


# ---------------------------------------------------------------- permisos (criterio de la semana)


def test_usuario_sin_permiso_no_puede_usar_la_funcion(client, admin):
    crear_usuario(client, admin, "sinrol@empresa.pe")
    h = login(client, "sinrol@empresa.pe", "Clave1234")
    r = client.get(f"{API}/usuarios", headers=h)
    assert r.status_code == 403
    assert r.json()["codigo"] == "sin_permiso"


def test_usuario_con_rol_accede_solo_a_lo_permitido(client, admin):
    rol = crear_rol(client, admin, "consulta", ["seguridad.usuario.ver"])
    crear_usuario(client, admin, "consulta@empresa.pe", roles=[rol["id"]])
    h = login(client, "consulta@empresa.pe", "Clave1234")
    assert client.get(f"{API}/usuarios", headers=h).status_code == 200
    r = client.post(
        f"{API}/usuarios",
        headers=h,
        json={"email": "otro@empresa.pe", "nombre": "Otro", "password": "Clave1234"},
    )
    assert r.status_code == 403


def test_rol_desactivado_pierde_sus_permisos(client, admin):
    rol = crear_rol(client, admin, "temporal", ["seguridad.usuario.ver"])
    crear_usuario(client, admin, "temp@empresa.pe", roles=[rol["id"]])
    h = login(client, "temp@empresa.pe", "Clave1234")
    client.patch(f"{API}/roles/{rol['id']}", headers=admin, json={"activo": False})
    assert client.get(f"{API}/usuarios", headers=h).status_code == 403


def test_usuario_desactivado_no_puede_ingresar(client, admin):
    u = crear_usuario(client, admin, "baja@empresa.pe")
    client.patch(f"{API}/usuarios/{u['id']}", headers=admin, json={"activo": False})
    r = client.post(f"{API}/auth/login", json={"email": "baja@empresa.pe", "password": "Clave1234"})
    assert r.status_code == 403
    assert r.json()["codigo"] == "usuario_inactivo"


def test_solo_un_administrador_crea_administradores(client, admin):
    rol = crear_rol(client, admin, "gestor", ["seguridad.usuario.crear"])
    crear_usuario(client, admin, "gestor@empresa.pe", roles=[rol["id"]])
    h = login(client, "gestor@empresa.pe", "Clave1234")
    r = client.post(
        f"{API}/usuarios",
        headers=h,
        json={
            "email": "nuevo@empresa.pe",
            "nombre": "Nuevo",
            "password": "Clave1234",
            "es_administrador": True,
        },
    )
    assert r.status_code == 403


def test_admin_no_puede_desactivarse_a_si_mismo(client, admin):
    yo = client.get(f"{API}/auth/sesion", headers=admin).json()["usuario"]
    r = client.patch(f"{API}/usuarios/{yo['id']}", headers=admin, json={"activo": False})
    assert r.status_code == 409


# ---------------------------------------------------------------- módulos


def test_modulo_obligatorio_no_se_desactiva(client, admin):
    r = client.patch(f"{API}/modulos/seguridad", headers=admin, json={"activo": False})
    assert r.status_code == 409


def test_activar_modulo_lo_muestra_en_la_sesion(client, admin):
    r = client.patch(f"{API}/modulos/compras", headers=admin, json={"activo": True})
    assert r.status_code == 200
    modulos = client.get(f"{API}/auth/sesion", headers=admin).json()["modulos"]
    assert "compras" in [m["codigo"] for m in modulos]


# ---------------------------------------------------------------- validaciones


def test_rol_con_permiso_inexistente_es_rechazado(client, admin):
    r = client.post(
        f"{API}/roles",
        headers=admin,
        json={"codigo": "malo", "nombre": "Malo", "permisos": ["no.existe.nunca"]},
    )
    assert r.status_code == 422
    assert r.json()["codigo"] == "permiso_inexistente"


def test_correo_duplicado_es_rechazado(client, admin):
    crear_usuario(client, admin, "repetido@empresa.pe")
    r = client.post(
        f"{API}/usuarios",
        headers=admin,
        json={"email": "Repetido@empresa.pe", "nombre": "Otro", "password": "Clave1234"},
    )
    assert r.status_code == 409


def test_password_corta_es_rechazada_con_detalle(client, admin):
    r = client.post(
        f"{API}/usuarios",
        headers=admin,
        json={"email": "corta@empresa.pe", "nombre": "Corta", "password": "123"},
    )
    assert r.status_code == 422
    assert r.json()["detalles"][0]["campo"] == "password"


# ---------------------------------------------------------------- auditoría (criterio de la semana)


def test_todo_cambio_queda_auditado(client, admin):
    rol = crear_rol(client, admin, "auditable", [])
    u = crear_usuario(client, admin, "auditado@empresa.pe")
    client.patch(f"{API}/usuarios/{u['id']}", headers=admin, json={"roles": [rol["id"]]})
    client.patch(f"{API}/modulos/maestros", headers=admin, json={"activo": True})
    client.post(f"{API}/auth/login", json={"email": "auditado@empresa.pe", "password": "mala"})

    eventos = client.get(f"{API}/auditoria", headers=admin).json()
    acciones = [(e["accion"], e["entidad"]) for e in eventos]
    for esperado in [
        ("crear", "rol"),
        ("crear", "usuario"),
        ("editar", "usuario"),
        ("activar", "modulo"),
        ("login_fallido", "sesion"),
        ("login", "sesion"),
    ]:
        assert esperado in acciones
    edicion = next(e for e in eventos if e["accion"] == "editar")
    assert edicion["detalle"]["roles"] == {"antes": [], "despues": ["auditable"]}
    assert edicion["usuario_email"] == "admin@erp-victoria.local"
