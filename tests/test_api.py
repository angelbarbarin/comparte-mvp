"""Recorrido por HTTP, el mismo que hace la interfaz. Hora: martes 10 de noviembre de 2026, 16:00.

El cliente corre en modo demo y cada petición manda el token del actor que la hace, igual que la interfaz.
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from comparte import reloj
from comparte.api import crear_app

HORA = datetime(2026, 11, 10, 16, 0)  # la misma de conftest.py

ADMIN = {"X-Comparte-Token": "demo-admin"}


def como(rol, id_=None):
    return {"X-Comparte-Token": f"demo-{rol}" + (f"-{id_}" if id_ is not None else "")}


@pytest.fixture
def c():
    with TestClient(crear_app(url="sqlite://", servir_web=False, modo_demo=True)) as cliente:
        yield cliente


def donar(c, texto="Tengo 25 kg de pan dulce del día", donante_id=1):
    c.post(f"/api/chat/{donante_id}", json={"texto": texto}, headers=como("donante", donante_id))
    return c.post(f"/api/chat/{donante_id}", json={"texto": "sí"}, headers=como("donante", donante_id)).json()["donacion_id"]


def receptor_de(c, did):
    return c.get(f"/api/donaciones/{did}").json()["receptor"]["id"]


def voluntario_de(c, did):
    return c.get(f"/api/donaciones/{did}").json()["voluntario"]["id"]


def test_catalogos(c):
    assert len(c.get("/api/donantes").json()) == 10
    assert len(c.get("/api/receptores").json()) == 5
    assert len(c.get("/api/voluntarios").json()) == 5
    estado = c.get("/api/estado").json()
    assert estado["hora"] == "2026-11-10T16:00:00" and estado["modo_demo"] is True


def test_recorrido_completo(c):
    did = donar(c)
    d = c.get(f"/api/donaciones/{did}").json()
    assert d["estado"] == "ofrecida" and d["evaluacion"][0]["viable"]
    rec = como("receptor", d["receptor"]["id"])

    assert c.post(f"/api/donaciones/{did}/receptor", json={"aceptar": True}, headers=rec).json()["estado"] == "asignada"
    vol = como("voluntario", voluntario_de(c, did))
    assert c.post(f"/api/donaciones/{did}/voluntario", json={"aceptar": True}, headers=vol).json()["estado"] == "en_recoleccion"
    for paso in ("recogida", "entregada"):
        assert c.post(f"/api/donaciones/{did}/avance", json={"estado": paso}, headers=vol).status_code == 200
    final = c.post(f"/api/donaciones/{did}/confirmacion", json={"kg_recibidos": 24}, headers=rec).json()
    assert final["estado"] == "completada"

    t = c.get("/api/impacto").json()["totales"]
    assert t["rescates"] == 1 and t["kg"] == 24.0 and t["raciones"] == 48.0
    detalle = c.get(f"/api/donaciones/{did}").json()
    assert {e["agente"] for e in detalle["eventos"]} >= {"captador", "orquestador", "coordinador", "logistico", "impacto"}
    assert "Rescate completado" in c.get("/api/chat/1", headers=como("donante", 1)).json()["mensajes"][-1]["texto"]


def test_riesgo_requiere_aprobacion(c):
    did = donar(c, "Tengo 12 kg de pollo, vence mañana", 10)
    assert c.get(f"/api/donaciones/{did}").json()["estado"] == "pendiente_validacion"
    assert c.post(f"/api/donaciones/{did}/revision", json={"aceptar": True}, headers=ADMIN).json()["estado"] == "ofrecida"


def test_errores(c):
    assert c.get("/api/donaciones/999").status_code == 404
    assert c.post("/api/chat/999", json={"texto": "hola"}, headers=ADMIN).status_code == 404
    did = donar(c)
    rec = como("receptor", receptor_de(c, did))
    assert c.post(f"/api/donaciones/{did}/confirmacion", json={}, headers=rec).status_code == 409  # aún no entregada
    assert c.post(f"/api/donaciones/{did}/avance", json={"estado": "volando"}, headers=ADMIN).status_code == 422
    assert c.post("/api/chat/1", json={"texto": ""}, headers=como("donante", 1)).status_code == 422


def test_doble_clic_en_aceptar_da_409(c):
    did = donar(c)
    rec = como("receptor", receptor_de(c, did))
    assert c.post(f"/api/donaciones/{did}/receptor", json={"aceptar": True}, headers=rec).status_code == 200
    segundo = c.post(f"/api/donaciones/{did}/receptor", json={"aceptar": True}, headers=rec)
    assert segundo.status_code == 409


def test_nueva_conversacion_y_reinicio(c):
    yo = como("donante", 1)
    c.post("/api/chat/1", json={"texto": "25 kg de pan"}, headers=yo)
    assert len(c.post("/api/chat/1/nueva", headers=yo).json()["mensajes"]) == 1
    donar(c)
    assert c.get("/api/donaciones").json()
    assert c.post("/api/demo/reiniciar", headers=ADMIN).status_code == 200
    assert c.get("/api/donaciones").json() == []


def test_la_oferta_vencida_pasa_a_otro_receptor(c):
    did = donar(c)
    primero = receptor_de(c, did)
    reloj.congelar(HORA + timedelta(minutes=16))
    d = c.get(f"/api/donaciones/{did}").json()  # la consulta expira las ofertas vencidas
    assert d["estado"] == "ofrecida" and d["receptor"]["id"] != primero
    assert any("venció" in e["resumen"] for e in d["eventos"])
    # el primer receptor ya no puede responder: su oferta venció (409, no 403)
    tarde = c.post(f"/api/donaciones/{did}/receptor", json={"aceptar": True}, headers=como("receptor", primero))
    assert tarde.status_code == 409 and "ya no está a tu nombre" in tarde.json()["detail"]


def test_ciclo_en_segundo_plano_expira_sin_peticiones(monkeypatch):
    import time

    from comparte.orquestador import Orquestador

    llamadas = []
    original = Orquestador.expirar_vencidas
    monkeypatch.setattr(Orquestador, "expirar_vencidas", lambda self: llamadas.append(1) or original(self))
    with TestClient(crear_app(url="sqlite://", servir_web=False, modo_demo=True, intervalo_vencimientos=0.05)):
        time.sleep(0.4)  # sin ninguna petición: solo el ciclo la llama
        assert len(llamadas) >= 2
    n = len(llamadas)
    time.sleep(0.2)
    assert len(llamadas) == n  # al apagar la app el ciclo se detiene
