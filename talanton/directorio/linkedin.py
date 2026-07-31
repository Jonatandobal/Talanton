"""Empresas de LinkedIn vía Apify.

Es la única fuente que devuelve los tres ejes con los que se define un cliente
—**cantidad de empleados, rubro y zona**— estructurados y en el mismo lugar, más
el sitio web, que es lo que después alimenta la búsqueda de mails.

Reusa `ClienteApify.correr_actor()`, que ya sabe disparar un actor, esperar a que
termine y leer el dataset. Lo único propio de acá es armar la entrada y mapear la
salida.

Las dos reglas de `docs/linkedin.md` siguen valiendo, y una es más fácil de
respetar en este carril que en el de avisos:

1. **Nunca una cookie de sesión propia.** Con tu cookie el ban deja de ser un
   riesgo del proveedor y pasa a ser tu cuenta de trabajo.
2. **Sólo datos de empresa.** Acá ni siquiera hay tentación: se piden páginas de
   empresa, que son datos firmográficos públicos. Nada de perfiles de personas —
   eso cae bajo la Ley 25.326 y no tenemos base legal. Si el actor devolviera
   personas, se descartan (`mapear()` sólo lee campos de empresa).
"""

from __future__ import annotations

import logging

from ..config import APIFY_TOKEN
from ..ingest.apify import ClienteApify, ErrorApify, _numero, _primero
from .base import EmpresaCruda, dentro_del_tramo

log = logging.getLogger("talanton.directorio")

# Actor por defecto. Se puede cambiar por variable de entorno sin tocar código:
# los actores de la tienda aparecen y desaparecen, y quedar clavado a uno sería
# repetir el error de los selectores.
ACTOR_POR_DEFECTO = "harvestapi/linkedin-company-search"

# Cómo llamamos nosotros a cada zona → cómo la nombra LinkedIn.
ZONAS = {
    "caba": "Buenos Aires, Argentina",
    "gba": "Buenos Aires Province, Argentina",
    "cordoba": "Córdoba, Argentina",
    "santa-fe": "Santa Fe, Argentina",
    "mendoza": "Mendoza, Argentina",
    "tucuman": "Tucumán, Argentina",
    "neuquen": "Neuquén, Argentina",
    "salta": "Salta, Argentina",
    "entre-rios": "Entre Ríos, Argentina",
    "chubut": "Chubut, Argentina",
    "todo-el-pais": "Argentina",
}

# Los rubros de LinkedIn en inglés, que es como los indexa. Varios términos por
# rubro porque su taxonomía parte cosas que para vender son lo mismo.
RUBROS = {
    "produccion": ["Manufacturing", "Industrial Machinery Manufacturing"],
    "logistica": ["Transportation, Logistics, Supply Chain and Storage"],
    "mantenimiento": ["Industrial Machinery Manufacturing", "Engineering Services"],
    "construccion": ["Construction"],
    "agro": ["Farming", "Food and Beverage Manufacturing"],
    "comercial": ["Wholesale"],
    "retail": ["Retail", "Consumer Goods"],
    "administracion": ["Financial Services", "Accounting"],
    "rrhh": ["Human Resources Services"],
    "tecnologia": ["IT Services and IT Consulting", "Software Development"],
    "salud": ["Hospitals and Health Care", "Pharmaceutical Manufacturing"],
    "gastronomia": ["Restaurants", "Hospitality"],
}

# Los tramos que LinkedIn ofrece como filtro. No son libres: hay que mapear el
# rango pedido a los tramos que se solapan con él.
_TRAMOS = [
    ("1-10", 1, 10),
    ("11-50", 11, 50),
    ("51-200", 51, 200),
    ("201-500", 201, 500),
    ("501-1000", 501, 1000),
    ("1001-5000", 1001, 5000),
    ("5001-10000", 5001, 10000),
    ("10001+", 10001, 10**9),
]


def tramos_para(minimo: int | None, maximo: int | None) -> list[str]:
    """Tramos de LinkedIn que se solapan con el rango pedido.

    Pedir 50-300 tiene que traer «51-200» y «201-500»: el tramo de LinkedIn se
    corta donde quiere, no donde uno lo necesita. Después `dentro_del_tramo()`
    afina sobre el número real de cada empresa.
    """
    if not minimo and not maximo:
        return []
    desde = minimo or 0
    hasta = maximo or 10**9
    return [nombre for nombre, bajo, alto in _TRAMOS if bajo <= hasta and alto >= desde]


# Nombres con que los distintos actores devuelven cada campo. Mismo criterio que
# en el conector de avisos: cambiar de actor no debería obligar a tocar código.
_CLAVES_EMPRESA = {
    "nombre": ("name", "companyName", "title", "company"),
    "sitio": ("website", "companyWebsite", "websiteUrl", "url"),
    "industria": ("industry", "companyIndustry", "industries", "sector"),
    "dotacion": ("employeeCount", "companySize", "staffCount", "employeesCount",
                 "employeeCountRange"),
    "ciudad": ("location", "headquarters", "city", "addressLocality", "locality"),
    "linkedin": ("linkedinUrl", "companyLinkedinUrl", "profileUrl", "link"),
    "descripcion": ("description", "tagline", "about"),
}


def mapear(item: dict, fuente: str = "linkedin", pais: str = "AR") -> EmpresaCruda | None:
    """Convierte un resultado del actor en EmpresaCruda. None si no sirve."""
    campos = dict(_CLAVES_EMPRESA)
    nombre = _leer(item, campos["nombre"])
    if not nombre:
        return None

    from ..normalize import normalizar_dominio

    sitio = _leer(item, campos["sitio"])
    dominio = None
    if sitio and "linkedin.com" not in sitio:
        dominio = normalizar_dominio(sitio)

    return EmpresaCruda(
        nombre=nombre,
        fuente=fuente,
        dominio=dominio,
        industria=_leer(item, campos["industria"]),
        dotacion=_numero(_leer(item, campos["dotacion"])),
        ciudad=_leer(item, campos["ciudad"]),
        pais=pais,
        fuente_url=_leer(item, campos["linkedin"]) or sitio,
        descripcion=(_leer(item, campos["descripcion"]) or "")[:2000] or None,
    )


def _leer(item: dict, claves: tuple[str, ...]) -> str | None:
    """Como `apify._primero`, pero con las claves puestas a mano."""
    for clave in claves:
        valor = item.get(clave)
        if isinstance(valor, dict):
            valor = valor.get("name") or valor.get("text") or valor.get("value")
        if isinstance(valor, list) and valor:
            valor = valor[0]
        if valor not in (None, "", []):
            return str(valor).strip()
    return None


class EmpresasLinkedIn:
    nombre = "linkedin"

    def __init__(self, cliente: ClienteApify | None = None, actor: str | None = None):
        self._cliente = cliente
        self.actor = actor or ACTOR_POR_DEFECTO

    def disponible(self) -> bool:
        return self._cliente is not None or bool(APIFY_TOKEN)

    def cliente(self) -> ClienteApify:
        if self._cliente is not None:
            return self._cliente
        if not APIFY_TOKEN:
            raise ErrorApify(
                "Falta TALANTON_APIFY_TOKEN. Sin eso no hay de dónde traer empresas."
            )
        return ClienteApify(token=APIFY_TOKEN)

    def entrada(self, segmento) -> dict:
        """El JSON que se le manda al actor."""
        entrada: dict = {
            "location": ZONAS.get(segmento.zona, "Argentina"),
            # Apify cobra por uso: un actor sin tope puede correr durante horas.
            "maxItems": segmento.tope,
        }
        rubros = RUBROS.get(segmento.rubro or "")
        if rubros:
            entrada["industries"] = rubros
        tramos = tramos_para(segmento.dotacion_min, segmento.dotacion_max)
        if tramos:
            entrada["companySizes"] = tramos
        return entrada

    def buscar(self, segmento) -> list[EmpresaCruda]:
        crudos = self.cliente().correr_actor(self.actor, self.entrada(segmento))

        empresas: list[EmpresaCruda] = []
        vistas: set[str] = set()
        for item in crudos:
            empresa = mapear(item, fuente=self.nombre)
            if empresa is None:
                continue
            # El filtro de tramo de LinkedIn es grueso; acá se afina sobre el
            # número real, sin descartar a las que no informan dotación.
            if not dentro_del_tramo(empresa, segmento.dotacion_min, segmento.dotacion_max):
                continue
            clave = (empresa.dominio or empresa.nombre).lower()
            if clave in vistas:
                continue
            vistas.add(clave)
            empresas.append(empresa)

        log.info(
            "linkedin: %s resultados del actor, %s empresas utilizables",
            len(crudos),
            len(empresas),
        )
        return empresas[: segmento.tope]
