"""Preparación de una base de datos: catálogo, administrador inicial y datos base de cada módulo.

Cada módulo que precarga datos agrega aquí su función `preparar`.
"""

from sqlalchemy.orm import Session

import app.modules.maestros.models  # noqa: F401  registra las tablas
import app.modules.seguridad.models  # noqa: F401
from app.modules.maestros import service as maestros
from app.modules.seguridad.service import preparar_base


def preparar_sistema(db: Session) -> None:
    preparar_base(db)
    maestros.preparar(db)
