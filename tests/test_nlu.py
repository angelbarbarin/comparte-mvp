from datetime import datetime

import pytest

from comparte.nlu import interpretar

AHORA = datetime(2026, 11, 10, 16, 0)


def items(texto):
    return [(i.nombre, i.cantidad, i.unidad) for i in interpretar(texto, AHORA).items]


@pytest.mark.parametrize("texto, esperado", [
    ("Tengo 25 kg de pan dulce del día", [("pan dulce", 25.0, "kg")]),
    ("25 kg de pan y 10 kg de fruta madura", [("pan", 25.0, "kg"), ("fruta", 10.0, "kg")]),
    ("3 cajas de jitomate", [("jitomate", 3.0, "caja")]),
    ("me sobraron 40 bolillos", [("bolillos", 40.0, "pieza")]),
    # un alimento fuera del catálogo (huevos) deja una cantidad suelta que el Captador pregunta
    ("media docena de huevos y 2 kg de queso", [(None, 0.5, "docena"), ("queso", 2.0, "kg")]),
    ("pan dulce, 25 kg", [("pan dulce", 25.0, "kg")]),
    ("tres charolas de pan", [("pan", 3.0, "charola")]),
    ("2,5 kg de arroz", [("arroz", 2.5, "kg")]),
    ("20 kg", [(None, 20.0, "kg")]),
    ("25 kilos de pan y fruta", [("pan", 25.0, "kg"), ("fruta", None, None)]),
])
def test_cantidades_y_alimentos(texto, esperado):
    assert items(texto) == esperado


def test_caducidad():
    assert interpretar("pan, caduca hoy", AHORA).caduca_en == datetime(2026, 11, 10, 23, 59)
    assert interpretar("leche, vence mañana", AHORA).caduca_en == datetime(2026, 11, 11, 23, 59)
    assert interpretar("pollo, caduca en 3 horas", AHORA).caduca_en == datetime(2026, 11, 10, 19, 0)
    assert interpretar("pan del día", AHORA).caduca_en == datetime(2026, 11, 10, 23, 59)
    assert interpretar("20 kg de arroz", AHORA).caduca_en is None


@pytest.mark.parametrize("texto, intencion", [
    ("sí", "confirmar"), ("Sí, correcto", "confirmar"), ("ok", "confirmar"),
    ("no", "negar"), ("cancelar", "cancelar"), ("mejor no", "cancelar"),
    ("hola buenas tardes", "otro"), ("tengo 5 kg de pan", "donar"), ("sí, tengo 5 kg de pan", "donar"),
])
def test_intencion(texto, intencion):
    assert interpretar(texto, AHORA).intencion == intencion


def test_mal_estado():
    assert interpretar("la fruta ya tiene moho", AHORA).mal_estado
    assert not interpretar("fruta fresca", AHORA).mal_estado
