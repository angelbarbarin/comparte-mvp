"""Agente Coordinador (CP-03 perfil de receptores y CP-04 asignación).

Elige al receptor para cada donación y deja guardado POR QUÉ: el ranking de todos los receptores con su
puntaje desglosado y el motivo de cada descarte.

1. Filtros (el receptor se descarta y se anota el motivo): ya rechazó esta donación; no tiene cadena de
   frío cuando hace falta; no le queda capacidad hoy; cerraría antes de que llegue; o la donación
   caducaría antes de llegar.
2. Puntaje 0-100 = 40 % necesidad + 30 % cercanía + 30 % capacidad (``PESOS``). La necesidad pondera los
   kg que el receptor necesita según su prioridad (1 a 3) por categoría de alimento.

3. La oferta vence a los ``VIGENCIA_OFERTA_MIN`` minutos. Una oferta vencida deja de apartar capacidad aunque
   nadie la haya expirado todavía, y ``Orquestador.expirar_vencidas`` la pasa al siguiente receptor.

Las respuestas se aplican con ``transicionar`` (``UPDATE ... WHERE estado = :esperado``): con un doble clic solo
la primera cuenta y la segunda recibe un 409.

Limitaciones del MVP: una donación va a un solo receptor y no hay componente de equidad entre receptores.
"""

from datetime import datetime, time, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..conocimiento import distancia_km, minutos
from ..modelos import Donacion, Estado, Receptor
from .base import avisar_donante, evento, transicionar

NOMBRE = "coordinador"
PESOS = {"necesidad": 0.4, "cercania": 0.3, "capacidad": 0.3}
PREPARACION_MIN = 20  # minutos asumidos hasta que el voluntario recoge
MARGEN_MIN = 30  # la entrega debe llegar al menos 30 min antes de caducar
DISTANCIA_MAX_KM = 30.0
VIGENCIA_OFERTA_MIN = 15  # minutos que tiene el receptor para responder


def oferta_vigente(d: Donacion, ahora: datetime) -> bool:
    return d.oferta_vence_en is None or d.oferta_vence_en > ahora


def _comprometido_hoy(db: Session, r: Receptor, ahora: datetime, solo_frio: bool) -> float:
    """kg que ya tiene asignados hoy (o reservados por una oferta pendiente)."""
    inicio = datetime.combine(ahora.date(), time.min)
    donaciones = db.scalars(select(Donacion).where(Donacion.receptor_id == r.id)).all()
    total = 0.0
    for d in donaciones:
        reservado = d.estado == Estado.OFRECIDA and oferta_vigente(d, ahora)  # una oferta vencida ya no aparta
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
        d.estado, d.receptor_id, d.oferta_vence_en = Estado.SIN_RECEPTOR, None, None
        evento(db, d.id, NOMBRE, "Ningún receptor es viable para esta donación.")
        avisar_donante(db, d, NOMBRE, "Por ahora no encontré un receptor que pueda recibir tu donación a tiempo.")
        return
    mejor = viables[0]
    d.receptor_id, d.estado = mejor["receptor_id"], Estado.OFRECIDA
    d.oferta_vence_en = ahora + timedelta(minutes=VIGENCIA_OFERTA_MIN)
    d.receptor = db.get(Receptor, mejor["receptor_id"])
    c = mejor["componentes"]
    evento(db, d.id, NOMBRE,
           f"Ofrecí la donación a {mejor['nombre']} (puntaje {mejor['puntaje']:.0f}/100: necesidad {c['necesidad']:.0%}, "
           f"cercanía {c['cercania']:.0%}, capacidad {c['capacidad']:.0%}). Mejor de {len(viables)} receptores viables.")
    avisar_donante(db, d, NOMBRE, f"Ofrecí tu donación a {mejor['nombre']}. Te aviso cuando responda.")


def _condiciones(d: Donacion, ahora: datetime) -> tuple:
    """La oferta sigue siendo para el mismo receptor y no ha vencido (se revisa en el mismo UPDATE)."""
    return (Donacion.receptor_id == d.receptor_id,
            or_(Donacion.oferta_vence_en.is_(None), Donacion.oferta_vence_en > ahora))


def responder(db: Session, d: Donacion, aceptar: bool, ahora: datetime, receptor_id: int | None = None) -> None:
    """Respuesta del receptor a la oferta. ``receptor_id`` (opcional) es quien responde: si no es el receptor
    ofrecido, se rechaza la petición (la API con roles lo pasa)."""
    if d.estado != Estado.OFRECIDA:
        raise ValueError(f"La donación #{d.id} no está ofrecida ({d.estado})")
    if receptor_id is not None and receptor_id != d.receptor_id:
        raise ValueError(f"La oferta de la donación #{d.id} es para otro receptor")
    if not oferta_vigente(d, ahora):
        raise ValueError(f"La oferta de la donación #{d.id} venció a las {d.oferta_vence_en:%H:%M}")
    rid, nombre = d.receptor_id, d.receptor.nombre
    if aceptar:
        transicionar(db, d, Estado.OFRECIDA, {"estado": Estado.ASIGNADA, "asignada_en": ahora, "oferta_vence_en": None},
                     *_condiciones(d, ahora))
        evento(db, d.id, NOMBRE, f"{nombre} aceptó la donación.")
        avisar_donante(db, d, NOMBRE, f"{nombre} aceptó tu donación. Ahora busco quién la recoja.")
    else:
        transicionar(db, d, Estado.OFRECIDA, {"estado": Estado.REGISTRADA, "receptor_id": None, "oferta_vence_en": None},
                     *_condiciones(d, ahora))
        d.rechazos_receptores = [*d.rechazos_receptores, rid]
        evento(db, d.id, NOMBRE, f"{nombre} rechazó la donación.")


def expirar(db: Session, d: Donacion, ahora: datetime) -> bool:
    """Retira una oferta vencida y anota al receptor como si hubiera rechazado. False si alguien se adelantó."""
    rid, nombre = d.receptor_id, d.receptor.nombre if d.receptor else "el receptor"
    try:
        transicionar(db, d, Estado.OFRECIDA, {"estado": Estado.REGISTRADA, "receptor_id": None, "oferta_vence_en": None},
                     Donacion.receptor_id == rid, Donacion.oferta_vence_en <= ahora)
    except ValueError:
        return False
    d.rechazos_receptores = [*d.rechazos_receptores, rid]
    evento(db, d.id, NOMBRE, f"La oferta a {nombre} venció sin respuesta ({VIGENCIA_OFERTA_MIN} min).")
    return True
