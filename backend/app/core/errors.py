"""Formato único de errores de la API: {"codigo": "...", "mensaje": "..."}."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErrorERP(Exception):
    def __init__(self, status: int, codigo: str, mensaje: str):
        self.status = status
        self.codigo = codigo
        self.mensaje = mensaje


def no_encontrado(entidad: str) -> ErrorERP:
    return ErrorERP(404, "no_encontrado", f"{entidad} no existe")


def registrar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(ErrorERP)
    async def _erp(_: Request, exc: ErrorERP):
        return JSONResponse(
            status_code=exc.status, content={"codigo": exc.codigo, "mensaje": exc.mensaje}
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"codigo": "http_error", "mensaje": str(exc.detail)},
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _validacion(_: Request, exc: RequestValidationError):
        detalles = [
            {"campo": ".".join(str(p) for p in e["loc"][1:]), "mensaje": e["msg"]}
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "codigo": "validacion",
                "mensaje": "Datos inválidos",
                "detalles": detalles,
            },
        )
