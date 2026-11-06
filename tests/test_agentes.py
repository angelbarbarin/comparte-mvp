"""Coordinador, Logístico e Impacto por separado. Hora: martes 10 de noviembre de 2026, 16:00."""

from datetime import timedelta

import pytest

from comparte import reloj
from comparte.agentes import coordinador, impacto, logistico
from comparte.modelos import Donacion, Estado, Receptor, Voluntario

PAN = [{"nombre": "pan", "clave": "pan", "categoria": "pan", "kg": 25.0}]
POLLO = [{"nombre": "pollo", "clave": "pollo", "categoria": "proteina", "kg": 12.0}]


def crear(db, items=PAN, donante_id=1, horas=6.0, frio=False) -> Donacion:
    d = Donacion(donante_id=donante_id, items=[dict(i) for i in items], total_kg=sum(i["kg"] for i in items),
                 requiere_frio=frio, caduca_en=reloj.ahora() + timedelta(hours=horas), creada_en=reloj.ahora())
    db.add(d)
    db.flush()
    return d


def por_id(cands):
    return {c["receptor_id"]: c for c in cands}


# ----------------------------------------------------------------------------------- Coordinador
def test_el_ranking_pone_primero_a_los_viables_por_puntaje(db):
    cands = coordinador.evaluar(db, crear(db), reloj.ahora())
    viables = [c for c in cands if c["viable"]]
    assert cands[:len(viables)] == viables
    assert [c["puntaje"] for c in viables] == sorted((c["puntaje"] for c in viables), reverse=True)
    assert sum(coordinador.PESOS.values()) == pytest.approx(1.0)


def test_descarta_con_motivo(db):
    c = por_id(coordinador.evaluar(db, crear(db, POLLO, 10, 20, frio=True), reloj.ahora()))
    assert "sin refrigeración" in c[2]["motivos"][0]  # Santa Cecilia no tiene frío
    assert not c[5]["viable"]  # Los Pinos: sin frío y cierra a las 18:00
    grande = [{"nombre": "pan", "clave": "pan", "categoria": "pan", "kg": 150.0}]
    c = por_id(coordinador.evaluar(db, crear(db, grande), reloj.ahora()))
    assert "capacidad insuficiente" in c[2]["motivos"][0] and c[1]["viable"]


def test_no_llega_antes_de_caducar(db):
    c = por_id(coordinador.evaluar(db, crear(db, horas=1.0), reloj.ahora()))
    assert any("no llegaría antes de que caduque" in m for m in c[2]["motivos"])


def test_ofrecer_rechazar_y_reasignar(db):
    d = crear(db)
    coordinador.ofrecer(db, d, reloj.ahora())
    primero = d.receptor_id
    assert d.estado == Estado.OFRECIDA and d.evaluacion[0]["receptor_id"] == primero
    coordinador.responder(db, d, False, reloj.ahora())
    coordinador.ofrecer(db, d, reloj.ahora())
    assert d.receptor_id != primero and primero in d.rechazos_receptores


def test_si_todos_rechazan_queda_sin_receptor(db):
    d = crear(db)
    for _ in range(10):
        coordinador.ofrecer(db, d, reloj.ahora())
        if d.estado == Estado.SIN_RECEPTOR:
            break
        coordinador.responder(db, d, False, reloj.ahora())
    assert d.estado == Estado.SIN_RECEPTOR


def test_la_capacidad_reservada_por_una_oferta_cuenta(db):
    d1 = crear(db)
    coordinador.ofrecer(db, d1, reloj.ahora())  # reserva 25 kg en el receptor elegido
    elegido = db.get(Receptor, d1.receptor_id)
    c = por_id(coordinador.evaluar(db, crear(db), reloj.ahora()))
    assert c[elegido.id]["disponible_kg"] == elegido.capacidad_diaria_kg - 25


def test_aceptar_asigna(db):
    d = crear(db)
    coordinador.ofrecer(db, d, reloj.ahora())
    coordinador.responder(db, d, True, reloj.ahora())
    assert d.estado == Estado.ASIGNADA and d.asignada_en == reloj.ahora()
    with pytest.raises(ValueError):
        coordinador.responder(db, d, True, reloj.ahora())


# ------------------------------------------------------------------------------------ Logístico
def asignada(db, kg=25.0, frio=False) -> Donacion:
    d = crear(db, [{"nombre": "pan", "clave": "pan", "categoria": "pan", "kg": kg}], frio=frio)
    d.receptor_id, d.estado = 1, Estado.ASIGNADA
    d.receptor = db.get(Receptor, 1)
    return d


def test_elige_voluntario_con_capacidad_y_ruta_valida(db):
    d = asignada(db, kg=25)
    logistico.proponer(db, d, reloj.ahora())
    assert d.voluntario.capacidad_kg >= 25 and d.voluntario.nombre != "Fernanda Ortiz"  # la moto no carga 25 kg
    assert [p["rol"] for p in d.ruta["puntos"]] == ["voluntario", "donante", "receptor"] and d.ruta["km"] > 0


def test_frio_exige_hielera(db):
    d = asignada(db, kg=12, frio=True)
    logistico.proponer(db, d, reloj.ahora())
    assert d.voluntario.tiene_hielera


def test_ciclo_completo_de_la_recoleccion(db):
    d = asignada(db)
    logistico.proponer(db, d, reloj.ahora())
    with pytest.raises(ValueError):
        logistico.avanzar(db, d, "entregada", reloj.ahora())  # no se salta la recogida
    logistico.responder(db, d, True)
    logistico.avanzar(db, d, "recogida", reloj.ahora())
    logistico.avanzar(db, d, "entregada", reloj.ahora())
    assert d.estado == Estado.ENTREGADA


def test_rechazo_reasigna_a_otro_voluntario_y_sin_voluntarios_queda_atorada(db):
    d = asignada(db)
    logistico.proponer(db, d, reloj.ahora())
    primero = d.voluntario_id
    logistico.responder(db, d, False)
    logistico.proponer(db, d, reloj.ahora())
    assert d.voluntario_id not in (None, primero)
    for v in db.query(Voluntario):
        v.capacidad_kg = 1
    d2 = asignada(db)
    logistico.proponer(db, d2, reloj.ahora())
    assert d2.estado == Estado.SIN_VOLUNTARIO


# ---------------------------------------------------------------------------------------- Impacto
def test_formulas_de_impacto(db):
    d = crear(db, [{"nombre": "pan", "clave": "pan", "categoria": "pan", "kg": 10.0}])
    assert impacto.metricas(d) == {"kg": 10.0, "raciones": 20.0, "personas": 6.7, "co2e_kg": 16.0}
    d.kg_recibidos = 5
    assert impacto.metricas(d)["kg"] == 5.0 and impacto.metricas(d)["co2e_kg"] == 8.0


def test_tablero_vacio_y_con_datos(db):
    assert impacto.resumen(db)["totales"]["kg"] == 0
    d = crear(db)
    d.estado, d.receptor_id, d.completada_en = Estado.COMPLETADA, 1, reloj.ahora()
    r = impacto.resumen(db)
    assert r["totales"]["rescates"] == 1 and r["totales"]["kg"] == 25.0
    assert r["por_categoria"][0]["etiqueta"] == "Pan y tortilla" and r["por_municipio"][0]["etiqueta"] == "Tlaquepaque"
