"""Búsqueda de empresas por segmento. Cero red: fuentes y portales son falsos.

Lo que se protege acá es la decisión de fondo del módulo: **la empresa es el lead,
el aviso es la excusa**. Una empresa sin búsqueda publicada hoy sigue siendo un
cliente posible, y ninguna falla de scraping puede hacerla desaparecer.
"""

from datetime import timedelta

import pytest

from talanton import busqueda, services
from talanton.directorio import EmpresaCruda
from talanton.directorio.base import Resultado as ResultadoFuentes
from talanton.ingest.base import VacanteCruda
from talanton.ingest.portales.base import Resultado as ResultadoPortales
from talanton.segmento import Segmento


class FuenteFalsa:
    """Devuelve lo que se le pase. Igual que el cliente falso de Apify."""

    def __init__(self, nombre, empresas, explota=False, lista=True):
        self.nombre = nombre
        self._empresas = empresas
        self._explota = explota
        self._lista = lista
        self.llamadas = 0

    def disponible(self):
        return self._lista

    def buscar(self, segmento):
        self.llamadas += 1
        if self._explota:
            raise RuntimeError("la fuente no respondió")
        return list(self._empresas)


class PortalFalso:
    nombre = "portal-falso"

    def __init__(self, crudas, explota=False):
        self._crudas = crudas
        self._explota = explota

    def buscar(self, segmento):
        if self._explota:
            raise RuntimeError("el portal devolvió 404")
        return list(self._crudas)


def empresa(nombre, *, dotacion=120, industria="Manufacturing", ciudad="Rosario"):
    return EmpresaCruda(
        nombre=nombre,
        fuente="fuente-falsa",
        dominio=None,
        industria=industria,
        dotacion=dotacion,
        ciudad=ciudad,
        pais="AR",
        fuente_url=f"https://ejemplo.test/{nombre.lower().replace(' ', '-')}",
    )


def aviso(nombre_empresa, titulo, *, dias=30, ident=None):
    return VacanteCruda(
        empresa=nombre_empresa,
        titulo=titulo,
        fuente="portal-falso",
        external_id=ident or f"{nombre_empresa}-{titulo}".lower().replace(" ", "-"),
        fuente_url="https://ejemplo.test/aviso",
        ubicacion="Rosario, Santa Fe",
        pais="AR",
        fecha_publicacion=services.fecha_hoy() - timedelta(days=dias),
    )


# --- Lo esencial: la empresa no depende del aviso ----------------------------


def test_una_empresa_sin_aviso_igual_es_lead(session):
    """El corazón del rediseño. Filtrar por aviso dejaba afuera a todo cliente
    que justo hoy no está publicando."""
    fuente = FuenteFalsa("uno", [empresa("Metalúrgica Paraná")])

    exploracion = busqueda.explorar(session, Segmento(), fuentes=[fuente])

    assert len(exploracion.hallazgos) == 1
    hallazgo = exploracion.hallazgos[0]
    assert not hallazgo.tiene_senal
    assert hallazgo.senal_texto == "Sin búsqueda publicada hoy"

    traida = busqueda.traer(session, exploracion.hallazgos)
    assert traida.empresas_nuevas == 1
    assert traida.leads[0].empresa.nombre == "Metalúrgica Paraná"


def test_si_los_portales_fallan_las_empresas_llegan_igual(session):
    """Es exactamente lo que salió mal en producción: un 404 de portal no puede
    traducirse en cero empresas."""
    fuente = FuenteFalsa("uno", [empresa("Metalúrgica Paraná")])
    portal = PortalFalso([], explota=True)

    exploracion = busqueda.explorar(
        session, Segmento(dias_minimos=45), fuentes=[fuente], portales=[portal]
    )

    assert len(exploracion.hallazgos) == 1
    assert not exploracion.hallazgos[0].tiene_senal


def test_el_aviso_se_adjunta_cuando_lo_hay(session):
    fuente = FuenteFalsa("uno", [empresa("Metalúrgica Paraná")])
    portal = PortalFalso([aviso("Metalurgica Parana SA", "Jefe de Producción", dias=92)])

    exploracion = busqueda.explorar(
        session, Segmento(dias_minimos=45), fuentes=[fuente], portales=[portal]
    )

    hallazgo = exploracion.hallazgos[0]
    assert hallazgo.tiene_senal
    assert hallazgo.dias_abierto == 92
    assert "Jefe de Producción" in hallazgo.senal_texto


def test_de_cada_empresa_se_queda_el_aviso_mas_viejo(session):
    """Es el que mejor argumenta: 92 días convence, 3 días no dice nada."""
    fuente = FuenteFalsa("uno", [empresa("Metalúrgica Paraná")])
    portal = PortalFalso(
        [
            aviso("Metalúrgica Paraná", "Comprador", dias=3, ident="a"),
            aviso("Metalúrgica Paraná", "Jefe de Producción", dias=92, ident="b"),
        ]
    )

    exploracion = busqueda.explorar(
        session, Segmento(dias_minimos=1), fuentes=[fuente], portales=[portal]
    )

    assert exploracion.hallazgos[0].dias_abierto == 92


def test_el_tilde_de_solo_con_aviso_recorta(session):
    fuente = FuenteFalsa(
        "uno", [empresa("Metalúrgica Paraná"), empresa("Frigorífico del Litoral")]
    )
    portal = PortalFalso([aviso("Metalúrgica Paraná", "Jefe de Producción", dias=92)])

    exploracion = busqueda.explorar(
        session,
        Segmento(solo_con_aviso=True),
        fuentes=[fuente],
        portales=[portal],
    )

    assert [h.empresa for h in exploracion.hallazgos] == ["Metalúrgica Paraná"]
    assert exploracion.descartes[busqueda.DESCARTE_SIN_AVISO] == 1


def test_sin_pedir_senal_no_se_consultan_los_portales(session):
    """Consultar portales cuesta tiempo y uno abre un navegador de verdad."""
    fuente = FuenteFalsa("uno", [empresa("Metalúrgica Paraná")])

    exploracion = busqueda.explorar(session, Segmento(), fuentes=[fuente])

    assert exploracion.hallazgos[0].vacante is None


# --- Descartes ---------------------------------------------------------------


def test_una_consultora_no_entra_como_lead(session):
    """Es competencia, no cliente. Es literalmente el pedido del usuario."""
    fuente = FuenteFalsa(
        "uno",
        [
            empresa("Randstad Argentina", industria="Human Resources Services"),
            empresa("Metalúrgica Paraná"),
        ],
    )

    exploracion = busqueda.explorar(session, Segmento(), fuentes=[fuente])

    assert [h.empresa for h in exploracion.hallazgos] == ["Metalúrgica Paraná"]
    assert exploracion.descartes[busqueda.DESCARTE_COMPETENCIA] == 1


def test_un_aviso_perenne_no_cuenta_como_senal(session):
    """«Postulación espontánea» no se cierra nunca: acumularía días para siempre
    y haría creer que la empresa está desesperada."""
    fuente = FuenteFalsa("uno", [empresa("Frigorífico del Litoral")])
    portal = PortalFalso(
        [aviso("Frigorífico del Litoral", "Postulación espontánea", dias=800)]
    )

    exploracion = busqueda.explorar(
        session, Segmento(dias_minimos=1), fuentes=[fuente], portales=[portal]
    )

    # La empresa entra igual; lo que no entra es la señal falsa.
    assert len(exploracion.hallazgos) == 1
    assert not exploracion.hallazgos[0].tiene_senal


def test_las_que_tienen_senal_van_primero(session):
    fuente = FuenteFalsa(
        "uno",
        [
            empresa("Alfa SA"),
            empresa("Beta SRL"),
            empresa("Gama SA"),
        ],
    )
    portal = PortalFalso(
        [
            aviso("Beta SRL", "Jefe de Depósito", dias=92, ident="b"),
            aviso("Gama SA", "Analista de Costos", dias=40, ident="c"),
        ]
    )

    exploracion = busqueda.explorar(
        session, Segmento(dias_minimos=1), fuentes=[fuente], portales=[portal]
    )

    assert [h.empresa for h in exploracion.hallazgos] == ["Beta SRL", "Gama SA", "Alfa SA"]


# --- Fuentes -----------------------------------------------------------------


def test_una_fuente_caida_no_frena_a_las_demas(session):
    buena = FuenteFalsa("buena", [empresa("Metalúrgica Paraná")])
    rota = FuenteFalsa("rota", [], explota=True)

    exploracion = busqueda.explorar(session, Segmento(), fuentes=[rota, buena])

    assert len(exploracion.hallazgos) == 1
    assert exploracion.fallidas and "rota" in exploracion.fallidas[0]


def test_sin_fuentes_configuradas_se_dice_distinto_que_sin_empresas(session):
    """«No pregunté» y «no hay» no se pueden ver iguales. Fue el error que hizo
    que 0 empresas pareciera un dato sobre el mercado."""
    apagada = FuenteFalsa("apagada", [empresa("X")], lista=False)

    exploracion = busqueda.explorar(session, Segmento(), fuentes=[apagada])

    assert exploracion.hallazgos == []
    assert not exploracion.hubo_donde_buscar
    assert exploracion.sin_configurar == ["apagada"]


def test_marca_las_empresas_que_ya_estaban(session):
    services.upsert_empresa(session, "Metalúrgica Paraná", pais="AR")
    session.flush()
    fuente = FuenteFalsa("uno", [empresa("Metalurgica Parana SA")])

    exploracion = busqueda.explorar(session, Segmento(), fuentes=[fuente])

    assert exploracion.hallazgos[0].ya_estaba
    assert exploracion.nuevas == 0


# --- Tramo de dotación -------------------------------------------------------


def test_el_tramo_de_empleados_filtra():
    from talanton.directorio.base import dentro_del_tramo

    chica = empresa("Chica", dotacion=8)
    justa = empresa("Justa", dotacion=120)
    enorme = empresa("Enorme", dotacion=9000)

    assert not dentro_del_tramo(chica, 50, 300)
    assert dentro_del_tramo(justa, 50, 300)
    assert not dentro_del_tramo(enorme, 50, 300)


def test_una_empresa_sin_dotacion_conocida_no_se_descarta():
    """Descartarla sería perder un cliente posible por un dato que falta."""
    from talanton.directorio.base import dentro_del_tramo

    assert dentro_del_tramo(empresa("Sin dato", dotacion=None), 50, 300)


def test_los_tramos_de_linkedin_cubren_el_rango_pedido():
    from talanton.directorio.linkedin import tramos_para

    # Pedir 50-300 tiene que traer los dos tramos que se solapan: LinkedIn corta
    # donde quiere, no donde uno necesita.
    assert tramos_para(50, 300) == ["11-50", "51-200", "201-500"]
    assert tramos_para(None, None) == []


# --- Persistencia ------------------------------------------------------------


def test_traer_deja_la_empresa_vigilada(session):
    """Sin esto, traerla sería sacarle una foto: no acumularía histórico, que es
    el único activo que no se puede improvisar."""
    from sqlalchemy import select

    from talanton.models import Objetivo

    fuente = FuenteFalsa("uno", [empresa("Metalúrgica Paraná")])
    exploracion = busqueda.explorar(session, Segmento(), fuentes=[fuente])

    traida = busqueda.traer(session, exploracion.hallazgos)
    session.flush()

    assert traida.vigiladas == 1
    objetivos = session.scalars(select(Objetivo)).all()
    assert any(o.nombre == "Metalúrgica Paraná" for o in objetivos)


def test_traer_crea_lead_puntuado_con_gancho_cuando_hay_senal(session):
    fuente = FuenteFalsa("uno", [empresa("Metalúrgica Paraná")])
    portal = PortalFalso([aviso("Metalúrgica Paraná", "Jefe de Producción", dias=92)])
    exploracion = busqueda.explorar(
        session, Segmento(dias_minimos=1), fuentes=[fuente], portales=[portal]
    )

    traida = busqueda.traer(session, exploracion.hallazgos)

    lead = traida.leads[0]
    assert lead.score > 0
    assert lead.gancho


def test_traer_dos_veces_no_duplica_ni_pisa_el_historico(session):
    """La invariante del producto. `primera_vez_vista` es lo que permite decir
    «hace 92 días que buscan»."""
    fuente = FuenteFalsa("uno", [empresa("Metalúrgica Paraná")])
    portal = PortalFalso([aviso("Metalúrgica Paraná", "Jefe de Producción", dias=92)])
    segmento = Segmento(dias_minimos=1)

    primera = busqueda.traer(
        session,
        busqueda.explorar(session, segmento, fuentes=[fuente], portales=[portal]).hallazgos,
    )
    vista_original = primera.leads[0].empresa.vacantes[0].primera_vez_vista

    segunda = busqueda.traer(
        session,
        busqueda.explorar(session, segmento, fuentes=[fuente], portales=[portal]).hallazgos,
    )

    assert segunda.empresas_nuevas == 0
    assert segunda.empresas_actualizadas == 1
    assert segunda.vacantes_nuevas == 0
    assert segunda.vacantes_repetidas == 1
    assert segunda.vigiladas == 0
    assert services.metricas(session)["empresas"] == 1
    assert segunda.leads[0].empresa.vacantes[0].primera_vez_vista == vista_original


def test_los_leads_vuelven_de_mayor_a_menor_score(session):
    fuente = FuenteFalsa("uno", [empresa("Alfa SA"), empresa("Beta SRL")])
    portal = PortalFalso([aviso("Beta SRL", "Gerente de Operaciones", dias=120)])
    exploracion = busqueda.explorar(
        session, Segmento(dias_minimos=1), fuentes=[fuente], portales=[portal]
    )

    traida = busqueda.traer(session, exploracion.hallazgos)

    scores = [lead.score for lead in traida.leads]
    assert scores == sorted(scores, reverse=True)


# --- Ida y vuelta por el formulario ------------------------------------------


def test_el_payload_sobrevive_al_formulario(session):
    fuente = FuenteFalsa("uno", [empresa("Metalúrgica Paraná")])
    portal = PortalFalso([aviso("Metalúrgica Paraná", "Jefe de Producción", dias=92)])
    original = busqueda.explorar(
        session, Segmento(dias_minimos=1), fuentes=[fuente], portales=[portal]
    ).hallazgos[0]

    rehecho = busqueda.hallazgo_desde_payload(original.payload)

    assert rehecho is not None
    assert rehecho.empresa == original.empresa
    assert rehecho.dotacion == original.dotacion
    assert rehecho.dias_abierto == original.dias_abierto
    assert rehecho.vacante.external_id == original.vacante.external_id


def test_una_empresa_sin_aviso_tambien_sobrevive_al_formulario(session):
    fuente = FuenteFalsa("uno", [empresa("Metalúrgica Paraná")])
    original = busqueda.explorar(session, Segmento(), fuentes=[fuente]).hallazgos[0]

    rehecho = busqueda.hallazgo_desde_payload(original.payload)

    assert rehecho is not None
    assert rehecho.vacante is None


@pytest.mark.parametrize("payload", [{}, {"f": "uno"}, {"e": "", "f": "uno"}])
def test_un_payload_sin_nombre_no_guarda_nada(payload):
    assert busqueda.hallazgo_desde_payload(payload) is None


def test_no_se_puede_colar_una_consultora_por_el_formulario():
    """El payload viene del navegador: se vuelve a filtrar del lado del servidor."""
    colado = {"e": "Randstad Argentina", "f": "uno"}
    assert busqueda.hallazgo_desde_payload(colado) is None


def test_no_se_puede_colar_un_aviso_perenne_por_el_formulario():
    colado = {
        "e": "Metalúrgica Paraná",
        "f": "uno",
        "v": {"t": "Postulación espontánea", "i": "x", "f": "portal"},
    }
    rehecho = busqueda.hallazgo_desde_payload(colado)
    assert rehecho is not None and rehecho.vacante is None


# --- La pantalla -------------------------------------------------------------


def test_la_pantalla_ofrece_zonas_rubros_y_empleados(cliente):
    """Nada de texto libre en zona ni rubro. Con Apollo ya aprendimos que
    escribir «Logística» a mano no matchea nada."""
    html = cliente.get("/buscar").text

    assert "Buscar empresas" in html
    assert 'name="zona"' in html and 'name="rubro"' in html
    assert "Córdoba" in html and "Logística y transporte" in html
    assert 'name="dotacion_min"' in html and 'name="dotacion_max"' in html
    # El tilde arranca apagado: la empresa es el lead, el aviso es la excusa.
    assert 'name="solo_con_aviso"' in html


def test_sin_fuentes_la_pantalla_lo_dice(cliente):
    html = cliente.get("/buscar").text
    # En los tests no hay TALANTON_APIFY_TOKEN, así que tiene que avisarlo en vez
    # de dejar creer que no hay empresas.
    assert "Todavía no hay de dónde traer empresas" in html


def test_buscar_muestra_lo_encontrado_sin_guardarlo(cliente, monkeypatch):
    monkeypatch.setattr(
        busqueda,
        "buscar_en_fuentes",
        lambda segmento, fuentes=None: ResultadoFuentes(
            empresas=[empresa("Metalúrgica Paraná")], por_fuente={"linkedin": 1}
        ),
    )

    html = cliente.post(
        "/buscar",
        data={
            "zona": "santa-fe",
            "rubro": "produccion",
            "dotacion_min": "50",
            "dotacion_max": "300",
            "dias_minimos": "0",
        },
    ).text

    assert "Metalúrgica Paraná" in html
    assert "Traer como leads" in html


def test_traer_sin_tildar_nada_lo_dice(cliente):
    assert "No tildaste ninguna empresa" in cliente.post("/buscar/traer", data={}).text


def test_traer_desde_la_pantalla_deja_el_lead_creado(cliente):
    import json

    payload = {
        "e": "Metalúrgica Paraná",
        "f": "linkedin",
        "ind": "Manufacturing",
        "dot": 120,
        "c": "Rosario",
    }
    html = cliente.post("/buscar/traer", data={"elegido": json.dumps(payload)}).text

    assert "Guardado" in html
    assert "Metalúrgica Paraná" in cliente.get("/leads").text


def test_el_diagnostico_responde(cliente, monkeypatch):
    from talanton import diagnostico

    monkeypatch.setattr(
        diagnostico,
        "revisar_portales",
        lambda segmento: [
            diagnostico.Revision(
                portal="computrabajo",
                url="https://ar.computrabajo.com/x",
                status=404,
                bytes=120,
            )
        ],
    )

    html = cliente.get("/buscar/diagnostico").text

    # El punto de la pantalla: un 404 tiene que verse como 404, no como "0".
    assert "404" in html
    assert "la URL está mal armada" in html


def test_una_pagina_con_status_de_error_no_pasa_por_buena():
    """El bug que originó todo esto: un 404 devolvía una página vacía pero
    válida, ningún selector matcheaba, y la pantalla decía «0 avisos»."""
    from talanton.ingest.base import verificar_status

    class PaginaFalsa:
        status = 404

    with pytest.raises(RuntimeError, match="404"):
        verificar_status(PaginaFalsa(), "https://ejemplo.test/x")


def test_una_pagina_sin_status_no_rompe():
    from talanton.ingest.base import verificar_status

    verificar_status(object(), "https://ejemplo.test/x")
