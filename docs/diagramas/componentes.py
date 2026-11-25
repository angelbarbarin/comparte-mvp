"""Genera el diagrama UML de componentes de ComParte (componentes.svg).

Notación UML: cada componente es una caja con el ícono de componente; una interfaz que el componente **ofrece** es un
círculo unido con línea continua; quien la **requiere** apunta al círculo con una flecha punteada («usa»).
Uso: ``python docs/diagramas/componentes.py`` (solo usa la biblioteca estándar).
"""

import math
from pathlib import Path

from casos_de_uso import FUENTE, texto

ANCHO, ALTO = 1720, 880
VERDE, TINTA, GRIS = "#17603a", "#1d2b24", "#4a5a52"

# Componentes: clave -> (x, y, ancho, alto, estereotipo, nombre, detalle, es agente)
COMP = {
    "web": (60, 250, 210, 76, "componente", "Interfaz web", "web/ · HTML, CSS y JS", False),
    "osm": (60, 640, 210, 64, "externo", "OpenStreetMap", "mosaicos del mapa", False),
    "api": (380, 250, 200, 76, "componente", "API REST", "api.py · roles, modo demo", False),
    "auth": (365, 520, 230, 76, "componente", "Autenticación por roles", "auth.py · X-Comparte-Token", False),
    "orq": (700, 250, 220, 76, "componente", "Orquestador", "orquestador.py · transiciones atómicas", True),
    "cap": (985, 150, 200, 64, "agente", "Captador", "registro conversacional", True),
    "coo": (985, 265, 200, 64, "agente", "Coordinador", "elige receptor", True),
    "lgs": (985, 380, 200, 64, "agente", "Logístico", "voluntario y ruta", True),
    "imp": (985, 495, 200, 64, "agente", "Impacto", "kg, raciones, CO2e", True),
    "nlu": (1285, 120, 235, 70, "componente", "Comprensión de lenguaje", "nlu.py · reglas", False),
    "con": (1285, 275, 235, 70, "componente", "Base de conocimiento", "conocimiento.py · catálogo", False),
    "per": (1285, 455, 235, 70, "componente", "Persistencia", "modelos.py, db.py · SQLAlchemy", False),
    "rel": (1285, 640, 235, 70, "componente", "Reloj", "reloj.py · hora de demo", False),
    "db": (1560, 455, 130, 70, "base de datos", "SQLite", "data/comparte.db", False),
}

# Interfaces ofrecidas: clave -> (x, y, etiqueta, componente que la ofrece, lado de la etiqueta)
INTER = {
    "http": (325, 288, "HTTP /api (JSON)", "api", "arriba"),
    "rol": (480, 440, "requiere(rol)", "auth", "der"),
    "flujo": (640, 288, "flujo de\nla donación", "orq", "arriba"),
    "nlu": (1245, 155, "interpretar()", "nlu", "arriba"),
    "con": (1245, 310, "catálogo e\ninocuidad", "con", "arriba"),
    "orm": (1245, 490, "modelos ORM", "per", "arriba"),
    "rel": (1245, 675, "ahora()", "rel", "arriba"),
    "sql": (1540, 490, "SQL", "db", "arriba"),
    "tiles": (165, 590, "mosaicos", "osm", "der"),
}

# Dependencias «usa»: (componente, interfaz o componente destino, puntos intermedios)
USA = [
    ("web", "http", []), ("web", "tiles", []),
    ("api", "rol", []), ("api", "flujo", []),
    ("orq", "cap", [(940, 288), (940, 182)]), ("orq", "coo", [(940, 288), (940, 297)]),
    ("orq", "lgs", [(940, 288), (940, 412)]), ("orq", "imp", [(940, 288), (940, 527)]),
    ("cap", "nlu", []),
    ("agentes", "con", []), ("agentes", "orm", []),
    ("orq", "orm", [(810, 640), (1245, 640)]),
    ("orq", "rel", [(810, 675)]),
    ("per", "sql", []),
]
R = 9  # radio del círculo de interfaz
SUBSISTEMA = (955, 105, 260, 480)  # caja «subsistema» Agentes: también puede ser origen de una dependencia


def centro(clave):
    if clave in INTER:
        return INTER[clave][:2]
    x, y, w, h = SUBSISTEMA if clave == "agentes" else COMP[clave][:4]
    return x + w / 2, y + h / 2


def borde(clave, hacia):
    """Punto del borde (caja o círculo) en dirección a ``hacia``."""
    cx, cy = centro(clave)
    dx, dy = hacia[0] - cx, hacia[1] - cy
    if dx == dy == 0:
        return cx, cy
    if clave in INTER:
        d = math.hypot(dx, dy)
        return cx + dx / d * R, cy + dy / d * R
    _, _, w, h = SUBSISTEMA if clave == "agentes" else COMP[clave][:4]
    t = min(w / 2 / abs(dx) if dx else math.inf, h / 2 / abs(dy) if dy else math.inf)
    return cx + dx * t, cy + dy * t


def icono_componente(x, y, color):
    return (f'<g stroke="{color}" stroke-width="1.3" fill="#ffffff"><rect x="{x}" y="{y}" width="18" height="22" rx="1"/>'
            f'<rect x="{x - 5}" y="{y + 4}" width="10" height="5"/><rect x="{x - 5}" y="{y + 13}" width="10" height="5"/></g>')


def componente(clave):
    x, y, w, h, estereo, nombre, detalle, agente = COMP[clave]
    cx = x + w / 2
    if clave == "db":  # cilindro
        e = 9
        return (f'<path d="M{x},{y + e} v{h - 2 * e} a{w / 2},{e} 0 0 0 {w},0 v-{h - 2 * e}" fill="#ffffff" stroke="{TINTA}" stroke-width="1.5"/>'
                f'<ellipse cx="{cx}" cy="{y + e}" rx="{w / 2}" ry="{e}" fill="#ffffff" stroke="{TINTA}" stroke-width="1.5"/>'
                + texto(cx, y + 32, f"«{estereo}»", tam=11, peso=400, color="#6b7a72")
                + texto(cx, y + 48, nombre, tam=14, peso=700) + texto(cx, y + 63, detalle, tam=10, peso=400, color="#6b7a72"))
    relleno, color = ("#e6f2ea", VERDE) if agente else ("#ffffff", TINTA)
    cx = x + (w - 30) / 2  # el texto se centra en el espacio que deja libre el ícono
    guion = ' stroke-dasharray="6 4"' if estereo == "externo" else ""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" fill="{relleno}" stroke="{color}" stroke-width="1.6"{guion}/>'
            + icono_componente(x + w - 28, y + 8, color)
            + texto(cx, y + h / 2 - 17, f"«{estereo}»", tam=11, peso=400, color="#6b7a72")
            + texto(cx, y + h / 2, nombre, tam=14, peso=700)
            + texto(cx, y + h / 2 + 17, detalle, tam=10.5, peso=400, color="#6b7a72"))


def generar() -> str:
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{ANCHO}" height="{ALTO}" viewBox="0 0 {ANCHO} {ALTO}">',
         '<defs><marker id="usa" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="10" markerHeight="10" '
         f'orient="auto"><path d="M1,1 L11,6 L1,11" fill="none" stroke="{GRIS}" stroke-width="1.6"/></marker></defs>',
         f'<rect width="{ANCHO}" height="{ALTO}" fill="#ffffff"/>',
         texto(ANCHO / 2, 32, "Diagrama de componentes", tam=24, peso=800, color=VERDE)]

    # Nodos de despliegue (contenedores)
    def caja(x, y, w, h, titulo, guion=False, color="#9aaaa1", fondo="#f7faf8"):
        extra = ' stroke-dasharray="7 5"' if guion else ""
        p.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fondo}" stroke="{color}" stroke-width="1.5"{extra}/>')
        p.append(texto(x + 14, y + 20, titulo, tam=13, peso=700, ancla="start", color=TINTA))

    caja(35, 200, 260, 160, "«dispositivo» Navegador")
    caja(310, 75, 1230, 690, "«servidor» ComParte · Python 3.11+ · FastAPI")
    caja(*SUBSISTEMA, "«subsistema» Agentes", guion=True, color=VERDE, fondo="#ffffff")

    # Interfaces ofrecidas (línea continua)
    for clave, (ix, iy, _, quien, _) in INTER.items():
        a = borde(quien, (ix, iy))
        p.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{ix}" y2="{iy}" stroke="{TINTA}" stroke-width="1.5"/>')

    # Dependencias «usa» (flecha punteada)
    for desde, hacia, via in USA:
        destino = centro(hacia)
        primero = via[0] if via else destino
        ultimo = via[-1] if via else centro(desde)
        pts = [borde(desde, primero), *via, borde(hacia, ultimo)]
        trazo = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        p.append(f'<polyline points="{trazo}" fill="none" stroke="{GRIS}" stroke-width="1.3" stroke-dasharray="6 4" '
                 'marker-end="url(#usa)"/>')

    for clave in INTER:
        ix, iy, etiqueta, _, lado = INTER[clave]
        p.append(f'<circle cx="{ix}" cy="{iy}" r="{R}" fill="#ffffff" stroke="{TINTA}" stroke-width="1.6"/>')
        if lado == "arriba":
            p.append(texto(ix, iy - 19 - 8 * etiqueta.count("\n"), etiqueta, tam=11.5, peso=500, color=TINTA, extra='font-style="italic"'))
        else:
            p.append(texto(ix + 16, iy, etiqueta, tam=11.5, peso=500, color=TINTA, ancla="start", extra='font-style="italic"'))

    for clave in COMP:
        p.append(componente(clave))

    # Leyenda
    ly = ALTO - 70
    p.append(f'<circle cx="60" cy="{ly}" r="{R}" fill="#ffffff" stroke="{TINTA}" stroke-width="1.6"/>'
             f'<line x1="69" y1="{ly}" x2="100" y2="{ly}" stroke="{TINTA}" stroke-width="1.5"/>')
    p.append(texto(112, ly, "Interfaz que ofrece el componente", tam=12.5, ancla="start"))
    p.append(f'<line x1="40" y1="{ly + 30}" x2="96" y2="{ly + 30}" stroke="{GRIS}" stroke-width="1.3" stroke-dasharray="6 4" marker-end="url(#usa)"/>')
    p.append(texto(112, ly + 30, "Dependencia: usa esa interfaz o componente", tam=12.5, ancla="start"))
    p.append(f'<rect x="440" y="{ly - 10}" width="34" height="20" rx="3" fill="#e6f2ea" stroke="{VERDE}" stroke-width="1.5"/>')
    p.append(texto(486, ly, "Toma decisiones del flujo (orquestador y agentes)", tam=12.5, ancla="start"))
    p.append(texto(ANCHO - 40, ly + 30, "Los agentes no se llaman entre sí: el orquestador decide quién actúa.",
                   tam=12.5, color="#6b7a72", ancla="end"))
    p.append("</svg>")
    return "\n".join(p)


if __name__ == "__main__":
    destino = Path(__file__).with_name("componentes.svg")
    destino.write_text(generar(), encoding="utf-8")
    print(f"Escrito {destino}")
