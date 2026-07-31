"""Qué se busca: zona, rubro, tamaño.

Es el vocabulario que comparten los dos carriles —el directorio de empresas y los
portales de avisos— y por eso vive acá arriba y no adentro de ninguno.

Las zonas y los rubros son **listas cerradas** a propósito. Con Apollo ya
aprendimos que un campo de texto libre es una trampa: quien busca escribe
«Logística», la fuente espera otra cosa, no matchea nada, y la conclusión
equivocada es que no hay empresas de logística. Acá cada opción que se muestra en
castellano tiene su traducción al término que espera cada fuente.
"""

from __future__ import annotations

from dataclasses import dataclass

# Provincias y regiones argentinas. El primer valor es la clave interna; cada
# fuente la traduce a lo suyo.
ZONAS: list[tuple[str, str]] = [
    ("caba", "Ciudad de Buenos Aires"),
    ("gba", "GBA / Provincia de Buenos Aires"),
    ("cordoba", "Córdoba"),
    ("santa-fe", "Santa Fe / Rosario"),
    ("mendoza", "Mendoza"),
    ("tucuman", "Tucumán"),
    ("neuquen", "Neuquén / Río Negro"),
    ("salta", "Salta / Jujuy"),
    ("entre-rios", "Entre Ríos"),
    ("chubut", "Chubut / Santa Cruz"),
    ("todo-el-pais", "Todo el país"),
]

# Rubros pensados para una consultora de selección en Argentina: los que compran
# búsquedas de mando medio, no las ~200 categorías de cada portal.
RUBROS: list[tuple[str, str]] = [
    ("produccion", "Producción y manufactura"),
    ("logistica", "Logística y transporte"),
    ("mantenimiento", "Mantenimiento e ingeniería"),
    ("construccion", "Construcción"),
    ("agro", "Agro y alimentos"),
    ("comercial", "Comercial y ventas"),
    ("retail", "Retail y consumo masivo"),
    ("administracion", "Administración y finanzas"),
    ("rrhh", "Recursos humanos"),
    ("tecnologia", "Tecnología y sistemas"),
    ("salud", "Salud"),
    ("gastronomia", "Gastronomía y hotelería"),
]

_ETIQUETA_ZONA = dict(ZONAS)
_ETIQUETA_RUBRO = dict(RUBROS)


@dataclass
class Segmento:
    """A quién le queremos vender. Es lo que el usuario define en pantalla."""

    zona: str = "todo-el-pais"
    rubro: str | None = None
    # El tramo de dotación: por debajo no hay presupuesto para un fee, por
    # encima hay un equipo de selección interno que compite por el mandato.
    dotacion_min: int | None = None
    dotacion_max: int | None = None
    # Antigüedad mínima del aviso, para cuando además se pide señal. No filtra
    # empresas por sí sola: sólo aplica si `solo_con_aviso` está encendido.
    dias_minimos: int = 0
    # Apagado por omisión, y es el corazón del rediseño. Una empresa sin aviso
    # publicado hoy sigue siendo un cliente posible; encender esto es decir
    # «hoy quiero atacar sólo lo que está caliente».
    solo_con_aviso: bool = False
    tope: int = 60

    @property
    def zona_etiqueta(self) -> str:
        return _ETIQUETA_ZONA.get(self.zona, self.zona)

    @property
    def rubro_etiqueta(self) -> str | None:
        return _ETIQUETA_RUBRO.get(self.rubro) if self.rubro else None

    @property
    def tramo_etiqueta(self) -> str:
        if self.dotacion_min and self.dotacion_max:
            return f"{self.dotacion_min} a {self.dotacion_max} empleados"
        if self.dotacion_min:
            return f"más de {self.dotacion_min} empleados"
        if self.dotacion_max:
            return f"hasta {self.dotacion_max} empleados"
        return "cualquier tamaño"
