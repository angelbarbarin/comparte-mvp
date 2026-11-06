"""Agente Logístico (CP-05 coordinación de recolección).

Cuando un receptor acepta, elige al voluntario con la ruta más corta (voluntario -> donante -> receptor)
entre los que cumplan: no estar ocupado con otra donación, vehículo con capacidad, hielera si hay cadena
de frío y llegar a entregar antes de que caduque y antes de que cierre el receptor. Guarda la ruta y los
tiempos estimados. Los voluntarios son simulados y la ruta es una estimación (``distancia_km``).
"""

from datetime import datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..conocimiento import distancia_km, minutos
from ..modelos import Donacion, Estado, Voluntario
from .base import avisar_donante, evento

NOMBRE = "logistico"
SALIDA_MIN = 5  # tiempo para aceptar y salir
CARGA_MIN = 5  # tiempo en cada punto
MARGEN_MIN = 15  # la entrega debe terminar 15 min antes de caducar


def proponer(db: Session, d: Donacion, ahora: datetime) -> None:
    """Propone la recolección al mejor voluntario. Si no hay ninguno, queda ``sin_voluntario``."""
    ocupados = {x.voluntario_id for x in db.scalars(
        select(Donacion).where(Donacion.estado.in_(Estado.CON_VOLUNTARIO), Donacion.id != d.id)) if x.voluntario_id}
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
        d.estado, d.voluntario_id, d.voluntario = Estado.SIN_VOLUNTARIO, None, None
        motivos = "; ".join(f"{c[0].nombre}: {c[1][0]}" for c in candidatos)
        evento(db, d.id, NOMBRE, f"Ningún voluntario puede hacer la recolección. {motivos}")
        avisar_donante(db, d, NOMBRE, "Tu donación ya tiene receptor, pero aún no encuentro voluntario.")
        return
    v, _, km, minutos_ruta, recoger, entrega = viables[0]
    d.voluntario_id, d.voluntario, d.estado = v.id, v, Estado.ASIGNADA
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


def responder(db: Session, d: Donacion, aceptar: bool) -> None:
    if d.estado != Estado.ASIGNADA or d.voluntario is None:
        raise ValueError(f"La donación #{d.id} no tiene una propuesta de recolección pendiente ({d.estado})")
    v = d.voluntario
    if aceptar:
        d.estado = Estado.EN_RECOLECCION
        evento(db, d.id, NOMBRE, f"{v.nombre} aceptó la recolección.")
        avisar_donante(db, d, NOMBRE, f"{v.nombre} ({v.vehiculo}) pasará por tu donación hacia las {d.ruta['recoger']} "
                       f"y la llevará a {d.receptor.nombre}.")
    else:
        d.rechazos_voluntarios = [*d.rechazos_voluntarios, v.id]
        d.voluntario_id, d.voluntario = None, None
        evento(db, d.id, NOMBRE, f"{v.nombre} rechazó la recolección.")


def avanzar(db: Session, d: Donacion, nuevo: str, ahora: datetime) -> None:
    """El voluntario avisa que ``recogida`` o ``entregada`` la donación (no se pueden saltar pasos)."""
    v = d.voluntario
    if nuevo == "recogida" and d.estado == Estado.EN_RECOLECCION:
        d.estado = Estado.EN_CAMINO
        evento(db, d.id, NOMBRE, f"{v.nombre} recogió la donación en {d.donante.nombre}.")
        avisar_donante(db, d, NOMBRE, f"{v.nombre} ya recogió tu donación y va rumbo a {d.receptor.nombre}. ¡Gracias!")
    elif nuevo == "entregada" and d.estado == Estado.EN_CAMINO:
        d.estado = Estado.ENTREGADA
        evento(db, d.id, NOMBRE, f"{v.nombre} entregó la donación; falta que {d.receptor.nombre} confirme.")
    else:
        raise ValueError(f"No se puede pasar de '{d.estado}' a '{nuevo}'")
