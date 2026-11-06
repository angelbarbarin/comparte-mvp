"""Agente Coordinador (CP-03 perfil de receptores y CP-04 asignación).

Elige al receptor para cada donación y deja guardado POR QUÉ: el ranking de todos los receptores con su
puntaje desglosado y el motivo de cada descarte.

1. Filtros (el receptor se descarta y se anota el motivo): ya rechazó esta donación; no tiene cadena de
   frío cuando hace falta; no le queda capacidad hoy; cerraría antes de que llegue; o la donación
   caducaría antes de llegar.
2. Puntaje 0-100 = 40 % necesidad + 30 % cercanía + 30 % capacidad (``PESOS``). La necesidad pondera los
   kg que el receptor necesita según su prioridad (1 a 3) por categoría de alimento.

Limitaciones del MVP: una donación va a un solo receptor; no hay tiempo límite de respuesta ni
componente de equidad entre receptores (pendientes en el plan del equipo).
"""

from datetime import datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..conocimiento import distancia_km, minutos
from ..modelos import Donacion, Estado, Receptor
from .base import avisar_donante, evento

NOMBRE = "coordinador"
PESOS = {"necesidad": 0.4, "cercania": 0.3, "capacidad": 0.3}
PREPARACION_MIN = 20  # minutos asumidos hasta que el voluntario recoge
MARGEN_MIN = 30  # la entrega debe llegar al menos 30 min antes de caducar
DISTANCIA_MAX_KM = 30.0


def _comprometido_hoy(db: Session, r: Receptor, ahora: datetime, solo_frio: bool) -> float:
    """kg que ya tiene asignados hoy (o reservados por una oferta pendiente)."""
    inicio = datetime.combine(ahora.date(), time.min)
    donaciones = db.scalars(select(Donacion).where(Donacion.receptor_id == r.id)).all()
    total = 0.0
    for d in donaciones:
        reservado = d.estado == Estado.OFRECIDA
        asignado = d.estado in Estado.COMPROMETIDOS and d.asignada_en and d.asignada_en >= inicio
        if (reservado or asignado) and (d.requiere_frio or not solo_frio):
            total += d.total_kg
    return total


def evaluar(db: Session, d: Donacion, ahora: datetime) -> list:
    """Ranking de todos los receptores: primero los viables, de mayor a menor puntaje."""
    recogida = ahora + timedelta(minutes=PREPARACION_MIN)
    candidatos = []
    for r in db.scalars(select(Receptor).order_by(Receptor.id)):
        km = distancia_km(d.donante.lat, d.donante.lon, r.lat, r.lon)
        llegada = recogida + timedelta(minutes=minutos(km))
        disponible = (r.capacidad_frio_kg if d.requiere_frio else r.capacidad_diaria_kg) \
            - _comprometido_hoy(db, r, ahora, d.requiere_frio)
        hh, mm = (int(x) for x in r.horario_cierre.split(":"))
        motivos = []
        if r.id in d.rechazos_receptores:
            motivos.append("ya rechazó esta donación")
        if d.requiere_frio and r.capacidad_frio_kg <= 0:
            motivos.append("sin refrigeración (la donación requiere cadena de frío)")
        elif disponible < d.total_kg:
            motivos.append(f"capacidad insuficiente (le quedan {max(disponible, 0):.0f} kg hoy)")
        if llegada > datetime.combine(llegada.date(), time(hh, mm)):
            motivos.append(f"cerrado al llegar (cierra a las {r.horario_cierre})")
        elif llegada + timedelta(minutes=MARGEN_MIN) > d.caduca_en:
            motivos.append("no llegaría antes de que caduque")

        necesidad = sum((it["kg"] or 0) * r.necesidades.get(it["categoria"], 0) / 3 for it in d.items) / d.total_kg
        comp = {"necesidad": necesidad, "cercania": max(0.0, 1 - km / DISTANCIA_MAX_KM),
                "capacidad": max(0.0, min(1.0, disponible / (2 * d.total_kg)))}
        candidatos.append({
            "receptor_id": r.id, "nombre": r.nombre, "viable": not motivos, "motivos": motivos,
            "puntaje": round(100 * sum(PESOS[k] * v for k, v in comp.items()), 1),
            "componentes": {k: round(v, 2) for k, v in comp.items()},
            "distancia_km": round(km, 1), "llegada": llegada.strftime("%H:%M"), "disponible_kg": round(max(disponible, 0)),
        })
    candidatos.sort(key=lambda c: (not c["viable"], -c["puntaje"], c["distancia_km"]))
    return candidatos


def ofrecer(db: Session, d: Donacion, ahora: datetime) -> None:
    """Ofrece la donación al mejor receptor viable. Si no hay ninguno, queda ``sin_receptor``."""
    candidatos = evaluar(db, d, ahora)
    d.evaluacion = candidatos
    viables = [c for c in candidatos if c["viable"]]
    if not viables:
        d.estado, d.receptor_id = Estado.SIN_RECEPTOR, None
        evento(db, d.id, NOMBRE, "Ningún receptor es viable para esta donación.")
        avisar_donante(db, d, NOMBRE, "Por ahora no encontré un receptor que pueda recibir tu donación a tiempo.")
        return
    mejor = viables[0]
    d.receptor_id, d.estado = mejor["receptor_id"], Estado.OFRECIDA
    d.receptor = db.get(Receptor, mejor["receptor_id"])
    c = mejor["componentes"]
    evento(db, d.id, NOMBRE,
           f"Ofrecí la donación a {mejor['nombre']} (puntaje {mejor['puntaje']:.0f}/100: necesidad {c['necesidad']:.0%}, "
           f"cercanía {c['cercania']:.0%}, capacidad {c['capacidad']:.0%}). Mejor de {len(viables)} receptores viables.")
    avisar_donante(db, d, NOMBRE, f"Ofrecí tu donación a {mejor['nombre']}. Te aviso cuando responda.")


def responder(db: Session, d: Donacion, aceptar: bool, ahora: datetime) -> None:
    if d.estado != Estado.OFRECIDA:
        raise ValueError(f"La donación #{d.id} no está ofrecida ({d.estado})")
    nombre = d.receptor.nombre
    if aceptar:
        d.estado, d.asignada_en = Estado.ASIGNADA, ahora
        evento(db, d.id, NOMBRE, f"{nombre} aceptó la donación.")
        avisar_donante(db, d, NOMBRE, f"{nombre} aceptó tu donación. Ahora busco quién la recoja.")
    else:
        d.rechazos_receptores = [*d.rechazos_receptores, d.receptor_id]
        d.receptor_id, d.receptor = None, None
        evento(db, d.id, NOMBRE, f"{nombre} rechazó la donación.")
