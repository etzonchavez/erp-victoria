"""Dependencias de FastAPI para proteger rutas.

Uso en cualquier módulo:

    @router.post("/ordenes", dependencies=[Depends(requiere("compras.orden.crear"))])
"""

from collections.abc import Callable

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import ErrorERP
from app.core.security import leer_token
from app.modules.seguridad import service
from app.modules.seguridad.models import Usuario

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/seguridad/auth/token", auto_error=False)


def usuario_actual(token: str | None = Depends(oauth2), db: Session = Depends(get_db)) -> Usuario:
    usuario_id = leer_token(token) if token else None
    usuario = db.get(Usuario, usuario_id) if usuario_id else None
    if not usuario:
        raise ErrorERP(401, "no_autenticado", "Sesión inválida o vencida")
    if not usuario.activo:
        raise ErrorERP(403, "usuario_inactivo", "El usuario está desactivado")
    return usuario


def requiere(permiso: str) -> Callable[..., Usuario]:
    def _verificar(
        usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)
    ) -> Usuario:
        service.verificar_permiso(db, usuario, permiso)
        return usuario

    return _verificar


def modulo_activo(modulo: str) -> Callable[..., Usuario]:
    """Para rutas sin permiso propio (aprobar, bandeja): basta con el módulo activo."""

    def _verificar(
        usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)
    ) -> Usuario:
        if modulo not in service.modulos_activos(db):
            raise ErrorERP(403, "modulo_inactivo", f"El módulo {modulo} no está activo")
        return usuario

    return _verificar
