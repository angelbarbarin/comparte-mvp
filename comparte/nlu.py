"""Comprensión de lenguaje por reglas (sin LLM, sin internet, determinista).

Interpreta mensajes como "Tengo 25 kg de pan dulce del día y 3 cajas de jitomate, caduca mañana" con
expresiones regulares y el catálogo de alimentos. Entiende un subconjunto del español coloquial:

* cantidades con unidad ("25 kg", "3 cajas", "media docena") y número pegado al alimento ("40 bolillos" = piezas),
* caducidad: "caduca hoy / mañana / en 3 horas / en 2 días" y "del día",
* intención: donar, confirmar ("sí"), negar ("no") o cancelar,
* alimento en mal estado ("tiene moho", "está echado a perder").

Limitaciones conocidas: no reconoce alimentos fuera del catálogo, ni horarios de recolección, ni fotos.
En el siguiente ciclo se puede sustituir por un LLM sin cambiar al Captador (misma salida: ``Interpretacion``).
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .conocimiento import UNIDAD_CANONICA, buscar_alimentos, normalizar

NUMEROS = {"un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7,
           "ocho": 8, "nueve": 9, "diez": 10, "doce": 12, "quince": 15, "veinte": 20, "medio": 0.5, "media": 0.5}
_UNI = "|".join(sorted(map(re.escape, UNIDAD_CANONICA), key=len, reverse=True))
_NUM = r"\d+(?:[.,]\d+)?|" + "|".join(NUMEROS)
_CANTIDAD = re.compile(rf"(?<![a-z0-9.,])({_NUM})\s*({_UNI})(?![a-z0-9])")
_NUMERO_SUELTO = re.compile(rf"(?<![a-z0-9.,])({_NUM})\s+$")  # "40 bolillos"
_CADUCA = re.compile(r"(?:caduc\w*|venc\w*)\s+(?:el\s+)?(?:(hoy)|(manana)|en\s+(\d+|" + "|".join(NUMEROS) + r")\s+(hora|dia)s?)")
_DEL_DIA = re.compile(r"\b(?:del dia|de hoy)\b")
_MAL_ESTADO = re.compile(r"podrid|moho|descompuest|echad\w* a perder|mal estado")
_CANCELAR = re.compile(r"\b(?:cancela\w*|olvidalo|mejor no|ya no quiero)\b")
_CONFIRMAR = re.compile(r"^(?:si|sip|claro|correcto|confirmo|dale|ok|okay|va|listo|perfecto|adelante|de acuerdo)\b")
_NEGAR = re.compile(r"^(?:no|nel|incorrecto|corrige|cambiar)\b")


@dataclass
class ItemDicho:
    nombre: str | None  # None = solo dijo una cantidad ("20 kg")
    clave: str | None = None
    cantidad: float | None = None
    unidad: str | None = None


@dataclass
class Interpretacion:
    intencion: str = "otro"  # donar | confirmar | negar | cancelar | otro
    items: list = field(default_factory=list)
    caduca_en: datetime | None = None
    mal_estado: bool = False


def _numero(texto: str) -> float:
    return float(NUMEROS[texto]) if texto in NUMEROS else float(texto.replace(",", "."))


def _items(original: str, t: str) -> list:
    eventos = []  # (posición, "Q"/"F", datos)
    ocupados = []
    for m in _CANTIDAD.finditer(t):
        eventos.append((m.start(), "Q", (m.end(), _numero(m.group(1)), UNIDAD_CANONICA[m.group(2)])))
        ocupados.append(m.span())
    sin_cantidades = t
    for ini, fin in ocupados:
        sin_cantidades = sin_cantidades[:ini] + " " * (fin - ini) + sin_cantidades[fin:]
    for alimento, ini, fin in buscar_alimentos(sin_cantidades):
        eventos.append((ini, "F", (alimento, fin)))
        m = _NUMERO_SUELTO.search(sin_cantidades[:ini])  # "40 bolillos" = 40 piezas
        if m:
            eventos.append((m.start(1), "Q", (m.end(1), _numero(m.group(1)), "pieza")))
            sin_cantidades = sin_cantidades[:m.start(1)] + " " * (m.end(1) - m.start(1)) + sin_cantidades[m.end(1):]
    eventos.sort(key=lambda e: e[0])

    items, usados = [], set()
    for i, (pos, tipo, datos) in enumerate(eventos):
        if i in usados:
            continue
        if tipo == "F":
            alimento, fin = datos
            items.append(ItemDicho(original[pos:fin].lower(), alimento.clave))
            continue
        fin_q, cantidad, unidad = datos
        sig = eventos[i + 1] if i + 1 < len(eventos) else None
        if sig and sig[1] == "F":  # "25 kg de pan dulce"
            hueco = t[fin_q:sig[0]]
            if len(hueco.strip()) <= 30 and not re.search(r"[\d,.;]", hueco):
                alimento, fin = sig[2]
                items.append(ItemDicho(original[sig[0]:fin].lower(), alimento.clave, cantidad, unidad))
                usados.add(i + 1)
                continue
        if items and items[-1].cantidad is None and eventos[i - 1][1] == "F":  # "pan dulce, 25 kg"
            items[-1].cantidad, items[-1].unidad = cantidad, unidad
            continue
        items.append(ItemDicho(None, None, cantidad, unidad))  # cantidad suelta
    return items


def _caduca(t: str, ahora: datetime) -> datetime | None:
    fin_del_dia = lambda d: d.replace(hour=23, minute=59, second=0, microsecond=0)  # noqa: E731
    m = _CADUCA.search(t)
    if m:
        if m.group(1):
            return fin_del_dia(ahora)
        if m.group(2):
            return fin_del_dia(ahora + timedelta(days=1))
        n = _numero(m.group(3))
        return ahora + timedelta(hours=n) if m.group(4) == "hora" else fin_del_dia(ahora + timedelta(days=n))
    return fin_del_dia(ahora) if _DEL_DIA.search(t) else None


def interpretar(texto: str, ahora: datetime) -> Interpretacion:
    t = normalizar(texto)
    items = _items(texto, t)
    caduca = _caduca(t, ahora)
    mal_estado = bool(_MAL_ESTADO.search(t))
    corto = t.strip(" ,.;:!¡?¿-")
    if _CANCELAR.search(t):
        intencion = "cancelar"
    elif items or caduca or mal_estado:
        intencion = "donar"
    elif _CONFIRMAR.match(corto):
        intencion = "confirmar"
    elif _NEGAR.match(corto):
        intencion = "negar"
    else:
        intencion = "otro"
    return Interpretacion(intencion, items, caduca, mal_estado)
