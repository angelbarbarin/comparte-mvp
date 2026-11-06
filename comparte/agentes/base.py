"""Utilidades comunes: bitácora de decisiones y mensajes al chat del donante."""

from sqlalchemy.orm import Session

from .. import reloj
from ..modelos import Conversacion, Donacion, Evento


def evento(db: Session, donacion_id: int | None, agente: str, resumen: str) -> None:
    """Registra una decisión en la bitácora (la interfaz la muestra como línea de tiempo)."""
    db.add(Evento(donacion_id=donacion_id, agente=agente, resumen=resumen, creado_en=reloj.ahora()))


def decir(conv: Conversacion, rol: str, texto: str) -> None:
    """Agrega un mensaje al chat. ``rol`` es "donante" o el nombre de un agente."""
    conv.mensajes = [*conv.mensajes, {"rol": rol, "texto": texto, "hora": reloj.ahora().strftime("%H:%M")}]


def avisar_donante(db: Session, donacion: Donacion, agente: str, texto: str) -> None:
    conv = db.query(Conversacion).filter_by(donante_id=donacion.donante_id).first()
    if conv is not None:
        decir(conv, agente, texto)


def fmt_kg(kg: float) -> str:
    return f"{kg:.1f}".rstrip("0").rstrip(".") + " kg"
