"""Catálogo de módulos, permisos y roles estándar del ERP.

Cada módulo nuevo agrega aquí:
- sus permisos, con formato modulo.objeto.accion
- sus roles estándar, uno por tipo que aplique (ver TIPOS_ROL)

Al iniciar la API el catálogo se sincroniza con la base de datos.
"""

from dataclasses import dataclass, field


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


# Tipos de rol, en orden de mayor a menor alcance.
TIPOS_ROL: dict[str, str] = {
    "administrador": "Control total del módulo",
    "configuracion": "Parametriza el módulo sin operar el día a día",
    "operativo": "Ejecuta las transacciones diarias",
    "consulta": "Solo lectura y auditoría",
}


@dataclass(frozen=True)
class RolDef:
    """Rol estándar. Su código lleva punto (modulo.nombre): nunca choca con uno del cliente."""

    codigo: str
    nombre: str
    tipo: str
    descripcion: str
    permisos: list[str] = field(default_factory=list)


ROLES_ESTANDAR: list[RolDef] = [
    RolDef(
        "seguridad.administrador",
        "Administrador de seguridad",
        "administrador",
        "Gestiona usuarios, roles, módulos y consulta la auditoría.",
        [p.codigo for p in PERMISOS if p.modulo == "seguridad"],
    ),
    RolDef(
        "seguridad.configurador",
        "Configurador del sistema",
        "configuracion",
        "Activa módulos y diseña los roles de la empresa.",
        [
            "seguridad.modulo.ver",
            "seguridad.modulo.editar",
            "seguridad.rol.ver",
            "seguridad.rol.crear",
            "seguridad.rol.editar",
        ],
    ),
    RolDef(
        "seguridad.gestor_usuarios",
        "Gestor de usuarios",
        "operativo",
        "Da de alta usuarios, cambia contraseñas y asigna roles existentes.",
        [
            "seguridad.usuario.ver",
            "seguridad.usuario.crear",
            "seguridad.usuario.editar",
            "seguridad.rol.ver",
        ],
    ),
    RolDef(
        "seguridad.auditor",
        "Auditor",
        "consulta",
        "Consulta usuarios, roles, módulos y la auditoría sin poder cambiar nada.",
        [
            "seguridad.usuario.ver",
            "seguridad.rol.ver",
            "seguridad.modulo.ver",
            "seguridad.auditoria.ver",
        ],
    ),
]
