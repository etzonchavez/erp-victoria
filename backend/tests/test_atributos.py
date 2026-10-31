from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import String, create_engine
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core import atributos as nucleo
from app.core.database import Base, ConAuditoria
from app.core.errors import ErrorERP
from app.modules.seguridad import atributos
from tests.conftest import API, login

URL = f"{API}/atributos"


def definir(client, h, documento, nivel, tipo, numero, **datos):
    return client.put(
        f"{URL}/{documento}/{nivel}/{tipo}/{numero}", headers=h, json={"activo": True, **datos}
    )


# ---------------------------------------------------------------- núcleo


def test_cada_documento_tiene_30_atributos_por_nivel(client, admin):
    filas = client.get(f"{URL}?documento=solicitud", headers=admin).json()
    assert len(filas) == 90  # 3 niveles x 30
    assert {f["nivel"] for f in filas} == {"cabecera", "linea", "distribucion"}
    assert all(not f["activo"] for f in filas)
    docs = {d["codigo"]: d for d in client.get(f"{API}/documentos", headers=admin).json()}
    assert docs["solicitud"]["destinos"] == ["orden_compra"]


def test_el_mixin_agrega_30_columnas_independientes():
    class DocPrueba(nucleo.ConAtributos, ConAuditoria, Base):
        __tablename__ = "zz_doc_prueba"
        nombre: Mapped[str] = mapped_column(String(10))

    columnas = [c.name for c in DocPrueba.__table__.c if c.name.startswith("atr_")]
    assert len(columnas) == 30 and "atr_fecha_10" in columnas
    engine = create_engine("sqlite://")
    DocPrueba.__table__.create(engine)
    with Session(engine) as s:
        d = DocPrueba(nombre="x", atr_numero_02=Decimal("1.5"), atr_fecha_01=date(2026, 11, 2))
        s.add(d)
        s.commit()
        assert s.get(DocPrueba, d.id).atr_numero_02 == Decimal("1.5")
    Base.metadata.remove(DocPrueba.__table__)


def test_columnas_para_migraciones():
    cols = nucleo.columnas_atributos()
    assert len(cols) == 30 and cols[0].name == "atr_texto_01"


# ---------------------------------------------------------------- configuración


def test_activar_requiere_nombre_unico(client, admin):
    assert (
        definir(client, admin, "solicitud", "cabecera", "texto", 1).json()["codigo"]
        == "etiqueta_requerida"
    )
    r = definir(
        client,
        admin,
        "solicitud",
        "cabecera",
        "texto",
        1,
        etiqueta="N.° de proyecto",
        ayuda="Código del proyecto",
    )
    assert r.status_code == 200 and r.json()["activo"] and r.json()["columna"] == "atr_texto_01"
    r = definir(client, admin, "solicitud", "cabecera", "texto", 2, etiqueta="n.° de proyecto")
    assert r.json()["codigo"] == "etiqueta_repetida"
    # el mismo nombre sí puede usarse en otro nivel
    assert (
        definir(
            client, admin, "solicitud", "linea", "texto", 2, etiqueta="N.° de proyecto"
        ).status_code
        == 200
    )


@pytest.mark.parametrize(
    ("tipo", "datos", "codigo"),
    [
        ("numero", {"valores": ["A"]}, "lista_solo_texto"),
        ("texto", {"valores": ["A", "a"]}, "valor_repetido"),
        ("texto", {"valores": ["A", "B"], "valor_defecto": "C"}, "defecto_fuera_de_lista"),
        ("numero", {"valor_defecto": "abc"}, "valor_invalido"),
        ("fecha", {"valor_defecto": "31/12/2026"}, "valor_invalido"),
        ("texto", {"copiar_documento": "orden_compra"}, "copia_incompleta"),
        ("texto", {"copiar_documento": "solicitud", "copiar_numero": 1}, "copia_invalida"),
        ("texto", {"copiar_documento": "orden_compra", "copiar_numero": 1}, "destino_inactivo"),
    ],
)
def test_validaciones_de_configuracion(client, admin, tipo, datos, codigo):
    r = definir(client, admin, "solicitud", "linea", tipo, 3, etiqueta="Campo", **datos)
    assert r.json()["codigo"] == codigo


def test_niveles_y_ranuras_validas(client, admin):
    assert (
        definir(client, admin, "solicitud", "pie", "texto", 1, etiqueta="X").json()["codigo"]
        == "nivel_invalido"
    )
    assert (
        definir(client, admin, "solicitud", "linea", "texto", 11, etiqueta="X").json()["codigo"]
        == "atributo_invalido"
    )
    assert (
        definir(client, admin, "factura", "linea", "texto", 1, etiqueta="X").json()["codigo"]
        == "documento_invalido"
    )


def test_mapeo_de_copia(client, admin):
    definir(client, admin, "orden_compra", "linea", "texto", 1, etiqueta="Proyecto")
    r = definir(
        client,
        admin,
        "solicitud",
        "linea",
        "texto",
        3,
        etiqueta="Proyecto",
        copiar_documento="orden_compra",
        copiar_numero=1,
    )
    assert r.json()["copiar_numero"] == 1
    r = definir(
        client,
        admin,
        "solicitud",
        "linea",
        "texto",
        4,
        etiqueta="Otro",
        copiar_documento="orden_compra",
        copiar_numero=1,
    )
    assert r.json()["codigo"] == "destino_ocupado"
    r = client.put(f"{URL}/orden_compra/linea/texto/1", headers=admin, json={"activo": False})
    assert r.json()["codigo"] == "destino_en_uso"


def test_solo_el_administrador_configura(client, admin):
    client.post(
        f"{API}/usuarios",
        headers=admin,
        json={"email": "op@x.pe", "nombre": "Operador", "password": "Clave1234"},
    )
    h = login(client, "op@x.pe", "Clave1234")
    assert client.get(f"{URL}?documento=solicitud&solo_activos=true", headers=h).status_code == 200
    assert definir(client, h, "solicitud", "cabecera", "texto", 1, etiqueta="X").status_code == 403


def test_configuracion_queda_auditada(client, admin):
    definir(client, admin, "solicitud", "cabecera", "fecha", 1, etiqueta="Fecha del evento")
    eventos = client.get(f"{API}/auditoria?entidad=atributo", headers=admin).json()
    assert eventos[0]["detalle"]["atributo"] == "atr_fecha_01"


# ---------------------------------------------------------------- uso en los documentos


@pytest.fixture
def configurado(client, admin):
    definir(client, admin, "orden_compra", "linea", "texto", 1, etiqueta="Proyecto")
    definir(client, admin, "orden_compra", "linea", "fecha", 2, etiqueta="Entrega")
    definir(
        client,
        admin,
        "solicitud",
        "linea",
        "texto",
        3,
        etiqueta="Proyecto",
        valores=["P-100", "P-200"],
        valor_defecto="P-100",
        copiar_documento="orden_compra",
        copiar_numero=1,
    )
    definir(client, admin, "solicitud", "linea", "numero", 1, etiqueta="Horas estimadas")
    definir(
        client,
        admin,
        "solicitud",
        "linea",
        "fecha",
        5,
        etiqueta="Fecha requerida",
        copiar_documento="orden_compra",
        copiar_numero=2,
    )


def test_validar_valores(configurado, db):
    with db() as s:
        v = atributos.validar_valores(
            s,
            "solicitud",
            "linea",
            {"atr_texto_03": "P-200", "atr_numero_01": "12.5", "atr_fecha_05": "2026-11-20"},
        )
        assert v == {
            "atr_texto_03": "P-200",
            "atr_numero_01": Decimal("12.5000"),
            "atr_fecha_05": date(2026, 11, 20),
        }
        assert atributos.validar_valores(s, "solicitud", "linea", {"atr_texto_03": ""}) == {
            "atr_texto_03": None
        }
        for valores, codigo in [
            ({"atr_texto_03": "P-999"}, "valor_fuera_de_lista"),
            ({"atr_numero_01": "doce"}, "valor_invalido"),
            ({"atr_texto_09": "x"}, "atributo_inactivo"),
        ]:
            with pytest.raises(ErrorERP) as e:
                atributos.validar_valores(s, "solicitud", "linea", valores)
            assert e.value.codigo == codigo


def test_valores_por_defecto_y_copia(configurado, db):
    with db() as s:
        assert atributos.valores_por_defecto(s, "solicitud", "linea") == {"atr_texto_03": "P-100"}
        origen = {
            "atr_texto_03": "P-200",
            "atr_numero_01": Decimal("3"),
            "atr_fecha_05": date(2026, 11, 20),
        }
        copia = atributos.copiar_valores(s, "solicitud", "orden_compra", "linea", origen)
        # horas estimadas no tiene destino: no se copia
        assert copia == {"atr_texto_01": "P-200", "atr_fecha_02": date(2026, 11, 20)}
