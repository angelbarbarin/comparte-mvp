"""Modelo de dominio. Seis tablas: Donante, Receptor, Voluntario, Conversacion, Donacion y Evento."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Estado:
    """Ciclo de vida de una donación (lo mueve el orquestador)."""

    REGISTRADA = "registrada"
    PENDIENTE_VALIDACION = "pendiente_validacion"  # alimento de riesgo: espera a una persona
    RECHAZADA = "rechazada"  # la persona revisora la rechazó
    OFRECIDA = "ofrecida"  # propuesta a un receptor
    SIN_RECEPTOR = "sin_receptor"
    ASIGNADA = "asignada"  # el receptor aceptó; propuesta a un voluntario
    SIN_VOLUNTARIO = "sin_voluntario"
    EN_RECOLECCION = "en_recoleccion"  # el voluntario aceptó
    EN_CAMINO = "en_camino"  # el voluntario ya la recogió
    ENTREGADA = "entregada"  # falta que el receptor confirme
    COMPLETADA = "completada"

    # Estados en los que el receptor ya tiene la donación comprometida (cuentan para su capacidad).
    COMPROMETIDOS = (ASIGNADA, EN_RECOLECCION, EN_CAMINO, ENTREGADA, COMPLETADA)
    # Estados en los que el voluntario está ocupado con ella.
    CON_VOLUNTARIO = (ASIGNADA, EN_RECOLECCION, EN_CAMINO)


class Donante(Base):
    __tablename__ = "donantes"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    giro: Mapped[str] = mapped_column(String(40))
    municipio: Mapped[str] = mapped_column(String(60))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    contacto: Mapped[str] = mapped_column(String(80), default="")


class Receptor(Base):
    __tablename__ = "receptores"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    tipo: Mapped[str] = mapped_column(String(40))
    municipio: Mapped[str] = mapped_column(String(60))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    horario_cierre: Mapped[str] = mapped_column(String(5), default="20:00")  # "HH:MM"
    necesidades: Mapped[dict] = mapped_column(JSON, default=dict)  # categoría -> prioridad 1-3
    capacidad_diaria_kg: Mapped[float] = mapped_column(Float, default=0.0)
    capacidad_frio_kg: Mapped[float] = mapped_column(Float, default=0.0)  # 0 = sin refrigeración


class Voluntario(Base):
    __tablename__ = "voluntarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    vehiculo: Mapped[str] = mapped_column(String(40))
    capacidad_kg: Mapped[float] = mapped_column(Float)
    tiene_hielera: Mapped[bool] = mapped_column(Boolean, default=False)
    lat: Mapped[float] = mapped_column(Float)  # ubicación base simulada
    lon: Mapped[float] = mapped_column(Float)


class Conversacion(Base):
    """Una conversación por donante. ``mensajes`` = [{"rol", "texto", "hora"}]; ``borrador`` = donación en construcción."""

    __tablename__ = "conversaciones"
    id: Mapped[int] = mapped_column(primary_key=True)
    donante_id: Mapped[int] = mapped_column(ForeignKey("donantes.id"), unique=True)
    mensajes: Mapped[list] = mapped_column(JSON, default=list)
    borrador: Mapped[dict] = mapped_column(JSON, default=dict)


class Donacion(Base):
    __tablename__ = "donaciones"
    id: Mapped[int] = mapped_column(primary_key=True)
    donante_id: Mapped[int] = mapped_column(ForeignKey("donantes.id"))
    estado: Mapped[str] = mapped_column(String(30), default=Estado.REGISTRADA)
    items: Mapped[list] = mapped_column(JSON, default=list)  # [{nombre, clave, categoria, cantidad, unidad, kg}]
    total_kg: Mapped[float] = mapped_column(Float, default=0.0)
    requiere_frio: Mapped[bool] = mapped_column(Boolean, default=False)
    requiere_revision: Mapped[bool] = mapped_column(Boolean, default=False)
    caduca_en: Mapped[datetime] = mapped_column(DateTime)
    receptor_id: Mapped[int | None] = mapped_column(ForeignKey("receptores.id"), nullable=True)
    voluntario_id: Mapped[int | None] = mapped_column(ForeignKey("voluntarios.id"), nullable=True)
    rechazos_receptores: Mapped[list] = mapped_column(JSON, default=list)  # ids que ya dijeron que no
    rechazos_voluntarios: Mapped[list] = mapped_column(JSON, default=list)
    evaluacion: Mapped[list] = mapped_column(JSON, default=list)  # ranking de receptores (explicable)
    ruta: Mapped[dict] = mapped_column(JSON, default=dict)
    kg_recibidos: Mapped[float | None] = mapped_column(Float, nullable=True)
    creada_en: Mapped[datetime] = mapped_column(DateTime)
    asignada_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completada_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    donante: Mapped[Donante] = relationship()
    receptor: Mapped[Receptor | None] = relationship()
    voluntario: Mapped[Voluntario | None] = relationship()


class Evento(Base):
    """Bitácora: qué agente decidió qué. La interfaz la muestra como línea de tiempo."""

    __tablename__ = "eventos"
    id: Mapped[int] = mapped_column(primary_key=True)
    donacion_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    agente: Mapped[str] = mapped_column(String(20))  # captador, coordinador, logistico, impacto, orquestador, humano
    resumen: Mapped[str] = mapped_column(String(500))
    creado_en: Mapped[datetime] = mapped_column(DateTime)
