"""Punto de entrada de la API de Victoria ERP."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.errors import registrar_manejadores
from app.modules.seguridad.service import preparar_base

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.bootstrap_on_startup:
        with SessionLocal() as db:
            preparar_base(db)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "API de Victoria ERP. Toda funcionalidad se expone aquí para el front y los agentes de IA."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

registrar_manejadores(app)
app.include_router(api_router, prefix="/api/v1")
