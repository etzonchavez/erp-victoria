"""Catálogo de módulos y permisos del ERP.

Cada módulo nuevo agrega aquí sus permisos con formato modulo.objeto.accion.
Al iniciar la API el catálogo se sincroniza con la base de datos.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModuloDef:
    codigo: str
    nombre: str
    orden: int
    obligatorio: bool = False


@dataclass(frozen=True)
class PermisoDef:
    codigo: str
    descripcion: str

    @property
    def modulo(self) -> str:
        return self.codigo.split(".")[0]


MODULOS: list[ModuloDef] = [
    ModuloDef("seguridad", "Seguridad", 10, obligatorio=True),
    ModuloDef("maestros", "Maestros", 20),
    ModuloDef("solicitudes", "Solicitudes de compra", 30),
    ModuloDef("compras", "Compras", 40),
]

PERMISOS: list[PermisoDef] = [
    PermisoDef("seguridad.usuario.ver", "Ver usuarios"),
    PermisoDef("seguridad.usuario.crear", "Crear usuarios"),
    PermisoDef("seguridad.usuario.editar", "Editar usuarios y asignar roles"),
    PermisoDef("seguridad.rol.ver", "Ver roles y permisos"),
    PermisoDef("seguridad.rol.crear", "Crear roles"),
    PermisoDef("seguridad.rol.editar", "Editar roles y sus permisos"),
    PermisoDef("seguridad.modulo.ver", "Ver módulos"),
    PermisoDef("seguridad.modulo.editar", "Activar y desactivar módulos"),
    PermisoDef("seguridad.auditoria.ver", "Consultar la auditoría"),
]
