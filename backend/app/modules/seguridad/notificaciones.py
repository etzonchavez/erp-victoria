"""Notificaciones del usuario (campana de la barra superior).

Los módulos las crean dentro de su propia transacción con notificar(); no hacen commit aquí.
"""

import uuid
from collections.abc import Iterable

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.database import ahora_utc
from app.core.errors import no_encontrado
from app.modules.seguridad.models import Notificacion, Usuario

LIMITE = 30


def notificar(
    db: Session,
    usuario_ids: Iterable[uuid.UUID],
    tipo: str,
    titulo: str,
    mensaje: str,
    enlace: str,
    documento: str | None = None,
    documento_id: uuid.UUID | None = None,
) -> int:
    """Crea un aviso por usuario (sin repetir). Devuelve cuántos creó."""
    creados = 0
    for usuario_id in dict.fromkeys(i for i in usuario_ids if i):
        db.add(
            Notificacion(
                usuario_id=usuario_id,
                tipo=tipo,
                titulo=titulo[:150],
                mensaje=mensaje[:300],
                enlace=enlace[:200],
                documento=documento,
                documento_id=documento_id,
            )
        )
        creados += 1
    return creados


def listar(db: Session, usuario: Usuario, solo_no_leidas: bool = False) -> list[Notificacion]:
    q = select(Notificacion).where(Notificacion.usuario_id == usuario.id)
    if solo_no_leidas:
        q = q.where(Notificacion.leida_en.is_(None))
    return list(db.scalars(q.order_by(Notificacion.creado_en.desc()).limit(LIMITE)))


def no_leidas(db: Session, usuario: Usuario) -> int:
    q = select(func.count()).where(
        Notificacion.usuario_id == usuario.id, Notificacion.leida_en.is_(None)
    )
    return db.scalar(q) or 0


def marcar_leida(db: Session, usuario: Usuario, notificacion_id: uuid.UUID) -> Notificacion:
    n = db.get(Notificacion, notificacion_id)
    if not n or n.usuario_id != usuario.id:
        raise no_encontrado("La notificación")
    if not n.leida_en:
        n.leida_en = ahora_utc()
        db.commit()
    return n


def marcar_todas(db: Session, usuario: Usuario) -> int:
    r = db.execute(
        update(Notificacion)
        .where(Notificacion.usuario_id == usuario.id, Notificacion.leida_en.is_(None))
        .values(leida_en=ahora_utc())
    )
    db.commit()
    return r.rowcount or 0
