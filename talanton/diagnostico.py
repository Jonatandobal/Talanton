"""Qué devuelve realmente cada portal.

Existe por un error que costó caro. Los tres conectores informaron «0 avisos»
cuando en realidad las URL devolvían 404: `traer_pagina()` no chequeaba el status,
la página venía vacía pero válida, ningún selector matcheaba, y en pantalla eso se
veía idéntico a «no hay empresas de ese rubro en esa zona». Un sistema que
confunde «no encontré» con «pregunté mal» le hace sacar al usuario la conclusión
equivocada sobre su propio mercado.

El chequeo de status ya está arreglado en `ingest/base.py`. Esto es la otra mitad:
poder ver, desde producción —que es el único lugar con salida a internet—, qué
URL se consultó, qué devolvió, y **cuántos nodos matcheó cada selector**. Con eso
un selector roto se arregla en una vuelta en vez de a ciegas.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

log = logging.getLogger("talanton.diagnostico")

# Cuántos caracteres del HTML mostrar. Suficiente para reconocer una página de
# error o un muro anti-bot, corto para que no sea ilegible.
_MUESTRA = 400


@dataclass
class Revision:
    portal: str
    url: str
    status: int | None = None
    bytes: int = 0
    # Selector -> cuántos nodos matcheó. El que da 0 es el que hay que arreglar.
    selectores: dict[str, int] = field(default_factory=dict)
    muestra: str | None = None
    error: str | None = None

    @property
    def veredicto(self) -> str:
        if self.error:
            return "No respondió"
        if self.status and self.status != 200:
            return f"Devolvió {self.status}: la URL está mal armada"
        if not self.bytes:
            return "Respondió vacío"
        if self.selectores and not any(self.selectores.values()):
            return "La página llegó bien pero ningún selector matchea: cambió el HTML"
        if self.selectores.get(_principal(self.selectores)) == 0:
            return "El selector de aviso no matchea"
        return "Anda"


def _principal(selectores: dict[str, int]) -> str:
    return next(iter(selectores), "")


def revisar_portales(segmento) -> list[Revision]:
    """Consulta cada portal y reporta qué pasó, sin interpretar nada."""
    from .ingest.portales.base import _portales

    revisiones = []
    for portal in _portales():
        revisiones.append(_revisar(portal, segmento))
    return revisiones


def _revisar(portal, segmento) -> Revision:
    from .ingest.base import traer_pagina

    url = portal.url(segmento) if hasattr(portal, "url") else "(sin url)"
    revision = Revision(portal=portal.nombre, url=url)

    stealth = getattr(portal, "necesita_navegador", False)
    try:
        pagina = traer_pagina(url, timeout=30, stealth=stealth)
    except Exception as exc:  # noqa: BLE001 - el error es el dato que buscamos
        revision.error = str(exc)
        return revision

    revision.status = getattr(pagina, "status", None)
    html = _html_de(pagina)
    revision.bytes = len(html)
    revision.muestra = html[:_MUESTRA] or None

    for nombre, selector in _selectores_de(portal):
        try:
            revision.selectores[f"{nombre}: {selector}"] = len(list(pagina.css(selector)))
        except Exception as exc:  # noqa: BLE001
            log.warning("Selector %s falló en %s: %s", selector, portal.nombre, exc)
            revision.selectores[f"{nombre}: {selector}"] = 0
    return revision


def _html_de(pagina) -> str:
    for atributo in ("html_content", "body", "text"):
        valor = getattr(pagina, atributo, None)
        if valor:
            return str(valor)
    return str(pagina)


def _selectores_de(portal) -> list[tuple[str, str]]:
    """Los selectores del módulo del portal, en orden de importancia."""
    import sys

    modulo = sys.modules.get(type(portal).__module__)
    if modulo is None:
        return []
    nombres = ("SEL_AVISO", "SEL_TITULO", "SEL_EMPRESA", "SEL_UBICACION", "SEL_ANTIGUEDAD")
    return [
        (nombre.removeprefix("SEL_").lower(), getattr(modulo, nombre))
        for nombre in nombres
        if getattr(modulo, nombre, None)
    ]
