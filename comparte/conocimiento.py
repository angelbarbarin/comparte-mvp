"""Conocimiento de dominio: catálogo de alimentos, reglas de inocuidad y factores de impacto.

⚠️  Son supuestos del equipo, pendientes de validar con un banco de alimentos real:
* Las reglas de inocuidad son heurísticas, **no una certificación sanitaria**.
* ``KG_POR_RACION``, ``RACIONES_POR_PERSONA_DIA`` y los factores de CO2e (kg de CO2e por kg de alimento,
  valores de referencia aproximados de la huella de producción) se tomaron de memoria, sin verificar.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from math import asin, cos, radians, sin, sqrt

KG_POR_RACION = 0.5
RACIONES_POR_PERSONA_DIA = 3.0

CATEGORIAS = {
    "pan": "Pan y tortilla", "fruta": "Fruta", "verdura": "Verdura", "abarrotes": "Abarrotes y bebidas",
    "lacteos": "Lácteos", "proteina": "Proteína", "preparado": "Comida preparada", "otro": "Otros",
}


def normalizar(texto: str) -> str:
    """Minúsculas y sin acentos."""
    t = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


@dataclass(frozen=True)
class Alimento:
    clave: str
    categoria: str
    almacenamiento: str  # ambiente | refrigerado | preparado
    riesgo: str  # bajo | alto
    vida_util_horas: float  # si el donante no da la caducidad
    kg_pieza: float
    co2e_por_kg: float
    sinonimos: tuple = field(default_factory=tuple)


def _a(clave, categoria, almacenamiento, riesgo, horas, kg_pieza, co2e, *sinonimos):
    return Alimento(clave, categoria, almacenamiento, riesgo, horas, kg_pieza, co2e, sinonimos)


_ALIMENTOS = [
    _a("pan", "pan", "ambiente", "bajo", 24, 0.07, 1.6,
       "pan dulce", "pan del dia", "pan de caja", "pan", "bolillo", "telera", "concha", "dona"),
    _a("tortilla", "pan", "ambiente", "bajo", 24, 0.03, 1.7, "tortilla"),
    _a("fruta", "fruta", "ambiente", "bajo", 48, 0.2, 0.8,
       "fruta", "manzana", "platano", "naranja", "mango", "papaya", "sandia", "melon", "uva", "limon",
       "fresa", "pera", "durazno", "pina", "guayaba", "aguacate"),
    _a("verdura", "verdura", "ambiente", "bajo", 72, 0.2, 0.7,
       "verdura", "jitomate", "tomate", "cebolla", "papa", "zanahoria", "lechuga", "calabacita",
       "chayote", "nopal", "chile", "espinaca", "brocoli", "cilantro", "pepino", "elote"),
    _a("abarrotes", "abarrotes", "ambiente", "bajo", 90 * 24, 0.5, 2.0,
       "abarrotes", "arroz", "frijol", "lenteja", "pasta", "aceite", "azucar", "harina", "avena",
       "cereal", "galleta", "enlatado", "atun", "sardina", "jugo", "agua", "refresco"),
    _a("lacteos", "lacteos", "refrigerado", "alto", 72, 0.25, 6.0,
       "leche", "yogurt", "yogur", "queso", "crema", "mantequilla"),
    _a("pollo", "proteina", "refrigerado", "alto", 24, 1.5, 9.9, "pollo"),
    _a("carne", "proteina", "refrigerado", "alto", 24, 1.0, 20.0,
       "carne", "res", "cerdo", "puerco", "pescado", "jamon", "salchicha", "chorizo"),
    _a("preparado", "preparado", "preparado", "alto", 4, 0.4, 3.0,
       "comida preparada", "guisado", "tamal", "pozole", "sopa", "ensalada", "pizza", "hamburguesa",
       "taco", "caldo", "torta", "comida"),
    _a("no_aceptado", "otro", "ambiente", "alto", 0, 0.0, 0.0,
       "cerveza", "vino", "tequila", "alcohol", "medicina", "medicamento", "cigarro"),
]
CATALOGO = {a.clave: a for a in _ALIMENTOS}

_INDICE = {s: a for a in _ALIMENTOS for s in a.sinonimos}
_PATRON_ALIMENTO = re.compile(
    r"(?<![a-z0-9])(" + "|".join(re.escape(s) for s in sorted(_INDICE, key=len, reverse=True)) + r")(?:es|s)?(?![a-z0-9])"
)


def buscar_alimentos(texto_normalizado: str):
    """[(alimento, inicio, fin)] mencionados en el texto, ya normalizado."""
    return [(_INDICE[m.group(1)], m.start(), m.end()) for m in _PATRON_ALIMENTO.finditer(texto_normalizado)]


# ----------------------------------------------------------------------------------------- unidades
_UNIDADES = {
    "kg": ("kg", "kgs", "kilo", "kilos", "kilogramo", "kilogramos"), "g": ("g", "gr", "gramo", "gramos"),
    "l": ("l", "lt", "litro", "litros"), "pieza": ("pieza", "piezas", "pza", "pzas", "pz"),
    "docena": ("docena", "docenas"), "caja": ("caja", "cajas"), "bolsa": ("bolsa", "bolsas"),
    "charola": ("charola", "charolas"), "costal": ("costal", "costales"),
}
UNIDAD_CANONICA = {s: u for u, ss in _UNIDADES.items() for s in ss}
_KG_GENERICO = {"caja": 10.0, "bolsa": 1.0, "charola": 3.0, "costal": 25.0}


def a_kg(cantidad: float, unidad: str, alimento: Alimento) -> float:
    """Convierte a kg. Piezas, cajas, etc. son estimaciones (el Captador se lo muestra al donante)."""
    if unidad == "kg" or unidad == "l":
        return cantidad
    if unidad == "g":
        return cantidad / 1000.0
    if unidad == "pieza":
        return cantidad * alimento.kg_pieza
    if unidad == "docena":
        return cantidad * 12 * alimento.kg_pieza
    return cantidad * _KG_GENERICO.get(unidad, 1.0)


# --------------------------------------------------------------------------------------- inocuidad
@dataclass
class Evaluacion:
    bloqueada: bool = False
    requiere_revision: bool = False
    requiere_frio: bool = False
    motivos: list = field(default_factory=list)


def evaluar_inocuidad(items: list, mal_estado: bool = False) -> Evaluacion:
    """Bloquea lo que no puede donarse y marca lo que necesita revisión humana.

    * Se bloquea: alcohol/medicamentos/tabaco y alimentos en mal estado.
    * Pide revisión humana: carnes, lácteos y comida preparada (riesgo alto).
    * Requiere cadena de frío: los alimentos refrigerados.
    """
    ev = Evaluacion()
    for it in items:
        if it["clave"] == "no_aceptado":
            ev.bloqueada = True
            ev.motivos.append(f"'{it['nombre']}' no se acepta: ComParte no gestiona alcohol, medicamentos ni tabaco.")
        elif it["riesgo"] == "alto":
            ev.requiere_revision = True
            ev.motivos.append(f"'{it['nombre']}' es un alimento de riesgo: una persona debe validarlo.")
        if it["almacenamiento"] == "refrigerado":
            ev.requiere_frio = True
    if mal_estado:
        ev.bloqueada = True
        ev.motivos.append("El donante reporta alimento en mal estado.")
    return ev


# ------------------------------------------------------------------------------------------ geografía
def distancia_km(lat1, lon1, lat2, lon2, factor_calles: float = 1.3) -> float:
    """Distancia por calles estimada: Haversine x 1.3 (el MVP no usa API de mapas)."""
    f1, f2 = radians(lat1), radians(lat2)
    a = sin((f2 - f1) / 2) ** 2 + cos(f1) * cos(f2) * sin(radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * asin(sqrt(a)) * factor_calles


def minutos(km: float, velocidad_kmh: float = 25.0) -> float:
    return km / velocidad_kmh * 60.0
