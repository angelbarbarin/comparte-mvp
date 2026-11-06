"""Agente Captador (CP-01 registro conversacional y CP-02 inocuidad).

Conversa con el donante, estructura la donación y aplica las reglas de inocuidad. Principio: **preguntar
lo mínimo**. Solo es obligatorio "qué alimento y cuánto"; la caducidad se estima con la vida útil del
catálogo si no se da, y se muestra marcada como "(estimado)". Donar toma dos mensajes: describir y "sí".
"""

import copy
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .. import reloj
from ..conocimiento import CATALOGO, a_kg, evaluar_inocuidad
from ..modelos import Conversacion, Donacion, Estado
from ..nlu import interpretar
from .base import decir, evento, fmt_kg

NOMBRE = "captador"
SALUDO = ("¡Hola! Soy el Agente Captador de ComParte. Cuéntame qué excedente tienes: qué alimento, cuánto y, "
          "si puedes, hasta cuándo dura. Por ejemplo: «25 kg de pan dulce, caduca hoy».")


def _item(nombre: str, clave: str, cantidad, unidad) -> dict:
    a = CATALOGO[clave]
    it = {"nombre": nombre, "clave": clave, "categoria": a.categoria, "almacenamiento": a.almacenamiento,
          "riesgo": a.riesgo, "cantidad": None, "unidad": None, "kg": None}
    if cantidad is not None:
        _poner_cantidad(it, cantidad, unidad)
    return it


def _poner_cantidad(it: dict, cantidad: float, unidad: str) -> None:
    it.update(cantidad=cantidad, unidad=unidad, kg=round(a_kg(cantidad, unidad, CATALOGO[it["clave"]]), 2))


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

    def procesar(self, conv: Conversacion, texto: str) -> Donacion | None:
        """Procesa un mensaje del donante. Devuelve la donación si este mensaje la registró."""
        ahora = reloj.ahora()
        b = copy.deepcopy(conv.borrador) or {"items": [], "caduca_en": None, "caduca_estimada": False,
                                              "mal_estado": False, "etapa": "recopilando"}
        decir(conv, "donante", texto)
        ent = interpretar(texto, ahora)

        if ent.intencion == "cancelar":
            conv.borrador = {}
            decir(conv, NOMBRE, "Listo, cancelé este registro. Cuando tengas otro excedente, cuéntame.")
            return None

        hay_datos = bool(ent.items or ent.caduca_en)
        if b["etapa"] == "confirmando" and not hay_datos:
            if ent.intencion == "confirmar":
                return self._registrar(conv, b, ahora)
            if ent.intencion == "negar":
                b["etapa"] = "recopilando"
                conv.borrador = b
                decir(conv, NOMBRE, "Entendido. ¿Qué quieres corregir? Dime el dato correcto, por ejemplo "
                                    "«son 30 kg» o «caduca mañana».")
                return None

        avisos = self._fusionar(b, ent)
        b["etapa"] = "recopilando"
        return self._avanzar(conv, b, ahora, avisos)

    # -------------------------------------------------------------------------------- interpretación
    def _fusionar(self, b: dict, ent) -> list:
        avisos = []
        for dicho in ent.items:
            if dicho.nombre is None:  # cantidad suelta: "20 kg" o "son 30 kg"
                destino = next((i for i in b["items"] if i["cantidad"] is None), None)
                if destino is None and len(b["items"]) == 1:
                    destino = b["items"][0]  # corrección de la única cantidad
                if destino is not None:
                    _poner_cantidad(destino, dicho.cantidad, dicho.unidad)
                else:
                    avisos.append("No reconocí a qué alimento corresponde esa cantidad. Dímelo así: «30 kg de pan».")
                continue
            existente = next((i for i in b["items"] if i["nombre"] == dicho.nombre), None)
            if existente is None:
                b["items"].append(_item(dicho.nombre, dicho.clave, dicho.cantidad, dicho.unidad))
            elif dicho.cantidad is not None:
                _poner_cantidad(existente, dicho.cantidad, dicho.unidad)
        if ent.caduca_en:
            b["caduca_en"], b["caduca_estimada"] = ent.caduca_en.isoformat(), False
        b["mal_estado"] = b["mal_estado"] or ent.mal_estado
        return avisos

    # ------------------------------------------------------------------------------------ conversación
    def _avanzar(self, conv, b, ahora, avisos) -> None:
        def responder(*textos):
            conv.borrador = b
            decir(conv, NOMBRE, "\n".join(t for t in (*avisos, *textos) if t))

        if not b["items"]:
            return responder("No reconocí ningún alimento. Dime qué alimento es y cuánto hay; "
                             "por ejemplo: «25 kg de pan dulce».")
        faltan = [i for i in b["items"] if i["cantidad"] is None]
        if faltan:
            return responder(f"¿Cuánto {faltan[0]['nombre']} tienes? Puedes decirlo en kg, piezas, cajas o charolas.")

        if not b["caduca_en"]:
            vidas = [CATALOGO[i["clave"]].vida_util_horas for i in b["items"] if i["clave"] != "no_aceptado"]
            horas = min(vidas) if vidas else 24
            b["caduca_en"], b["caduca_estimada"] = (ahora + timedelta(hours=horas)).isoformat(), True

        ev = evaluar_inocuidad(b["items"], b["mal_estado"])
        if ev.bloqueada:
            evento(self.db, None, NOMBRE, "Inocuidad bloqueó un registro: " + "; ".join(ev.motivos))
            conv.borrador = {}
            decir(conv, NOMBRE, "No puedo registrar esta donación:\n" + "\n".join(f"• {m}" for m in ev.motivos)
                  + "\nGracias por avisar. Si tienes otro excedente, cuéntame.")
            return None

        b["etapa"] = "confirmando"
        total = sum(i["kg"] for i in b["items"])
        lineas = ["Esto es lo que entendí:"]
        lineas += [f"• {i['cantidad']:g} {i['unidad']} de {i['nombre']}" for i in b["items"]]
        lineas.append(f"Total: {fmt_kg(total)} (los pesos en piezas, cajas o charolas son estimados)")
        lineas.append(f"Caduca: {b['caduca_en'][:16].replace('T', ' ')}" + (" (estimado)" if b["caduca_estimada"] else ""))
        if ev.requiere_revision:
            lineas.append("⚠ Incluye alimentos de riesgo: una persona del equipo lo revisará antes de asignarlo.")
        lineas.append("¿Lo confirmo? Responde «sí» o dime qué corregir.")
        return responder(*lineas)

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
        decir(conv, NOMBRE, f"¡Listo! Registré tu donación #{d.id} ({fmt_kg(d.total_kg)}).")
        return d
