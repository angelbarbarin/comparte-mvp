"""Roles por token (comparte/auth.py) y modo demo explícito."""

import json

import pytest
from fastapi.testclient import TestClient

from comparte.api import crear_app
from comparte.auth import Actor, cargar_tokens, resolver

TOKENS = {"clave-admin": "admin", "tok-donante-1": "donante:1", "tok-receptor-2": "receptor:2"}


@pytest.fixture
def demo():
    with TestClient(crear_app(url="sqlite://", servir_web=False, modo_demo=True)) as c:
        yield c


@pytest.fixture
def real(monkeypatch):
    monkeypatch.delenv("COMPARTE_DEMO", raising=False)
    monkeypatch.setenv("COMPARTE_TOKENS", json.dumps(TOKENS))
    with TestClient(crear_app(url="sqlite://", servir_web=False)) as c:
        yield c


def h(token):
    return {"X-Comparte-Token": token}


def donar(c, token, donante_id=1, texto="Tengo 25 kg de pan dulce del día"):
    c.post(f"/api/chat/{donante_id}", json={"texto": texto}, headers=h(token))
    return c.post(f"/api/chat/{donante_id}", json={"texto": "sí"}, headers=h(token)).json()["donacion_id"]


# ------------------------------------------------------------------------------------------ unidades
def test_cargar_tokens():
    tokens = cargar_tokens(json.dumps(TOKENS))
    assert tokens["clave-admin"] == Actor("admin") and tokens["tok-donante-1"] == Actor("donante", 1)
    assert cargar_tokens("") == {}
    for malo in ("no es json", "[1, 2]", '{"t": "jefe:1"}', '{"t": "receptor"}', '{"t": "admin:3"}'):
        with pytest.raises(ValueError):
            cargar_tokens(malo)


def test_tokens_demo_solo_en_modo_demo():
    assert resolver("demo-receptor-3", {}, modo_demo=True) == Actor("receptor", 3)
    assert resolver("demo-admin", {}, modo_demo=True) == Actor("admin")
    assert resolver("demo-receptor-3", {}, modo_demo=False) is None
    assert resolver("demo-jefe-1", {}, modo_demo=True) is None
    assert resolver(None, {}, modo_demo=True) is None


# ------------------------------------------------------------------------------------------- 401 / 403
def test_sin_token_401(demo):
    assert demo.post("/api/chat/1", json={"texto": "hola"}).status_code == 401
    assert demo.get("/api/chat/1").status_code == 401
    assert demo.post("/api/donaciones/1/revision", json={"aceptar": True}).status_code == 401
    assert demo.post("/api/donaciones/1/receptor", json={"aceptar": True}, headers=h("inventado")).status_code == 401


def test_lecturas_publicas(demo):
    for ruta in ("/api/estado", "/api/donantes", "/api/receptores", "/api/voluntarios", "/api/donaciones", "/api/impacto"):
        assert demo.get(ruta).status_code == 200, ruta


def test_donante_solo_su_chat(demo):
    assert demo.post("/api/chat/2", json={"texto": "hola"}, headers=h("demo-donante-1")).status_code == 403
    assert demo.get("/api/chat/2", headers=h("demo-donante-1")).status_code == 403
    assert demo.post("/api/chat/2/nueva", headers=h("demo-donante-1")).status_code == 403
    assert demo.get("/api/chat/2", headers=h("demo-receptor-1")).status_code == 403
    assert demo.get("/api/chat/2", headers=h("demo-admin")).status_code == 200


def test_receptor_no_responde_la_oferta_de_otro(demo):
    did = donar(demo, "demo-donante-1")
    dueno = demo.get(f"/api/donaciones/{did}").json()["receptor"]["id"]
    otro = 1 if dueno != 1 else 2
    r = demo.post(f"/api/donaciones/{did}/receptor", json={"aceptar": True}, headers=h(f"demo-receptor-{otro}"))
    assert r.status_code == 403
    assert demo.get(f"/api/donaciones/{did}").json()["estado"] == "ofrecida"  # no cambió nada
    assert demo.post(f"/api/donaciones/{did}/receptor", json={"aceptar": True}, headers=h("demo-voluntario-1")).status_code == 403
    assert demo.post(f"/api/donaciones/{did}/receptor", json={"aceptar": True}, headers=h(f"demo-receptor-{dueno}")).status_code == 200


def test_voluntario_no_avanza_una_donacion_ajena(demo):
    did = donar(demo, "demo-donante-1")
    d = demo.get(f"/api/donaciones/{did}").json()
    demo.post(f"/api/donaciones/{did}/receptor", json={"aceptar": True}, headers=h(f"demo-receptor-{d['receptor']['id']}"))
    vol = demo.get(f"/api/donaciones/{did}").json()["voluntario"]["id"]
    otro = 1 if vol != 1 else 2
    assert demo.post(f"/api/donaciones/{did}/voluntario", json={"aceptar": True}, headers=h(f"demo-voluntario-{otro}")).status_code == 403
    demo.post(f"/api/donaciones/{did}/voluntario", json={"aceptar": True}, headers=h(f"demo-voluntario-{vol}"))
    assert demo.post(f"/api/donaciones/{did}/avance", json={"estado": "recogida"}, headers=h(f"demo-voluntario-{otro}")).status_code == 403
    assert demo.post(f"/api/donaciones/{did}/avance", json={"estado": "recogida"}, headers=h(f"demo-voluntario-{vol}")).status_code == 200


def test_solo_el_admin_revisa(demo):
    did = donar(demo, "demo-donante-10", 10, "Tengo 12 kg de pollo, vence mañana")
    for token in ("demo-donante-10", "demo-receptor-1", "demo-voluntario-1"):
        assert demo.post(f"/api/donaciones/{did}/revision", json={"aceptar": True}, headers=h(token)).status_code == 403
    assert demo.post(f"/api/donaciones/{did}/revision", json={"aceptar": True}, headers=h("demo-admin")).status_code == 200


# --------------------------------------------------------------------------------------- modo demo
def test_reiniciar_en_modo_demo(demo):
    assert demo.post("/api/demo/reiniciar").status_code == 401
    assert demo.post("/api/demo/reiniciar", headers=h("demo-donante-1")).status_code == 403
    assert demo.post("/api/demo/reiniciar", headers=h("demo-admin")).status_code == 200


def test_reiniciar_no_existe_fuera_del_modo_demo(real):
    assert real.get("/api/estado").json()["modo_demo"] is False
    assert real.post("/api/demo/reiniciar", headers=h("clave-admin")).status_code == 404
    assert real.post("/api/demo/reiniciar", headers=h("demo-admin")).status_code == 404


def test_tokens_demo_no_valen_fuera_del_modo_demo(real):
    assert real.post("/api/chat/1", json={"texto": "hola"}, headers=h("demo-donante-1")).status_code == 401
    assert real.post("/api/donaciones/1/revision", json={"aceptar": True}, headers=h("demo-admin")).status_code == 401


def test_tokens_configurados(real):
    did = donar(real, "tok-donante-1")
    assert did is not None
    assert real.post("/api/chat/2", json={"texto": "hola"}, headers=h("tok-donante-1")).status_code == 403
    assert real.get(f"/api/donaciones/{did}").status_code == 200


def test_comparte_demo_por_variable(monkeypatch):
    monkeypatch.setenv("COMPARTE_DEMO", "1")
    with TestClient(crear_app(url="sqlite://", servir_web=False)) as c:
        assert c.get("/api/estado").json()["modo_demo"] is True
        assert c.post("/api/demo/reiniciar", headers=h("demo-admin")).status_code == 200


def test_cli_exige_demo_para_reiniciar(monkeypatch):
    from comparte.__main__ import main

    monkeypatch.delenv("COMPARTE_DEMO", raising=False)
    for args in (["--reiniciar"], ["--hora-demo", "16:00"]):
        with pytest.raises(SystemExit) as e:
            main(args)
        assert e.value.code == 2


def test_reiniciar_da_404_con_la_interfaz_web(monkeypatch):
    """Como en la PC: con la interfaz servida en "/", la ruta inexistente debe dar 404 y no 405."""
    monkeypatch.delenv("COMPARTE_DEMO", raising=False)
    with TestClient(crear_app(url="sqlite://")) as c:
        r = c.post("/api/demo/reiniciar", headers=h("demo-admin"))
        assert r.status_code == 404 and "No existe" in r.json()["detail"]
        assert c.get("/api/no-existe").status_code == 404
        assert c.get("/").status_code == 200  # la interfaz se sigue sirviendo
        assert c.get("/api/estado").status_code == 200
    with TestClient(crear_app(url="sqlite://", modo_demo=True)) as c:
        assert c.post("/api/demo/reiniciar").status_code == 401
        assert c.post("/api/demo/reiniciar", headers=h("demo-admin")).status_code == 200
