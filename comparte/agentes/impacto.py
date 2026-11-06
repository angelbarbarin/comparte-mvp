"""Agente de Impacto (CP-07 tablero de impacto).

Métricas definidas a partir de las recepciones confirmadas por los receptores:

* kg rescatados: los kg confirmados (o los registrados si no corrigió la cantidad).
* Raciones: kg / 0.5.   * Personas beneficiadas (estimado): raciones / 3 (personas alimentadas un día completo).
* CO2e evitado: kg x factor de emisión de cada alimento.

Los supuestos están en ``conocimiento.py`` y están por validar con un banco de alimentos real.
"""

from collections import defaultdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..conocimiento import CATALOGO, CATEGORIAS, KG_POR_RACION, RACIONES_POR_PERSONA_DIA
from ..modelos import Donacion, Estado
from .base import avisar_donante, evento, fmt_kg

NOMBRE = "impacto"


def metricas(d: Donacion) -> dict:
    """Métricas de una donación; si el receptor confirmó otra cantidad, todo se escala proporcionalmente."""
    escala = (d.kg_recibidos / d.total_kg) if d.kg_recibidos and d.total_kg else 1.0
    kg = d.total_kg * escala
    co2e = sum((i["kg"] or 0) * escala * CATALOGO[i["clave"]].co2e_por_kg for i in d.items)
    raciones = kg / KG_POR_RACION
    return {"kg": round(kg, 1), "raciones": round(raciones, 1),
            "personas": round(raciones / RACIONES_POR_PERSONA_DIA, 1), "co2e_kg": round(co2e, 1)}


def registrar(db: Session, d: Donacion, ahora: datetime) -> dict:
    """Cierra el rescate: calcula su impacto y se lo comunica al donante y a la bitácora."""
    m = metricas(d)
    evento(db, d.id, NOMBRE, f"Impacto: {fmt_kg(m['kg'])} rescatados, {m['raciones']:.0f} raciones, "
           f"≈{m['personas']:.0f} personas, {m['co2e_kg']:.0f} kg de CO2e evitados.")
    avisar_donante(db, d, NOMBRE, f"¡Rescate completado! Tu donación #{d.id} llegó a {d.receptor.nombre}.\n"
                   f"• {fmt_kg(m['kg'])} rescatados\n• {m['raciones']:.0f} raciones\n"
                   f"• ≈{m['personas']:.0f} personas alimentadas un día completo\n• {m['co2e_kg']:.0f} kg de CO2e evitados")
    return m


def resumen(db: Session) -> dict:
    """Tablero: totales, por tipo de alimento, por municipio de origen y últimos rescates."""
    completadas = list(db.scalars(select(Donacion).where(Donacion.estado == Estado.COMPLETADA).order_by(Donacion.id.desc())))
    totales = {"rescates": len(completadas), "kg": 0.0, "raciones": 0.0, "personas": 0.0, "co2e_kg": 0.0}
    por_categoria, por_municipio = defaultdict(float), defaultdict(float)
    ultimos = []
    for d in completadas:
        m = metricas(d)
        for k in ("kg", "raciones", "personas", "co2e_kg"):
            totales[k] += m[k]
        escala = m["kg"] / d.total_kg if d.total_kg else 1
        for i in d.items:
            por_categoria[i["categoria"]] += (i["kg"] or 0) * escala
        por_municipio[d.donante.municipio] += m["kg"]
        if len(ultimos) < 8:
            ultimos.append({"id": d.id, "donante": d.donante.nombre, "receptor": d.receptor.nombre, **m})

    def filas(dic, etiqueta=lambda k: k):
        return sorted(({"etiqueta": etiqueta(k), "kg": round(v, 1)} for k, v in dic.items()), key=lambda f: -f["kg"])

    return {"totales": {k: round(v, 1) if k != "rescates" else v for k, v in totales.items()},
            "por_categoria": filas(por_categoria, lambda c: CATEGORIAS.get(c, c)),
            "por_municipio": filas(por_municipio), "ultimos": ultimos,
            "supuestos": {"kg_por_racion": KG_POR_RACION, "raciones_por_persona_dia": RACIONES_POR_PERSONA_DIA}}
