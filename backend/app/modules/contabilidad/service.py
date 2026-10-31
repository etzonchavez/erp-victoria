"""Reglas de la contabilidad base (ADR-004). Otros módulos usan solo estas funciones."""

import re
import uuid
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import ErrorERP, no_encontrado
from app.core.eventos import suscribir
from app.localizacion import pais
from app.modules.contabilidad.models import (
    ArticuloPerfil,
    CategoriaPerfil,
    CentroCosto,
    Cuenta,
    Impuesto,
    Perfil,
)
from app.modules.maestros import datos_base
from app.modules.maestros import service as maestros
from app.modules.maestros.models import Articulo, Categoria, Empresa
from app.modules.seguridad.models import Usuario
from app.modules.seguridad.service import auditar

TIPOS_ARTICULO = datos_base.TIPOS_ARTICULO

NATURALEZAS = [
    "activo",
    "pasivo",
    "patrimonio",
    "gasto",
    "ingreso",
    "resultado",
    "analitica",
    "orden",
]

# Naturaleza que debe tener cada cuenta del perfil, según el tipo de artículo.
# None = la cuenta no aplica y debe quedar vacía.
REGLAS_PERFIL: dict[str, dict[str, set[str] | None]] = {
    "bien_inventariable": {
        "cargo": {"gasto"},
        "existencia": {"activo"},
        "variacion": {"gasto"},
        "por_pagar": {"pasivo"},
    },
    "bien_no_inventariable": {
        "cargo": {"gasto"},
        "existencia": None,
        "variacion": None,
        "por_pagar": {"pasivo"},
    },
    "servicio": {
        "cargo": {"gasto"},
        "existencia": None,
        "variacion": None,
        "por_pagar": {"pasivo"},
    },
    "activo_fijo": {
        "cargo": {"activo"},
        "existencia": None,
        "variacion": None,
        "por_pagar": {"pasivo"},
    },
}
NOMBRE_CUENTA_PERFIL = {
    "cargo": "cuenta de cargo",
    "existencia": "cuenta de existencia",
    "variacion": "cuenta de variación",
    "por_pagar": "cuenta por pagar",
}

CODIGO_CUENTA = re.compile(r"^\d{1,20}$")
CODIGO_PERFIL = re.compile(r"^[A-Z0-9_]{2,30}$")
CODIGO_CC = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,19}$")
CODIGO_IMPUESTO = re.compile(r"^[A-Z0-9_]{2,20}$")


def _cambios(obj, cambios: dict, campos: tuple[str, ...]) -> dict:
    detalle = {}
    for campo in campos:
        if campo in cambios and getattr(obj, campo) != cambios[campo]:
            antes, despues = getattr(obj, campo), cambios[campo]
            detalle[campo] = {"antes": _txt(antes), "despues": _txt(despues)}
            setattr(obj, campo, despues)
    return detalle


def _txt(v):
    return str(v) if isinstance(v, Decimal | uuid.UUID) else v


# ---------------------------------------------------------------- plantilla


def cargar_plantilla(db: Session, actor: Usuario, empresa: Empresa, commit: bool = True) -> int:
    """Carga plan de cuentas, perfiles e impuestos del país. Devuelve el n.° de cuentas."""
    p = pais(empresa.pais)
    plan = p.plan_contable if p else None
    if not plan:
        return 0
    if db.scalar(select(Cuenta.id).where(Cuenta.empresa_id == empresa.id).limit(1)):
        raise ErrorERP(
            409,
            "plan_existente",
            "La empresa ya tiene plan de cuentas; edítalo en lugar de recargarlo",
        )
    codigos = [c for c, _ in plan.CUENTAS]
    cuentas: dict[str, Cuenta] = {}
    for codigo, nombre in sorted(plan.CUENTAS, key=lambda c: (len(c[0]), c[0])):
        padre = _padre_por_prefijo(codigo, cuentas)
        cuenta = Cuenta(
            id=uuid.uuid4(),
            empresa_id=empresa.id,
            codigo=codigo,
            nombre=nombre,
            padre_id=padre.id if padre else None,
            nivel=padre.nivel + 1 if padre else 1,
            naturaleza=plan.NATURALEZA_POR_ELEMENTO[codigo[0]],
            imputable=not any(o != codigo and o.startswith(codigo) for o in codigos),
            plantilla=plan.PLANTILLA,
            creado_por=actor.id if actor else None,
            actualizado_por=actor.id if actor else None,
        )
        cuentas[codigo] = cuenta
        db.add(cuenta)
    db.flush()
    for codigo, nombre, tipo, cargo, existencia, variacion, por_pagar in plan.PERFILES:
        db.add(
            Perfil(
                empresa_id=empresa.id,
                codigo=codigo,
                nombre=nombre,
                tipo_articulo=tipo,
                cuenta_cargo_id=cuentas[cargo].id,
                cuenta_existencia_id=cuentas[existencia].id if existencia else None,
                cuenta_variacion_id=cuentas[variacion].id if variacion else None,
                cuenta_por_pagar_id=cuentas[por_pagar].id,
                creado_por=actor.id if actor else None,
            )
        )
    for codigo, nombre, tasa, cuenta in plan.IMPUESTOS:
        db.add(
            Impuesto(
                empresa_id=empresa.id,
                codigo=codigo,
                nombre=nombre,
                tasa=tasa,
                cuenta_id=cuentas[cuenta].id if cuenta else None,
                creado_por=actor.id if actor else None,
            )
        )
    db.flush()
    auditar(
        db,
        actor,
        "cargar_plantilla",
        "plan_cuentas",
        empresa.id,
        {
            "empresa": empresa.razon_social,
            "plantilla": plan.PLANTILLA,
            "cuentas": len(plan.CUENTAS),
            "perfiles": len(plan.PERFILES),
            "impuestos": len(plan.IMPUESTOS),
        },
    )
    if commit:
        db.commit()
    return len(plan.CUENTAS)


@suscribir("empresa_creada")
def _al_crear_empresa(db: Session, actor: Usuario, empresa: Empresa) -> None:
    cargar_plantilla(db, actor, empresa, commit=False)
    aplicar_sugeridos(db, actor, empresa, commit=False)


def _padre_por_prefijo(codigo: str, cuentas: dict[str, Cuenta]) -> Cuenta | None:
    """La cuenta existente de código más largo que sea prefijo de este código."""
    for largo in range(len(codigo) - 1, 0, -1):
        if codigo[:largo] in cuentas:
            return cuentas[codigo[:largo]]
    return None


# ---------------------------------------------------------------- plan de cuentas


def listar_cuentas(db: Session, empresa_id: uuid.UUID) -> list[Cuenta]:
    maestros.obtener_empresa(db, empresa_id)
    return list(
        db.scalars(select(Cuenta).where(Cuenta.empresa_id == empresa_id).order_by(Cuenta.codigo))
    )


def obtener_cuenta(db: Session, cuenta_id: uuid.UUID) -> Cuenta:
    cuenta = db.get(Cuenta, cuenta_id)
    if not cuenta:
        raise no_encontrado("La cuenta")
    return cuenta


def usos_de_cuenta(db: Session, cuenta: Cuenta) -> list[str]:
    """Perfiles e impuestos que usan la cuenta (para no romperlos)."""
    perfiles = db.scalars(
        select(Perfil.codigo).where(
            or_(
                Perfil.cuenta_cargo_id == cuenta.id,
                Perfil.cuenta_existencia_id == cuenta.id,
                Perfil.cuenta_variacion_id == cuenta.id,
                Perfil.cuenta_por_pagar_id == cuenta.id,
            )
        )
    )
    impuestos = db.scalars(select(Impuesto.codigo).where(Impuesto.cuenta_id == cuenta.id))
    return [f"perfil {c}" for c in perfiles] + [f"impuesto {c}" for c in impuestos]


def crear_cuenta(
    db: Session,
    actor: Usuario,
    empresa_id: uuid.UUID,
    codigo: str,
    nombre: str,
    naturaleza: str | None,
) -> Cuenta:
    empresa = maestros.obtener_empresa(db, empresa_id)
    codigo = codigo.strip()
    if not CODIGO_CUENTA.match(codigo):
        raise ErrorERP(422, "codigo_invalido", "El código de cuenta solo tiene dígitos (hasta 20)")
    existentes = {c.codigo: c for c in listar_cuentas(db, empresa.id)}
    if codigo in existentes:
        raise ErrorERP(409, "cuenta_duplicada", f"La cuenta {codigo} ya existe")
    if any(c.startswith(codigo) for c in existentes):
        raise ErrorERP(
            422,
            "cuenta_intermedia",
            f"Ya hay cuentas que empiezan con {codigo}; agrega la cuenta nueva como subcuenta",
        )
    padre = _padre_por_prefijo(codigo, existentes)
    if padre:
        naturaleza = padre.naturaleza
        if padre.imputable:
            usos = usos_de_cuenta(db, padre)
            if usos:
                raise ErrorERP(
                    409,
                    "cuenta_en_uso",
                    f"La cuenta {padre.codigo} la usa {', '.join(usos)}. Crea la subcuenta después "
                    "de reasignar esos perfiles o impuestos a otra cuenta.",
                )
            padre.imputable = False
    else:
        p = pais(empresa.pais)
        naturaleza = naturaleza or (
            p.plan_contable.NATURALEZA_POR_ELEMENTO.get(codigo[0])
            if p and p.plan_contable
            else None
        )
        if naturaleza not in NATURALEZAS:
            raise ErrorERP(
                422, "naturaleza_invalida", f"Indica la naturaleza: {', '.join(NATURALEZAS)}"
            )
    cuenta = Cuenta(
        empresa_id=empresa.id,
        codigo=codigo,
        nombre=nombre.strip(),
        padre_id=padre.id if padre else None,
        nivel=padre.nivel + 1 if padre else 1,
        naturaleza=naturaleza,
        imputable=True,
        plantilla="propia",
        creado_por=actor.id,
        actualizado_por=actor.id,
    )
    db.add(cuenta)
    db.flush()
    auditar(
        db,
        actor,
        "crear",
        "cuenta",
        cuenta.id,
        {"empresa": empresa.razon_social, "codigo": codigo, "nombre": cuenta.nombre},
    )
    db.commit()
    return cuenta


def cambiar_cuenta(db: Session, actor: Usuario, cuenta_id: uuid.UUID, cambios: dict) -> Cuenta:
    cuenta = obtener_cuenta(db, cuenta_id)
    if cambios.get("activo") is False and cuenta.activo:
        usos = usos_de_cuenta(db, cuenta)
        if usos:
            raise ErrorERP(409, "cuenta_en_uso", f"No se desactiva: la usa {', '.join(usos)}")
        hijas = db.scalar(
            select(Cuenta.codigo)
            .where(Cuenta.padre_id == cuenta.id, Cuenta.activo.is_(True))
            .limit(1)
        )
        if hijas:
            raise ErrorERP(
                409, "tiene_subcuentas_activas", "Desactiva primero sus subcuentas activas"
            )
    if cambios.get("nombre"):
        cambios["nombre"] = cambios["nombre"].strip()
    detalle = _cambios(cuenta, cambios, ("nombre", "activo"))
    if detalle:
        cuenta.actualizado_por = actor.id
        auditar(db, actor, "editar", "cuenta", cuenta.id, {"codigo": cuenta.codigo, **detalle})
        db.commit()
    return cuenta


# ---------------------------------------------------------------- perfiles contables


def listar_perfiles(db: Session, empresa_id: uuid.UUID) -> list[Perfil]:
    maestros.obtener_empresa(db, empresa_id)
    return list(
        db.scalars(select(Perfil).where(Perfil.empresa_id == empresa_id).order_by(Perfil.codigo))
    )


def obtener_perfil(db: Session, perfil_id: uuid.UUID) -> Perfil:
    perfil = db.get(Perfil, perfil_id)
    if not perfil:
        raise no_encontrado("El perfil contable")
    return perfil


def _validar_cuentas_perfil(
    db: Session, empresa_id: uuid.UUID, tipo: str, ids: dict[str, uuid.UUID | None]
) -> None:
    if tipo not in REGLAS_PERFIL:
        raise ErrorERP(
            422, "tipo_invalido", f"Tipo de artículo no válido: {', '.join(TIPOS_ARTICULO)}"
        )
    for rol, naturalezas in REGLAS_PERFIL[tipo].items():
        cuenta_id = ids.get(rol)
        nombre = NOMBRE_CUENTA_PERFIL[rol]
        if naturalezas is None:
            if cuenta_id:
                raise ErrorERP(
                    422,
                    "cuenta_no_aplica",
                    f"Un perfil de {TIPOS_ARTICULO[tipo].lower()} no lleva {nombre}",
                )
            continue
        if not cuenta_id:
            raise ErrorERP(422, "cuenta_requerida", f"Falta la {nombre}")
        cuenta = db.get(Cuenta, cuenta_id)
        if not cuenta or cuenta.empresa_id != empresa_id:
            raise ErrorERP(422, "cuenta_invalida", f"La {nombre} no pertenece a esta empresa")
        if not cuenta.imputable or not cuenta.activo:
            raise ErrorERP(
                422,
                "cuenta_no_imputable",
                f"La {nombre} ({cuenta.codigo}) debe ser una cuenta activa del último nivel",
            )
        if cuenta.naturaleza not in naturalezas:
            raise ErrorERP(
                422,
                "naturaleza_incorrecta",
                f"La {nombre} debe ser de {' o '.join(sorted(naturalezas))}; "
                f"{cuenta.codigo} es de {cuenta.naturaleza}",
            )


def _ids_perfil(datos: dict) -> dict[str, uuid.UUID | None]:
    return {
        "cargo": datos.get("cuenta_cargo_id"),
        "existencia": datos.get("cuenta_existencia_id"),
        "variacion": datos.get("cuenta_variacion_id"),
        "por_pagar": datos.get("cuenta_por_pagar_id"),
    }


def crear_perfil(db: Session, actor: Usuario, empresa_id: uuid.UUID, datos: dict) -> Perfil:
    empresa = maestros.obtener_empresa(db, empresa_id)
    codigo = datos["codigo"].strip().upper()
    if not CODIGO_PERFIL.match(codigo):
        raise ErrorERP(422, "codigo_invalido", "El código usa mayúsculas, números y guion bajo")
    if db.scalar(select(Perfil.id).where(Perfil.empresa_id == empresa.id, Perfil.codigo == codigo)):
        raise ErrorERP(409, "perfil_duplicado", f"Ya existe el perfil {codigo}")
    _validar_cuentas_perfil(db, empresa.id, datos["tipo_articulo"], _ids_perfil(datos))
    perfil = Perfil(
        empresa_id=empresa.id,
        codigo=codigo,
        nombre=datos["nombre"].strip(),
        tipo_articulo=datos["tipo_articulo"],
        cuenta_cargo_id=datos["cuenta_cargo_id"],
        cuenta_existencia_id=datos.get("cuenta_existencia_id"),
        cuenta_variacion_id=datos.get("cuenta_variacion_id"),
        cuenta_por_pagar_id=datos["cuenta_por_pagar_id"],
        creado_por=actor.id,
        actualizado_por=actor.id,
    )
    db.add(perfil)
    db.flush()
    auditar(
        db,
        actor,
        "crear",
        "perfil_contable",
        perfil.id,
        {"empresa": empresa.razon_social, "codigo": codigo, "tipo": perfil.tipo_articulo},
    )
    db.commit()
    db.refresh(perfil)
    return perfil


def cambiar_perfil(db: Session, actor: Usuario, perfil_id: uuid.UUID, cambios: dict) -> Perfil:
    """El código y el tipo no cambian; las cuentas sí (afectan solo a compras nuevas)."""
    perfil = obtener_perfil(db, perfil_id)
    campos_cuenta = (
        "cuenta_cargo_id",
        "cuenta_existencia_id",
        "cuenta_variacion_id",
        "cuenta_por_pagar_id",
    )
    if any(c in cambios for c in campos_cuenta):
        final = {c: cambios.get(c, getattr(perfil, c)) for c in campos_cuenta}
        _validar_cuentas_perfil(db, perfil.empresa_id, perfil.tipo_articulo, _ids_perfil(final))
    if cambios.get("nombre"):
        cambios["nombre"] = cambios["nombre"].strip()
    detalle = _cambios(perfil, cambios, ("nombre", "activo", *campos_cuenta))
    if detalle:
        perfil.actualizado_por = actor.id
        auditar(
            db, actor, "editar", "perfil_contable", perfil.id, {"codigo": perfil.codigo, **detalle}
        )
        db.commit()
        db.refresh(perfil)
    return perfil


# ---------------------------------------------------------------- centros de costo


def listar_centros(db: Session, empresa_id: uuid.UUID) -> list[CentroCosto]:
    maestros.obtener_empresa(db, empresa_id)
    return list(
        db.scalars(
            select(CentroCosto)
            .where(CentroCosto.empresa_id == empresa_id)
            .order_by(CentroCosto.codigo)
        )
    )


def _validar_unidad(db: Session, empresa_id: uuid.UUID, unidad_id: uuid.UUID) -> None:
    un = maestros.obtener_unidad_negocio(db, unidad_id)
    if un.empresa_id != empresa_id:
        raise ErrorERP(422, "unidad_otra_empresa", "La unidad de negocio es de otra empresa")
    if not un.activo:
        raise ErrorERP(422, "unidad_inactiva", f"La unidad de negocio {un.codigo} está inactiva")


def crear_centro(db: Session, actor: Usuario, empresa_id: uuid.UUID, datos: dict) -> CentroCosto:
    empresa = maestros.obtener_empresa(db, empresa_id)
    codigo = datos["codigo"].strip().upper()
    if not CODIGO_CC.match(codigo):
        raise ErrorERP(
            422,
            "codigo_invalido",
            "El código usa mayúsculas, números, guion o guion bajo (hasta 20)",
        )
    if db.scalar(
        select(CentroCosto.id).where(
            CentroCosto.empresa_id == empresa.id, CentroCosto.codigo == codigo
        )
    ):
        raise ErrorERP(409, "centro_duplicado", f"Ya existe el centro de costo {codigo}")
    _validar_unidad(db, empresa.id, datos["unidad_negocio_id"])
    cc = CentroCosto(
        empresa_id=empresa.id,
        unidad_negocio_id=datos["unidad_negocio_id"],
        codigo=codigo,
        nombre=datos["nombre"].strip(),
        responsable=(datos.get("responsable") or "").strip() or None,
        creado_por=actor.id,
        actualizado_por=actor.id,
    )
    db.add(cc)
    db.flush()
    auditar(
        db,
        actor,
        "crear",
        "centro_costo",
        cc.id,
        {"empresa": empresa.razon_social, "codigo": codigo, "nombre": cc.nombre},
    )
    db.commit()
    return cc


def cambiar_centro(db: Session, actor: Usuario, centro_id: uuid.UUID, cambios: dict) -> CentroCosto:
    cc = db.get(CentroCosto, centro_id)
    if not cc:
        raise no_encontrado("El centro de costo")
    if "unidad_negocio_id" in cambios:
        _validar_unidad(db, cc.empresa_id, cambios["unidad_negocio_id"])
    for campo in ("nombre", "responsable"):
        if isinstance(cambios.get(campo), str):
            cambios[campo] = cambios[campo].strip() or None
    detalle = _cambios(cc, cambios, ("nombre", "responsable", "unidad_negocio_id", "activo"))
    if detalle:
        cc.actualizado_por = actor.id
        auditar(db, actor, "editar", "centro_costo", cc.id, {"codigo": cc.codigo, **detalle})
        db.commit()
    return cc


# ---------------------------------------------------------------- impuestos


def listar_impuestos(db: Session, empresa_id: uuid.UUID) -> list[Impuesto]:
    maestros.obtener_empresa(db, empresa_id)
    return list(
        db.scalars(
            select(Impuesto).where(Impuesto.empresa_id == empresa_id).order_by(Impuesto.codigo)
        )
    )


def _validar_impuesto(db: Session, empresa_id: uuid.UUID, tasa: Decimal, cuenta_id) -> None:
    if tasa < 0 or tasa > 100:
        raise ErrorERP(422, "tasa_invalida", "La tasa es un porcentaje entre 0 y 100")
    if tasa > 0 and not cuenta_id:
        raise ErrorERP(
            422, "cuenta_requerida", "Un impuesto con tasa mayor a cero necesita su cuenta"
        )
    if cuenta_id:
        cuenta = db.get(Cuenta, cuenta_id)
        if not cuenta or cuenta.empresa_id != empresa_id:
            raise ErrorERP(422, "cuenta_invalida", "La cuenta no pertenece a esta empresa")
        if not cuenta.imputable or not cuenta.activo:
            raise ErrorERP(
                422, "cuenta_no_imputable", "La cuenta debe ser activa y del último nivel"
            )
        if cuenta.naturaleza not in ("pasivo", "activo"):
            raise ErrorERP(
                422, "naturaleza_incorrecta", "La cuenta de un impuesto es de pasivo o de activo"
            )


def crear_impuesto(db: Session, actor: Usuario, empresa_id: uuid.UUID, datos: dict) -> Impuesto:
    empresa = maestros.obtener_empresa(db, empresa_id)
    codigo = datos["codigo"].strip().upper()
    if not CODIGO_IMPUESTO.match(codigo):
        raise ErrorERP(422, "codigo_invalido", "El código usa mayúsculas, números y guion bajo")
    if db.scalar(
        select(Impuesto.id).where(Impuesto.empresa_id == empresa.id, Impuesto.codigo == codigo)
    ):
        raise ErrorERP(409, "impuesto_duplicado", f"Ya existe el impuesto {codigo}")
    _validar_impuesto(db, empresa.id, datos["tasa"], datos.get("cuenta_id"))
    imp = Impuesto(
        empresa_id=empresa.id,
        codigo=codigo,
        nombre=datos["nombre"].strip(),
        tasa=datos["tasa"],
        cuenta_id=datos.get("cuenta_id"),
        creado_por=actor.id,
        actualizado_por=actor.id,
    )
    db.add(imp)
    db.flush()
    auditar(
        db,
        actor,
        "crear",
        "impuesto",
        imp.id,
        {"empresa": empresa.razon_social, "codigo": codigo, "tasa": str(imp.tasa)},
    )
    db.commit()
    db.refresh(imp)
    return imp


def cambiar_impuesto(
    db: Session, actor: Usuario, impuesto_id: uuid.UUID, cambios: dict
) -> Impuesto:
    imp = db.get(Impuesto, impuesto_id)
    if not imp:
        raise no_encontrado("El impuesto")
    tasa = cambios.get("tasa", imp.tasa)
    cuenta_id = cambios["cuenta_id"] if "cuenta_id" in cambios else imp.cuenta_id
    _validar_impuesto(db, imp.empresa_id, tasa, cuenta_id)
    if cambios.get("nombre"):
        cambios["nombre"] = cambios["nombre"].strip()
    detalle = _cambios(imp, cambios, ("nombre", "tasa", "cuenta_id", "activo"))
    if detalle:
        imp.actualizado_por = actor.id
        auditar(db, actor, "editar", "impuesto", imp.id, {"codigo": imp.codigo, **detalle})
        db.commit()
        db.refresh(imp)
    return imp


# ---------------------------------------------------------------- categorías de artículo


def aplicar_sugeridos(db: Session, actor: Usuario, empresa: Empresa, commit: bool = True) -> dict:
    """Completa la configuración con lo sugerido por la plantilla del país, sin pisar nada:

    - crea los perfiles de la plantilla que la empresa aún no tiene (si existen sus cuentas);
    - asigna el perfil sugerido a las categorías de ejemplo que no tengan perfil en la empresa.
    """
    p = pais(empresa.pais)
    plan = p.plan_contable if p else None
    if not plan:
        return {"perfiles": 0, "categorias": 0}
    cuentas = {
        c.codigo: c
        for c in db.scalars(select(Cuenta).where(Cuenta.empresa_id == empresa.id))
        if c.imputable and c.activo
    }
    perfiles = {
        x.codigo: x for x in db.scalars(select(Perfil).where(Perfil.empresa_id == empresa.id))
    }
    nuevos_perfiles = 0
    for codigo, nombre, tipo, cargo, existencia, variacion, por_pagar in plan.PERFILES:
        necesarias = [c for c in (cargo, existencia, variacion, por_pagar) if c]
        if codigo in perfiles or any(c not in cuentas for c in necesarias):
            continue
        perfil = Perfil(
            empresa_id=empresa.id,
            codigo=codigo,
            nombre=nombre,
            tipo_articulo=tipo,
            cuenta_cargo_id=cuentas[cargo].id,
            cuenta_existencia_id=cuentas[existencia].id if existencia else None,
            cuenta_variacion_id=cuentas[variacion].id if variacion else None,
            cuenta_por_pagar_id=cuentas[por_pagar].id,
            creado_por=actor.id if actor else None,
        )
        db.add(perfil)
        perfiles[codigo] = perfil
        nuevos_perfiles += 1
    db.flush()
    asignadas = set(
        db.scalars(
            select(CategoriaPerfil.categoria_id).where(CategoriaPerfil.empresa_id == empresa.id)
        )
    )
    categorias = {
        c.codigo: c
        for c in db.scalars(select(Categoria).where(Categoria.codigo.in_(plan.CATEGORIAS_PERFIL)))
    }
    nuevas = 0
    for cat_codigo, perfil_codigo in plan.CATEGORIAS_PERFIL.items():
        cat, perfil = categorias.get(cat_codigo), perfiles.get(perfil_codigo)
        if cat and perfil and perfil.activo and cat.id not in asignadas:
            db.add(
                CategoriaPerfil(
                    empresa_id=empresa.id,
                    categoria_id=cat.id,
                    perfil_id=perfil.id,
                    creado_por=actor.id if actor else None,
                )
            )
            nuevas += 1
    db.flush()
    resultado = {"perfiles": nuevos_perfiles, "categorias": nuevas}
    if nuevos_perfiles or nuevas:
        auditar(
            db,
            actor,
            "aplicar_sugeridos",
            "categoria_perfil",
            empresa.id,
            {"empresa": empresa.razon_social, **resultado},
        )
    if commit:
        db.commit()
    return resultado


def _asignaciones(db: Session, empresa_id: uuid.UUID) -> dict[uuid.UUID, CategoriaPerfil]:
    return {
        a.categoria_id: a
        for a in db.scalars(select(CategoriaPerfil).where(CategoriaPerfil.empresa_id == empresa_id))
    }


def perfil_de_categoria(
    db: Session, empresa_id: uuid.UUID, categoria_id: uuid.UUID
) -> tuple[Perfil | None, Categoria | None]:
    """Perfil efectivo de una categoría en una empresa y la categoría de la que viene.

    Recorre la categoría y sus padres; devuelve (None, None) si ninguno tiene perfil.
    Lo usarán los artículos y las compras.
    """
    asignaciones = _asignaciones(db, empresa_id)
    for cat in maestros.ancestros_categoria(db, maestros.obtener_categoria(db, categoria_id)):
        if cat.id in asignaciones:
            return asignaciones[cat.id].perfil, cat
    return None, None


def categorias_con_perfil(db: Session, empresa_id: uuid.UUID) -> list[dict]:
    """Árbol de categorías con el perfil propio y el efectivo (heredado) en la empresa."""
    maestros.obtener_empresa(db, empresa_id)
    asignaciones = _asignaciones(db, empresa_id)
    categorias = maestros.listar_categorias(db)
    por_id = {c.id: c for c in categorias}
    resultado = []
    for cat in categorias:
        propio = asignaciones.get(cat.id)
        efectivo, origen, actual = None, None, cat
        while actual:
            if actual.id in asignaciones:
                efectivo, origen = asignaciones[actual.id].perfil, actual
                break
            actual = por_id.get(actual.padre_id) if actual.padre_id else None
        resultado.append(
            {
                "categoria_id": cat.id,
                "perfil_propio": propio.perfil if propio else None,
                "perfil_efectivo": efectivo,
                "heredado_de": origen if origen and origen.id != cat.id else None,
            }
        )
    return resultado


def asignar_perfil_categoria(
    db: Session,
    actor: Usuario,
    empresa_id: uuid.UUID,
    categoria_id: uuid.UUID,
    perfil_id: uuid.UUID | None,
) -> None:
    """Asigna (o quita, con None) el perfil propio. Sin perfil propio, la categoría hereda."""
    empresa = maestros.obtener_empresa(db, empresa_id)
    cat = maestros.obtener_categoria(db, categoria_id)
    actual = db.scalar(
        select(CategoriaPerfil).where(
            CategoriaPerfil.empresa_id == empresa.id, CategoriaPerfil.categoria_id == cat.id
        )
    )
    antes = actual.perfil.codigo if actual else None
    if perfil_id is None:
        if not actual:
            return
        db.delete(actual)
        despues = None
    else:
        perfil = obtener_perfil(db, perfil_id)
        if perfil.empresa_id != empresa.id:
            raise ErrorERP(422, "perfil_otra_empresa", "El perfil contable es de otra empresa")
        if not perfil.activo:
            raise ErrorERP(422, "perfil_inactivo", f"El perfil {perfil.codigo} está inactivo")
        if actual and actual.perfil_id == perfil.id:
            return
        if actual:
            actual.perfil_id, actual.actualizado_por = perfil.id, actor.id
        else:
            db.add(
                CategoriaPerfil(
                    empresa_id=empresa.id,
                    categoria_id=cat.id,
                    perfil_id=perfil.id,
                    creado_por=actor.id,
                    actualizado_por=actor.id,
                )
            )
        despues = perfil.codigo
    db.flush()
    db.expire_all()  # que la verificación lea el perfil nuevo, no el que estaba en memoria
    _verificar_articulos_de_rama(db, empresa, cat)
    auditar(
        db,
        actor,
        "asignar_perfil",
        "categoria_perfil",
        cat.id,
        {
            "empresa": empresa.razon_social,
            "categoria": cat.codigo,
            "perfil": {"antes": antes, "despues": despues or "heredado"},
        },
    )
    db.commit()


# ---------------------------------------------------------------- artículos


def _excepciones(db: Session, articulo_id: uuid.UUID) -> dict[uuid.UUID, ArticuloPerfil]:
    return {
        e.empresa_id: e
        for e in db.scalars(select(ArticuloPerfil).where(ArticuloPerfil.articulo_id == articulo_id))
    }


def perfil_de_articulo(
    db: Session, empresa_id: uuid.UUID, articulo: Articulo
) -> tuple[Perfil | None, str | None]:
    """Perfil efectivo del artículo en la empresa y de dónde viene.

    Primero la excepción del artículo; si no hay, el de su categoría (con herencia).
    Lo usarán las solicitudes y órdenes de compra para guardar la cuenta de cada línea.
    """
    excepcion = db.scalar(
        select(ArticuloPerfil).where(
            ArticuloPerfil.empresa_id == empresa_id, ArticuloPerfil.articulo_id == articulo.id
        )
    )
    if excepcion:
        return excepcion.perfil, "Excepción del artículo"
    perfil, origen = perfil_de_categoria(db, empresa_id, articulo.categoria_id)
    return perfil, (f"Categoría {origen.codigo}" if origen else None)


def _empresas_activas(db: Session) -> list[Empresa]:
    return maestros.listar_empresas(db, solo_activas=True)


def _desajustes(db: Session, articulo: Articulo) -> list[str]:
    """Empresas donde el perfil efectivo es de otro tipo que el artículo."""
    problemas = []
    for empresa in _empresas_activas(db):
        perfil, origen = perfil_de_articulo(db, empresa.id, articulo)
        if perfil and perfil.tipo_articulo != articulo.tipo:
            problemas.append(
                f"{empresa.razon_social}: {origen} usa el perfil {perfil.nombre} "
                f"({TIPOS_ARTICULO[perfil.tipo_articulo].lower()})"
            )
    return problemas


@suscribir("validar_articulo")
def _validar_articulo(db: Session, articulo: Articulo) -> None:
    """Al guardar un artículo: el tipo debe coincidir con el perfil de cada empresa que lo tenga."""
    problemas = _desajustes(db, articulo)
    if problemas:
        raise ErrorERP(
            422,
            "tipo_no_coincide",
            f"El artículo es {TIPOS_ARTICULO[articulo.tipo].lower()}, pero en "
            + "; ".join(problemas)
            + ". Elige otra categoría o pide al contador un perfil del mismo tipo.",
        )
    empresas = _empresas_activas(db)
    if empresas and not db.scalar(
        select(Impuesto.id).where(Impuesto.codigo == articulo.impuesto).limit(1)
    ):
        raise ErrorERP(
            422, "impuesto_inexistente", f"Ninguna empresa tiene el impuesto {articulo.impuesto}"
        )


def _verificar_articulos_de_rama(db: Session, empresa: Empresa, categoria: Categoria) -> None:
    """Al cambiar el perfil de una categoría, sus artículos deben seguir siendo del mismo tipo."""
    rama = [c.id for c in maestros.subcategorias(db, categoria.id)]
    distintos = []
    for art in maestros.articulos_de_categorias(db, rama):
        perfil, _ = perfil_de_articulo(db, empresa.id, art)
        if perfil and perfil.tipo_articulo != art.tipo:
            distintos.append(art.codigo)
    if distintos:
        db.rollback()
        muestra = ", ".join(distintos[:5]) + ("…" if len(distintos) > 5 else "")
        raise ErrorERP(
            409,
            "articulos_de_otro_tipo",
            f"{len(distintos)} artículo(s) de esta rama son de otro tipo que el perfil "
            f"({muestra}). "
            "Cámbialos de categoría o define una excepción para ellos.",
        )


def estado_contable(db: Session, articulo: Articulo) -> list[dict]:
    """Para cada empresa activa: perfil efectivo, origen, impuesto y si se puede comprar."""
    excepciones = _excepciones(db, articulo.id)
    filas = []
    for empresa in _empresas_activas(db):
        perfil, origen = perfil_de_articulo(db, empresa.id, articulo)
        impuesto = db.scalar(
            select(Impuesto).where(
                Impuesto.empresa_id == empresa.id, Impuesto.codigo == articulo.impuesto
            )
        )
        problema = None
        if not perfil:
            problema = "Sin perfil contable: la categoría no tiene perfil en esta empresa"
        elif not perfil.activo:
            problema = f"El perfil {perfil.nombre} está inactivo"
        elif perfil.tipo_articulo != articulo.tipo:
            problema = "El perfil es de otro tipo de artículo"
        elif not impuesto or not impuesto.activo:
            problema = f"La empresa no tiene activo el impuesto {articulo.impuesto}"
        filas.append(
            {
                "empresa_id": empresa.id,
                "razon_social": empresa.razon_social,
                "perfil": perfil,
                "origen": origen,
                "excepcion": empresa.id in excepciones,
                "impuesto": impuesto,
                "problema": problema,
            }
        )
    return filas


def asignar_perfil_articulo(
    db: Session,
    actor: Usuario,
    empresa_id: uuid.UUID,
    articulo_id: uuid.UUID,
    perfil_id: uuid.UUID | None,
) -> None:
    """Define (o quita, con None) la excepción contable del artículo en la empresa."""
    empresa = maestros.obtener_empresa(db, empresa_id)
    art = maestros.obtener_articulo(db, articulo_id)
    actual = _excepciones(db, art.id).get(empresa.id)
    antes = actual.perfil.codigo if actual else None
    if perfil_id is None:
        if not actual:
            return
        db.delete(actual)
        db.flush()
        problemas = _desajustes(db, art)
        if problemas:
            db.rollback()
            raise ErrorERP(
                409,
                "tipo_no_coincide",
                "Sin la excepción, el artículo tomaría un perfil de otro tipo: "
                + "; ".join(problemas),
            )
        despues = "categoría"
    else:
        perfil = obtener_perfil(db, perfil_id)
        if perfil.empresa_id != empresa.id:
            raise ErrorERP(422, "perfil_otra_empresa", "El perfil contable es de otra empresa")
        if not perfil.activo:
            raise ErrorERP(422, "perfil_inactivo", f"El perfil {perfil.codigo} está inactivo")
        if perfil.tipo_articulo != art.tipo:
            raise ErrorERP(
                422,
                "tipo_no_coincide",
                f"El perfil {perfil.nombre} es para {TIPOS_ARTICULO[perfil.tipo_articulo].lower()}"
                f" y el artículo es {TIPOS_ARTICULO[art.tipo].lower()}",
            )
        if actual and actual.perfil_id == perfil.id:
            return
        if actual:
            actual.perfil_id, actual.actualizado_por = perfil.id, actor.id
        else:
            db.add(
                ArticuloPerfil(
                    empresa_id=empresa.id,
                    articulo_id=art.id,
                    perfil_id=perfil.id,
                    creado_por=actor.id,
                    actualizado_por=actor.id,
                )
            )
        despues = perfil.codigo
    auditar(
        db,
        actor,
        "excepcion_contable",
        "articulo",
        art.id,
        {
            "empresa": empresa.razon_social,
            "articulo": art.codigo,
            "perfil": {"antes": antes or "categoría", "despues": despues},
        },
    )
    db.commit()


def codigos_impuesto(db: Session) -> list[str]:
    return sorted(set(db.scalars(select(Impuesto.codigo).where(Impuesto.activo.is_(True)))))
