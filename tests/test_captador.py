from datetime import datetime

from sqlalchemy import select

from comparte.agentes.captador import Captador, cuando
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
    assert "25 kg de pan dulce" in resumen and "10 kg de fruta" in resumen and "35 kg en total" in resumen
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
    assert "Calculo que dura hasta mañana a las 4 de la tarde" in ultimo(conv)
    decir("caduca mañana")
    assert "Calculo" not in ultimo(conv) and "Caduca mañana antes de la medianoche" in ultimo(conv)


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


# ------------------------------------------------------------------------------- principios de diseño de voz
def mensajes_del_captador(conv):
    return [m["texto"] for m in conv.mensajes if m["rol"] == "captador"]


CONVERSACIONES = [
    ["hola", "no sé", "qué", "25 kg de pan", "sí"],
    ["Tengo pan dulce", "mucho", "bastante", "harto", "20 kg", "eh", "no", "son 30 kg", "sí"],
    ["12 kg de pollo y 8 litros de leche", "corregir", "corregir", "caduca mañana", "empezar de nuevo", "empezar de nuevo"],
    ["tengo 10 litros de cerveza", "mejor no", "cancelar", "sí"],
    ["3 cajas de jitomate y 40 bolillos", "qué", "qué", "qué", "sí"],
]


def test_cancelar_a_la_mitad(db):
    conv, decir = chat(db)
    decir("Tengo pan dulce")
    assert "¿Cuánto pan dulce tienes?" in ultimo(conv)
    assert decir("cancelar") is None
    assert "cancelé" in ultimo(conv) and conv.borrador == {}
    decir("cancelar")  # sin nada en curso no dice lo mismo
    assert "No tengo ningún registro en curso" in ultimo(conv)
    assert db.scalar(select(Donacion.id)) is None


def test_empezar_de_nuevo_y_corregir_en_cualquier_etapa(db):
    conv, decir = chat(db)
    decir("25 kg de pan")
    decir("empezar de nuevo")
    assert conv.borrador == {} and "empezamos de nuevo" in ultimo(conv)
    decir("25 kg de pan")
    decir("corregir")
    assert "¿Qué quieres cambiar?" in ultimo(conv)
    decir("son 40 kg")
    assert decir("sí").total_kg == 40.0


def test_recuperacion_progresiva_de_errores(db):
    conv, decir = chat(db)
    decir("hola")
    primero = ultimo(conv)
    assert "No reconocí ningún alimento" in primero and "«25 kg de pan dulce»" in primero  # reformula con ejemplo
    decir("no sé")
    segundo = ultimo(conv)
    assert segundo != primero and "Recibo pan, tortilla, fruta" in segundo and "cancelar" in segundo  # opciones
    decir("qué")
    assert ultimo(conv) not in (segundo,)  # sigue alternando, no se repite


def test_segundo_fallo_al_confirmar_da_opciones(db):
    conv, decir = chat(db)
    decir("25 kg de pan")
    decir("mmm")
    assert "no te entendí" in ultimo(conv)
    decir("mmm")
    assert "«sí»" in ultimo(conv) and "«corregir»" in ultimo(conv) and "«cancelar»" in ultimo(conv)
    assert decir("sí").total_kg == 25.0  # tras los errores, el flujo sigue normal


def test_confirmacion_implicita_al_anotar(db):
    conv, decir = chat(db)
    decir("Tengo pan dulce")
    assert ultimo(conv).startswith("Anoto pan dulce.")


def test_ningun_mensaje_tiene_mas_de_una_pregunta_y_va_al_final(db):
    for n, guion in enumerate(CONVERSACIONES, start=1):
        conv, decir = chat(db, n)
        for texto in guion:
            decir(texto)
        for m in mensajes_del_captador(conv):
            assert m.count("¿") <= 1 and m.count("?") <= 1, m
            if "?" in m:
                assert m.endswith("?"), m


def test_nunca_repite_el_mismo_mensaje_seguido(db):
    for n, guion in enumerate(CONVERSACIONES, start=1):
        conv, decir = chat(db, n)
        for texto in guion:
            decir(texto)
        ms = mensajes_del_captador(conv)
        assert all(a != b for a, b in zip(ms, ms[1:])), ms


def test_se_entiende_sin_pantalla(db):
    for n, guion in enumerate(CONVERSACIONES, start=1):
        conv, decir = chat(db, n)
        for texto in guion:
            decir(texto)
        for m in mensajes_del_captador(conv):
            assert not any(s in m for s in ("•", "⚠", "\n", "T1", "T2")), m  # sin viñetas, emojis ni fechas ISO
            assert not any(c.isdigit() and m[i:i + 5].count("-") >= 2 for i, c in enumerate(m)), m


def test_fechas_faciles_de_decir():
    ahora = datetime(2026, 11, 10, 16, 0)  # martes
    assert cuando(datetime(2026, 11, 10, 18, 0), ahora) == "hoy a las 6 de la tarde"
    assert cuando(datetime(2026, 11, 10, 23, 59), ahora) == "hoy antes de la medianoche"
    assert cuando(datetime(2026, 11, 11, 13, 30), ahora) == "mañana a la 1 y media de la tarde"
    assert cuando(datetime(2026, 11, 12, 9, 15), ahora) == "el jueves 12 a las 9 y cuarto de la mañana"
    assert cuando(datetime(2026, 11, 11, 12, 0), ahora) == "mañana a mediodía"
