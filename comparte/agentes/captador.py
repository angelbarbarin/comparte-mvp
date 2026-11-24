"""Agente Captador (CP-01 registro conversacional y CP-02 inocuidad).

Conversa con el donante, estructura la donación y aplica las reglas de inocuidad. Principio: **preguntar
lo mínimo**. Solo es obligatorio "qué alimento y cuánto"; la caducidad se estima con la vida útil del
catálogo si no se da, y se avisa que es una estimación. Donar toma dos mensajes: describir y "sí".

Principios de diseño de voz (provisionales, ver el PR):

1. **Mensajes cortos**: una idea y una sola pregunta por turno, y la pregunta va al final.
2. **Ejemplos** en las preguntas abiertas ("por ejemplo «20 kg» o «3 cajas»").
3. **Confirmación implícita** de lo entendido ("Anoto pan dulce.") y **explícita** solo antes de registrar.
4. **Recuperación progresiva**: el primer "no entendí" reformula; el segundo da opciones concretas; nunca se
   repite el mismo texto dos veces seguidas.
5. **Siempre hay salida**: "corregir", "cancelar" o "empezar de nuevo" funcionan en cualquier etapa.
6. **Se entiende sin pantalla**: sin viñetas ni emojis, y con fechas fáciles de decir ("hoy a las 6 de la tarde").
7. **Una sola persona**: tuteo, tono cálido y breve.
"""

import copy
import re
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .. import reloj
from ..conocimiento import CATALOGO, a_kg, evaluar_inocuidad, normalizar
from ..modelos import Conversacion, Donacion, Estado
from ..nlu import interpretar
from .base import decir, evento, fmt_kg

NOMBRE = "captador"
SALUDO = ("¡Hola! Soy el Captador de ComParte y te ayudo a donar lo que te sobró. Cuéntame qué alimento es y "
          "cuánto hay, por ejemplo «25 kg de pan dulce, caduca hoy». Si te equivocas, di «corregir» o «empezar de nuevo».")

_REINICIAR = re.compile(r"\b(?:empez\w*|comenz\w*|inici\w*) de nuevo\b|\bdesde cero\b|\breinici\w*\b")
_CORREGIR = re.compile(r"^(?:quiero )?(?:corregir|corrijo|editar|cambiar algo|me equivoque)\b")
_UNIDADES_HABLADAS = {"l": ("litro", "litros"), "pieza": ("pieza", "piezas"), "docena": ("docena", "docenas"),
                      "caja": ("caja", "cajas"), "bolsa": ("bolsa", "bolsas"), "charola": ("charola", "charolas"),
                      "costal": ("costal", "costales")}
_DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


# ------------------------------------------------------------------------------- formato para decir en voz alta
def _cantidad(it: dict) -> str:
    """``25 kg``, ``3 cajas``, ``1 litro``: sin abreviaturas raras, salvo kg y g, que se leen bien."""
    n, u = it["cantidad"], it["unidad"]
    if u in _UNIDADES_HABLADAS:
        u = _UNIDADES_HABLADAS[u][0 if n == 1 else 1]
    return f"{n:g} {u}"


def _lista(partes: list) -> str:
    return partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + " y " + partes[-1]


def cuando(momento: datetime, ahora: datetime) -> str:
    """Fecha fácil de decir: "hoy a las 6 de la tarde", "mañana antes de la medianoche", "el jueves 12 a la 1 y media"."""
    dias = (momento.date() - ahora.date()).days
    dia = "hoy" if dias == 0 else "mañana" if dias == 1 else f"el {_DIAS[momento.weekday()]} {momento.day}"
    h, m = momento.hour, momento.minute
    if (h, m) >= (23, 45):
        return f"{dia} antes de la medianoche"
    if h == 12 and m == 0:
        return f"{dia} a mediodía"
    h12 = h % 12 or 12
    minutos = "" if m == 0 else " y media" if m == 30 else " y cuarto" if m == 15 else f":{m:02d}"
    parte = ("de la madrugada" if h < 6 else "de la mañana" if h < 12 else "de la tarde" if h < 19 else "de la noche")
    return f"{dia} a {'la' if h12 == 1 else 'las'} {h12}{minutos} {parte}"


# ------------------------------------------------------------------------------------------------ borrador
def _item(nombre: str, clave: str, cantidad, unidad) -> dict:
    a = CATALOGO[clave]
    it = {"nombre": nombre, "clave": clave, "categoria": a.categoria, "almacenamiento": a.almacenamiento,
          "riesgo": a.riesgo, "cantidad": None, "unidad": None, "kg": None}
    if cantidad is not None:
        _poner_cantidad(it, cantidad, unidad)
    return it


def _poner_cantidad(it: dict, cantidad: float, unidad: str) -> None:
    it.update(cantidad=cantidad, unidad=unidad, kg=round(a_kg(cantidad, unidad, CATALOGO[it["clave"]]), 2))


def _borrador_vacio() -> dict:
    return {"items": [], "caduca_en": None, "caduca_estimada": False, "mal_estado": False, "etapa": "recopilando",
            "fallos": 0}


class Captador:
    def __init__(self, db: Session):
        self.db = db

    def iniciar(self, donante_id: int) -> Conversacion:
        conv = self.db.query(Conversacion).filter_by(donante_id=donante_id).first()
        if conv is None:
            conv = Conversacion(donante_id=donante_id, mensajes=[], borrador={})
            self.db.add(conv)
            decir(conv, NOMBRE, SALUDO)
            self.db.flush()
        return conv

    # ------------------------------------------------------------------------------------------- hablar
    def _decir(self, conv: Conversacion, texto: str, alterna: str | None = None) -> None:
        """Nunca dice dos veces seguidas exactamente lo mismo (principio 4)."""
        previo = next((m["texto"] for m in reversed(conv.mensajes) if m["rol"] != "donante"), None)
        if texto == previo:
            texto = alterna if alterna and alterna != previo else "Sigo con lo mismo: " + texto
        decir(conv, NOMBRE, texto)

    # ----------------------------------------------------------------------------------------- procesar
    def procesar(self, conv: Conversacion, texto: str) -> Donacion | None:
        """Procesa un mensaje del donante. Devuelve la donación si este mensaje la registró."""
        ahora = reloj.ahora()
        b = {**_borrador_vacio(), **copy.deepcopy(conv.borrador)} if conv.borrador else _borrador_vacio()
        decir(conv, "donante", texto)
        ent = interpretar(texto, ahora)
        t = normalizar(texto).strip(" ,.;:!¡?¿-")

        # Salidas: funcionan en cualquier etapa (principio 5).
        if ent.intencion == "cancelar":
            en_curso = bool(conv.borrador and conv.borrador.get("items"))
            conv.borrador = {}
            self._decir(conv, "Listo, cancelé este registro. Cuando tengas otro excedente, cuéntame." if en_curso else
                        "No tengo ningún registro en curso. Cuando tengas un excedente, cuéntame qué es y cuánto hay.")
            return None
        if _REINICIAR.search(t):
            conv.borrador = {}
            self._decir(conv, "Va, empezamos de nuevo. Cuéntame qué alimento te sobró y cuánto hay, por ejemplo «3 cajas de jitomate».",
                        alterna="Ya está todo en blanco. Dime qué alimento es y cuánto hay, por ejemplo «10 kg de fruta».")
            return None

        hay_datos = bool(ent.items or ent.caduca_en or ent.mal_estado)
        if not hay_datos:
            if b["etapa"] == "confirmando" and ent.intencion == "confirmar":
                return self._registrar(conv, b, ahora)
            if (ent.intencion == "negar" and b["items"]) or _CORREGIR.match(t):
                return self._corregir(conv, b)
            b["fallos"] += 1
            return self._no_entendi(conv, b)

        b["fallos"] = 0
        avisos, nuevos = self._fusionar(b, ent)
        b["etapa"] = "recopilando"
        return self._avanzar(conv, b, ahora, avisos, nuevos)

    # -------------------------------------------------------------------------------- interpretación
    def _fusionar(self, b: dict, ent) -> tuple:
        avisos, nuevos = [], []
        for dicho in ent.items:
            if dicho.nombre is None:  # cantidad suelta: "20 kg" o "son 30 kg"
                destino = next((i for i in b["items"] if i["cantidad"] is None), None)
                if destino is None and len(b["items"]) == 1:
                    destino = b["items"][0]  # corrección de la única cantidad
                if destino is not None:
                    _poner_cantidad(destino, dicho.cantidad, dicho.unidad)
                else:
                    avisos.append("No supe a qué alimento va esa cantidad; dímelo junto, como «30 kg de pan».")
                continue
            existente = next((i for i in b["items"] if i["nombre"] == dicho.nombre), None)
            if existente is None:
                b["items"].append(_item(dicho.nombre, dicho.clave, dicho.cantidad, dicho.unidad))
                nuevos.append(dicho.nombre)
            elif dicho.cantidad is not None:
                _poner_cantidad(existente, dicho.cantidad, dicho.unidad)
        if ent.caduca_en:
            b["caduca_en"], b["caduca_estimada"] = ent.caduca_en.isoformat(), False
        b["mal_estado"] = b["mal_estado"] or ent.mal_estado
        return avisos, nuevos

    # ------------------------------------------------------------------------------------ conversación
    def _avanzar(self, conv, b, ahora, avisos, nuevos) -> None:
        def responder(*textos, alterna=None):
            conv.borrador = b
            self._decir(conv, " ".join(t for t in (*avisos, *textos) if t), alterna)

        if not b["items"]:
            return responder("Me falta saber qué alimento es. Puedes decir algo como «25 kg de pan dulce». "
                             "¿Qué alimento es y cuánto hay?")
        faltan = [i for i in b["items"] if i["cantidad"] is None]
        if faltan:
            eco = f"Anoto {_lista(nuevos)}." if nuevos else ""
            return responder(eco, "Puedes decirlo en kilos, piezas o cajas, por ejemplo «20 kg».",
                             f"¿Cuánto {faltan[0]['nombre']} tienes?")

        if not b["caduca_en"]:
            vidas = [CATALOGO[i["clave"]].vida_util_horas for i in b["items"] if i["clave"] != "no_aceptado"]
            horas = min(vidas) if vidas else 24
            b["caduca_en"], b["caduca_estimada"] = (ahora + timedelta(hours=horas)).isoformat(), True

        ev = evaluar_inocuidad(b["items"], b["mal_estado"])
        if ev.bloqueada:
            evento(self.db, None, NOMBRE, "Inocuidad bloqueó un registro: " + "; ".join(ev.motivos))
            conv.borrador = {}
            motivos = ["Me dijiste que está en mal estado, y por seguridad no lo recibimos."
                       if m.startswith("El donante reporta") else m for m in ev.motivos]
            self._decir(conv, "No puedo registrar esta donación. " + " ".join(motivos)
                        + " Gracias por avisar. Si tienes otro excedente, cuéntame.")
            return None

        b["etapa"] = "confirmando"
        total = sum(i["kg"] for i in b["items"])
        caduca = cuando(datetime.fromisoformat(b["caduca_en"]), ahora)
        partes = [f"{_cantidad(i)} de {i['nombre']}" for i in b["items"]]
        frases = [f"Entonces son {_lista(partes)}" + (f", {fmt_kg(total)} en total." if len(partes) > 1 or b["items"][0]["unidad"] != "kg" else ".")]
        if any(i["unidad"] not in ("kg", "g", "l") for i in b["items"]):
            frases.append("El peso es aproximado porque lo calculé por piezas o cajas.")
        frases.append(f"Calculo que dura hasta {caduca}, por el tipo de alimento." if b["caduca_estimada"] else f"Caduca {caduca}.")
        if ev.requiere_revision:
            frases.append("Como trae alimentos de riesgo, una persona del equipo la revisará antes de asignarla.")
        frases.append("¿La registro así o quieres corregir algo?")
        return responder(*frases, alterna=" ".join(["No cambió nada.", *frases]))

    def _corregir(self, conv: Conversacion, b: dict) -> None:
        if not b["items"]:
            conv.borrador = b
            return self._decir(conv, "Todavía no tengo nada anotado. Cuéntame qué alimento te sobró y cuánto hay, "
                                     "por ejemplo «3 cajas de jitomate».")
        b["etapa"], b["fallos"] = "recopilando", 0
        conv.borrador = b
        self._decir(conv, "Claro. Dime el dato correcto, por ejemplo «son 30 kg» o «caduca mañana». ¿Qué quieres cambiar?",
                    alterna="Te escucho. Puedes decir «son 30 kg» o «caduca mañana». ¿Cuál es el dato correcto?")

    def _no_entendi(self, conv: Conversacion, b: dict) -> None:
        """Recuperación progresiva (principio 4): reformula, luego da opciones, y alterna para no repetirse."""
        conv.borrador = b
        intento = b["fallos"]
        faltan = [i for i in b["items"] if i["cantidad"] is None]
        if b["etapa"] == "confirmando":
            textos = ("Perdón, no te entendí. Si todo está bien di «sí»; si algo no cuadra, di «corregir». ¿La registro?",
                      "Tienes tres opciones: «sí» para registrarla, «corregir» para cambiar un dato o «cancelar» para dejarla. "
                      "¿Cuál prefieres?",
                      "Para seguir necesito que me digas «sí», «corregir» o «cancelar». ¿Qué hago con tu donación?")
        elif faltan:
            n = faltan[0]["nombre"]
            textos = (f"No entendí la cantidad. Puedes decirla en kilos, piezas o cajas, por ejemplo «20 kg». ¿Cuánto {n} tienes?",
                      f"Probemos así: un número y una unidad, como «20 kg», «15 piezas» o «2 cajas». ¿Cuánto {n} hay?",
                      f"Si no sabes el peso exacto, una estimación sirve, como «unos 10 kg». También puedes decir «cancelar». "
                      f"¿Cuánto {n} calculas que hay?")
        else:
            textos = ("No reconocí ningún alimento en tu mensaje. Puedes decirme algo como «25 kg de pan dulce» o "
                      "«3 cajas de jitomate». ¿Qué alimento te sobró y cuánto hay?",
                      "Sigo sin reconocerlo. Recibo pan, tortilla, fruta, verdura, abarrotes, lácteos, carne, pollo y comida "
                      "preparada. Si prefieres dejarlo, di «cancelar». ¿Cuál de esos tienes y cuánto?",
                      "Probemos de otra forma: dime solo el alimento y la cantidad, como «10 kg de fruta». ¿Qué tienes?")
        # 1: reformula; 2, 3, 2, 3...: opciones concretas, alternando para nunca repetir el mismo texto.
        self._decir(conv, textos[0] if intento <= 1 else textos[1 + (intento - 2) % 2])

    def _registrar(self, conv: Conversacion, b: dict, ahora) -> Donacion:
        ev = evaluar_inocuidad(b["items"], b["mal_estado"])
        d = Donacion(
            donante_id=conv.donante_id, estado=Estado.REGISTRADA, items=b["items"],
            total_kg=round(sum(i["kg"] for i in b["items"]), 2), requiere_frio=ev.requiere_frio,
            requiere_revision=ev.requiere_revision, caduca_en=datetime.fromisoformat(b["caduca_en"]), creada_en=ahora,
        )
        self.db.add(d)
        self.db.flush()
        resumen = ", ".join(f"{i['cantidad']:g} {i['unidad']} de {i['nombre']}" for i in b["items"])
        evento(self.db, d.id, NOMBRE, f"Registré la donación #{d.id}: {resumen} ({fmt_kg(d.total_kg)}). "
               + ("Requiere revisión humana por alimentos de riesgo." if ev.requiere_revision else "Sin riesgo que exija revisión."))
        conv.borrador = {}
        self._decir(conv, f"¡Listo! Registré tu donación número {d.id}, de {fmt_kg(d.total_kg)}.")
        return d
