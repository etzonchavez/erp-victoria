"""Motor de aprobación: reglas configurables y pasos de aprobación de los documentos.

Lo usan los módulos dueños de documentos (solicitudes hoy, compras después):

    ctx = Contexto(documento="solicitud", documento_id=..., empresa_id=..., ...)
    aprobaciones.simular(db, ctx)                 # quién aprobaría, sin guardar nada
    estado = aprobaciones.iniciar(db, ctx, ronda)  # "en_aprobacion" o "aprobado"
    estado = aprobaciones.actuar(db, actor, ctx, ronda, "aprobar", comentario)

Reglas:
- Por empresa y documento. Se elige la regla activa de menor prioridad cuyas condiciones
  (unidad de negocio, categoría, tipo de artículo, centro de costo) se cumplen todas.
- Hasta 3 niveles. Un nivel se activa si el monto (en la moneda de la empresa) alcanza su
  "monto desde". Los niveles van en orden: el 2 empieza cuando termina el 1.
- Modo de cada nivel: serie, paralelo_todos o paralelo_cualquiera.
- El solicitante nunca aprueba su propia solicitud: su paso se omite.
"""

import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import false, or_, select
from sqlalchemy.orm import Session

from app.core.database import ahora_utc
from app.core.errors import ErrorERP, no_encontrado
from app.modules.aprobaciones.models import (
    MAX_NIVELES,
    MODOS,
    TIPOS_APROBADOR,
    Aprobador,
    Nivel,
    Paso,
    Regla,
)
from app.modules.contabilidad import service as contabilidad
from app.modules.maestros import datos_base
from app.modules.maestros import service as maestros
from app.modules.seguridad import notificaciones
from app.modules.seguridad import service as seguridad
from app.modules.seguridad.models import Rol, Usuario
from app.modules.seguridad.service import auditar

FINALES = {"aprobado", "omitido", "rechazado", "devuelto", "cancelado"}


@dataclass
class Contexto:
    """Lo que el motor necesita saber del documento para elegir aprobadores."""

    documento: str
    documento_id: uuid.UUID
    empresa_id: uuid.UUID
    unidad_negocio_id: uuid.UUID
    solicitante_id: uuid.UUID
    monto: Decimal  # en la moneda funcional de la empresa
    categorias: set[uuid.UUID] = field(default_factory=set)  # incluye las categorías padre
    tipos: set[str] = field(default_factory=set)
    centros: list[uuid.UUID] = field(default_factory=list)
    # Para los avisos: "Solicitud SC-2026-000001 · Útiles de oficina" y ruta del frontend
    referencia: str = ""
    enlace: str = ""


# ---------------------------------------------------------------- reglas


def listar_reglas(db: Session, empresa_id: uuid.UUID, documento: str) -> list[Regla]:
    return list(
        db.scalars(
            select(Regla)
            .where(Regla.empresa_id == empresa_id, Regla.documento == documento)
            .order_by(Regla.prioridad)
        )
    )


def obtener_regla(db: Session, regla_id: uuid.UUID) -> Regla:
    regla = db.get(Regla, regla_id)
    if not regla:
        raise no_encontrado("La regla de aprobación")
    return regla


def _validar_condiciones(db: Session, empresa_id: uuid.UUID, datos: dict, donde: str) -> None:
    if datos.get("unidad_negocio_id"):
        un = maestros.obtener_unidad_negocio(db, datos["unidad_negocio_id"])
        if un.empresa_id != empresa_id:
            raise ErrorERP(422, "unidad_otra_empresa", f"{donde}: la unidad es de otra empresa")
    if datos.get("categoria_id"):
        maestros.obtener_categoria(db, datos["categoria_id"])
    if datos.get("tipo_articulo") and datos["tipo_articulo"] not in datos_base.TIPOS_ARTICULO:
        raise ErrorERP(422, "tipo_invalido", f"{donde}: tipo de artículo inexistente")
    if datos.get("centro_costo_id"):
        cc = contabilidad.obtener_centro(db, datos["centro_costo_id"])
        if cc.empresa_id != empresa_id:
            raise ErrorERP(
                422, "centro_otra_empresa", f"{donde}: el centro de costo es de otra empresa"
            )


def _validar_aprobador(db: Session, empresa_id: uuid.UUID, a: dict, donde: str) -> None:
    tipo = a.get("tipo")
    if tipo not in TIPOS_APROBADOR:
        raise ErrorERP(422, "tipo_aprobador_invalido", f"{donde}: tipo de aprobador inexistente")
    if tipo == "usuario":
        usuario = db.get(Usuario, a.get("usuario_id")) if a.get("usuario_id") else None
        if not usuario or not usuario.activo:
            raise ErrorERP(422, "aprobador_invalido", f"{donde}: elige un usuario activo")
    if tipo == "rol":
        rol = db.get(Rol, a.get("rol_id")) if a.get("rol_id") else None
        if not rol or not rol.activo:
            raise ErrorERP(422, "aprobador_invalido", f"{donde}: elige un rol activo")
    _validar_condiciones(db, empresa_id, a, donde)


def _validar_niveles(db: Session, empresa_id: uuid.UUID, niveles: list[dict]) -> None:
    if not 1 <= len(niveles) <= MAX_NIVELES:
        raise ErrorERP(
            422, "niveles_invalidos", f"La regla debe tener entre 1 y {MAX_NIVELES} niveles"
        )
    anterior = Decimal(0)
    for i, n in enumerate(niveles, start=1):
        monto = Decimal(str(n.get("monto_desde") or 0))
        if monto < 0:
            raise ErrorERP(422, "monto_invalido", f"Nivel {i}: el monto no puede ser negativo")
        if monto < anterior:
            raise ErrorERP(
                422,
                "montos_desordenados",
                f"Nivel {i}: el monto desde no puede ser menor que el del nivel anterior",
            )
        anterior = monto
        if n.get("modo") not in MODOS:
            raise ErrorERP(422, "modo_invalido", f"Nivel {i}: modo inexistente")
        if not n.get("aprobadores"):
            raise ErrorERP(422, "nivel_sin_aprobadores", f"Nivel {i}: agrega al menos un aprobador")
        for j, a in enumerate(n["aprobadores"], start=1):
            _validar_aprobador(db, empresa_id, a, f"Nivel {i}, aprobador {j}")


def _describir(regla: Regla) -> dict:
    return {
        "nombre": regla.nombre,
        "prioridad": regla.prioridad,
        "activo": regla.activo,
        "condiciones": {
            c: str(getattr(regla, c)) if getattr(regla, c) else None
            for c in ("unidad_negocio_id", "categoria_id", "tipo_articulo", "centro_costo_id")
        },
        "niveles": [
            {
                "numero": n.numero,
                "monto_desde": str(n.monto_desde),
                "modo": n.modo,
                "aprobadores": [a.tipo for a in n.aprobadores],
            }
            for n in regla.niveles
        ],
    }


def guardar_regla(
    db: Session,
    actor: Usuario,
    documento: str,
    datos: dict,
    empresa_id: uuid.UUID | None = None,
    regla_id: uuid.UUID | None = None,
) -> Regla:
    """Crea una regla (empresa_id) o la reemplaza completa con sus niveles (regla_id)."""
    regla = obtener_regla(db, regla_id) if regla_id else None
    empresa_id = regla.empresa_id if regla else empresa_id
    maestros.obtener_empresa(db, empresa_id)
    nombre = (datos.get("nombre") or "").strip()
    if len(nombre) < 3:
        raise ErrorERP(422, "nombre_invalido", "Escribe un nombre para la regla")
    prioridad = int(datos.get("prioridad") or 0)
    if prioridad < 1:
        raise ErrorERP(422, "prioridad_invalida", "La prioridad empieza en 1")
    q = select(Regla).where(
        Regla.empresa_id == empresa_id,
        Regla.documento == documento,
        Regla.prioridad == prioridad,
    )
    if regla:
        q = q.where(Regla.id != regla.id)
    repetida = db.scalar(q)
    if repetida:
        raise ErrorERP(
            409,
            "prioridad_repetida",
            f"La prioridad {prioridad} ya la usa la regla «{repetida.nombre}»",
        )
    _validar_condiciones(db, empresa_id, datos, "Condición de la regla")
    niveles = datos.get("niveles") or []
    _validar_niveles(db, empresa_id, niveles)

    antes = _describir(regla) if regla else None
    if not regla:
        regla = Regla(empresa_id=empresa_id, documento=documento, creado_por=actor.id)
        db.add(regla)
    regla.nombre = nombre
    regla.prioridad = prioridad
    regla.activo = datos.get("activo", True)
    for c in ("unidad_negocio_id", "categoria_id", "tipo_articulo", "centro_costo_id"):
        setattr(regla, c, datos.get(c) or None)
    regla.actualizado_por = actor.id
    regla.niveles.clear()
    db.flush()
    for i, n in enumerate(niveles, start=1):
        regla.niveles.append(
            Nivel(
                numero=i,
                monto_desde=Decimal(str(n.get("monto_desde") or 0)),
                modo=n["modo"],
                aprobadores=[
                    Aprobador(
                        orden=j,
                        tipo=a["tipo"],
                        usuario_id=a.get("usuario_id") if a["tipo"] == "usuario" else None,
                        rol_id=a.get("rol_id") if a["tipo"] == "rol" else None,
                        unidad_negocio_id=a.get("unidad_negocio_id") or None,
                        categoria_id=a.get("categoria_id") or None,
                        centro_costo_id=a.get("centro_costo_id") or None,
                    )
                    for j, a in enumerate(n["aprobadores"], start=1)
                ],
            )
        )
    db.flush()
    auditar(
        db,
        actor,
        "editar" if antes else "crear",
        "regla_aprobacion",
        regla.id,
        {"documento": documento, "antes": antes, "despues": _describir(regla)},
    )
    db.commit()
    db.refresh(regla)
    return regla


# ---------------------------------------------------------------- planificación


def _cumple(condiciones, ctx: Contexto, con_tipo: bool = True) -> bool:
    if condiciones.unidad_negocio_id and condiciones.unidad_negocio_id != ctx.unidad_negocio_id:
        return False
    if condiciones.categoria_id and condiciones.categoria_id not in ctx.categorias:
        return False
    if con_tipo and condiciones.tipo_articulo and condiciones.tipo_articulo not in ctx.tipos:
        return False
    if condiciones.centro_costo_id and condiciones.centro_costo_id not in ctx.centros:
        return False
    return True


def regla_aplicable(db: Session, ctx: Contexto) -> Regla:
    for regla in listar_reglas(db, ctx.empresa_id, ctx.documento):
        if regla.activo and _cumple(regla, ctx):
            return regla
    raise ErrorERP(
        422,
        "sin_regla_aprobacion",
        "No hay una regla de aprobación para esta solicitud. Avisa al administrador de "
        "solicitudes para que la configure.",
    )


def _pasos_del_aprobador(db: Session, a: Aprobador, ctx: Contexto, nivel: int) -> list[dict]:
    donde = f"Nivel {nivel}"
    if a.tipo == "usuario":
        u = db.get(Usuario, a.usuario_id)
        if not u or not u.activo:
            raise ErrorERP(
                422,
                "aprobador_inactivo",
                f"{donde}: el aprobador {u.nombre if u else ''} está inactivo. Avisa al "
                "administrador de solicitudes.",
            )
        return [{"usuario_id": u.id, "descripcion": u.nombre}]
    if a.tipo == "rol":
        rol = db.get(Rol, a.rol_id)
        if not rol or not rol.activo or not seguridad.usuarios_con_rol(db, rol.id):
            raise ErrorERP(
                422,
                "rol_sin_usuarios",
                f"{donde}: el rol {rol.nombre if rol else ''} no tiene usuarios activos",
            )
        return [{"rol_id": rol.id, "descripcion": f"Rol {rol.nombre}"}]
    if a.tipo == "jefe":
        solicitante = db.get(Usuario, ctx.solicitante_id)
        jefe = db.get(Usuario, solicitante.jefe_id) if solicitante.jefe_id else None
        if not jefe or not jefe.activo:
            raise ErrorERP(
                422,
                "sin_jefe",
                f"{donde}: aprueba el jefe del solicitante, pero {solicitante.nombre} no tiene "
                "un jefe inmediato activo registrado",
            )
        return [{"usuario_id": jefe.id, "descripcion": f"{jefe.nombre} · Jefe del solicitante"}]
    # responsable_cc
    centros = [a.centro_costo_id] if a.centro_costo_id else ctx.centros
    pasos = []
    for centro_id in centros:
        cc = contabilidad.obtener_centro(db, centro_id)
        resp = contabilidad.responsable_de_centro(db, centro_id)
        if not resp:
            raise ErrorERP(
                422,
                "centro_sin_responsable",
                f"{donde}: el centro de costo {cc.codigo} no tiene un usuario responsable. "
                "Pide a Contabilidad que lo registre.",
            )
        pasos.append(
            {"usuario_id": resp.id, "descripcion": f"{resp.nombre} · Responsable de {cc.codigo}"}
        )
    return pasos


def planificar(db: Session, ctx: Contexto) -> tuple[Regla, list[dict]]:
    """Pasos que tendría la aprobación, sin guardarlos."""
    regla = regla_aplicable(db, ctx)
    pasos: list[dict] = []
    for nivel in regla.niveles:
        if ctx.monto < nivel.monto_desde:
            continue
        del_nivel: list[dict] = []
        vistos: set = set()
        for a in nivel.aprobadores:
            if not _cumple(a, ctx, con_tipo=False):
                continue
            for p in _pasos_del_aprobador(db, a, ctx, nivel.numero):
                clave = p.get("usuario_id") or p.get("rol_id")
                if clave in vistos:
                    continue
                vistos.add(clave)
                omitido = p.get("usuario_id") == ctx.solicitante_id
                del_nivel.append(
                    {
                        "nivel": nivel.numero,
                        "modo": nivel.modo,
                        "monto_desde": nivel.monto_desde,
                        "orden": len(del_nivel) + 1,
                        "tipo": a.tipo,
                        "usuario_id": p.get("usuario_id"),
                        "rol_id": p.get("rol_id"),
                        "descripcion": p["descripcion"],
                        "estado": "omitido" if omitido else "en_espera",
                        "motivo": "Es el solicitante" if omitido else None,
                    }
                )
        if not del_nivel:
            raise ErrorERP(
                422,
                "nivel_sin_aprobadores",
                f"Nivel {nivel.numero} de la regla «{regla.nombre}»: ningún aprobador cumple "
                "sus condiciones para esta solicitud. Avisa al administrador de solicitudes.",
            )
        pasos.extend(del_nivel)
    return regla, pasos


def simular(db: Session, ctx: Contexto) -> dict:
    regla, pasos = planificar(db, ctx)
    niveles: dict[int, dict] = {}
    for p in pasos:
        n = niveles.setdefault(
            p["nivel"],
            {"numero": p["nivel"], "modo": p["modo"], "monto_desde": p["monto_desde"], "pasos": []},
        )
        n["pasos"].append(
            {"descripcion": p["descripcion"], "estado": p["estado"], "motivo": p["motivo"]}
        )
    return {"regla": regla.nombre, "niveles": list(niveles.values())}


# ---------------------------------------------------------------- ejecución


def pasos_de(db: Session, documento: str, documento_id: uuid.UUID) -> list[Paso]:
    return list(
        db.scalars(
            select(Paso)
            .where(Paso.documento == documento, Paso.documento_id == documento_id)
            .order_by(Paso.ronda, Paso.nivel, Paso.orden)
        )
    )


def _de_ronda(db: Session, ctx: Contexto, ronda: int) -> list[Paso]:
    return [p for p in pasos_de(db, ctx.documento, ctx.documento_id) if p.ronda == ronda]


def _nivel_completo(pasos: list[Paso]) -> bool:
    vigentes = [p for p in pasos if p.estado != "omitido"]
    if not vigentes:
        return True
    if pasos[0].modo == "paralelo_cualquiera":
        return any(p.estado == "aprobado" for p in vigentes)
    return all(p.estado == "aprobado" for p in vigentes)


def _avanzar(pasos: list[Paso]) -> str:
    """Activa lo que sigue. Devuelve "en_aprobacion" o "aprobado"."""
    for numero in sorted({p.nivel for p in pasos}):
        del_nivel = [p for p in pasos if p.nivel == numero]
        if _nivel_completo(del_nivel):
            for p in del_nivel:  # en paralelo-cualquiera, los demás ya no hacen falta
                if p.estado in ("en_espera", "pendiente"):
                    p.estado, p.motivo = "omitido", "Ya aprobó otro del mismo nivel"
            continue
        if any(p.estado == "pendiente" for p in del_nivel):
            return "en_aprobacion"
        espera = [p for p in del_nivel if p.estado == "en_espera"]
        if del_nivel[0].modo == "serie":
            espera[0].estado = "pendiente"
        else:
            for p in espera:
                p.estado = "pendiente"
        return "en_aprobacion"
    return "aprobado"


def _avisar_pendientes(db: Session, ctx: Contexto, pasos: list[Paso]) -> None:
    """Avisa a quien le toca aprobar (una vez por paso). Un rol avisa a sus usuarios con acceso."""
    for p in pasos:
        if p.estado != "pendiente" or p.notificado:
            continue
        if p.usuario_id:
            destino = [p.usuario_id]
        else:
            destino = []
            for u in seguridad.usuarios_con_rol(db, p.rol_id):
                if u.id == ctx.solicitante_id:
                    continue
                try:
                    maestros.verificar_acceso_unidad(db, u, ctx.unidad_negocio_id)
                except ErrorERP:
                    continue
                destino.append(u.id)
        notificaciones.notificar(
            db,
            destino,
            "por_aprobar",
            f"Por aprobar: {ctx.referencia}"
            if ctx.referencia
            else "Tienes un documento por aprobar",
            f"Nivel {p.nivel} · {MODOS[p.modo].split(':')[0].lower()}. Revísalo y decide.",
            ctx.enlace,
            ctx.documento,
            ctx.documento_id,
        )
        p.notificado = True


def iniciar(db: Session, ctx: Contexto, ronda: int) -> str:
    regla, plan = planificar(db, ctx)
    pasos = []
    for p in plan:
        paso = Paso(
            documento=ctx.documento,
            documento_id=ctx.documento_id,
            ronda=ronda,
            regla_id=regla.id,
            regla_nombre=regla.nombre,
            **{k: v for k, v in p.items() if k != "monto_desde"},
        )
        db.add(paso)
        pasos.append(paso)
    db.flush()
    resultado = _avanzar(pasos)
    _avisar_pendientes(db, ctx, pasos)
    return resultado


def puede_actuar(db: Session, usuario: Usuario, paso: Paso, ctx: Contexto) -> bool:
    if paso.estado != "pendiente" or usuario.id == ctx.solicitante_id:
        return False
    if paso.usuario_id:
        return paso.usuario_id == usuario.id
    if paso.rol_id and seguridad.tiene_rol(usuario, paso.rol_id):
        try:
            maestros.verificar_acceso_unidad(db, usuario, ctx.unidad_negocio_id)
        except ErrorERP:
            return False
        return True
    return False


def pasos_actuables(db: Session, usuario: Usuario, ctx: Contexto, ronda: int) -> list[Paso]:
    return [p for p in _de_ronda(db, ctx, ronda) if puede_actuar(db, usuario, p, ctx)]


def actuar(
    db: Session, actor: Usuario, ctx: Contexto, ronda: int, accion: str, comentario: str | None
) -> str:
    """Aprobar, rechazar o devolver. Devuelve el estado que toma el documento."""
    comentario = (comentario or "").strip() or None
    if accion in ("rechazar", "devolver") and (not comentario or len(comentario) < 3):
        raise ErrorERP(422, "comentario_requerido", "Escribe el motivo en el comentario")
    if ctx.solicitante_id == actor.id:
        raise ErrorERP(403, "autoaprobacion", "No puedes aprobar tu propia solicitud")
    pasos = _de_ronda(db, ctx, ronda)
    mio = next((p for p in pasos if puede_actuar(db, actor, p, ctx)), None)
    if not mio:
        raise ErrorERP(
            403, "no_es_tu_turno", "No tienes una aprobación pendiente en este documento"
        )
    mio.estado = {"aprobar": "aprobado", "rechazar": "rechazado", "devolver": "devuelto"}[accion]
    mio.actuado_por, mio.actuado_por_nombre = actor.id, actor.nombre
    mio.actuado_en, mio.comentario = ahora_utc(), comentario
    if accion == "aprobar":
        resultado = _avanzar(pasos)
        _avisar_pendientes(db, ctx, pasos)
        return resultado
    for p in pasos:
        if p.estado in ("en_espera", "pendiente"):
            p.estado = "cancelado"
    return "rechazado" if accion == "rechazar" else "devuelto"


def cancelar_ronda(db: Session, ctx: Contexto, ronda: int) -> None:
    for p in _de_ronda(db, ctx, ronda):
        if p.estado in ("en_espera", "pendiente"):
            p.estado = "cancelado"


def documentos_pendientes(db: Session, usuario: Usuario, documento: str) -> set[uuid.UUID]:
    """Documentos con un paso pendiente para el usuario o para alguno de sus roles.

    El módulo dueño del documento confirma luego el acceso a la unidad de negocio.
    """
    roles = [r.id for r in usuario.roles if r.activo]
    q = select(Paso.documento_id).where(
        Paso.documento == documento,
        Paso.estado == "pendiente",
        or_(Paso.usuario_id == usuario.id, Paso.rol_id.in_(roles) if roles else false()),
    )
    return set(db.scalars(q))


def documentos_con_paso(db: Session, usuario: Usuario, documento: str) -> set[uuid.UUID]:
    """Documentos en los que el usuario participa o participó como aprobador."""
    roles = [r.id for r in usuario.roles if r.activo]
    q = select(Paso.documento_id).where(
        Paso.documento == documento,
        or_(
            Paso.usuario_id == usuario.id,
            Paso.actuado_por == usuario.id,
            Paso.rol_id.in_(roles) if roles else false(),
        ),
    )
    return set(db.scalars(q))
