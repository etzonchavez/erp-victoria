"""Rutas del módulo de seguridad: /api/v1/seguridad/..."""

import uuid

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core import atributos as nucleo_atributos
from app.core.database import get_db
from app.core.errors import no_encontrado
from app.core.security import crear_token
from app.modules.seguridad import atributos, catalogo, service
from app.modules.seguridad.deps import requiere, usuario_actual
from app.modules.seguridad.models import Rol, Usuario
from app.modules.seguridad.schemas import (
    AtributoCambio,
    AtributoSalida,
    AuditoriaSalida,
    DocumentoSalida,
    LoginEntrada,
    ModuloCambio,
    ModuloSalida,
    PermisoSalida,
    PersonalizacionCambio,
    PersonalizacionSalida,
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
        modulo=rol.modulo,
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
            db,
            actor,
            datos.codigo,
            datos.modulo,
            datos.nombre,
            datos.tipo,
            datos.descripcion,
            datos.permisos,
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
    return _rol(service.duplicar_rol(db, actor, rol_id, datos.codigo, datos.nombre, datos.modulo))


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


# ---------------------------------------------------------------- personalización


def _personalizacion(p, request: Request) -> PersonalizacionSalida:
    logo = None
    if p.logo:
        version = int(p.actualizado_en.timestamp())
        logo = str(request.url_for("logo_empresa").include_query_params(v=version))
    return PersonalizacionSalida(
        nombre_empresa=p.nombre_empresa, logo_url=logo, actualizado_en=p.actualizado_en
    )


@router.get(
    "/personalizacion",
    response_model=PersonalizacionSalida,
    summary="Nombre y logo de la empresa (público, se usa en la pantalla de ingreso)",
)
def personalizacion(request: Request, db: Session = Depends(get_db)):
    return _personalizacion(service.obtener_personalizacion(db), request)


@router.get("/personalizacion/logo", name="logo_empresa", summary="Logo de la empresa (público)")
def logo_empresa(db: Session = Depends(get_db)):
    p = service.obtener_personalizacion(db)
    if not p.logo:
        raise no_encontrado("El logo")
    return Response(
        content=p.logo,
        media_type=p.logo_tipo,
        headers={
            "Cache-Control": "public, max-age=86400",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.put(
    "/personalizacion", response_model=PersonalizacionSalida, summary="Cambiar nombre de empresa"
)
def cambiar_personalizacion(
    datos: PersonalizacionCambio,
    request: Request,
    actor: Usuario = Depends(requiere("seguridad.personalizacion.editar")),
    db: Session = Depends(get_db),
):
    return _personalizacion(
        service.cambiar_nombre_empresa(db, actor, datos.nombre_empresa), request
    )


@router.put(
    "/personalizacion/logo",
    response_model=PersonalizacionSalida,
    summary="Subir logo (PNG, JPG o WebP, máximo 2 MB)",
)
async def subir_logo(
    request: Request,
    archivo: UploadFile = File(...),
    actor: Usuario = Depends(requiere("seguridad.personalizacion.editar")),
    db: Session = Depends(get_db),
):
    datos = await archivo.read(service.TAMANO_MAXIMO_LOGO + 1)
    return _personalizacion(service.cambiar_logo(db, actor, datos), request)


@router.delete("/personalizacion/logo", response_model=PersonalizacionSalida, summary="Quitar logo")
def quitar_logo(
    request: Request,
    actor: Usuario = Depends(requiere("seguridad.personalizacion.editar")),
    db: Session = Depends(get_db),
):
    return _personalizacion(service.quitar_logo(db, actor), request)


# ---------------------------------------------------------------- atributos adicionales


@router.get(
    "/documentos",
    response_model=list[DocumentoSalida],
    summary="Documentos operativos que llevan atributos adicionales",
)
def documentos(_: Usuario = Depends(usuario_actual)):
    return [
        DocumentoSalida(
            codigo=d.codigo,
            nombre=d.nombre,
            niveles=list(d.niveles),
            destinos=nucleo_atributos.destinos(d.codigo),
        )
        for d in nucleo_atributos.DOCUMENTOS.values()
    ]


@router.get(
    "/atributos",
    response_model=list[AtributoSalida],
    summary="Configuración de atributos (las pantallas la usan para dibujar los campos)",
)
def listar_atributos(
    documento: str | None = None,
    solo_activos: bool = False,
    _: Usuario = Depends(usuario_actual),
    db: Session = Depends(get_db),
):
    return atributos.listar(db, documento, solo_activos)


@router.put(
    "/atributos/{documento}/{nivel}/{tipo}/{numero}",
    response_model=AtributoSalida,
    summary="Activar, configurar o desactivar un atributo",
)
def definir_atributo(
    documento: str,
    nivel: str,
    tipo: str,
    numero: int,
    datos: AtributoCambio,
    actor: Usuario = Depends(requiere("seguridad.atributo.editar")),
    db: Session = Depends(get_db),
):
    atributos.definir(db, actor, documento, nivel, tipo, numero, datos.model_dump())
    fila = next(
        a
        for a in atributos.listar(db, documento)
        if (a["nivel"], a["tipo"], a["numero"]) == (nivel, tipo, numero)
    )
    return fila
