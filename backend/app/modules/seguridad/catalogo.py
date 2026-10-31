"""Catálogo de módulos, permisos y roles estándar del ERP.

Cada módulo nuevo agrega aquí:
- su abreviatura de 3 letras (se usa en el código de sus roles)
- sus permisos, con formato modulo.objeto.accion
- sus roles estándar, uno por tipo que aplique (ver TIPOS_ROL)

Al iniciar la API el catálogo se sincroniza con la base de datos.
"""

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModuloDef:
    codigo: str
    nombre: str
    abreviatura: str
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
    ModuloDef("seguridad", "Seguridad", "SEG", 10, obligatorio=True),
    ModuloDef("maestros", "Maestros", "MAE", 20),
    ModuloDef("contabilidad", "Contabilidad", "CNT", 25),
    ModuloDef("solicitudes", "Solicitudes de compra", "SOL", 30),
    ModuloDef("compras", "Compras", "COM", 40),
]
ABREVIATURAS: dict[str, str] = {m.codigo: m.abreviatura for m in MODULOS}

PERMISOS: list[PermisoDef] = [
    PermisoDef("seguridad.usuario.ver", "Ver usuarios"),
    PermisoDef("seguridad.usuario.crear", "Crear usuarios"),
    PermisoDef("seguridad.usuario.editar", "Editar usuarios y asignar roles"),
    PermisoDef("seguridad.rol.ver", "Ver roles y permisos"),
    PermisoDef("seguridad.rol.crear", "Crear roles"),
    PermisoDef("seguridad.rol.editar", "Editar roles y sus permisos"),
    PermisoDef("seguridad.modulo.ver", "Ver módulos"),
    PermisoDef("seguridad.modulo.editar", "Activar y desactivar módulos"),
    PermisoDef("seguridad.personalizacion.editar", "Cambiar el logo y el nombre de la empresa"),
    PermisoDef("seguridad.auditoria.ver", "Consultar la auditoría"),
    # Maestros
    PermisoDef("maestros.empresa.ver", "Ver empresas y unidades de negocio"),
    PermisoDef("maestros.empresa.editar", "Crear y editar empresas y unidades de negocio"),
    PermisoDef("maestros.moneda.ver", "Ver monedas y tipos de cambio"),
    PermisoDef("maestros.moneda.editar", "Activar y editar monedas"),
    PermisoDef("maestros.tipo_cambio.registrar", "Registrar el tipo de cambio diario"),
    PermisoDef("maestros.unidad.ver", "Ver unidades de medida y conversiones"),
    PermisoDef("maestros.unidad.editar", "Crear y editar unidades de medida y conversiones"),
    # Contabilidad base (ADR-004)
    PermisoDef("contabilidad.cuenta.ver", "Ver el plan de cuentas"),
    PermisoDef(
        "contabilidad.cuenta.editar", "Crear y editar cuentas; cargar la plantilla del país"
    ),
    PermisoDef("contabilidad.perfil.ver", "Ver perfiles contables"),
    PermisoDef("contabilidad.perfil.editar", "Crear y editar perfiles contables"),
    PermisoDef("contabilidad.centro_costo.ver", "Ver centros de costo"),
    PermisoDef("contabilidad.centro_costo.editar", "Crear y editar centros de costo"),
    PermisoDef("contabilidad.impuesto.ver", "Ver impuestos"),
    PermisoDef("contabilidad.impuesto.editar", "Crear y editar impuestos"),
]


# Tipos de rol, en orden de mayor a menor alcance.
TIPOS_ROL: dict[str, str] = {
    "administrador": "Control total del módulo",
    "configuracion": "Parametriza el módulo sin operar el día a día",
    "operativo": "Ejecuta las transacciones diarias",
    "consulta": "Solo lectura y auditoría",
}

# Nomenclatura de roles: ERP_<ABREVIATURA DEL MÓDULO>_<FUNCIÓN>, en mayúsculas.
# Ejemplos: ERP_SEG_ADMINISTRADOR, ERP_COM_ANALISTA.
PATRON_CODIGO_ROL = re.compile(r"^ERP_([A-Z]{3})_[A-Z0-9]+(?:_[A-Z0-9]+)*$")
LARGO_MAXIMO_CODIGO_ROL = 50


def prefijo_rol(modulo: str) -> str:
    return f"ERP_{ABREVIATURAS[modulo]}_"


def validar_codigo_rol(codigo: str, modulo: str) -> str | None:
    """Devuelve el motivo si el código no cumple la nomenclatura; None si es válido."""
    prefijo = prefijo_rol(modulo)
    if len(codigo) > LARGO_MAXIMO_CODIGO_ROL:
        return f"El código no puede superar {LARGO_MAXIMO_CODIGO_ROL} caracteres"
    if not PATRON_CODIGO_ROL.match(codigo) or not codigo.startswith(prefijo):
        return (
            f"El código debe seguir el formato {prefijo}FUNCION: mayúsculas, números y guion "
            f"bajo (ejemplo: {prefijo}ANALISTA)"
        )
    return None


@dataclass(frozen=True)
class RolDef:
    codigo: str
    modulo: str
    nombre: str
    tipo: str
    descripcion: str
    permisos: list[str] = field(default_factory=list)


ROLES_ESTANDAR: list[RolDef] = [
    RolDef(
        "ERP_SEG_ADMINISTRADOR",
        "seguridad",
        "Administrador de seguridad",
        "administrador",
        "Gestiona usuarios, roles, módulos, la personalización y consulta la auditoría.",
        [p.codigo for p in PERMISOS if p.modulo == "seguridad"],
    ),
    RolDef(
        "ERP_SEG_CONFIGURADOR",
        "seguridad",
        "Configurador del sistema",
        "configuracion",
        "Activa módulos, diseña los roles y personaliza el logo de la empresa.",
        [
            "seguridad.modulo.ver",
            "seguridad.modulo.editar",
            "seguridad.rol.ver",
            "seguridad.rol.crear",
            "seguridad.rol.editar",
            "seguridad.personalizacion.editar",
        ],
    ),
    RolDef(
        "ERP_SEG_GESTOR_USUARIOS",
        "seguridad",
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
        "ERP_SEG_AUDITOR",
        "seguridad",
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
    RolDef(
        "ERP_MAE_ADMINISTRADOR",
        "maestros",
        "Administrador de maestros",
        "administrador",
        "Responsable de los datos maestros: empresas, monedas, tipo de cambio y unidades.",
        [p.codigo for p in PERMISOS if p.modulo == "maestros"],
    ),
    RolDef(
        "ERP_MAE_CONFIGURADOR",
        "maestros",
        "Configurador de maestros",
        "configuracion",
        "Configura empresas, unidades de negocio, monedas y unidades de medida.",
        [
            "maestros.empresa.ver",
            "maestros.empresa.editar",
            "maestros.moneda.ver",
            "maestros.moneda.editar",
            "maestros.unidad.ver",
            "maestros.unidad.editar",
        ],
    ),
    RolDef(
        "ERP_MAE_ANALISTA",
        "maestros",
        "Analista de maestros",
        "operativo",
        "Registra el tipo de cambio diario y consulta los maestros.",
        [
            "maestros.empresa.ver",
            "maestros.moneda.ver",
            "maestros.tipo_cambio.registrar",
            "maestros.unidad.ver",
        ],
    ),
    RolDef(
        "ERP_MAE_CONSULTA",
        "maestros",
        "Consulta de maestros",
        "consulta",
        "Consulta empresas, monedas, tipos de cambio y unidades sin poder cambiarlos.",
        ["maestros.empresa.ver", "maestros.moneda.ver", "maestros.unidad.ver"],
    ),
    RolDef(
        "ERP_CNT_ADMINISTRADOR",
        "contabilidad",
        "Contador",
        "administrador",
        "Define el plan de cuentas, los perfiles contables, los impuestos y los centros de costo.",
        [p.codigo for p in PERMISOS if p.modulo == "contabilidad"],
    ),
    RolDef(
        "ERP_CNT_CONFIGURADOR",
        "contabilidad",
        "Analista contable",
        "configuracion",
        "Mantiene los centros de costo y consulta la configuración contable.",
        [
            "contabilidad.cuenta.ver",
            "contabilidad.perfil.ver",
            "contabilidad.centro_costo.ver",
            "contabilidad.centro_costo.editar",
            "contabilidad.impuesto.ver",
        ],
    ),
    RolDef(
        "ERP_CNT_CONSULTA",
        "contabilidad",
        "Consulta contable",
        "consulta",
        "Consulta el plan de cuentas, perfiles, centros de costo e impuestos.",
        [
            "contabilidad.cuenta.ver",
            "contabilidad.perfil.ver",
            "contabilidad.centro_costo.ver",
            "contabilidad.impuesto.ver",
        ],
    ),
]
