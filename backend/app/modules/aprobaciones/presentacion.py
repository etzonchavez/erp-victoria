"""Textos legibles de reglas y aprobadores, y listas de apoyo para los formularios.

Lo usan las API de aprobaciones, solicitudes y compras.
"""

import uuid

from sqlalchemy.orm import Session

from app.modules.aprobaciones.models import TIPOS_APROBADOR, Regla
from app.modules.contabilidad import service as contabilidad
from app.modules.maestros import datos_base
from app.modules.maestros import service as maestros
from app.modules.seguridad.models import Rol, Usuario


def nombre(db: Session, modelo, id_, campo: str = "nombre") -> str:
    obj = db.get(modelo, id_) if id_ else None
    return getattr(obj, campo) if obj else "—"


def condiciones(db: Session, c) -> list[str]:
    partes = []
    if c.unidad_negocio_id:
        partes.append(f"Unidad {maestros.obtener_unidad_negocio(db, c.unidad_negocio_id).nombre}")
    if c.categoria_id:
        partes.append(f"Categoría {maestros.obtener_categoria(db, c.categoria_id).codigo}")
    if getattr(c, "tipo_articulo", None):
        partes.append(datos_base.TIPOS_ARTICULO.get(c.tipo_articulo, c.tipo_articulo))
    if c.centro_costo_id:
        partes.append(f"Centro {contabilidad.obtener_centro(db, c.centro_costo_id).codigo}")
    return partes


def aprobador(db: Session, a) -> dict:
    if a.tipo == "usuario":
        base = nombre(db, Usuario, a.usuario_id)
    elif a.tipo == "rol":
        base = f"Rol {nombre(db, Rol, a.rol_id)}"
    else:
        base = TIPOS_APROBADOR[a.tipo]
    extra = condiciones(db, a)
    return {
        "tipo": a.tipo,
        "usuario_id": a.usuario_id,
        "rol_id": a.rol_id,
        "unidad_negocio_id": a.unidad_negocio_id,
        "categoria_id": a.categoria_id,
        "centro_costo_id": a.centro_costo_id,
        "descripcion": base + (f" · solo si {', '.join(extra)}" if extra else ""),
    }


def regla(db: Session, r: Regla) -> dict:
    extra = condiciones(db, r)
    return {
        "id": r.id,
        "empresa_id": r.empresa_id,
        "documento": r.documento,
        "nombre": r.nombre,
        "prioridad": r.prioridad,
        "activo": r.activo,
        "unidad_negocio_id": r.unidad_negocio_id,
        "categoria_id": r.categoria_id,
        "tipo_articulo": r.tipo_articulo,
        "centro_costo_id": r.centro_costo_id,
        "condiciones": " · ".join(extra) if extra else "Todos los documentos",
        "niveles": [
            {
                "numero": n.numero,
                "monto_desde": n.monto_desde,
                "modo": n.modo,
                "aprobadores": [aprobador(db, a) for a in n.aprobadores],
            }
            for n in r.niveles
        ],
    }


def opciones_empresa(db: Session, usuario: Usuario, empresa_id: uuid.UUID) -> dict:
    """Unidades (permitidas), centros de costo, categorías y tipos de artículo activos."""
    empresa = maestros.obtener_empresa(db, empresa_id)
    return {
        "unidades": [
            {"id": un.id, "codigo": un.codigo, "nombre": un.nombre}
            for un in maestros.unidades_permitidas(db, usuario, empresa)
            if un.activo
        ],
        "centros": [
            {"id": c.id, "codigo": c.codigo, "nombre": c.nombre}
            for c in contabilidad.listar_centros(db, empresa_id)
            if c.activo
        ],
        "categorias": [
            {"id": c.id, "codigo": c.codigo, "nombre": "· " * (c.nivel - 1) + c.nombre}
            for c in maestros.listar_categorias(db)
            if c.activo
        ],
        "tipos_articulo": [
            {"codigo": k, "nombre": v} for k, v in datos_base.TIPOS_ARTICULO.items()
        ],
    }


def pasos_pendientes(pasos: list, ronda: int) -> list[str]:
    return [p.descripcion for p in pasos if p.ronda == ronda and p.estado == "pendiente"]
