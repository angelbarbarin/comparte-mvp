"""Doble clic, peticiones simultáneas y ofertas que vencen (retroalimentación del profesor).

Para simular dos peticiones a la vez se usan DOS sesiones sobre la misma base en archivo: cada una carga la
donación cuando todavía estaba en el estado anterior, como pasaría con dos clics casi simultáneos.
Hora: martes 10 de noviembre de 2026, 16:00 (ver conftest.py).
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select

from comparte import reloj
from comparte.agentes import coordinador, logistico
from comparte.datos import sembrar
from comparte.db import crear_fabrica, crear_motor, crear_tablas
from comparte.modelos import Donacion, Estado, Evento, Receptor
from comparte.orquestador import Orquestador


HORA = datetime(2026, 11, 10, 16, 0)  # la misma de conftest.py
PAN = "Tengo 25 kg de pan dulce del día"


@pytest.fixture
def fabrica(tmp_path):
    motor = crear_motor(f"sqlite:///{(tmp_path / 'concurrencia.db').as_posix()}")
    crear_tablas(motor)
    fab = crear_fabrica(motor)
    with fab() as db:
        sembrar(db)
    yield fab
    motor.dispose()


def donar(db, texto=PAN, donante_id=1) -> int:
    orq = Orquestador(db)
    orq.mensaje(donante_id, texto)
    return orq.mensaje(donante_id, "sí").id


def contar_eventos(db, donacion_id, texto, agente=None) -> int:
    filtro = [Evento.donacion_id == donacion_id, Evento.resumen.contains(texto)]
    if agente:
        filtro.append(Evento.agente == agente)
    return db.scalar(select(func.count()).select_from(Evento).where(*filtro))


_vivos = []  # la sesión guarda sus objetos con referencias débiles: los retenemos para que sigan "leídos"


def dos_sesiones(fabrica, did):
    """Dos peticiones que leyeron la donación antes de que cualquiera de las dos escribiera."""
    a, b = fabrica(), fabrica()
    da, db_ = a.get(Donacion, did), b.get(Donacion, did)
    assert da.estado == db_.estado
    _vivos.extend((da, db_))
    return a, b


# ------------------------------------------------------------------------------------ doble clic
def test_doble_clic_en_aceptar_oferta_solo_cuenta_una_vez(fabrica):
    with fabrica() as db:
        did = donar(db)
    a, b = dos_sesiones(fabrica, did)
    Orquestador(a).responder_receptor(did, True)
    with pytest.raises(ValueError, match="ya cambió de estado|no está ofrecida"):
        Orquestador(b).responder_receptor(did, True)
    a.close(), b.close()
    with fabrica() as db:
        assert db.get(Donacion, did).estado == Estado.ASIGNADA
        assert contar_eventos(db, did, "aceptó la donación", "coordinador") == 1


def test_aceptar_y_rechazar_a_la_vez_al_receptor(fabrica):
    with fabrica() as db:
        did = donar(db)
        primero = db.get(Donacion, did).receptor_id
    a, b = dos_sesiones(fabrica, did)
    Orquestador(a).responder_receptor(did, False, receptor_id=primero)
    with pytest.raises(ValueError):
        Orquestador(b).responder_receptor(did, True, receptor_id=primero)  # ya no es la oferta que veía
    a.close(), b.close()
    with fabrica() as db:
        d = db.get(Donacion, did)
        assert d.estado == Estado.OFRECIDA and d.receptor_id != primero and d.rechazos_receptores == [primero]


def test_aceptar_y_rechazar_a_la_vez_al_voluntario(fabrica):
    with fabrica() as db:
        did = donar(db)
        Orquestador(db).responder_receptor(did, True)
    a, b = dos_sesiones(fabrica, did)
    Orquestador(a).responder_voluntario(did, True)
    with pytest.raises(ValueError):
        Orquestador(b).responder_voluntario(did, False)
    a.close(), b.close()
    with fabrica() as db:
        d = db.get(Donacion, did)
        assert d.estado == Estado.EN_RECOLECCION and d.rechazos_voluntarios == []


def test_doble_clic_en_recogida(fabrica):
    with fabrica() as db:
        did = donar(db)
        orq = Orquestador(db)
        orq.responder_receptor(did, True)
        orq.responder_voluntario(did, True)
    a, b = dos_sesiones(fabrica, did)
    Orquestador(a).avanzar(did, "recogida")
    with pytest.raises(ValueError):
        Orquestador(b).avanzar(did, "recogida")
    a.close(), b.close()
    with fabrica() as db:
        assert contar_eventos(db, did, "recogió la donación", "logistico") == 1


def test_confirmar_dos_veces_no_duplica_el_impacto(fabrica):
    with fabrica() as db:
        did = donar(db)
        orq = Orquestador(db)
        orq.responder_receptor(did, True)
        orq.responder_voluntario(did, True)
        orq.avanzar(did, "recogida")
        orq.avanzar(did, "entregada")
    a, b = dos_sesiones(fabrica, did)
    Orquestador(a).confirmar(did, 24)
    with pytest.raises(ValueError, match="ya fue confirmada|aún no ha sido entregada"):
        Orquestador(b).confirmar(did, 24)
    a.close(), b.close()
    with fabrica() as db:
        assert contar_eventos(db, did, "Impacto:", "impacto") == 1
        assert db.get(Donacion, did).kg_recibidos == 24


def test_doble_aprobacion_en_revision(fabrica):
    with fabrica() as db:
        did = donar(db, "Tengo 12 kg de pollo, vence mañana", 10)
    a, b = dos_sesiones(fabrica, did)
    Orquestador(a).revision(did, True)
    with pytest.raises(ValueError):
        Orquestador(b).revision(did, False)
    a.close(), b.close()
    with fabrica() as db:
        assert db.get(Donacion, did).estado == Estado.OFRECIDA
        assert contar_eventos(db, did, "Una persona", "humano") == 1


def test_doble_si_en_el_chat_registra_una_sola_donacion(fabrica):
    with fabrica() as db:
        Orquestador(db).mensaje(1, PAN)  # el Captador ya pidió confirmar
    a, b = fabrica(), fabrica()
    _vivos.extend((Orquestador(a).chat(1), Orquestador(b).chat(1)))  # las dos pestañas cargaron la conversación
    assert Orquestador(a).mensaje(1, "sí") is not None
    with pytest.raises(ValueError, match="dos mensajes"):
        Orquestador(b).mensaje(1, "sí")
    a.close(), b.close()
    with fabrica() as db:
        assert db.scalar(select(func.count()).select_from(Donacion)) == 1


def test_no_se_responde_por_otro_receptor_o_voluntario(db):
    orq = Orquestador(db)
    orq.mensaje(1, PAN)
    d = orq.mensaje(1, "sí")
    otro = next(r.id for r in db.scalars(select(Receptor)) if r.id != d.receptor_id)
    with pytest.raises(ValueError, match="otro receptor"):
        orq.responder_receptor(d.id, True, receptor_id=otro)
    orq.responder_receptor(d.id, True, receptor_id=d.receptor_id)
    with pytest.raises(ValueError, match="otro voluntario"):
        orq.responder_voluntario(d.id, True, voluntario_id=d.voluntario_id + 100)
    orq.responder_voluntario(d.id, True, voluntario_id=d.voluntario_id)
    assert d.estado == Estado.EN_RECOLECCION


# ------------------------------------------------------------------------------------ vencimiento
def test_la_oferta_tiene_tiempo_limite(db):
    orq = Orquestador(db)
    orq.mensaje(1, PAN)
    d = orq.mensaje(1, "sí")
    assert d.oferta_vence_en == HORA + timedelta(minutes=coordinador.VIGENCIA_OFERTA_MIN)


def test_la_oferta_vencida_pasa_al_siguiente_receptor(db):
    orq = Orquestador(db)
    orq.mensaje(1, PAN)
    d = orq.mensaje(1, "sí")
    primero = d.receptor_id
    assert orq.expirar_vencidas() == 0  # aún no vence
    reloj.congelar(HORA + timedelta(minutes=coordinador.VIGENCIA_OFERTA_MIN + 1))
    assert orq.expirar_vencidas() == 1
    assert d.estado == Estado.OFRECIDA and d.receptor_id != primero and primero in d.rechazos_receptores
    assert contar_eventos(db, d.id, "venció sin respuesta") == 1
    assert orq.expirar_vencidas() == 0  # no se expira dos veces


def test_responder_una_oferta_vencida_falla(db):
    d = Donacion(donante_id=1, items=[{"nombre": "pan", "clave": "pan", "categoria": "pan", "kg": 25.0}], total_kg=25.0,
                 caduca_en=HORA + timedelta(hours=6), creada_en=HORA)
    db.add(d)
    db.flush()
    coordinador.ofrecer(db, d, HORA)
    tarde = HORA + timedelta(minutes=coordinador.VIGENCIA_OFERTA_MIN)
    with pytest.raises(ValueError, match="venció"):
        coordinador.responder(db, d, True, tarde)
    assert d.estado == Estado.OFRECIDA  # la respuesta tardía no cambió nada


def test_una_oferta_vencida_ya_no_aparta_capacidad(db):
    d = Donacion(donante_id=1, items=[{"nombre": "pan", "clave": "pan", "categoria": "pan", "kg": 25.0}], total_kg=25.0,
                 caduca_en=HORA + timedelta(hours=6), creada_en=HORA)
    db.add(d)
    db.flush()
    coordinador.ofrecer(db, d, HORA)
    r = db.get(Receptor, d.receptor_id)
    otra = Donacion(donante_id=2, items=d.items, total_kg=25.0, caduca_en=HORA + timedelta(hours=6), creada_en=HORA)
    db.add(otra)
    db.flush()
    disponible = {c["receptor_id"]: c["disponible_kg"] for c in coordinador.evaluar(db, otra, HORA)}
    assert disponible[r.id] == r.capacidad_diaria_kg - 25  # oferta vigente: aparta
    despues = HORA + timedelta(minutes=coordinador.VIGENCIA_OFERTA_MIN + 1)
    disponible = {c["receptor_id"]: c["disponible_kg"] for c in coordinador.evaluar(db, otra, despues)}
    assert disponible[r.id] == r.capacidad_diaria_kg  # vencida: ya no aparta


def test_la_propuesta_al_voluntario_vence_y_se_reasigna(db):
    orq = Orquestador(db)
    orq.mensaje(1, PAN)
    d = orq.mensaje(1, "sí")
    orq.responder_receptor(d.id, True)
    primero = d.voluntario_id
    assert d.propuesta_vence_en == HORA + timedelta(minutes=logistico.VIGENCIA_PROPUESTA_MIN)
    reloj.congelar(HORA + timedelta(minutes=logistico.VIGENCIA_PROPUESTA_MIN + 1))
    with pytest.raises(ValueError):
        logistico.responder(db, d, True, reloj.ahora())  # respuesta tardía directa al agente
    assert orq.expirar_vencidas() == 1
    assert d.estado == Estado.ASIGNADA and d.voluntario_id not in (None, primero) and primero in d.rechazos_voluntarios


def test_las_operaciones_expiran_antes_de_actuar(db):
    """Un clic tardío del receptor original (ya identificado) no acepta la oferta que ahora es de otro."""
    orq = Orquestador(db)
    orq.mensaje(1, PAN)
    d = orq.mensaje(1, "sí")
    primero = d.receptor_id
    reloj.congelar(HORA + timedelta(minutes=coordinador.VIGENCIA_OFERTA_MIN + 1))
    with pytest.raises(ValueError, match="otro receptor"):
        orq.responder_receptor(d.id, True, receptor_id=primero)
    assert d.estado == Estado.OFRECIDA and d.receptor_id != primero
