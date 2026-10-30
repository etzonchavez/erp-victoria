"""Reglas de negocio de seguridad. Otros módulos usan solo estas funciones."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import ahora_utc
from app.core.errors import ErrorERP, no_encontrado
from app.core.security import hashear_password, verificar_password
from app.modules.seguridad import catalogo
from app.modules.seguridad.models import (
    Auditoria,
    Modulo,
    Permiso,
    Personalizacion,
    Rol,
    Usuario,
)

# ---------------------------------------------------------------- auditoría


def auditar(
    db: Session,
    actor: Usuario | None,
    accion: str,
    entidad: str,
    entidad_id: str | uuid.UUID | None = None,
    detalle: dict | None = None,
) -> None:
    db.add(
        Auditoria(
            usuario_id=actor.id if actor else None,
            usuario_email=actor.email if actor else None,
            accion=accion,
            entidad=entidad,
            entidad_id=str(entidad_id) if entidad_id else None,
            detalle=detalle,
        )
    )


def listar_auditoria(db: Session, entidad: str | None = None, limite: int = 100) -> list[Auditoria]:
    q = select(Auditoria).order_by(Auditoria.fecha.desc()).limit(min(limite, 500))
    if entidad:
        q = q.where(Auditoria.entidad == entidad)
    return list(db.scalars(q))


# ---------------------------------------------------------------- arranque


def sincronizar_catalogo(db: Session) -> None:
    """Crea los módulos y permisos del catálogo que aún no existen en la BD."""
    existentes = {m.codigo: m for m in db.scalars(select(Modulo))}
    for m in catalogo.MODULOS:
        if m.codigo in existentes:
            reg = existentes[m.codigo]
            reg.nombre, reg.orden, reg.obligatorio = m.nombre, m.orden, m.obligatorio
            reg.abreviatura = m.abreviatura
            if m.obligatorio:
                reg.activo = True
        else:
            db.add(
                Modulo(
                    codigo=m.codigo,
                    nombre=m.nombre,
                    abreviatura=m.abreviatura,
                    orden=m.orden,
                    obligatorio=m.obligatorio,
                    activo=m.obligatorio,
                )
            )
    db.flush()
    permisos = {p.codigo: p for p in db.scalars(select(Permiso))}
    for p in catalogo.PERMISOS:
        if p.codigo in permisos:
            permisos[p.codigo].descripcion = p.descripcion
        else:
            db.add(Permiso(codigo=p.codigo, modulo=p.modulo, descripcion=p.descripcion))
    db.flush()
    sincronizar_roles_estandar(db)
    db.commit()


def sincronizar_roles_estandar(db: Session) -> None:
    """Crea o actualiza los roles estándar. Siempre quedan iguales al catálogo de la versión."""
    todos = {r.codigo: r for r in db.scalars(select(Rol))}
    for d in catalogo.ROLES_ESTANDAR:
        permisos = list(db.scalars(select(Permiso).where(Permiso.codigo.in_(d.permisos))))
        rol = todos.get(d.codigo)
        if rol and not rol.estandar:
            # Una versión nueva trae un rol estándar con el código de un rol propio del cliente:
            # el rol del cliente se renombra para no perderlo.
            nuevo = _codigo_libre(db, f"{d.codigo}_CLIENTE")
            auditar(db, None, "renombrar", "rol", rol.id, {"antes": rol.codigo, "despues": nuevo})
            rol.codigo = nuevo
            db.flush()
            rol = None
        if not rol:
            rol = Rol(codigo=d.codigo, estandar=True)
            db.add(rol)
        rol.modulo, rol.nombre, rol.tipo = d.modulo, d.nombre, d.tipo
        rol.descripcion, rol.activo, rol.permisos = d.descripcion, True, permisos


def _codigo_libre(db: Session, base: str) -> str:
    codigo, n = base, 2
    while db.scalar(select(Rol.id).where(Rol.codigo == codigo)):
        codigo, n = f"{base}_{n}", n + 1
    return codigo


def crear_administrador_inicial(db: Session) -> None:
    """Si no hay usuarios, crea el administrador definido en las variables de entorno."""
    if db.scalar(select(func.count()).select_from(Usuario)):
        return
    s = get_settings()
    admin = Usuario(
        email=s.admin_email.lower(),
        nombre="Administrador",
        password_hash=hashear_password(s.admin_password),
        es_administrador=True,
    )
    db.add(admin)
    db.flush()
    auditar(db, None, "crear", "usuario", admin.id, {"email": admin.email, "origen": "arranque"})
    db.commit()


def preparar_base(db: Session) -> None:
    sincronizar_catalogo(db)
    crear_administrador_inicial(db)


# ---------------------------------------------------------------- autenticación


def autenticar(db: Session, email: str, password: str) -> Usuario:
    usuario = db.scalar(select(Usuario).where(Usuario.email == email.lower()))
    if not usuario or not verificar_password(password, usuario.password_hash):
        auditar(db, None, "login_fallido", "sesion", detalle={"email": email.lower()})
        db.commit()
        raise ErrorERP(401, "credenciales_invalidas", "Correo o contraseña incorrectos")
    if not usuario.activo:
        raise ErrorERP(403, "usuario_inactivo", "El usuario está desactivado")
    usuario.ultimo_acceso = ahora_utc()
    auditar(db, usuario, "login", "sesion", usuario.id)
    db.commit()
    return usuario


def modulos_activos(db: Session) -> set[str]:
    return set(db.scalars(select(Modulo.codigo).where(Modulo.activo.is_(True))))


def permisos_de(db: Session, usuario: Usuario) -> set[str]:
    """Permisos efectivos: los de sus roles activos, solo de módulos activos."""
    activos = modulos_activos(db)
    if usuario.es_administrador:
        todos = db.scalars(select(Permiso))
        return {p.codigo for p in todos if p.modulo in activos}
    return {
        p.codigo for rol in usuario.roles if rol.activo for p in rol.permisos if p.modulo in activos
    }


# ---------------------------------------------------------------- módulos


def listar_modulos(db: Session) -> list[Modulo]:
    return list(db.scalars(select(Modulo).order_by(Modulo.orden)))


def cambiar_modulo(db: Session, actor: Usuario, codigo: str, activo: bool) -> Modulo:
    modulo = db.get(Modulo, codigo)
    if not modulo:
        raise no_encontrado("El módulo")
    if modulo.obligatorio and not activo:
        raise ErrorERP(
            409, "modulo_obligatorio", f"El módulo {modulo.nombre} no se puede desactivar"
        )
    if modulo.activo != activo:
        modulo.activo = activo
        auditar(db, actor, "activar" if activo else "desactivar", "modulo", codigo)
        db.commit()
    return modulo


# ---------------------------------------------------------------- roles


def _validar_permisos(db: Session, codigos: list[str]) -> list[Permiso]:
    encontrados = list(db.scalars(select(Permiso).where(Permiso.codigo.in_(codigos))))
    faltan = set(codigos) - {p.codigo for p in encontrados}
    if faltan:
        raise ErrorERP(
            422, "permiso_inexistente", f"Permisos no válidos: {', '.join(sorted(faltan))}"
        )
    return encontrados


def listar_permisos(db: Session) -> list[Permiso]:
    return list(db.scalars(select(Permiso).order_by(Permiso.codigo)))


def listar_roles(db: Session) -> list[Rol]:
    orden_tipo = list(catalogo.TIPOS_ROL)
    roles = db.scalars(select(Rol))
    return sorted(roles, key=lambda r: (not r.estandar, orden_tipo.index(r.tipo), r.nombre))


def obtener_rol(db: Session, rol_id: uuid.UUID) -> Rol:
    rol = db.get(Rol, rol_id)
    if not rol:
        raise no_encontrado("El rol")
    return rol


def _validar_codigo(db: Session, codigo: str, modulo: str) -> None:
    if not db.get(Modulo, modulo):
        raise ErrorERP(422, "modulo_inexistente", f"El módulo {modulo} no existe")
    motivo = catalogo.validar_codigo_rol(codigo, modulo)
    if motivo:
        raise ErrorERP(422, "codigo_rol_invalido", motivo)


def crear_rol(
    db: Session,
    actor: Usuario,
    codigo: str,
    modulo: str,
    nombre: str,
    tipo: str,
    descripcion: str | None,
    permisos: list[str],
    origen: Rol | None = None,
) -> Rol:
    codigo = codigo.strip().upper()
    _validar_codigo(db, codigo, modulo)
    if db.scalar(select(Rol).where(Rol.codigo == codigo)):
        raise ErrorERP(409, "rol_duplicado", f"Ya existe un rol con código {codigo}")
    rol = Rol(
        codigo=codigo,
        modulo=modulo,
        nombre=nombre,
        tipo=tipo,
        descripcion=descripcion,
        permisos=_validar_permisos(db, permisos),
        creado_por=actor.id,
        actualizado_por=actor.id,
    )
    db.add(rol)
    db.flush()
    detalle = {"codigo": codigo, "modulo": modulo, "tipo": tipo, "permisos": sorted(permisos)}
    if origen:
        detalle["duplicado_de"] = origen.codigo
    auditar(db, actor, "crear", "rol", rol.id, detalle)
    db.commit()
    return rol


def duplicar_rol(
    db: Session,
    actor: Usuario,
    rol_id: uuid.UUID,
    codigo: str,
    nombre: str,
    modulo: str | None = None,
) -> Rol:
    """Crea un rol propio con el tipo y los permisos de otro (normalmente uno estándar)."""
    origen = obtener_rol(db, rol_id)
    return crear_rol(
        db,
        actor,
        codigo,
        modulo or origen.modulo,
        nombre,
        origen.tipo,
        origen.descripcion,
        [p.codigo for p in origen.permisos],
        origen=origen,
    )


def cambiar_rol(db: Session, actor: Usuario, rol_id: uuid.UUID, cambios: dict) -> Rol:
    rol = obtener_rol(db, rol_id)
    if rol.estandar:
        raise ErrorERP(
            409,
            "rol_estandar",
            "Los roles estándar no se modifican. Duplícalo para crear una versión propia.",
        )
    detalle: dict = {}
    for campo in ("nombre", "tipo", "descripcion", "activo"):
        if campo in cambios and getattr(rol, campo) != cambios[campo]:
            detalle[campo] = {"antes": getattr(rol, campo), "despues": cambios[campo]}
            setattr(rol, campo, cambios[campo])
    if cambios.get("permisos") is not None:
        antes = sorted(p.codigo for p in rol.permisos)
        despues = sorted(set(cambios["permisos"]))
        if antes != despues:
            rol.permisos = _validar_permisos(db, despues)
            detalle["permisos"] = {"antes": antes, "despues": despues}
    if detalle:
        rol.actualizado_por = actor.id
        auditar(db, actor, "editar", "rol", rol.id, detalle)
        db.commit()
    return rol


# ---------------------------------------------------------------- usuarios


def listar_usuarios(db: Session) -> list[Usuario]:
    return list(db.scalars(select(Usuario).order_by(Usuario.nombre)))


def obtener_usuario(db: Session, usuario_id: uuid.UUID) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise no_encontrado("El usuario")
    return usuario


def _roles(db: Session, ids: list[uuid.UUID]) -> list[Rol]:
    roles = list(db.scalars(select(Rol).where(Rol.id.in_(ids)))) if ids else []
    if len(roles) != len(set(ids)):
        raise ErrorERP(422, "rol_inexistente", "Uno o más roles no existen")
    return roles


def crear_usuario(db: Session, actor: Usuario, datos: dict) -> Usuario:
    email = datos["email"].lower()
    if db.scalar(select(Usuario).where(Usuario.email == email)):
        raise ErrorERP(409, "usuario_duplicado", f"Ya existe un usuario con el correo {email}")
    if datos.get("es_administrador") and not actor.es_administrador:
        raise ErrorERP(403, "sin_permiso", "Solo un administrador puede crear administradores")
    usuario = Usuario(
        email=email,
        nombre=datos["nombre"],
        password_hash=hashear_password(datos["password"]),
        es_administrador=datos.get("es_administrador", False),
        roles=_roles(db, datos.get("roles", [])),
        creado_por=actor.id,
        actualizado_por=actor.id,
    )
    db.add(usuario)
    db.flush()
    auditar(
        db,
        actor,
        "crear",
        "usuario",
        usuario.id,
        {
            "email": email,
            "es_administrador": usuario.es_administrador,
            "roles": sorted(r.codigo for r in usuario.roles),
        },
    )
    db.commit()
    return usuario


def cambiar_usuario(db: Session, actor: Usuario, usuario_id: uuid.UUID, cambios: dict) -> Usuario:
    usuario = obtener_usuario(db, usuario_id)
    if "es_administrador" in cambios and not actor.es_administrador:
        raise ErrorERP(403, "sin_permiso", "Solo un administrador puede cambiar ese atributo")
    if usuario.id == actor.id and (
        cambios.get("activo") is False or cambios.get("es_administrador") is False
    ):
        raise ErrorERP(409, "auto_bloqueo", "No puedes desactivarte ni quitarte la administración")
    detalle: dict = {}
    for campo in ("nombre", "activo", "es_administrador"):
        if campo in cambios and getattr(usuario, campo) != cambios[campo]:
            detalle[campo] = {"antes": getattr(usuario, campo), "despues": cambios[campo]}
            setattr(usuario, campo, cambios[campo])
    if cambios.get("password"):
        usuario.password_hash = hashear_password(cambios["password"])
        detalle["password"] = "cambiada"
    if cambios.get("roles") is not None:
        antes = sorted(r.codigo for r in usuario.roles)
        usuario.roles = _roles(db, cambios["roles"])
        despues = sorted(r.codigo for r in usuario.roles)
        if antes != despues:
            detalle["roles"] = {"antes": antes, "despues": despues}
    if detalle:
        usuario.actualizado_por = actor.id
        auditar(db, actor, "editar", "usuario", usuario.id, detalle)
        db.commit()
    return usuario


# ---------------------------------------------------------------- personalización

TIPOS_IMAGEN = {
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
}
TAMANO_MAXIMO_LOGO = 2 * 1024 * 1024  # 2 MB: permite logos nítidos (≥ 600 px de ancho)


def tipo_de_imagen(datos: bytes) -> str | None:
    """Detecta el formato por su contenido, no por la extensión del archivo."""
    for firma, tipo in TIPOS_IMAGEN.items():
        if datos.startswith(firma):
            return tipo
    if datos[:4] == b"RIFF" and datos[8:12] == b"WEBP":
        return "image/webp"
    return None


def obtener_personalizacion(db: Session) -> Personalizacion:
    p = db.get(Personalizacion, 1)
    if not p:
        p = Personalizacion(id=1)
        db.add(p)
        db.commit()
    return p


def cambiar_nombre_empresa(db: Session, actor: Usuario, nombre: str | None) -> Personalizacion:
    p = obtener_personalizacion(db)
    nombre = (nombre or "").strip() or None
    if p.nombre_empresa != nombre:
        auditar(
            db,
            actor,
            "editar",
            "personalizacion",
            detalle={"nombre_empresa": {"antes": p.nombre_empresa, "despues": nombre}},
        )
        p.nombre_empresa, p.actualizado_por = nombre, actor.id
        db.commit()
    return p


def cambiar_logo(db: Session, actor: Usuario, datos: bytes) -> Personalizacion:
    if len(datos) > TAMANO_MAXIMO_LOGO:
        raise ErrorERP(413, "logo_muy_grande", "El logo no puede superar 2 MB")
    tipo = tipo_de_imagen(datos)
    if not tipo:
        raise ErrorERP(415, "logo_formato", "El logo debe ser una imagen PNG, JPG o WebP")
    p = obtener_personalizacion(db)
    p.logo, p.logo_tipo, p.actualizado_por = datos, tipo, actor.id
    auditar(
        db, actor, "editar", "personalizacion", detalle={"logo": f"{tipo}, {len(datos) // 1024} KB"}
    )
    db.commit()
    return p


def quitar_logo(db: Session, actor: Usuario) -> Personalizacion:
    p = obtener_personalizacion(db)
    if p.logo:
        p.logo, p.logo_tipo, p.actualizado_por = None, None, actor.id
        auditar(db, actor, "editar", "personalizacion", detalle={"logo": "quitado"})
        db.commit()
    return p
