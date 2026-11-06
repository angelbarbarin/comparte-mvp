"""API REST (FastAPI) y servidor de la interfaz. Documentación interactiva en /docs.

Entidades inexistentes -> 404; transiciones inválidas -> 409. MVP sin autenticación: cualquiera puede
"actuar como" cualquier donante, receptor, voluntario o administrador (ver docs/ALCANCE.md).

Nota técnica: este módulo no usa ``from __future__ import annotations`` para que FastAPI resuelva bien
las dependencias.
"""

from typing import Literal

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import reloj
from .agentes import impacto
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


def crear_app(url: str | None = None, hora_demo: str | None = None, servir_web: bool = True) -> FastAPI:
    motor = crear_motor(url)
    crear_tablas(motor)
    fabrica = crear_fabrica(motor)
    if hora_demo:
        reloj.fijar_hora_hoy(hora_demo)
    with fabrica() as db:
        sembrar(db)

    app = FastAPI(title="ComParte API (MVP)", description="Agentes: Captador, Coordinador, Logístico e Impacto, coordinados por un orquestador.")

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

    def donante(db: Session, donante_id: int) -> Donante:
        d = db.get(Donante, donante_id)
        if d is None:
            raise LookupError(f"No existe el donante {donante_id}")
        return d

    # ---------------------------------------------------------------------------------- catálogos
    @app.get("/api/estado")
    def estado():
        return {"hora": reloj.ahora().isoformat(timespec="seconds"), "reloj_de_demo": reloj.hay_desfase(), "pesos": PESOS}

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
    def ver_chat(donante_id: int, db: Session = Depends(get_db)):
        donante(db, donante_id)
        return {"mensajes": Orquestador(db).chat(donante_id).mensajes}

    @app.post("/api/chat/{donante_id}")
    def enviar(donante_id: int, cuerpo: MensajeIn, db: Session = Depends(get_db)):
        donante(db, donante_id)
        d = Orquestador(db).mensaje(donante_id, cuerpo.texto)
        conv = db.query(Conversacion).filter_by(donante_id=donante_id).one()
        return {"mensajes": conv.mensajes, "donacion_id": d.id if d else None}

    @app.post("/api/chat/{donante_id}/nueva")
    def nueva_conversacion(donante_id: int, db: Session = Depends(get_db)):
        donante(db, donante_id)
        db.query(Conversacion).filter_by(donante_id=donante_id).delete()
        db.commit()
        return {"mensajes": Orquestador(db).chat(donante_id).mensajes}

    # ----------------------------------------------------------------------------------- donaciones
    @app.get("/api/donaciones")
    def listar(db: Session = Depends(get_db)):
        return [_donacion(db, d) for d in db.scalars(select(Donacion).order_by(Donacion.id.desc()))]

    @app.get("/api/donaciones/{donacion_id}")
    def ver(donacion_id: int, db: Session = Depends(get_db)):
        d = db.get(Donacion, donacion_id)
        if d is None:
            raise LookupError(f"No existe la donación {donacion_id}")
        return _donacion(db, d, detalle=True)

    @app.post("/api/donaciones/{donacion_id}/revision")
    def revisar(donacion_id: int, cuerpo: RespuestaIn, db: Session = Depends(get_db)):
        return _donacion(db, Orquestador(db).revision(donacion_id, cuerpo.aceptar))

    @app.post("/api/donaciones/{donacion_id}/receptor")
    def responder_receptor(donacion_id: int, cuerpo: RespuestaIn, db: Session = Depends(get_db)):
        return _donacion(db, Orquestador(db).responder_receptor(donacion_id, cuerpo.aceptar))

    @app.post("/api/donaciones/{donacion_id}/voluntario")
    def responder_voluntario(donacion_id: int, cuerpo: RespuestaIn, db: Session = Depends(get_db)):
        return _donacion(db, Orquestador(db).responder_voluntario(donacion_id, cuerpo.aceptar))

    @app.post("/api/donaciones/{donacion_id}/avance")
    def avanzar(donacion_id: int, cuerpo: AvanceIn, db: Session = Depends(get_db)):
        return _donacion(db, Orquestador(db).avanzar(donacion_id, cuerpo.estado))

    @app.post("/api/donaciones/{donacion_id}/confirmacion")
    def confirmar(donacion_id: int, cuerpo: ConfirmacionIn, db: Session = Depends(get_db)):
        return _donacion(db, Orquestador(db).confirmar(donacion_id, cuerpo.kg_recibidos))

    # ------------------------------------------------------------------------------ impacto y demo
    @app.get("/api/impacto")
    def tablero(db: Session = Depends(get_db)):
        return impacto.resumen(db)

    @app.post("/api/demo/reiniciar")
    def reiniciar():
        """Borra todo y recarga el piloto simulado (para repetir la demo desde cero)."""
        reiniciar_tablas(motor)
        with fabrica() as db:
            sembrar(db)
        return {"ok": True}

    if servir_web:
        app.mount("/", StaticFiles(directory=RAIZ / "web", html=True), name="web")
    return app
