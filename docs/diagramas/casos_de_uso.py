"""Genera el diagrama UML de casos de uso de ComParte (casos_de_uso.svg).

Mermaid no tiene diagrama de casos de uso, así que este script dibuja el SVG con la notación UML: actores como monigotes,
casos de uso como elipses dentro del límite del sistema, asociaciones con línea continua y «include» / «extend» con
flecha punteada. Uso: ``python docs/diagramas/casos_de_uso.py`` (solo usa la biblioteca estándar).
"""

import math
from pathlib import Path
from xml.sax.saxutils import escape

ANCHO, ALTO = 1600, 1020
SISTEMA = (250, 70, 1100, 880)  # x, y, ancho, alto del límite del sistema
FUENTE = "Inter, 'Segoe UI', Helvetica, Arial, sans-serif"
RX, RY = 132, 34
PASILLOS = (955, 995)  # x libres entre la columna de agentes y la de receptor/voluntario, para rutear flechas largas

# Casos de uso: clave -> (x, y, texto, característica, agente que lo realiza o None si lo inicia una persona)
CASOS = {
    "corregir": (440, 145, "Corregir, cancelar o\nempezar de nuevo", "CP-01", None),
    "registrar": (440, 285, "Registrar donación\npor chat", "CP-01", None),
    "seguimiento": (440, 420, "Consultar seguimiento\nde la donación", "CP-06", None),
    "tablero": (440, 550, "Consultar tablero\nde impacto", "CP-07", None),
    "validar": (440, 700, "Validar alimentos\nde riesgo", "CP-02 · CP-09", None),
    "reiniciar": (440, 830, "Reiniciar datos\nde demostración", "CP-09", None),
    "inocuidad": (800, 145, "Evaluar inocuidad", "CP-02", "Agente Captador"),
    "asignar": (800, 355, "Asignar receptor", "CP-04", "Agente Coordinador"),
    "planear": (800, 560, "Planear recolección\ny ruta", "CP-05", "Agente Logístico"),
    "impacto": (800, 760, "Registrar impacto", "CP-07", "Agente de Impacto"),
    "oferta": (1160, 230, "Responder oferta\nde donación", "CP-04", None),
    "confirmar": (1160, 370, "Confirmar recepción\ncon kg reales", "CP-07", None),
    "propuesta": (1160, 530, "Responder propuesta\nde recolección", "CP-05", None),
    "avance": (1160, 665, "Actualizar avance\n(recogida, entregada)", "CP-05 · CP-06", None),
    "vencer": (1160, 830, "Reasignar ofertas\ny propuestas vencidas", "CP-04 · CP-05", "Orquestador"),
}

ACTORES = {  # clave -> (x, y de la cabeza, nombre)
    "donante": (110, 330, "Donante"),
    "admin": (110, 715, "Administrador"),
    "receptor": (1490, 245, "Receptor"),
    "voluntario": (1490, 540, "Voluntario"),
    "tiempo": (1490, 790, "Tiempo"),
}

ASOCIACIONES = [
    ("donante", "registrar"), ("donante", "corregir"), ("donante", "seguimiento"), ("donante", "tablero"),
    ("admin", "validar"), ("admin", "reiniciar"), ("admin", "tablero"),
    ("receptor", "oferta"), ("receptor", "confirmar"),
    ("voluntario", "propuesta"), ("voluntario", "avance"),
    ("tiempo", "vencer"),
]

# (desde, hacia, estereotipo, puntos intermedios, posición de la etiqueta: (segmento, 0..1, dx, dy))
DEPENDENCIAS = [
    ("registrar", "inocuidad", "include", [], (0, .5, 0, 0)),
    ("registrar", "asignar", "include", [], (0, .5, 0, 0)),
    ("corregir", "registrar", "extend", [], (0, .55, 58, 12)),
    ("oferta", "planear", "include", [], (0, .7, 0, 0)),
    ("confirmar", "impacto", "include", [], (0, .8, 0, 0)),
    ("vencer", "asignar", "include", [(PASILLOS[0], 830), (PASILLOS[0], 355)], (1, .274, 0, 0)),
    ("vencer", "planear", "include", [(PASILLOS[1], 830), (PASILLOS[1], 560)], (1, .222, 0, 0)),
]


def borde_elipse(cx, cy, hacia_x, hacia_y, rx=RX, ry=RY):
    """Punto del borde de la elipse en dirección a (hacia_x, hacia_y)."""
    dx, dy = hacia_x - cx, hacia_y - cy
    if dx == dy == 0:
        return cx, cy
    t = 1 / math.sqrt((dx / rx) ** 2 + (dy / ry) ** 2)
    return cx + dx * t, cy + dy * t


def texto(x, y, contenido, tam=15, peso=500, color="#1d2b24", ancla="middle", extra=""):
    lineas = contenido.split("\n")
    alto = tam * 1.25
    y0 = y - (len(lineas) - 1) * alto / 2
    tspans = "".join(f'<tspan x="{x:.1f}" y="{y0 + i * alto:.1f}">{escape(l)}</tspan>' for i, l in enumerate(lineas))
    return (f'<text font-family="{FUENTE}" font-size="{tam}" font-weight="{peso}" fill="{color}" text-anchor="{ancla}" '
            f'dominant-baseline="middle" {extra}>{tspans}</text>')


def actor(x, y, nombre):
    c = "#1d2b24"
    return (f'<g stroke="{c}" stroke-width="2.2" fill="none" stroke-linecap="round">'
            f'<circle cx="{x}" cy="{y}" r="15" fill="#ffffff"/>'
            f'<line x1="{x}" y1="{y + 15}" x2="{x}" y2="{y + 60}"/>'
            f'<line x1="{x - 28}" y1="{y + 32}" x2="{x + 28}" y2="{y + 32}"/>'
            f'<line x1="{x}" y1="{y + 60}" x2="{x - 22}" y2="{y + 95}"/>'
            f'<line x1="{x}" y1="{y + 60}" x2="{x + 22}" y2="{y + 95}"/></g>'
            + texto(x, y + 118, nombre, tam=16, peso=700))


def punto_actor(clave, hacia_x):
    x, y, _ = ACTORES[clave]
    return (x + (34 if hacia_x > x else -34), y + 40)


def generar() -> str:
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{ANCHO}" height="{ALTO}" viewBox="0 0 {ANCHO} {ALTO}">',
         '<defs><marker id="abierta" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="11" markerHeight="11" '
         'orient="auto-start-reverse"><path d="M1,1 L11,6 L1,11" fill="none" stroke="#4a5a52" stroke-width="1.6"/></marker></defs>',
         f'<rect width="{ANCHO}" height="{ALTO}" fill="#ffffff"/>']
    sx, sy, sw, sh = SISTEMA
    p.append(f'<rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" rx="6" fill="#f7faf8" stroke="#1d2b24" stroke-width="2"/>')
    p.append(texto(sx + sw / 2, sy + 26, "ComParte · rescate de alimentos (ODS 2: Hambre cero)", tam=18, peso=700))
    p.append(texto(ANCHO / 2, 30, "Diagrama de casos de uso", tam=24, peso=800, color="#17603a"))

    # Asociaciones actor - caso de uso
    for a, c in ASOCIACIONES:
        cx, cy = CASOS[c][:2]
        ax, ay = punto_actor(a, cx)
        bx, by = borde_elipse(cx, cy, ax, ay)
        p.append(f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" stroke="#1d2b24" stroke-width="1.6"/>')

    # «include» y «extend»: línea punteada con flecha abierta, con puntos intermedios opcionales
    for desde, hacia, tipo, via, (seg, pos, dx, dy) in DEPENDENCIAS:
        x1, y1 = CASOS[desde][:2]
        x2, y2 = CASOS[hacia][:2]
        primero = via[0] if via else (x2, y2)
        ultimo = via[-1] if via else (x1, y1)
        puntos = [borde_elipse(x1, y1, *primero), *via, borde_elipse(x2, y2, *ultimo)]
        trazo = " ".join(f"{x:.1f},{y:.1f}" for x, y in puntos)
        p.append(f'<polyline points="{trazo}" fill="none" stroke="#4a5a52" stroke-width="1.5" '
                 f'stroke-dasharray="7 5" marker-end="url(#abierta)"/>')
        (ax, ay), (bx, by) = puntos[seg], puntos[seg + 1]
        lx, ly = ax + (bx - ax) * pos + dx, ay + (by - ay) * pos + dy
        p.append(f'<rect x="{lx - 34:.1f}" y="{ly - 10:.1f}" width="68" height="20" rx="4" fill="#ffffff"/>')
        p.append(texto(lx, ly, f"«{tipo}»", tam=13, peso=600, color="#4a5a52", extra='font-style="italic"'))

    # Casos de uso
    for clave, (x, y, nombre, cp, agente) in CASOS.items():
        auto = agente is not None
        relleno, borde = ("#e6f2ea", "#17603a") if auto else ("#ffffff", "#1d2b24")
        p.append(f'<ellipse cx="{x}" cy="{y}" rx="{RX}" ry="{RY}" fill="{relleno}" stroke="{borde}" stroke-width="1.8"/>')
        p.append(texto(x, y - (5 if auto else 0), nombre, tam=14.5, peso=600))
        etiqueta = f"{cp} · {agente}" if auto else cp
        dx = 75 if clave == "corregir" else 0  # para no quedar debajo de la flecha «extend»
        p.append(texto(x + dx, y + RY + 12, etiqueta, tam=11.5, peso=500, color="#17603a" if auto else "#6b7a72"))

    # Actores
    for clave, (x, y, nombre) in ACTORES.items():
        p.append(actor(x, y, nombre))

    # Leyenda
    lx, ly = 270, ALTO - 50
    p.append(f'<ellipse cx="{lx + 26}" cy="{ly}" rx="24" ry="11" fill="#ffffff" stroke="#1d2b24" stroke-width="1.5"/>')
    p.append(texto(lx + 60, ly, "Lo inicia una persona", tam=13, ancla="start"))
    p.append(f'<ellipse cx="{lx + 26}" cy="{ly + 30}" rx="24" ry="11" fill="#e6f2ea" stroke="#17603a" stroke-width="1.5"/>')
    p.append(texto(lx + 60, ly + 30, "Lo realiza un agente de forma automática", tam=13, ancla="start"))
    p.append(texto(ANCHO - 270, ALTO - 35, "CP-xx: característica del documento de Visión y Alcances",
                   tam=12, color="#6b7a72", ancla="end"))
    p.append("</svg>")
    return "\n".join(p)


if __name__ == "__main__":
    destino = Path(__file__).with_name("casos_de_uso.svg")
    destino.write_text(generar(), encoding="utf-8")
    print(f"Escrito {destino}")
