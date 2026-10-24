"""Rutas del módulo de seguridad: /api/v1/seguridad/..."""

import uuid

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import crear_token
from app.modules.seguridad import catalogo, service
from app.modules.seguridad.deps import requiere, usuario_actual
from app.modules.seguridad.models import Rol, Usuario
from app.modules.seguridad.schemas import (
    AuditoriaSalida,
    LoginEntrada,
    ModuloCambio,
    ModuloSalida,
    PermisoSalida,
    RolCambio,
    RolCrear,
    RolDuplicar,
    RolSalida,
    Sesion,
    TipoRolSalida,
    Token,
    UsuarioCambio,
    UsuarioCrear,
    UsuarioSalida,
)

router = APIRouter()


def _rol(rol: Rol) -> RolSalida:
    return RolSalida(
        id=rol.id,
        codigo=rol.codigo,
        nombre=rol.nombre,
        tipo=rol.tipo,
        estandar=rol.estandar,
        descripcion=rol.descripcion,
        activo=rol.activo,
        permisos=sorted(p.codigo for p in rol.permisos),
    )


# ---------------------------------------------------------------- autenticación


@router.post("/auth/login", response_model=Token, summary="Iniciar sesión")
def login(datos: LoginEntrada, db: Session = Depends(get_db)):
    usuario = service.autenticar(db, datos.email, datos.password)
    return Token(access_token=crear_token(usuario.id))


@router.post("/auth/token", response_model=Token, include_in_schema=False)
def token_formulario(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Usado por el botón Authorize de /docs."""
    usuario = service.autenticar(db, form.username, form.password)
    return Token(access_token=crear_token(usuario.id))


@router.get("/auth/sesion", response_model=Sesion, summary="Usuario, permisos y módulos activos")
def sesion(usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    return Sesion(
        usuario=UsuarioSalida.model_validate(usuario),
        permisos=sorted(service.permisos_de(db, usuario)),
        modulos=[ModuloSalida.model_validate(m) for m in service.listar_modulos(db) if m.activo],
    )


# ---------------------------------------------------------------- módulos


@router.get("/modulos", response_model=list[ModuloSalida], summary="Listar módulos")
def modulos(_: Usuario = Depends(requiere("seguridad.modulo.ver")), db: Session = Depends(get_db)):
    return service.listar_modulos(db)


@router.patch("/modulos/{codigo}", response_model=ModuloSalida, summary="Activar o desactivar")
def cambiar_modulo(
    codigo: str,
    datos: ModuloCambio,
    actor: Usuario = Depends(requiere("seguridad.modulo.editar")),
    db: Session = Depends(get_db),
):
    return service.cambiar_modulo(db, actor, codigo, datos.activo)


# ---------------------------------------------------------------- permisos y roles


@router.get("/permisos", response_model=list[PermisoSalida], summary="Catálogo de permisos")
def permisos(_: Usuario = Depends(requiere("seguridad.rol.ver")), db: Session = Depends(get_db)):
    return service.listar_permisos(db)


@router.get("/tipos-rol", response_model=list[TipoRolSalida], summary="Tipos de rol")
def tipos_rol(_: Usuario = Depends(requiere("seguridad.rol.ver"))):
    return [TipoRolSalida(codigo=c, descripcion=d) for c, d in catalogo.TIPOS_ROL.items()]


@router.get("/roles", response_model=list[RolSalida], summary="Listar roles")
def roles(_: Usuario = Depends(requiere("seguridad.rol.ver")), db: Session = Depends(get_db)):
    return [_rol(r) for r in service.listar_roles(db)]


@router.post("/roles", response_model=RolSalida, status_code=201, summary="Crear rol")
def crear_rol(
    datos: RolCrear,
    actor: Usuario = Depends(requiere("seguridad.rol.crear")),
    db: Session = Depends(get_db),
):
    return _rol(
        service.crear_rol(
            db, actor, datos.codigo, datos.nombre, datos.tipo, datos.descripcion, datos.permisos
        )
    )


@router.post(
    "/roles/{rol_id}/duplicar",
    response_model=RolSalida,
    status_code=201,
    summary="Crear un rol propio a partir de otro",
)
def duplicar_rol(
    rol_id: uuid.UUID,
    datos: RolDuplicar,
    actor: Usuario = Depends(requiere("seguridad.rol.crear")),
    db: Session = Depends(get_db),
):
    return _rol(service.duplicar_rol(db, actor, rol_id, datos.codigo, datos.nombre))


@router.get("/roles/{rol_id}", response_model=RolSalida, summary="Detalle de rol")
def rol(
    rol_id: uuid.UUID,
    _: Usuario = Depends(requiere("seguridad.rol.ver")),
    db: Session = Depends(get_db),
):
    return _rol(service.obtener_rol(db, rol_id))


@router.patch("/roles/{rol_id}", response_model=RolSalida, summary="Editar rol y permisos")
def cambiar_rol(
    rol_id: uuid.UUID,
    datos: RolCambio,
    actor: Usuario = Depends(requiere("seguridad.rol.editar")),
    db: Session = Depends(get_db),
):
    return _rol(service.cambiar_rol(db, actor, rol_id, datos.model_dump(exclude_unset=True)))


# ---------------------------------------------------------------- usuarios


@router.get("/usuarios", response_model=list[UsuarioSalida], summary="Listar usuarios")
def usuarios(
    _: Usuario = Depends(requiere("seguridad.usuario.ver")), db: Session = Depends(get_db)
):
    return service.listar_usuarios(db)


@router.post("/usuarios", response_model=UsuarioSalida, status_code=201, summary="Crear usuario")
def crear_usuario(
    datos: UsuarioCrear,
    actor: Usuario = Depends(requiere("seguridad.usuario.crear")),
    db: Session = Depends(get_db),
):
    return service.crear_usuario(db, actor, datos.model_dump())


@router.get("/usuarios/{usuario_id}", response_model=UsuarioSalida, summary="Detalle de usuario")
def usuario(
    usuario_id: uuid.UUID,
    _: Usuario = Depends(requiere("seguridad.usuario.ver")),
    db: Session = Depends(get_db),
):
    return service.obtener_usuario(db, usuario_id)


@router.patch("/usuarios/{usuario_id}", response_model=UsuarioSalida, summary="Editar usuario")
def cambiar_usuario(
    usuario_id: uuid.UUID,
    datos: UsuarioCambio,
    actor: Usuario = Depends(requiere("seguridad.usuario.editar")),
    db: Session = Depends(get_db),
):
    return service.cambiar_usuario(db, actor, usuario_id, datos.model_dump(exclude_unset=True))


# ---------------------------------------------------------------- auditoría


@router.get("/auditoria", response_model=list[AuditoriaSalida], summary="Consultar auditoría")
def auditoria(
    entidad: str | None = None,
    limite: int = 100,
    _: Usuario = Depends(requiere("seguridad.auditoria.ver")),
    db: Session = Depends(get_db),
):
    return service.listar_auditoria(db, entidad, limite)
