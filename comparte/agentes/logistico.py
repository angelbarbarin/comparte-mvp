"""Agente Logístico (CP-05 coordinación de recolección).

Cuando un receptor acepta, elige al voluntario con la ruta más corta (voluntario -> donante -> receptor)
entre los que cumplan: no estar ocupado con otra donación, vehículo con capacidad, hielera si hay cadena
de frío y llegar a entregar antes de que caduque y antes de que cierre el receptor. Guarda la ruta y los
tiempos estimados. Los voluntarios son simulados y la ruta es una estimación (``distancia_km``).

La propuesta vence a los ``VIGENCIA_PROPUESTA_MIN`` minutos: mientras está vencida el voluntario deja de
contar como ocupado y ``Orquestador.expirar_vencidas`` busca a otro. Cada respuesta y cada avance se aplican
con ``transicionar`` (``UPDATE ... WHERE estado = :esperado``), así que un doble clic no avanza dos veces.
"""

from datetime import datetime, time, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import reloj
from ..conocimiento import distancia_km, minutos
from ..modelos import Donacion, Estado, Voluntario
from .base import avisar_donante, evento, transicionar

NOMBRE = "logistico"
SALIDA_MIN = 5  # tiempo para aceptar y salir
CARGA_MIN = 5  # tiempo en cada punto
MARGEN_MIN = 15  # la entrega debe terminar 15 min antes de caducar
VIGENCIA_PROPUESTA_MIN = 15  # minutos que tiene el voluntario para responder


def propuesta_vigente(d: Donacion, ahora: datetime) -> bool:
    return d.propuesta_vence_en is None or d.propuesta_vence_en > ahora


def _ocupa_voluntario(d: Donacion, ahora: datetime) -> bool:
    """Una propuesta pendiente y vencida ya no aparta al voluntario."""
    return not (d.estado == Estado.ASIGNADA and not propuesta_vigente(d, ahora))


def proponer(db: Session, d: Donacion, ahora: datetime) -> None:
    """Propone la recolección al mejor voluntario. Si no hay ninguno, queda ``sin_voluntario``."""
    ocupados = {x.voluntario_id for x in db.scalars(
        select(Donacion).where(Donacion.estado.in_(Estado.CON_VOLUNTARIO), Donacion.id != d.id))
        if x.voluntario_id and _ocupa_voluntario(x, ahora)}
    r = d.receptor
    hh, mm = (int(x) for x in r.horario_cierre.split(":"))
    candidatos = []
    for v in db.scalars(select(Voluntario).order_by(Voluntario.id)):
        km1 = distancia_km(v.lat, v.lon, d.donante.lat, d.donante.lon)
        km2 = distancia_km(d.donante.lat, d.donante.lon, r.lat, r.lon)
        recoger = ahora + timedelta(minutes=SALIDA_MIN + minutos(km1))
        entrega = recoger + timedelta(minutes=CARGA_MIN + minutos(km2))
        motivos = []
        if v.id in d.rechazos_voluntarios:
            motivos.append("ya rechazó esta recolección")
        if v.id in ocupados:
            motivos.append("tiene otra recolección en curso")
        if v.capacidad_kg < d.total_kg:
            motivos.append(f"su vehículo ({v.vehiculo}) carga {v.capacidad_kg:.0f} kg y la donación pesa {d.total_kg:.0f} kg")
        if d.requiere_frio and not v.tiene_hielera:
            motivos.append("sin hielera para la cadena de frío")
        if entrega + timedelta(minutes=MARGEN_MIN) > d.caduca_en:
            motivos.append("no alcanza a entregar antes de que caduque")
        if entrega > datetime.combine(entrega.date(), time(hh, mm)):
            motivos.append(f"el receptor ya habría cerrado ({r.horario_cierre})")
        candidatos.append((v, motivos, km1 + km2, minutos(km1) + minutos(km2), recoger, entrega))

    viables = sorted((c for c in candidatos if not c[1]), key=lambda c: (c[3], c[0].id))
    if not viables:
        d.estado, d.voluntario_id, d.voluntario, d.propuesta_vence_en = Estado.SIN_VOLUNTARIO, None, None, None
        motivos = "; ".join(f"{c[0].nombre}: {c[1][0]}" for c in candidatos)
        evento(db, d.id, NOMBRE, f"Ningún voluntario puede hacer la recolección. {motivos}")
        avisar_donante(db, d, NOMBRE, "Tu donación ya tiene receptor, pero aún no encuentro voluntario.")
        return
    v, _, km, minutos_ruta, recoger, entrega = viables[0]
    d.voluntario_id, d.voluntario, d.estado = v.id, v, Estado.ASIGNADA
    d.propuesta_vence_en = ahora + timedelta(minutes=VIGENCIA_PROPUESTA_MIN)
    d.ruta = {
        "puntos": [{"rol": "voluntario", "nombre": v.nombre, "lat": v.lat, "lon": v.lon},
                   {"rol": "donante", "nombre": d.donante.nombre, "lat": d.donante.lat, "lon": d.donante.lon},
                   {"rol": "receptor", "nombre": r.nombre, "lat": r.lat, "lon": r.lon}],
        "km": round(km, 1), "minutos": round(minutos_ruta),
        "recoger": recoger.strftime("%H:%M"), "entrega": entrega.strftime("%H:%M"),
    }
    evento(db, d.id, NOMBRE, f"Propuse la recolección a {v.nombre} ({v.vehiculo}): ruta de {km:.1f} km "
           f"(~{minutos_ruta:.0f} min), recoge {d.ruta['recoger']} y entrega {d.ruta['entrega']}. "
           f"Mejor de {len(viables)} voluntarios viables.")


def _condiciones(d: Donacion, ahora: datetime) -> tuple:
    return (Donacion.voluntario_id == d.voluntario_id,
            or_(Donacion.propuesta_vence_en.is_(None), Donacion.propuesta_vence_en > ahora))


def responder(db: Session, d: Donacion, aceptar: bool, ahora: datetime | None = None, voluntario_id: int | None = None) -> None:
    """Respuesta del voluntario. ``voluntario_id`` (opcional) es quien responde; si no es el propuesto, se rechaza."""
    ahora = ahora or reloj.ahora()
    if d.estado != Estado.ASIGNADA or d.voluntario is None:
        raise ValueError(f"La donación #{d.id} no tiene una propuesta de recolección pendiente ({d.estado})")
    if voluntario_id is not None and voluntario_id != d.voluntario_id:
        raise ValueError(f"La recolección de la donación #{d.id} está propuesta a otro voluntario")
    if not propuesta_vigente(d, ahora):
        raise ValueError(f"La propuesta de recolección de la donación #{d.id} venció a las {d.propuesta_vence_en:%H:%M}")
    v = d.voluntario
    if aceptar:
        transicionar(db, d, Estado.ASIGNADA, {"estado": Estado.EN_RECOLECCION, "propuesta_vence_en": None},
                     *_condiciones(d, ahora))
        evento(db, d.id, NOMBRE, f"{v.nombre} aceptó la recolección.")
        avisar_donante(db, d, NOMBRE, f"{v.nombre} ({v.vehiculo}) pasará por tu donación hacia las {d.ruta['recoger']} "
                       f"y la llevará a {d.receptor.nombre}.")
    else:
        transicionar(db, d, Estado.ASIGNADA, {"voluntario_id": None, "propuesta_vence_en": None}, *_condiciones(d, ahora))
        d.rechazos_voluntarios = [*d.rechazos_voluntarios, v.id]
        evento(db, d.id, NOMBRE, f"{v.nombre} rechazó la recolección.")


def expirar(db: Session, d: Donacion, ahora: datetime) -> bool:
    """Retira una propuesta vencida y anota al voluntario como si la hubiera rechazado. False si alguien se adelantó."""
    v = d.voluntario
    try:
        transicionar(db, d, Estado.ASIGNADA, {"voluntario_id": None, "propuesta_vence_en": None},
                     Donacion.voluntario_id == d.voluntario_id, Donacion.propuesta_vence_en <= ahora)
    except ValueError:
        return False
    d.rechazos_voluntarios = [*d.rechazos_voluntarios, v.id]
    evento(db, d.id, NOMBRE, f"La propuesta a {v.nombre} venció sin respuesta ({VIGENCIA_PROPUESTA_MIN} min).")
    return True


def avanzar(db: Session, d: Donacion, nuevo: str, ahora: datetime, voluntario_id: int | None = None) -> None:
    """El voluntario avisa que ``recogida`` o ``entregada`` la donación (no se pueden saltar pasos)."""
    if voluntario_id is not None and voluntario_id != d.voluntario_id:
        raise ValueError(f"La donación #{d.id} la lleva otro voluntario")
    v = d.voluntario
    pasos = {"recogida": (Estado.EN_RECOLECCION, Estado.EN_CAMINO), "entregada": (Estado.EN_CAMINO, Estado.ENTREGADA)}
    if nuevo not in pasos or d.estado != pasos[nuevo][0]:
        raise ValueError(f"No se puede pasar de '{d.estado}' a '{nuevo}'")
    desde, hacia = pasos[nuevo]
    transicionar(db, d, desde, {"estado": hacia}, error=f"La donación #{d.id} ya se marcó como '{nuevo}' o cambió de estado")
    if nuevo == "recogida":
        evento(db, d.id, NOMBRE, f"{v.nombre} recogió la donación en {d.donante.nombre}.")
        avisar_donante(db, d, NOMBRE, f"{v.nombre} ya recogió tu donación y va rumbo a {d.receptor.nombre}. ¡Gracias!")
    else:
        evento(db, d.id, NOMBRE, f"{v.nombre} entregó la donación; falta que {d.receptor.nombre} confirme.")
