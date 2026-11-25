"""API REST (FastAPI) y servidor de la interfaz. Documentación interactiva en /docs.

Entidades inexistentes -> 404; transiciones inválidas -> 409. Las acciones piden un rol (``comparte/auth.py``):
sin token -> 401, con un rol o un dueño que no corresponde -> 403. Los catálogos, el seguimiento y el impacto son
públicos. ``POST /api/demo/reiniciar`` solo existe en modo demo (``modo_demo=True`` o ``COMPARTE_DEMO=1``).

Nota técnica: este módulo no usa ``from __future__ import annotations`` para que FastAPI resuelva bien
las dependencias.
"""

import asyncio
import contextlib
import logging
import os
from typing import Literal

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import reloj
from .agentes import impacto
from .auth import Actor, cargar_tokens, exigir_propiedad, requiere
from .agentes.coordinador import PESOS
from .datos import sembrar
from .db import RAIZ, crear_fabrica, crear_motor, crear_tablas, reiniciar_tablas
from .modelos import Conversacion, Donacion, Donante, Estado, Evento, Receptor, Voluntario
from .orquestador import Orquestador


class MensajeIn(BaseModel):
    texto: str = Field(min_length=1, max_length=2000)


class RespuestaIn(BaseModel):
    aceptar: bool


class AvanceIn(BaseModel):
    estado: Literal["recogida", "entregada"]


class ConfirmacionIn(BaseModel):
    kg_recibidos: float | None = Field(default=None, gt=0, le=100000)


def _actor(x, extra=()):
    if x is None:
        return None
    return {"id": x.id, "nombre": x.nombre, **{k: getattr(x, k) for k in ("lat", "lon", *extra)}}


def _donacion(db: Session, d: Donacion, detalle: bool = False) -> dict:
    datos = {
        "id": d.id, "estado": d.estado, "items": d.items, "total_kg": d.total_kg,
        "requiere_frio": d.requiere_frio, "requiere_revision": d.requiere_revision, "caduca_en": d.caduca_en.isoformat(timespec="minutes"),
        "donante": _actor(d.donante, ("municipio",)), "receptor": _actor(d.receptor, ("municipio",)),
        "voluntario": _actor(d.voluntario, ("vehiculo",)), "ruta": d.ruta,
    }
    if detalle:
        eventos = db.scalars(select(Evento).where(Evento.donacion_id == d.id).order_by(Evento.id))
        datos["evaluacion"] = d.evaluacion
        datos["eventos"] = [{"agente": e.agente, "resumen": e.resumen, "hora": e.creado_en.strftime("%H:%M")} for e in eventos]
    return datos


log = logging.getLogger("comparte")


def crear_app(url: str | None = None, hora_demo: str | None = None, servir_web: bool = True, modo_demo: bool = False,
              intervalo_vencimientos: float = 30) -> FastAPI:
    """``modo_demo`` (o ``COMPARTE_DEMO=1``) acepta los tokens ``demo-*`` y registra ``POST /api/demo/reiniciar``.

    ``intervalo_vencimientos``: cada cuántos segundos un ciclo en segundo plano retira las ofertas y propuestas vencidas.
    """
    modo_demo = modo_demo or os.getenv("COMPARTE_DEMO") == "1"
    tokens = cargar_tokens()
    motor = crear_motor(url)
    crear_tablas(motor)
    fabrica = crear_fabrica(motor)
    if hora_demo:
        reloj.fijar_hora_hoy(hora_demo)
    with fabrica() as db:
        sembrar(db)

    def expirar_una_vez() -> int:
        with fabrica() as db:
            return Orquestador(db).expirar_vencidas()

    async def vigilar_vencimientos():
        while True:
            await asyncio.sleep(intervalo_vencimientos)
            try:
                n = expirar_una_vez()
                if n:
                    log.info("Expiraron %s ofertas o propuestas", n)
            except Exception:  # noqa: BLE001  (el ciclo no debe morir por un error puntual)
                log.exception("No se pudieron expirar las ofertas vencidas")

    @contextlib.asynccontextmanager
    async def ciclo_de_vida(_: FastAPI):
        tarea = asyncio.create_task(vigilar_vencimientos())
        try:
            yield
        finally:
            tarea.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await tarea

    app = FastAPI(title="ComParte API (MVP)", lifespan=ciclo_de_vida,
                  description="Agentes: Captador, Coordinador, Logístico e Impacto, coordinados por un orquestador. "
                              "Las acciones piden la cabecera X-Comparte-Token.")
    app.state.modo_demo = modo_demo
    app.state.tokens = tokens

    def get_db():
        db = fabrica()
        try:
            yield db
        finally:
            db.close()

    @app.exception_handler(LookupError)
    async def _404(_: Request, exc: LookupError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def _409(_: Request, exc: ValueError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    def donante(db: Session, donante_id: int, actor: Actor) -> Donante:
        d = db.get(Donante, donante_id)
        if d is None:
            raise LookupError(f"No existe el donante {donante_id}")
        exigir_propiedad(actor, "donante", d.id, "Esta conversación")
        return d

    def donacion(db: Session, donacion_id: int) -> Donacion:
        d = db.get(Donacion, donacion_id)
        if d is None:
            raise LookupError(f"No existe la donación {donacion_id}")
        return d

    def propia(actor: Actor, d: Donacion, rol: str, que: str) -> None:
        """403 si la donación es de otro receptor o voluntario. Si el actor la tuvo y la perdió (la rechazó o su
        oferta venció y pasó a alguien más), es una carrera, no un permiso: 409 con un mensaje claro."""
        dueno, anteriores = (d.receptor_id, d.rechazos_receptores) if rol == "receptor" else (d.voluntario_id, d.rechazos_voluntarios)
        if actor.rol == rol and actor.id != dueno and actor.id in (anteriores or []):
            raise ValueError(f"{que} de la donación #{d.id} ya no está a tu nombre: venció o ya la respondiste")
        exigir_propiedad(actor, rol, dueno, que)

    def id_si(actor: Actor, rol: str) -> int | None:
        """El id del actor si tiene ese rol (para que el orquestador valide de nuevo); None si es admin."""
        return actor.id if actor.rol == rol else None

    # ---------------------------------------------------------------------------------- catálogos
    @app.get("/api/estado")
    def estado():
        return {"hora": reloj.ahora().isoformat(timespec="seconds"), "reloj_de_demo": reloj.hay_desfase(), "pesos": PESOS,
                "modo_demo": modo_demo}

    @app.get("/api/donantes")
    def donantes(db: Session = Depends(get_db)):
        return [{"id": d.id, "nombre": d.nombre, "municipio": d.municipio, "contacto": d.contacto} for d in db.scalars(select(Donante))]

    @app.get("/api/receptores")
    def receptores(db: Session = Depends(get_db)):
        return [{"id": r.id, "nombre": r.nombre, "tipo": r.tipo, "municipio": r.municipio, "cierra": r.horario_cierre,
                 "necesidades": r.necesidades, "capacidad_diaria_kg": r.capacidad_diaria_kg,
                 "capacidad_frio_kg": r.capacidad_frio_kg} for r in db.scalars(select(Receptor))]

    @app.get("/api/voluntarios")
    def voluntarios(db: Session = Depends(get_db)):
        return [{"id": v.id, "nombre": v.nombre, "vehiculo": v.vehiculo, "capacidad_kg": v.capacidad_kg,
                 "tiene_hielera": v.tiene_hielera} for v in db.scalars(select(Voluntario))]

    # --------------------------------------------------------------------------------------- chat
    @app.get("/api/chat/{donante_id}")
    def ver_chat(donante_id: int, db: Session = Depends(get_db), actor: Actor = requiere("donante", "admin")):
        donante(db, donante_id, actor)
        return {"mensajes": Orquestador(db).chat(donante_id).mensajes}

    @app.post("/api/chat/{donante_id}")
    def enviar(donante_id: int, cuerpo: MensajeIn, db: Session = Depends(get_db), actor: Actor = requiere("donante", "admin")):
        donante(db, donante_id, actor)
        d = Orquestador(db).mensaje(donante_id, cuerpo.texto)
        conv = db.query(Conversacion).filter_by(donante_id=donante_id).one()
        return {"mensajes": conv.mensajes, "donacion_id": d.id if d else None}

    @app.post("/api/chat/{donante_id}/nueva")
    def nueva_conversacion(donante_id: int, db: Session = Depends(get_db), actor: Actor = requiere("donante", "admin")):
        donante(db, donante_id, actor)
        db.query(Conversacion).filter_by(donante_id=donante_id).delete()
        db.commit()
        return {"mensajes": Orquestador(db).chat(donante_id).mensajes}

    # ----------------------------------------------------------------------------------- donaciones
    @app.get("/api/donaciones")
    def listar(db: Session = Depends(get_db)):
        Orquestador(db).expirar_vencidas()
        return [_donacion(db, d) for d in db.scalars(select(Donacion).order_by(Donacion.id.desc()))]

    @app.get("/api/donaciones/{donacion_id}")
    def ver(donacion_id: int, db: Session = Depends(get_db)):
        Orquestador(db).expirar_vencidas()
        return _donacion(db, donacion(db, donacion_id), detalle=True)

    # Las acciones revisan el rol (requiere) y que el actor sea el dueño de la donación (exigir_propiedad). La transición
    # en sí es atómica en el orquestador: si dos peticiones llegan a la vez, la segunda recibe 409.
    @app.post("/api/donaciones/{donacion_id}/revision")
    def revisar(donacion_id: int, cuerpo: RespuestaIn, db: Session = Depends(get_db), _: Actor = requiere("admin")):
        return _donacion(db, Orquestador(db).revision(donacion_id, cuerpo.aceptar))

    @app.post("/api/donaciones/{donacion_id}/receptor")
    def responder_receptor(donacion_id: int, cuerpo: RespuestaIn, db: Session = Depends(get_db),
                           actor: Actor = requiere("receptor", "admin")):
        propia(actor, donacion(db, donacion_id), "receptor", "Esta oferta")
        return _donacion(db, Orquestador(db).responder_receptor(donacion_id, cuerpo.aceptar, id_si(actor, "receptor")))

    @app.post("/api/donaciones/{donacion_id}/voluntario")
    def responder_voluntario(donacion_id: int, cuerpo: RespuestaIn, db: Session = Depends(get_db),
                             actor: Actor = requiere("voluntario", "admin")):
        propia(actor, donacion(db, donacion_id), "voluntario", "Esta propuesta")
        return _donacion(db, Orquestador(db).responder_voluntario(donacion_id, cuerpo.aceptar, id_si(actor, "voluntario")))

    @app.post("/api/donaciones/{donacion_id}/avance")
    def avanzar(donacion_id: int, cuerpo: AvanceIn, db: Session = Depends(get_db),
                actor: Actor = requiere("voluntario", "admin")):
        propia(actor, donacion(db, donacion_id), "voluntario", "Esta recolección")
        return _donacion(db, Orquestador(db).avanzar(donacion_id, cuerpo.estado, id_si(actor, "voluntario")))

    @app.post("/api/donaciones/{donacion_id}/confirmacion")
    def confirmar(donacion_id: int, cuerpo: ConfirmacionIn, db: Session = Depends(get_db),
                  actor: Actor = requiere("receptor", "admin")):
        propia(actor, donacion(db, donacion_id), "receptor", "Esta donación")
        return _donacion(db, Orquestador(db).confirmar(donacion_id, cuerpo.kg_recibidos, id_si(actor, "receptor")))

    # ------------------------------------------------------------------------------ impacto y demo
    @app.get("/api/impacto")
    def tablero(db: Session = Depends(get_db)):
        return impacto.resumen(db)

    if modo_demo:  # fuera del modo demo la ruta no existe (404): nadie puede borrar la base desde la red
        @app.post("/api/demo/reiniciar")
        def reiniciar(_: Actor = requiere("admin")):
            """Borra todo y recarga el piloto simulado (para repetir la demo desde cero). Solo modo demo y admin."""
            reiniciar_tablas(motor)
            with fabrica() as db:
                sembrar(db)
            return {"ok": True}

    # Va al final: cualquier /api/... que no exista (por ejemplo /api/demo/reiniciar fuera del modo demo) da 404.
    # Sin esto, la petición caería en los archivos de la interfaz, que a un POST le responden 405.
    @app.api_route("/api/{ruta:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
    def no_existe(ruta: str):
        raise LookupError(f"No existe la ruta /api/{ruta}")

    if servir_web:
        app.mount("/", StaticFiles(directory=RAIZ / "web", html=True), name="web")
    return app
