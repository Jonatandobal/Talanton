"""De dónde sale la lista de empresas a las que vender.

Esto es lo principal del producto y durante un tiempo estuvo al revés. La versión
anterior entraba por el aviso: buscaba búsquedas abiertas y las empresas salían de
ahí. Suena elegante y es un error, porque deja fuera a toda empresa vendible que
justo hoy no está publicando, y porque ata el listado comercial a que funcione el
scraping de tres portales. Cuando los portales fallaron, el resultado fue cero
empresas — no cero oportunidades, cero información.

El orden correcto es el de siempre en venta consultiva:

1. **Quién es cliente** — zona, rubro y cantidad de empleados. Eso es este módulo.
2. **Qué le digo** — que tenga una búsqueda estirada hace 92 días es munición para
   el mail, y de eso se ocupa la ingesta de avisos. Cambia *cómo* le escribís, no
   *si* es cliente.

Una fuente nueva se agrega sola: implementá `buscar(segmento) -> list[EmpresaCruda]`
y sumala a `_fuentes()` en `base.py`. Misma forma que `talanton/ingest/portales/`.
"""

from .base import EmpresaCruda, Resultado, buscar_en_fuentes, fuentes_configuradas

__all__ = [
    "EmpresaCruda",
    "Resultado",
    "buscar_en_fuentes",
    "fuentes_configuradas",
]
