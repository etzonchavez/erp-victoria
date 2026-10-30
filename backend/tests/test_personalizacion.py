from tests.conftest import API, login

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'


def subir(client, headers, datos, nombre="logo.png"):
    return client.put(
        f"{API}/personalizacion/logo", headers=headers, files={"archivo": (nombre, datos)}
    )


def test_personalizacion_es_publica_y_vacia_al_inicio(client):
    r = client.get(f"{API}/personalizacion")
    assert r.status_code == 200
    assert r.json()["nombre_empresa"] is None
    assert r.json()["logo_url"] is None


def test_subir_logo_y_verlo_sin_sesion(client, admin):
    r = subir(client, admin, PNG)
    assert r.status_code == 200, r.text
    url = r.json()["logo_url"]
    assert url and "/personalizacion/logo?v=" in url
    logo = client.get(f"{API}/personalizacion/logo")
    assert logo.status_code == 200
    assert logo.headers["content-type"] == "image/png"
    assert logo.content == PNG


def test_tipo_se_detecta_por_contenido_no_por_extension(client, admin):
    assert subir(client, admin, JPG, "logo.png").status_code == 200
    assert client.get(f"{API}/personalizacion/logo").headers["content-type"] == "image/jpeg"


def test_svg_y_otros_formatos_son_rechazados(client, admin):
    r = subir(client, admin, SVG, "logo.svg")
    assert r.status_code == 415
    assert r.json()["codigo"] == "logo_formato"


def test_logo_de_hasta_2_mb_es_aceptado(client, admin):
    r = subir(client, admin, PNG + b"\x00" * (1536 * 1024))
    assert r.status_code == 200, r.text


def test_logo_de_mas_de_2_mb_es_rechazado(client, admin):
    r = subir(client, admin, PNG + b"\x00" * (2 * 1024 * 1024))
    assert r.status_code == 413
    assert r.json()["codigo"] == "logo_muy_grande"
    assert "2 MB" in r.json()["mensaje"]


def test_quitar_logo(client, admin):
    subir(client, admin, PNG)
    r = client.delete(f"{API}/personalizacion/logo", headers=admin)
    assert r.json()["logo_url"] is None
    assert client.get(f"{API}/personalizacion/logo").status_code == 404


def test_nombre_de_empresa(client, admin):
    r = client.put(
        f"{API}/personalizacion", headers=admin, json={"nombre_empresa": "Distribuidora Andina"}
    )
    assert r.json()["nombre_empresa"] == "Distribuidora Andina"
    assert client.get(f"{API}/personalizacion").json()["nombre_empresa"] == "Distribuidora Andina"


def test_sin_permiso_no_se_cambia_la_personalizacion(client, admin):
    client.post(
        f"{API}/usuarios",
        headers=admin,
        json={"email": "operador@empresa.pe", "nombre": "Operador", "password": "Clave1234"},
    )
    h = login(client, "operador@empresa.pe", "Clave1234")
    assert subir(client, h, PNG).status_code == 403
    r = client.put(f"{API}/personalizacion", headers=h, json={"nombre_empresa": "X"})
    assert r.status_code == 403


def test_cambios_de_personalizacion_quedan_auditados(client, admin):
    subir(client, admin, PNG)
    client.put(f"{API}/personalizacion", headers=admin, json={"nombre_empresa": "ACME"})
    eventos = client.get(f"{API}/auditoria?entidad=personalizacion", headers=admin).json()
    assert len(eventos) == 2
