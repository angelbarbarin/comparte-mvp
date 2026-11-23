"""Utilidades comunes: bitácora de decisiones y mensajes al chat del donante."""

from sqlalchemy import update
from sqlalchemy.orm import Session

from .. import reloj
from ..modelos import Conversacion, Donacion, Evento


def evento(db: Session, donacion_id: int | None, agente: str, resumen: str) -> None:
    """Registra una decisión en la bitácora (la interfaz la muestra como línea de tiempo)."""
    db.add(Evento(donacion_id=donacion_id, agente=agente, resumen=resumen, creado_en=reloj.ahora()))


def transicionar(db: Session, d: Donacion, desde: str | tuple, valores: dict, *condiciones, error: str | None = None) -> None:
    """Cambia el estado de forma atómica: ``UPDATE donaciones SET ... WHERE id = :id AND estado IN (:desde) [AND ...]``.

    Si otra petición ya movió la donación (un doble clic, dos pestañas, una oferta que venció), el ``UPDATE`` no
    afecta ninguna fila y se lanza ``ValueError`` (la API responde 409). Solo quien gana el ``UPDATE`` debe escribir
    eventos, avisos o listas de rechazos; así nunca se duplican. ``condiciones`` son expresiones extra de SQLAlchemy.
    """
    desde = (desde,) if isinstance(desde, str) else tuple(desde)
    resultado = db.execute(
        update(Donacion).where(Donacion.id == d.id, Donacion.estado.in_(desde), *condiciones).values(**valores)
        .execution_options(synchronize_session=False))
    db.refresh(d)  # el objeto en memoria refleja lo que quedó en la base (y sus relaciones se recargan)
    if resultado.rowcount != 1:
        raise ValueError(error or f"La donación #{d.id} ya cambió de estado ({d.estado}); actualiza la vista e intenta de nuevo")


def decir(conv: Conversacion, rol: str, texto: str) -> None:
    """Agrega un mensaje al chat. ``rol`` es "donante" o el nombre de un agente."""
    conv.mensajes = [*conv.mensajes, {"rol": rol, "texto": texto, "hora": reloj.ahora().strftime("%H:%M")}]


def avisar_donante(db: Session, donacion: Donacion, agente: str, texto: str) -> None:
    conv = db.query(Conversacion).filter_by(donante_id=donacion.donante_id).first()
    if conv is not None:
        decir(conv, agente, texto)


def fmt_kg(kg: float) -> str:
    return f"{kg:.1f}".rstrip("0").rstrip(".") + " kg"
