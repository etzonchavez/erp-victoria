"""Dependencias de FastAPI para el acceso por empresa.

Toda ruta con {empresa_id} en la URL se protege agregando al router:

    router = APIRouter(dependencies=[Depends(acceso_empresa_de_ruta)])
"""

import uuid

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import ErrorERP
from app.modules.maestros import service
from app.modules.seguridad.deps import usuario_actual
from app.modules.seguridad.models import Usuario


def acceso_empresa_de_ruta(
    request: Request, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)
) -> None:
    empresa_id = request.path_params.get("empresa_id")
    if empresa_id:
        try:
            service.verificar_acceso_empresa(db, usuario, uuid.UUID(empresa_id))
        except ValueError:
            raise ErrorERP(404, "no_encontrado", "La empresa no existe") from None
