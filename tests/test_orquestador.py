"""Flujos completos: el orquestador coordinando a los cuatro agentes."""

import pytest
from sqlalchemy import select

from comparte.modelos import Estado, Evento
from comparte.orquestador import Orquestador

PAN = "Tengo 25 kg de pan dulce del día"


@pytest.fixture
def orq(db):
    return Orquestador(db)


def donar(orq, texto, donante_id=1):
    assert orq.mensaje(donante_id, texto) is None  # primero el resumen
    d = orq.mensaje(donante_id, "sí")
    assert d is not None
    return d


def agentes(db, d):
    return {e.agente for e in db.scalars(select(Evento).where(Evento.donacion_id == d.id))}


def test_rescate_completo_deja_huella_de_todos_los_agentes(db, orq):
    d = donar(orq, PAN)
    assert d.estado == Estado.OFRECIDA
    orq.responder_receptor(d.id, True)
    assert d.estado == Estado.ASIGNADA and d.voluntario is not None
    orq.responder_voluntario(d.id, True)
    orq.avanzar(d.id, "recogida")
    orq.avanzar(d.id, "entregada")
    assert d.estado == Estado.ENTREGADA
    orq.confirmar(d.id, kg_recibidos=23)
    assert d.estado == Estado.COMPLETADA and d.kg_recibidos == 23
    assert agentes(db, d) == {"captador", "orquestador", "coordinador", "logistico", "impacto"}
    chat = [m["rol"] for m in orq.chat(1).mensajes]
    assert {"captador", "coordinador", "logistico", "impacto", "donante"} <= set(chat)
    assert "Rescate completado" in orq.chat(1).mensajes[-1]["texto"]


def test_rechazo_del_receptor_reasigna(db, orq):
    d = donar(orq, PAN)
    primero = d.receptor_id
    orq.responder_receptor(d.id, False)
    assert d.estado == Estado.OFRECIDA and d.receptor_id != primero


def test_rechazo_del_voluntario_reasigna(db, orq):
    d = donar(orq, PAN)
    orq.responder_receptor(d.id, True)
    primero = d.voluntario_id
    orq.responder_voluntario(d.id, False)
    assert d.estado == Estado.ASIGNADA and d.voluntario_id not in (None, primero)


def test_alimento_de_riesgo_espera_aprobacion_y_solo_va_a_receptores_con_frio(db, orq):
    d = donar(orq, "Tengo 12 kg de pollo, vence mañana", 10)
    assert d.estado == Estado.PENDIENTE_VALIDACION and d.receptor_id is None
    orq.revision(d.id, True)
    assert d.estado == Estado.OFRECIDA and d.receptor.capacidad_frio_kg > 0
    assert "humano" in agentes(db, d)


def test_la_revision_puede_rechazar(db, orq):
    d = donar(orq, "Tengo 12 kg de pollo, vence mañana", 10)
    orq.revision(d.id, False)
    assert d.estado == Estado.RECHAZADA
    with pytest.raises(ValueError):
        orq.revision(d.id, True)


def test_transiciones_invalidas(db, orq):
    d = donar(orq, PAN)
    with pytest.raises(ValueError):
        orq.confirmar(d.id)  # aún no se entrega
    with pytest.raises(ValueError):
        orq.responder_voluntario(d.id, True)  # aún no hay propuesta
    orq.responder_receptor(d.id, True)
    with pytest.raises(ValueError):
        orq.responder_receptor(d.id, True)  # ya respondió
    with pytest.raises(LookupError):
        orq.responder_receptor(999, True)
