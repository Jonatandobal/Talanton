"""Orquestación de la búsqueda de avisos en los portales.

Los portales son el carril de **señal**, no el de descubrimiento: dicen qué está
buscando una empresa y desde cuándo. Quién es cliente lo define
`talanton/directorio/`, que no depende de que haya un aviso publicado hoy.

El vocabulario de zonas y rubros vive en `talanton/segmento.py`, compartido con
el directorio; se reexporta acá porque los conectores lo importan de este módulo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Protocol

from ...segmento import RUBROS, ZONAS, Segmento
from ..base import VacanteCruda

log = logging.getLogger("talanton.portales")

__all__ = [
    "RUBROS",
    "ZONAS",
    "Segmento",
    "Portal",
    "Resultado",
    "buscar_en_portales",
    "aplicar_antiguedad",
    "texto_de",
    "atributo_de",
    "nodos",
    "PORTALES",
]


class Portal(Protocol):
    nombre: str

    def buscar(self, segmento: Segmento) -> list[VacanteCruda]: ...


@dataclass
class Resultado:
    crudas: list[VacanteCruda] = field(default_factory=list)
    por_portal: dict[str, int] = field(default_factory=dict)
    fallidos: list[str] = field(default_factory=list)


def _portales() -> list[Portal]:
    # Import perezoso: cada conector arrastra su propio parseo y no hace falta
    # cargarlos todos para, por ejemplo, correr los tests del scoring.
    from .bumeran import Bumeran, ZonaJobs
    from .computrabajo import Computrabajo

    return [Computrabajo(), Bumeran(), ZonaJobs()]


def buscar_en_portales(
    segmento: Segmento, portales: list[Portal] | None = None
) -> Resultado:
    """Consulta todos los portales. Uno caído no frena a los demás."""
    resultado = Resultado()
    for portal in portales if portales is not None else _portales():
        try:
            crudas = portal.buscar(segmento)
        except Exception as exc:  # red, HTML cambiado, anti-bot: todo es "no vino"
            log.warning("Portal %s falló: %s", portal.nombre, exc)
            resultado.fallidos.append(f"{portal.nombre}: {exc}")
            continue
        resultado.por_portal[portal.nombre] = len(crudas)
        resultado.crudas.extend(crudas)
    return resultado


def texto_de(nodo, selector: str) -> str | None:
    """Saca el texto de un selector, tolerando que no exista.

    Los portales cambian el HTML seguido: que falte un campo secundario no
    puede tirar abajo el aviso entero.
    """
    try:
        encontrado = nodo.css_first(selector)
    except Exception:
        return None
    if encontrado is None:
        return None
    texto = getattr(encontrado, "text", None) or str(encontrado)
    return " ".join(str(texto).split()) or None


def atributo_de(nodo, selector: str, atributo: str) -> str | None:
    try:
        encontrado = nodo.css_first(selector)
    except Exception:
        return None
    if encontrado is None:
        return None
    valor = encontrado.attrib.get(atributo) if hasattr(encontrado, "attrib") else None
    return str(valor).strip() if valor else None


def nodos(pagina, selector: str) -> list:
    try:
        return list(pagina.css(selector))
    except Exception:
        return []


def aplicar_antiguedad(
    crudas: list[VacanteCruda], dias_minimos: int
) -> list[VacanteCruda]:
    """Deja sólo los avisos con al menos `dias_minimos` publicados.

    Se filtra acá y no en el portal porque no todos permiten pedir «más viejo
    que N días» —casi todos ofrecen lo contrario, «de los últimos N»—.
    """
    if dias_minimos <= 0:
        return crudas
    from ...services import fecha_hoy

    hoy = fecha_hoy()
    quedan = []
    for cruda in crudas:
        if cruda.fecha_publicacion is None:
            # Sin fecha no se puede afirmar que sea vieja, y el producto se
            # apoya en poder decir el número. Mejor perderlo que inventarlo.
            continue
        if (hoy - cruda.fecha_publicacion).days >= dias_minimos:
            quedan.append(cruda)
    return quedan


PORTALES: Callable[[], list[Portal]] = _portales
