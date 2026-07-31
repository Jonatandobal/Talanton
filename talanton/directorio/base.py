"""Contrato de las fuentes de empresas y orquestación de la búsqueda."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol

log = logging.getLogger("talanton.directorio")


@dataclass
class EmpresaCruda:
    """Una empresa tal como la devuelve una fuente, antes de normalizar.

    Es el equivalente de `VacanteCruda` para el otro carril. Nótese lo que **no**
    trae: nada de personas. Los contactos se consiguen después, por los caminos
    que ya están documentados (la web de la empresa, Hunter, o a mano), y cada
    uno guarda su `fuente_url` para poder auditarlo y borrarlo si lo piden.
    """

    nombre: str
    fuente: str
    dominio: str | None = None
    industria: str | None = None
    dotacion: int | None = None
    ciudad: str | None = None
    pais: str | None = "AR"
    fuente_url: str | None = None
    descripcion: str | None = None


class Fuente(Protocol):
    nombre: str

    def disponible(self) -> bool: ...

    def buscar(self, segmento) -> list[EmpresaCruda]: ...


@dataclass
class Resultado:
    empresas: list[EmpresaCruda] = field(default_factory=list)
    por_fuente: dict[str, int] = field(default_factory=dict)
    fallidas: list[str] = field(default_factory=list)
    # Fuentes que existen pero no están configuradas —falta la clave—. Se
    # distinguen de las que fallaron: una se arregla poniendo un token, la otra
    # es un problema. Mezclarlas fue justamente lo que hizo que «0 empresas»
    # pareciera un dato sobre el mercado.
    sin_configurar: list[str] = field(default_factory=list)

    @property
    def hubo_fuentes(self) -> bool:
        return bool(self.por_fuente or self.fallidas)


def _fuentes() -> list[Fuente]:
    # Import perezoso: cada fuente arrastra su cliente HTTP y no hace falta
    # cargarlas para, por ejemplo, correr los tests del scoring.
    from .linkedin import EmpresasLinkedIn

    return [EmpresasLinkedIn()]


def fuentes_configuradas() -> list[str]:
    """Nombres de las fuentes listas para usar. Vacío = no hay de dónde buscar."""
    return [f.nombre for f in _fuentes() if f.disponible()]


def buscar_en_fuentes(segmento, fuentes: list[Fuente] | None = None) -> Resultado:
    """Consulta todas las fuentes. Una caída no frena a las demás."""
    resultado = Resultado()
    for fuente in fuentes if fuentes is not None else _fuentes():
        if not fuente.disponible():
            resultado.sin_configurar.append(fuente.nombre)
            continue
        try:
            empresas = fuente.buscar(segmento)
        except Exception as exc:  # red, cuota, credenciales: todo es "no vino"
            log.warning("Fuente %s falló: %s", fuente.nombre, exc)
            resultado.fallidas.append(f"{fuente.nombre}: {exc}")
            continue
        resultado.por_fuente[fuente.nombre] = len(empresas)
        resultado.empresas.extend(empresas)
    return resultado


def dentro_del_tramo(
    empresa: EmpresaCruda, minimo: int | None, maximo: int | None
) -> bool:
    """Filtra por dotación sin descartar a las que no la informan.

    Una empresa sin dotación conocida se deja pasar a propósito: descartarla
    sería perder un cliente posible por un dato que falta, y el tamaño se puede
    ver de un vistazo cuando se abre la ficha. El scoring ya no le regala puntos
    por eso.
    """
    if empresa.dotacion is None:
        return True
    if minimo and empresa.dotacion < minimo:
        return False
    if maximo and empresa.dotacion > maximo:
        return False
    return True
