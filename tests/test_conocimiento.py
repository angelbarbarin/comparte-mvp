import pytest
from sqlalchemy import func, select

from comparte.conocimiento import (
    CATALOGO,
    a_kg,
    buscar_alimentos,
    distancia_km,
    evaluar_inocuidad,
    normalizar,
)
from comparte.modelos import Donante, Receptor, Voluntario


def item(clave):
    a = CATALOGO[clave]
    return {"nombre": clave, "clave": clave, "riesgo": a.riesgo, "almacenamiento": a.almacenamiento}


@pytest.mark.parametrize("texto, clave", [
    ("pan dulce", "pan"), ("bolillos", "pan"), ("jitomates", "verdura"), ("mangos", "fruta"),
    ("leche", "lacteos"), ("pollo", "pollo"), ("cerveza", "no_aceptado"), ("arroz", "abarrotes"),
])
def test_reconoce_alimentos_con_plurales(texto, clave):
    assert buscar_alimentos(normalizar(texto))[0][0].clave == clave


def test_no_reconoce_dentro_de_otras_palabras():
    assert buscar_alimentos("panorama") == []


def test_conversion_a_kg():
    assert a_kg(25, "kg", CATALOGO["pan"]) == 25
    assert a_kg(500, "g", CATALOGO["pan"]) == 0.5
    assert a_kg(100, "pieza", CATALOGO["pan"]) == pytest.approx(7.0)
    assert a_kg(3, "caja", CATALOGO["fruta"]) == 30.0


def test_pan_no_necesita_revision_ni_frio():
    ev = evaluar_inocuidad([item("pan")])
    assert not (ev.bloqueada or ev.requiere_revision or ev.requiere_frio)


def test_lacteos_y_carnes_piden_revision_humana_y_frio():
    ev = evaluar_inocuidad([item("lacteos")])
    assert ev.requiere_revision and ev.requiere_frio and not ev.bloqueada


def test_alcohol_y_mal_estado_se_bloquean():
    assert evaluar_inocuidad([item("no_aceptado")]).bloqueada
    assert evaluar_inocuidad([item("pan")], mal_estado=True).bloqueada


def test_distancia_razonable():
    km = distancia_km(20.6767, -103.3475, 20.7236, -103.3848)  # Centro GDL -> Zapopan
    assert 6 < km < 10


def test_el_piloto_cumple_lo_prometido(db):
    assert db.scalar(select(func.count(Donante.id))) >= 10
    assert db.scalar(select(func.count(Receptor.id))) >= 5
    assert db.scalar(select(func.count(Voluntario.id))) >= 4
