"""Buscar empresas a las que vender.

La operación completa de la pantalla **Buscar empresas**, en dos pasos separados
a propósito:

1. `explorar()` consulta las fuentes y devuelve lo que encontró **sin tocar la
   base**. Se revisa en pantalla antes de decidir.
2. `traer()` persiste lo elegido con el circuito de siempre —`upsert_empresa` →
   `upsert_vacante` → `asegurar_lead` → `recalcular_lead`— y deja la empresa
   **vigilada**, así la corrida diaria empieza a contarle los días desde hoy.

El orden importa y estuvo mal una versión: **la empresa es el lead, el aviso es
la excusa**. Se busca por zona, rubro y tamaño; si además hay un aviso abierto se
adjunta como señal y la empresa puntúa más alto, pero una empresa sin aviso entra
igual — se le escribe con la plantilla de presentación en vez de con el dato duro.
Filtrar por aviso dejaba afuera a todo cliente que justo hoy no está publicando, y
ataba el listado comercial a que funcione el scraping.

Lo que sí se descarta: consultoras de selección (son competencia, no clientes) y
avisos perennes tipo «Postulación espontánea», que nunca se cierran y por eso
acumulan días para siempre.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from .directorio import EmpresaCruda, buscar_en_fuentes, fuentes_configuradas
from .ingest.base import VacanteCruda
from .ingest.portales import buscar_en_portales
from .models import Empresa, Lead
from .normalize import es_aviso_perenne, es_competencia, normalizar_nombre_empresa
from .segmento import Segmento
from .services import (
    asegurar_lead,
    fecha_hoy,
    perfil,
    recalcular_lead,
    upsert_empresa,
    upsert_vacante,
)

log = logging.getLogger("talanton.busqueda")

# Motivos de descarte, en castellano, para poder contarlos y mostrarlos: si una
# búsqueda trae 40 y entran 6, hay que poder explicar dónde fueron los 34.
DESCARTE_COMPETENCIA = "consultoras de selección"
DESCARTE_PERENNE = "avisos que nunca se cierran"
DESCARTE_SIN_NOMBRE = "resultados sin nombre de empresa"
DESCARTE_SIN_AVISO = "empresas sin búsqueda abierta"


@dataclass
class Hallazgo:
    """Una empresa encontrada, todavía sin guardar.

    El aviso es opcional y ésa es toda la diferencia con la versión anterior:
    `vacante is None` significa «cliente posible sin señal todavía», no
    «descartar».
    """

    empresa: str
    fuente: str
    dominio: str | None = None
    industria: str | None = None
    dotacion: int | None = None
    ciudad: str | None = None
    fuente_url: str | None = None
    # La señal, cuando la hay.
    titulo: str | None = None
    aviso_url: str | None = None
    dias_abierto: int | None = None
    fecha_aproximada: bool = False
    # True si esa empresa ya está en la base. No es un descubrimiento, pero el
    # aviso puede ser nuevo y vale la pena traerla igual.
    ya_estaba: bool = False
    cruda: EmpresaCruda | None = None
    vacante: VacanteCruda | None = None

    @property
    def tiene_senal(self) -> bool:
        return self.vacante is not None

    @property
    def senal_texto(self) -> str:
        if not self.titulo:
            return "Sin búsqueda publicada hoy"
        if self.dias_abierto is None:
            return self.titulo
        prefijo = "~" if self.fecha_aproximada else ""
        if self.dias_abierto == 0:
            return f"{self.titulo} · publicado hoy"
        plural = "s" if self.dias_abierto != 1 else ""
        return f"{self.titulo} · {prefijo}{self.dias_abierto} día{plural}"

    @property
    def tamano_texto(self) -> str:
        return f"{self.dotacion} empleados" if self.dotacion else "sin dato"

    @property
    def payload(self) -> dict:
        """Lo mínimo para reconstruir el hallazgo en el POST siguiente.

        La pantalla explora primero y guarda después, en dos pedidos distintos.
        Volver a consultar las fuentes para guardar sería pagar dos veces lo más
        caro —una corrida de Apify cuesta plata— y, peor, arriesgarse a guardar
        algo distinto de lo que el usuario vio y eligió. Así viaja en el
        formulario.
        """
        datos = {
            "e": self.empresa,
            "f": self.fuente,
            "dom": self.dominio,
            "ind": self.industria,
            "dot": self.dotacion,
            "c": self.ciudad,
            "url": self.fuente_url,
        }
        if self.vacante is not None:
            datos["v"] = {
                "t": self.vacante.titulo,
                "f": self.vacante.fuente,
                "i": self.vacante.external_id,
                "u": self.vacante.fuente_url,
                "d": (
                    self.vacante.fecha_publicacion.isoformat()
                    if self.vacante.fecha_publicacion
                    else None
                ),
                "a": self.vacante.fecha_aproximada,
            }
        return datos


@dataclass
class Exploracion:
    hallazgos: list[Hallazgo] = field(default_factory=list)
    por_fuente: dict[str, int] = field(default_factory=dict)
    descartes: dict[str, int] = field(default_factory=dict)
    fallidas: list[str] = field(default_factory=list)
    sin_configurar: list[str] = field(default_factory=list)
    # False cuando no hay ninguna fuente lista. Es distinto de «no hay empresas»
    # y la pantalla tiene que decirlo distinto.
    hubo_donde_buscar: bool = True

    @property
    def con_senal(self) -> int:
        return len([h for h in self.hallazgos if h.tiene_senal])

    @property
    def nuevas(self) -> int:
        return len([h for h in self.hallazgos if not h.ya_estaba])


@dataclass
class Traida:
    """Qué quedó guardado después de traer los hallazgos."""

    empresas_nuevas: int = 0
    empresas_actualizadas: int = 0
    vacantes_nuevas: int = 0
    vacantes_repetidas: int = 0
    vigiladas: int = 0
    leads: list[Lead] = field(default_factory=list)


# --- Exploración -------------------------------------------------------------


def explorar(
    session: Session,
    segmento: Segmento,
    *,
    fuentes=None,
    portales=None,
) -> Exploracion:
    """Busca empresas y les adjunta la señal que haya. No escribe nada."""
    resultado = buscar_en_fuentes(segmento, fuentes)
    exploracion = Exploracion(
        por_fuente=dict(resultado.por_fuente),
        fallidas=list(resultado.fallidas),
        sin_configurar=list(resultado.sin_configurar),
        hubo_donde_buscar=resultado.hubo_fuentes,
    )

    conocidas = _empresas_conocidas(session)
    avisos = _avisos_por_empresa(segmento, portales)
    vistas: set[str] = set()

    for cruda in resultado.empresas:
        nombre = (cruda.nombre or "").strip()
        if not nombre:
            _sumar(exploracion, DESCARTE_SIN_NOMBRE)
            continue
        if es_competencia(nombre, cruda.industria):
            _sumar(exploracion, DESCARTE_COMPETENCIA)
            continue

        clave = normalizar_nombre_empresa(nombre)
        if clave in vistas:
            continue
        vistas.add(clave)

        vacante = avisos.get(clave)
        if segmento.solo_con_aviso and vacante is None:
            _sumar(exploracion, DESCARTE_SIN_AVISO)
            continue

        exploracion.hallazgos.append(
            _hallazgo(cruda, vacante, ya_estaba=clave in conocidas)
        )

    # Primero las que tienen la búsqueda más estirada; después las que no tienen
    # señal, que igual son clientes posibles y hay que poder verlas.
    exploracion.hallazgos.sort(
        key=lambda h: (not h.tiene_senal, -(h.dias_abierto or 0))
    )
    return exploracion


def _hallazgo(
    cruda: EmpresaCruda, vacante: VacanteCruda | None, *, ya_estaba: bool
) -> Hallazgo:
    dias = None
    if vacante is not None and vacante.fecha_publicacion is not None:
        dias = (fecha_hoy() - vacante.fecha_publicacion).days
    return Hallazgo(
        empresa=cruda.nombre.strip(),
        fuente=cruda.fuente,
        dominio=cruda.dominio,
        industria=cruda.industria,
        dotacion=cruda.dotacion,
        ciudad=cruda.ciudad,
        fuente_url=cruda.fuente_url,
        titulo=vacante.titulo if vacante else None,
        aviso_url=vacante.fuente_url if vacante else None,
        dias_abierto=dias,
        fecha_aproximada=bool(vacante and vacante.fecha_aproximada),
        ya_estaba=ya_estaba,
        cruda=cruda,
        vacante=vacante,
    )


def _avisos_por_empresa(segmento: Segmento, portales) -> dict[str, VacanteCruda]:
    """Los avisos del segmento, indexados por empresa, para cruzar.

    Si los portales fallan **no pasa nada grave**: se pierde la señal, no la
    lista de empresas. Ésa es exactamente la separación que faltaba antes, cuando
    un 404 de un portal se traducía en cero empresas.
    """
    if segmento.dias_minimos <= 0 and not segmento.solo_con_aviso and portales is None:
        # Nadie pidió señal y consultar portales cuesta tiempo (uno abre un
        # navegador de verdad). No se hace por las dudas.
        return {}

    try:
        resultado = buscar_en_portales(segmento, portales)
    except Exception as exc:  # noqa: BLE001
        log.warning("No se pudieron traer avisos: %s", exc)
        return {}

    por_empresa: dict[str, VacanteCruda] = {}
    for cruda in resultado.crudas:
        if not (cruda.empresa or "").strip():
            continue
        if es_aviso_perenne(cruda.titulo, cruda.descripcion):
            continue
        clave = normalizar_nombre_empresa(cruda.empresa)
        anterior = por_empresa.get(clave)
        # De cada empresa se queda el aviso más viejo: es el que mejor argumenta.
        if anterior is None or _mas_viejo(cruda, anterior):
            por_empresa[clave] = cruda
    return por_empresa


def _mas_viejo(nueva: VacanteCruda, actual: VacanteCruda) -> bool:
    if nueva.fecha_publicacion is None:
        return False
    if actual.fecha_publicacion is None:
        return True
    return nueva.fecha_publicacion < actual.fecha_publicacion


def _sumar(exploracion: Exploracion, motivo: str) -> None:
    exploracion.descartes[motivo] = exploracion.descartes.get(motivo, 0) + 1


# --- Persistencia ------------------------------------------------------------


def traer(session: Session, hallazgos: list[Hallazgo]) -> Traida:
    """Guarda los hallazgos como empresas + leads puntuados, y los deja vigilados."""
    traida = Traida()
    p = perfil(session)
    tocadas: dict[int, Empresa] = {}

    for hallazgo in hallazgos:
        cruda = hallazgo.cruda
        if cruda is None:
            continue

        existia = normalizar_nombre_empresa(cruda.nombre) in _empresas_conocidas(session)
        empresa = upsert_empresa(
            session,
            cruda.nombre,
            dominio=cruda.dominio,
            pais=cruda.pais or "AR",
            ciudad=cruda.ciudad,
            industria=cruda.industria,
            dotacion_estimada=cruda.dotacion,
        )
        session.flush()
        if existia:
            traida.empresas_actualizadas += 1
        else:
            traida.empresas_nuevas += 1

        if hallazgo.vacante is not None:
            _, es_nueva = upsert_vacante(
                session,
                empresa,
                titulo=hallazgo.vacante.titulo,
                fuente=hallazgo.vacante.fuente,
                external_id=hallazgo.vacante.external_id,
                fuente_url=hallazgo.vacante.fuente_url,
                ubicacion=hallazgo.vacante.ubicacion or cruda.ciudad,
                pais=cruda.pais or "AR",
                descripcion=hallazgo.vacante.descripcion,
                fecha_publicacion=hallazgo.vacante.fecha_publicacion,
                fecha_aproximada=hallazgo.vacante.fecha_aproximada,
            )
            if es_nueva:
                traida.vacantes_nuevas += 1
            else:
                traida.vacantes_repetidas += 1

        if _vigilar(session, empresa):
            traida.vigiladas += 1
        tocadas[empresa.id] = empresa

    session.flush()
    for empresa in tocadas.values():
        session.refresh(empresa)
        lead = asegurar_lead(session, empresa)
        recalcular_lead(session, lead, p)
        traida.leads.append(lead)

    # Mejor score arriba: es el orden en que conviene trabajarlos.
    traida.leads.sort(key=lambda lead: lead.score, reverse=True)
    return traida


def _vigilar(session: Session, empresa: Empresa) -> bool:
    """Deja la empresa como objetivo de la corrida diaria. True si es nueva.

    Es lo que hace que dentro de tres semanas esta empresa tenga histórico
    propio, que es el único activo que no se puede improvisar. Sin esto, traerla
    sería sacarle una foto y nada más.
    """
    from sqlalchemy import select

    from .models import Objetivo

    normalizado = normalizar_nombre_empresa(empresa.nombre)
    ya = session.scalar(
        select(Objetivo).where(Objetivo.nombre_normalizado == normalizado)
    )
    if ya is not None:
        if empresa.dominio and not ya.dominio:
            ya.dominio = empresa.dominio
        return False
    session.add(
        Objetivo(
            nombre=empresa.nombre,
            nombre_normalizado=normalizado,
            dominio=empresa.dominio,
        )
    )
    return True


# --- Ida y vuelta por el formulario ------------------------------------------


def hallazgo_desde_payload(datos: dict) -> Hallazgo | None:
    """Rehace un `Hallazgo` a partir de lo que mandó el formulario.

    Viene del navegador, así que se valida y se vuelve a filtrar: sin nombre no
    se guarda nada, y una consultora no se puede colar editando el HTML.
    """
    from datetime import date

    nombre = (datos.get("e") or "").strip()
    fuente = (datos.get("f") or "").strip() or "manual"
    if not nombre:
        return None

    industria = datos.get("ind") or None
    if es_competencia(nombre, industria):
        return None

    cruda = EmpresaCruda(
        nombre=nombre,
        fuente=fuente,
        dominio=datos.get("dom") or None,
        industria=industria,
        dotacion=_entero(datos.get("dot")),
        ciudad=datos.get("c") or None,
        pais="AR",
        fuente_url=datos.get("url") or None,
    )

    vacante = None
    bruto = datos.get("v")
    if isinstance(bruto, dict):
        titulo = (bruto.get("t") or "").strip()
        external_id = (bruto.get("i") or "").strip()
        if titulo and external_id and not es_aviso_perenne(titulo):
            publicada = None
            if bruto.get("d"):
                try:
                    publicada = date.fromisoformat(str(bruto["d"]))
                except ValueError:
                    publicada = None
            vacante = VacanteCruda(
                empresa=nombre,
                titulo=titulo,
                fuente=(bruto.get("f") or fuente).strip(),
                external_id=external_id,
                fuente_url=bruto.get("u") or None,
                ubicacion=cruda.ciudad,
                pais="AR",
                fecha_publicacion=publicada,
                fecha_aproximada=bool(bruto.get("a")),
            )

    return _hallazgo(cruda, vacante, ya_estaba=False)


def _entero(valor) -> int | None:
    try:
        return int(valor) if valor not in (None, "", []) else None
    except (TypeError, ValueError):
        return None


def _empresas_conocidas(session: Session) -> set[str]:
    from sqlalchemy import select

    return set(session.scalars(select(Empresa.nombre_normalizado)).all())


def hay_donde_buscar() -> bool:
    """True si al menos una fuente de empresas está configurada."""
    return bool(fuentes_configuradas())
