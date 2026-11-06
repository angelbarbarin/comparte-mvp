from sqlalchemy import select

from comparte.agentes.captador import Captador
from comparte.modelos import Donacion, Estado


def chat(db, donante_id=1):
    cap = Captador(db)
    conv = cap.iniciar(donante_id)
    db.commit()

    def decir(texto):
        d = cap.procesar(conv, texto)
        db.commit()
        return d

    return conv, decir


def ultimo(conv):
    return conv.mensajes[-1]["texto"]


def test_donar_toma_dos_mensajes(db):
    conv, decir = chat(db)
    assert decir("Tengo 25 kg de pan dulce del día y 10 kg de fruta madura") is None
    resumen = ultimo(conv)
    assert "25 kg de pan dulce" in resumen and "10 kg de fruta" in resumen and "Total: 35 kg" in resumen
    assert db.scalar(select(Donacion.id)) is None  # aún falta confirmar

    d = decir("sí")
    assert d.estado == Estado.REGISTRADA and d.total_kg == 35.0 and len(d.items) == 2
    assert not d.requiere_revision and not d.requiere_frio
    assert conv.borrador == {}


def test_pregunta_la_cantidad_si_falta(db):
    conv, decir = chat(db)
    decir("Tengo pan dulce")
    assert "¿Cuánto pan dulce tienes?" in ultimo(conv)
    decir("20 kg")
    assert "20 kg de pan dulce" in ultimo(conv)


def test_estima_la_caducidad_y_lo_dice(db):
    conv, decir = chat(db)
    decir("20 kg de pan")
    assert "(estimado)" in ultimo(conv)
    decir("caduca mañana")
    assert "(estimado)" not in ultimo(conv)


def test_corregir_la_cantidad(db):
    conv, decir = chat(db)
    decir("25 kg de pan")
    decir("son 30 kg")
    assert decir("sí").total_kg == 30.0


def test_cancelar(db):
    conv, decir = chat(db)
    decir("25 kg de pan")
    decir("mejor no")
    assert conv.borrador == {} and db.scalar(select(Donacion.id)) is None


def test_alimentos_de_riesgo_quedan_marcados(db):
    conv, decir = chat(db, 10)
    decir("12 kg de pollo y 8 litros de leche")
    assert "revisará" in ultimo(conv)
    d = decir("sí")
    assert d.requiere_revision and d.requiere_frio


def test_bloquea_alcohol_y_mal_estado(db):
    conv, decir = chat(db)
    assert decir("tengo 10 litros de cerveza") is None
    assert "No puedo registrar" in ultimo(conv)
    decir("15 kg de papa que ya tiene moho")
    assert "mal estado" in ultimo(conv)
    assert db.scalar(select(Donacion.id)) is None


def test_un_alimento_desconocido_recibe_orientacion(db):
    conv, decir = chat(db)
    decir("hola, tengo sushi")
    assert "No reconocí ningún alimento" in ultimo(conv)
