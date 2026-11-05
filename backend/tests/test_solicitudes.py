"""Solicitudes de compra con reglas de aprobación configurables."""

import pytest

from tests.conftest import API as API_SEG
from tests.conftest import login
from tests.test_maestros import crear_empresa

MAE = "/api/v1/maestros"
CNT = "/api/v1/contabilidad"
SOL = "/api/v1/solicitudes"
APR = "/api/v1/aprobaciones"


@pytest.fixture
def h(client, admin):
    for modulo in ("maestros", "contabilidad", "solicitudes"):
        client.patch(f"{API_SEG}/modulos/{modulo}", headers=admin, json={"activo": True})
    return admin


@pytest.fixture
def emp(client, h) -> dict:
    """Empresa con unidad Principal, dos centros de costo y un artículo con perfil."""
    empresa = crear_empresa(client, h).json()
    cats = {c["codigo"]: c["id"] for c in client.get(f"{MAE}/categorias", headers=h).json()}
    un = empresa["unidades"][0]["id"]
    centros = {}
    for codigo in ("ADM", "VEN"):
        r = client.post(
            f"{CNT}/empresas/{empresa['id']}/centros-costo",
            headers=h,
            json={"codigo": codigo, "nombre": codigo, "unidad_negocio_id": un},
        )
        assert r.status_code == 201, r.text
        centros[codigo] = r.json()["id"]
    art = client.post(
        f"{MAE}/articulos",
        headers=h,
        json={
            "descripcion": "Papel bond A4",
            "tipo": "bien_no_inventariable",
            "categoria_id": cats["SUM-OFI"],
            "unidad": "PAQ",
        },
    )
    assert art.status_code == 201, art.text
    return {**empresa, "un": un, "centros": centros, "art": art.json()["id"], "cats": cats}


_roles_cache: dict = {}


def usuario(client, h, emp, nombre: str, roles=(), jefe: dict | None = None) -> dict:
    """Crea un usuario con acceso a la empresa; devuelve {id, h}."""
    ids = {r["codigo"]: r["id"] for r in client.get(f"{API_SEG}/roles", headers=h).json()}
    email = f"{nombre.lower()}@grupo.pe"
    r = client.post(
        f"{API_SEG}/usuarios",
        headers=h,
        json={
            "email": email,
            "nombre": nombre,
            "password": "Clave1234",
            "roles": [ids[r] for r in roles],
            "jefe_id": jefe["id"] if jefe else None,
        },
    )
    assert r.status_code == 201, r.text
    uid = r.json()["id"]
    r = client.put(
        f"{MAE}/usuarios/{uid}/accesos",
        headers=h,
        json={"accesos": [{"empresa_id": emp["id"]}]},
    )
    assert r.status_code == 200, r.text
    return {"id": uid, "h": login(client, email, "Clave1234")}


def regla(client, h, emp, niveles, prioridad=1, documento="solicitud", **extra):
    datos = {"nombre": f"Regla {prioridad}", "prioridad": prioridad, "niveles": niveles, **extra}
    return client.post(
        f"{APR}/empresas/{emp['id']}/reglas", headers=h, json=datos, params={"documento": documento}
    )


def nivel(*aprobadores, desde=0, modo="serie"):
    return {"monto_desde": desde, "modo": modo, "aprobadores": list(aprobadores)}


def u(x):
    return {"tipo": "usuario", "usuario_id": x["id"]}


def solicitud(client, quien, emp, precio=100, cantidad=1, centros=None, **extra):
    centros = centros or [{"centro_costo_id": emp["centros"]["ADM"], "porcentaje": 100}]
    datos = {
        "empresa_id": emp["id"],
        "unidad_negocio_id": emp["un"],
        "titulo": "Útiles para la oficina",
        "lineas": [
            {
                "articulo_id": emp["art"],
                "cantidad": cantidad,
                "precio": precio,
                "distribuciones": centros,
            }
        ],
        **extra,
    }
    return client.post(SOL, headers=quien["h"], json=datos)


def accion(client, quien, sol, nombre, comentario=None):
    return client.post(
        f"{SOL}/{sol['id']}/{nombre}", headers=quien["h"], json={"comentario": comentario}
    )


@pytest.fixture
def gente(client, h, emp) -> dict:
    jefa = usuario(client, h, emp, "Jefa")
    return {
        "sol": usuario(client, h, emp, "Solicitante", ["ERP_SOL_SOLICITANTE"], jefe=jefa),
        "jefa": jefa,
        "ana": usuario(client, h, emp, "Ana"),
        "beto": usuario(client, h, emp, "Beto"),
        "carla": usuario(client, h, emp, "Carla"),
        "dante": usuario(client, h, emp, "Dante"),
    }


# ---------------------------------------------------------------- registro


def test_borrador_con_numero_totales_y_distribucion(client, h, emp, gente):
    centros = [
        {"centro_costo_id": emp["centros"]["ADM"], "porcentaje": 33.3333},
        {"centro_costo_id": emp["centros"]["VEN"], "porcentaje": 66.6667},
    ]
    r = solicitud(client, gente["sol"], emp, precio=10, cantidad=10, centros=centros)
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["numero"].startswith("SC-") and s["numero"].endswith("-000001")
    assert s["estado"] == "borrador" and s["total"] == "100.00"
    montos = [d["monto"] for d in s["lineas"][0]["distribuciones"]]
    assert montos == ["33.33", "66.67"]  # el último centro cuadra el céntimo
    assert s["acciones"] == {"editar": True, "enviar": True, "aprobar": False, "anular": True}
    assert solicitud(client, gente["sol"], emp).json()["numero"].endswith("-000002")


def test_distribucion_debe_sumar_100(client, h, emp, gente):
    centros = [{"centro_costo_id": emp["centros"]["ADM"], "porcentaje": 60}]
    r = solicitud(client, gente["sol"], emp, centros=centros)
    assert r.status_code == 422 and r.json()["codigo"] == "distribucion_incompleta"


def test_sin_permiso_no_registra(client, h, emp, gente):
    r = solicitud(client, gente["ana"], emp)
    assert r.status_code == 403


def test_sin_regla_se_bloquea_el_envio(client, h, emp, gente):
    s = solicitud(client, gente["sol"], emp).json()
    r = accion(client, gente["sol"], s, "enviar")
    assert r.status_code == 422 and r.json()["codigo"] == "sin_regla_aprobacion"


# ---------------------------------------------------------------- reglas


def test_validaciones_de_regla(client, h, emp, gente):
    a = u(gente["ana"])
    r = regla(client, h, emp, [nivel(a, desde=1000), nivel(a, desde=500)])
    assert r.json()["codigo"] == "montos_desordenados"
    r = regla(client, h, emp, [nivel(a)] * 4)
    assert r.json()["codigo"] == "niveles_invalidos"
    r = regla(client, h, emp, [nivel()])
    assert r.json()["codigo"] == "nivel_sin_aprobadores"
    r = regla(client, h, emp, [nivel(a, modo="otro")])
    assert r.json()["codigo"] == "modo_invalido"
    assert regla(client, h, emp, [nivel(a)]).status_code == 201
    r = regla(client, h, emp, [nivel(a)])
    assert r.status_code == 409 and r.json()["codigo"] == "prioridad_repetida"


def test_regla_se_lee_y_se_reemplaza(client, h, emp, gente):
    r = regla(client, h, emp, [nivel(u(gente["ana"]))], unidad_negocio_id=emp["un"])
    regla_id = r.json()["id"]
    assert r.json()["condiciones"].startswith("Unidad")
    assert r.json()["niveles"][0]["aprobadores"][0]["descripcion"] == "Ana"
    datos = {
        "nombre": "Compras grandes",
        "prioridad": 1,
        "niveles": [nivel(u(gente["ana"])), nivel(u(gente["beto"]), desde=5000)],
    }
    r = client.put(f"{APR}/reglas/{regla_id}", headers=h, json=datos)
    assert r.status_code == 200, r.text
    assert len(r.json()["niveles"]) == 2 and r.json()["condiciones"] == "Todos los documentos"


# ---------------------------------------------------------------- flujo


def test_monto_define_los_niveles_y_serie_va_en_orden(client, h, emp, gente):
    g = gente
    regla(
        client,
        h,
        emp,
        [
            nivel(u(g["ana"]), u(g["beto"]), modo="serie"),
            nivel(u(g["carla"]), u(g["dante"]), desde=5000, modo="paralelo_cualquiera"),
        ],
    )
    # Monto bajo: solo nivel 1
    chica = solicitud(client, g["sol"], emp, precio=100).json()
    ruta = client.get(f"{SOL}/{chica['id']}/ruta", headers=g["sol"]["h"]).json()
    assert [n["numero"] for n in ruta["niveles"]] == [1]

    grande = solicitud(client, g["sol"], emp, precio=6000).json()
    r = accion(client, g["sol"], grande, "enviar")
    assert r.status_code == 200 and r.json()["estado"] == "en_aprobacion"
    assert r.json()["pendiente_de"] == ["Ana"]
    # Beto todavía no: es en serie
    assert accion(client, g["beto"], grande, "aprobar").json()["codigo"] == "no_es_tu_turno"
    assert [s["numero"] for s in client.get(f"{SOL}/bandeja", headers=g["ana"]["h"]).json()] == [
        grande["numero"]
    ]
    assert accion(client, g["ana"], grande, "aprobar").json()["pendiente_de"] == ["Beto"]
    r = accion(client, g["beto"], grande, "aprobar").json()
    assert sorted(r["pendiente_de"]) == ["Carla", "Dante"]  # nivel 2 en paralelo
    r = accion(client, g["dante"], grande, "aprobar", "Conforme").json()
    assert r["estado"] == "aprobada"
    estados = {p["descripcion"]: p["estado"] for p in r["pasos"]}
    assert estados == {
        "Ana": "aprobado",
        "Beto": "aprobado",
        "Carla": "omitido",
        "Dante": "aprobado",
    }
    assert r["lineas"][0]["cuenta"]  # la cuenta se fijó al enviar


def test_paralelo_todos(client, h, emp, gente):
    g = gente
    regla(client, h, emp, [nivel(u(g["ana"]), u(g["beto"]), modo="paralelo_todos")])
    s = solicitud(client, g["sol"], emp).json()
    accion(client, g["sol"], s, "enviar")
    assert accion(client, g["beto"], s, "aprobar").json()["estado"] == "en_aprobacion"
    assert accion(client, g["ana"], s, "aprobar").json()["estado"] == "aprobada"


def test_rechazo_exige_comentario_y_es_final(client, h, emp, gente):
    g = gente
    regla(client, h, emp, [nivel(u(g["ana"]), u(g["beto"]))])
    s = solicitud(client, g["sol"], emp).json()
    accion(client, g["sol"], s, "enviar")
    assert accion(client, g["ana"], s, "rechazar").json()["codigo"] == "comentario_requerido"
    r = accion(client, g["ana"], s, "rechazar", "No hay presupuesto").json()
    assert r["estado"] == "rechazada"
    assert {p["descripcion"]: p["estado"] for p in r["pasos"]}["Beto"] == "cancelado"
    assert accion(client, g["sol"], s, "enviar").status_code == 409


def test_devolver_y_reenviar_empieza_en_el_nivel_1(client, h, emp, gente):
    g = gente
    regla(client, h, emp, [nivel(u(g["ana"])), nivel(u(g["beto"]))])
    s = solicitud(client, g["sol"], emp).json()
    accion(client, g["sol"], s, "enviar")
    accion(client, g["ana"], s, "aprobar")
    r = accion(client, g["beto"], s, "devolver", "Falta la cotización").json()
    assert r["estado"] == "devuelta" and not r["acciones"]["editar"]
    propia = client.get(f"{SOL}/{s['id']}", headers=g["sol"]["h"]).json()
    assert propia["acciones"]["editar"] and propia["acciones"]["enviar"]
    datos = {
        "unidad_negocio_id": emp["un"],
        "titulo": "Útiles corregido",
        "lineas": [
            {
                "articulo_id": emp["art"],
                "cantidad": 2,
                "precio": 50,
                "distribuciones": [{"centro_costo_id": emp["centros"]["ADM"], "porcentaje": 100}],
            }
        ],
    }
    assert client.put(f"{SOL}/{s['id']}", headers=g["sol"]["h"], json=datos).status_code == 200
    r = accion(client, g["sol"], s, "enviar").json()
    assert r["ronda"] == 2 and r["pendiente_de"] == ["Ana"]


def test_el_solicitante_no_se_aprueba_a_si_mismo(client, h, emp, gente):
    g = gente
    regla(client, h, emp, [nivel(u(g["sol"]), u(g["ana"]))])
    s = solicitud(client, g["sol"], emp).json()
    r = accion(client, g["sol"], s, "enviar").json()
    pasos = {p["descripcion"]: (p["estado"], p["motivo"]) for p in r["pasos"]}
    assert pasos["Solicitante"] == ("omitido", "Es el solicitante")
    assert r["pendiente_de"] == ["Ana"]


def test_sin_niveles_para_el_monto_se_aprueba_al_enviar(client, h, emp, gente):
    regla(client, h, emp, [nivel(u(gente["ana"]), desde=1000)])
    s = solicitud(client, gente["sol"], emp, precio=50).json()
    assert accion(client, gente["sol"], s, "enviar").json()["estado"] == "aprobada"


# ---------------------------------------------------------------- tipos de aprobador


def test_jefe_del_solicitante(client, h, emp, gente):
    regla(client, h, emp, [nivel({"tipo": "jefe"})])
    s = solicitud(client, gente["sol"], emp).json()
    r = accion(client, gente["sol"], s, "enviar").json()
    assert r["pendiente_de"] == ["Jefa · Jefe del solicitante"]
    assert accion(client, gente["jefa"], s, "aprobar").json()["estado"] == "aprobada"


def test_sin_jefe_registrado_no_se_envia(client, h, emp, gente):
    otro = usuario(client, h, emp, "Nuevo", ["ERP_SOL_SOLICITANTE"])
    regla(client, h, emp, [nivel({"tipo": "jefe"})])
    s = solicitud(client, otro, emp).json()
    assert accion(client, otro, s, "enviar").json()["codigo"] == "sin_jefe"


def test_responsable_de_cada_centro_de_costo(client, h, emp, gente):
    g = gente
    regla(client, h, emp, [nivel({"tipo": "responsable_cc"}, modo="paralelo_todos")])
    centros = [
        {"centro_costo_id": emp["centros"]["ADM"], "porcentaje": 50},
        {"centro_costo_id": emp["centros"]["VEN"], "porcentaje": 50},
    ]
    s = solicitud(client, g["sol"], emp, centros=centros).json()
    assert accion(client, g["sol"], s, "enviar").json()["codigo"] == "centro_sin_responsable"
    for codigo, quien in (("ADM", "ana"), ("VEN", "beto")):
        r = client.patch(
            f"{CNT}/centros-costo/{emp['centros'][codigo]}",
            headers=h,
            json={"responsable_id": g[quien]["id"]},
        )
        assert r.json()["responsable_nombre"] == quien.capitalize()
    r = accion(client, g["sol"], s, "enviar").json()
    assert sorted(r["pendiente_de"]) == ["Ana · Responsable de ADM", "Beto · Responsable de VEN"]


def test_rol_aprobador_con_acceso_a_la_unidad(client, h, emp, gente):
    g = gente
    gerente = usuario(client, h, emp, "Gerente", ["ERP_SOL_CONSULTA"])
    roles = {r["codigo"]: r["id"] for r in client.get(f"{API_SEG}/roles", headers=h).json()}
    regla(client, h, emp, [nivel({"tipo": "rol", "rol_id": roles["ERP_SOL_CONSULTA"]})])
    s = solicitud(client, g["sol"], emp).json()
    r = accion(client, g["sol"], s, "enviar").json()
    assert r["pendiente_de"] == ["Rol Consulta de solicitudes"]
    assert accion(client, g["ana"], s, "aprobar").status_code == 403
    assert accion(client, gerente, s, "aprobar").json()["estado"] == "aprobada"


def test_condiciones_de_aprobador_y_prioridad_de_reglas(client, h, emp, gente):
    g = gente
    otra_un = client.post(
        f"{MAE}/empresas/{emp['id']}/unidades-negocio",
        headers=h,
        json={"codigo": "NOR", "nombre": "Planta Norte"},
    ).json()["id"]
    # Regla 1 solo para servicios; regla 2 general con aprobador condicionado por unidad
    regla(client, h, emp, [nivel(u(g["dante"]))], prioridad=1, tipo_articulo="servicio")
    regla(
        client,
        h,
        emp,
        [nivel({**u(g["ana"]), "unidad_negocio_id": otra_un}, u(g["beto"]))],
        prioridad=2,
    )
    s = solicitud(client, g["sol"], emp).json()
    ruta = client.get(f"{SOL}/{s['id']}/ruta", headers=g["sol"]["h"]).json()
    assert ruta["regla"] == "Regla 2"
    assert [p["descripcion"] for p in ruta["niveles"][0]["pasos"]] == ["Beto"]


# ---------------------------------------------------------------- anulación y visibilidad


def test_anular(client, h, emp, gente):
    g = gente
    regla(client, h, emp, [nivel(u(g["ana"]))])
    borrador = solicitud(client, g["sol"], emp).json()
    assert accion(client, g["sol"], borrador, "anular").json()["codigo"] == "comentario_requerido"
    assert accion(client, g["sol"], borrador, "anular", "Ya no se necesita").json()["estado"] == (
        "anulada"
    )
    s = solicitud(client, g["sol"], emp).json()
    accion(client, g["sol"], s, "enviar")
    assert accion(client, g["sol"], s, "anular", "x" * 5).json()["codigo"] == "en_aprobacion"
    accion(client, g["ana"], s, "aprobar")
    assert accion(client, g["sol"], s, "anular", "Cambio de plan").status_code == 403
    admin_sol = usuario(client, h, emp, "Compras", ["ERP_SOL_ADMINISTRADOR"])
    assert accion(client, admin_sol, s, "anular", "Cambio de plan").json()["estado"] == "anulada"


def test_visibilidad(client, h, emp, gente):
    g = gente
    s = solicitud(client, g["sol"], emp).json()
    assert client.get(f"{SOL}/{s['id']}", headers=g["ana"]["h"]).status_code == 403
    consulta = usuario(client, h, emp, "Auditora", ["ERP_SOL_CONSULTA"])
    assert client.get(f"{SOL}/{s['id']}", headers=consulta["h"]).status_code == 200
    r = client.get(SOL, headers=consulta["h"], params={"empresa_id": emp["id"], "alcance": "todas"})
    assert len(r.json()) == 1
    r = client.get(SOL, headers=g["ana"]["h"], params={"empresa_id": emp["id"], "alcance": "todas"})
    assert r.status_code == 403


def test_articulo_sin_perfil_no_se_envia(client, h, emp, gente):
    cat = client.post(f"{MAE}/categorias", headers=h, json={"codigo": "OTR", "nombre": "Otros"})
    art = client.post(
        f"{MAE}/articulos",
        headers=h,
        json={
            "descripcion": "Servicio raro",
            "tipo": "servicio",
            "categoria_id": cat.json()["id"],
            "unidad": "SRV",
        },
    ).json()
    regla(client, h, emp, [nivel(u(gente["ana"]))])
    s = solicitud(client, gente["sol"], {**emp, "art": art["id"]}).json()
    assert accion(client, gente["sol"], s, "enviar").json()["codigo"] == "articulo_sin_perfil"


def test_jefe_sin_ciclos(client, h, emp, gente):
    r = client.patch(
        f"{API_SEG}/usuarios/{gente['jefa']['id']}",
        headers=h,
        json={"jefe_id": gente["sol"]["id"]},
    )
    assert r.status_code == 422 and r.json()["codigo"] == "jefe_ciclo"


def test_listas_de_apoyo_para_el_solicitante(client, h, emp, gente):
    r = client.get(f"{SOL}/articulos", headers=gente["sol"]["h"], params={"texto": "papel"})
    assert [a["descripcion"] for a in r.json()] == ["Papel bond A4"]
    r = client.get(f"{SOL}/empresas/{emp['id']}/opciones", headers=gente["sol"]["h"])
    assert {c["codigo"] for c in r.json()["centros"]} == {"ADM", "VEN"}
    assert client.get(f"{SOL}/articulos", headers=gente["ana"]["h"]).status_code == 403
