"""Eventos entre módulos sin acoplarlos (ADR-002).

Un módulo publica un evento ("empresa_creada") y otros se suscriben sin que el
publicador los conozca. Los suscriptores corren dentro de la misma transacción:
si uno falla, no se guarda nada.

    @suscribir("empresa_creada")
    def cargar_plantilla(db, actor, empresa): ...

    emitir("empresa_creada", db, actor, empresa)
"""

from collections import defaultdict
from collections.abc import Callable

_suscriptores: dict[str, list[Callable]] = defaultdict(list)


def suscribir(evento: str) -> Callable[[Callable], Callable]:
    def _registrar(funcion: Callable) -> Callable:
        if funcion not in _suscriptores[evento]:
            _suscriptores[evento].append(funcion)
        return funcion

    return _registrar


def emitir(evento: str, *args, **kwargs) -> None:
    for funcion in _suscriptores[evento]:
        funcion(*args, **kwargs)
