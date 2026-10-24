"""Entradas y salidas de la API de seguridad."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Esquema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# Autenticación
class LoginEntrada(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=100)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# Módulos y permisos
class ModuloSalida(Esquema):
    codigo: str
    nombre: str
    orden: int
    activo: bool
    obligatorio: bool


class ModuloCambio(BaseModel):
    activo: bool


class PermisoSalida(Esquema):
    codigo: str
    modulo: str
    descripcion: str


# Roles
TipoRol = Literal["administrador", "configuracion", "operativo", "consulta"]
CodigoRol = Annotated[str, Field(min_length=2, max_length=50, pattern=r"^[a-z0-9_]+$")]


class TipoRolSalida(BaseModel):
    codigo: str
    descripcion: str


class RolCrear(BaseModel):
    codigo: CodigoRol
    nombre: str = Field(min_length=2, max_length=100)
    tipo: TipoRol
    descripcion: str | None = Field(default=None, max_length=300)
    permisos: list[str] = []


class RolDuplicar(BaseModel):
    codigo: CodigoRol
    nombre: str = Field(min_length=2, max_length=100)


class RolCambio(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=100)
    tipo: TipoRol | None = None
    descripcion: str | None = Field(default=None, max_length=300)
    activo: bool | None = None
    permisos: list[str] | None = None


class RolSalida(Esquema):
    id: uuid.UUID
    codigo: str
    nombre: str
    tipo: str
    estandar: bool
    descripcion: str | None
    activo: bool
    permisos: list[str]


class RolResumen(Esquema):
    id: uuid.UUID
    codigo: str
    nombre: str
    tipo: str


# Usuarios
class UsuarioCrear(BaseModel):
    email: EmailStr
    nombre: str = Field(min_length=2, max_length=150)
    password: str = Field(min_length=8, max_length=100)
    es_administrador: bool = False
    roles: list[uuid.UUID] = []


class UsuarioCambio(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=150)
    password: str | None = Field(default=None, min_length=8, max_length=100)
    activo: bool | None = None
    es_administrador: bool | None = None
    roles: list[uuid.UUID] | None = None


class UsuarioSalida(Esquema):
    id: uuid.UUID
    email: str
    nombre: str
    activo: bool
    es_administrador: bool
    ultimo_acceso: datetime | None
    roles: list[RolResumen]


class Sesion(BaseModel):
    usuario: UsuarioSalida
    permisos: list[str]
    modulos: list[ModuloSalida]


# Auditoría
class AuditoriaSalida(Esquema):
    id: uuid.UUID
    fecha: datetime
    usuario_email: str | None
    accion: str
    entidad: str
    entidad_id: str | None
    detalle: dict | None
