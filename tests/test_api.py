"""Recorrido por HTTP, el mismo que hace la interfaz. Hora: martes 10 de noviembre de 2026, 16:00."""

import pytest
from fastapi.testclient import TestClient

from comparte.api import crear_app


@pytest.fixture
def c():
    with TestClient(crear_app(url="sqlite://", servir_web=False)) as cliente:
        yield cliente


def donar(c, texto="Tengo 25 kg de pan dulce del día", donante_id=1):
    c.post(f"/api/chat/{donante_id}", json={"texto": texto})
    return c.post(f"/api/chat/{donante_id}", json={"texto": "sí"}).json()["donacion_id"]


def test_catalogos(c):
    assert len(c.get("/api/donantes").json()) == 10
    assert len(c.get("/api/receptores").json()) == 5
    assert len(c.get("/api/voluntarios").json()) == 5
    assert c.get("/api/estado").json()["hora"] == "2026-11-10T16:00:00"


def test_recorrido_completo(c):
    did = donar(c)
    d = c.get(f"/api/donaciones/{did}").json()
    assert d["estado"] == "ofrecida" and d["evaluacion"][0]["viable"]

    assert c.post(f"/api/donaciones/{did}/receptor", json={"aceptar": True}).json()["estado"] == "asignada"
    assert c.post(f"/api/donaciones/{did}/voluntario", json={"aceptar": True}).json()["estado"] == "en_recoleccion"
    for paso in ("recogida", "entregada"):
        assert c.post(f"/api/donaciones/{did}/avance", json={"estado": paso}).status_code == 200
    final = c.post(f"/api/donaciones/{did}/confirmacion", json={"kg_recibidos": 24}).json()
    assert final["estado"] == "completada"

    t = c.get("/api/impacto").json()["totales"]
    assert t["rescates"] == 1 and t["kg"] == 24.0 and t["raciones"] == 48.0
    detalle = c.get(f"/api/donaciones/{did}").json()
    assert {e["agente"] for e in detalle["eventos"]} >= {"captador", "orquestador", "coordinador", "logistico", "impacto"}
    assert "Rescate completado" in c.get("/api/chat/1").json()["mensajes"][-1]["texto"]


def test_riesgo_requiere_aprobacion(c):
    did = donar(c, "Tengo 12 kg de pollo, vence mañana", 10)
    assert c.get(f"/api/donaciones/{did}").json()["estado"] == "pendiente_validacion"
    assert c.post(f"/api/donaciones/{did}/revision", json={"aceptar": True}).json()["estado"] == "ofrecida"


def test_errores(c):
    assert c.get("/api/donaciones/999").status_code == 404
    assert c.post("/api/chat/999", json={"texto": "hola"}).status_code == 404
    did = donar(c)
    assert c.post(f"/api/donaciones/{did}/confirmacion", json={}).status_code == 409  # aún no entregada
    assert c.post(f"/api/donaciones/{did}/avance", json={"estado": "volando"}).status_code == 422
    assert c.post("/api/chat/1", json={"texto": ""}).status_code == 422


def test_nueva_conversacion_y_reinicio(c):
    c.post("/api/chat/1", json={"texto": "25 kg de pan"})
    assert len(c.post("/api/chat/1/nueva").json()["mensajes"]) == 1
    donar(c)
    assert c.get("/api/donaciones").json()
    c.post("/api/demo/reiniciar")
    assert c.get("/api/donaciones").json() == []
