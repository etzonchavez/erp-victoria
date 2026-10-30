"""Router raíz de la API v1. Cada módulo registra aquí sus rutas."""

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.database import database_is_up
from app.modules.maestros.api import router as maestros_router
from app.modules.seguridad.api import router as seguridad_router

api_router = APIRouter()


@api_router.get("/health", tags=["sistema"], summary="Estado del servicio")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "database": "ok" if database_is_up() else "sin conexión",
    }


api_router.include_router(seguridad_router, prefix="/seguridad", tags=["seguridad"])
api_router.include_router(maestros_router, prefix="/maestros", tags=["maestros"])
