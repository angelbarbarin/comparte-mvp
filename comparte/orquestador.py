"""Orquestador: el único componente que conoce a los cuatro agentes y decide quién actúa después.

Los agentes no se llaman entre sí: cada uno hace su trabajo y devuelve el control. El orquestador enruta
según el estado de la donación y deja cada traspaso en la bitácora (aparece como "Orquestador" en la línea
de tiempo de la interfaz).

    Donante ─chat→ Captador ──registra──▶ Orquestador
        riesgo ─▶ revisión humana ─aprueba─┐
        sin riesgo ───────────────────────┴▶ Coordinador ─oferta─▶ Receptor ─acepta─▶ Logístico ─▶ Voluntario
                                                                  ◀─rechaza─ reasigna      │ recoge y entrega
        Impacto ◀────────────── el receptor confirma la recepción ◀───────────────────────┘

Cada método público hace ``commit``. ``LookupError`` = no existe (404); ``ValueError`` = transición inválida (409).
"""

from sqlalchemy.orm import Session

from . import reloj
from .agentes import coordinador, impacto, logistico
from .agentes.base import avisar_donante, evento
from .agentes.captador import Captador
from .modelos import Conversacion, Donacion, Estado

NOMBRE = "orquestador"


class Orquestador:
    def __init__(self, db: Session):
        self.db = db
        self.captador = Captador(db)

    def _donacion(self, id_: int) -> Donacion:
        d = self.db.get(Donacion, id_)
        if d is None:
            raise LookupError(f"No existe la donación {id_}")
        return d

    # ------------------------------------------------------------------------------------- captura
    def chat(self, donante_id: int) -> Conversacion:
        conv = self.captador.iniciar(donante_id)
        self.db.commit()
        return conv

    def mensaje(self, donante_id: int, texto: str) -> Donacion | None:
        """Mensaje del donante. Si el Captador registra una donación, se enruta de inmediato."""
        conv = self.captador.iniciar(donante_id)
        d = self.captador.procesar(conv, texto)
        if d is not None:
            self._enrutar(d)
        self.db.commit()
        return d

    def _enrutar(self, d: Donacion) -> None:
        if d.requiere_revision:
            d.estado = Estado.PENDIENTE_VALIDACION
            evento(self.db, d.id, NOMBRE, f"Donación #{d.id} con alimentos de riesgo: la envío a revisión humana.")
            avisar_donante(self.db, d, NOMBRE, "Tu donación incluye alimentos que requieren la revisión de una persona "
                           "antes de asignarse. Te aviso en cuanto la valide.")
        else:
            evento(self.db, d.id, NOMBRE, f"Donación #{d.id} sin riesgo que exija revisión: la turno al Coordinador.")
            coordinador.ofrecer(self.db, d, reloj.ahora())

    # ------------------------------------------------------------------------------ supervisión humana
    def revision(self, donacion_id: int, aprobar: bool) -> Donacion:
        d = self._donacion(donacion_id)
        if d.estado != Estado.PENDIENTE_VALIDACION:
            raise ValueError(f"La donación #{d.id} no está pendiente de validación ({d.estado})")
        if aprobar:
            evento(self.db, d.id, "humano", f"Una persona aprobó la donación #{d.id}.")
            avisar_donante(self.db, d, "humano", "Una persona del equipo revisó y aprobó tu donación.")
            coordinador.ofrecer(self.db, d, reloj.ahora())
        else:
            d.estado = Estado.RECHAZADA
            evento(self.db, d.id, "humano", f"Una persona rechazó la donación #{d.id}.")
            avisar_donante(self.db, d, "humano", "Una persona del equipo revisó tu donación y no pudimos aceptarla.")
        self.db.commit()
        return d

    # ------------------------------------------------------------------------------------ asignación
    def responder_receptor(self, donacion_id: int, aceptar: bool) -> Donacion:
        d = self._donacion(donacion_id)
        ahora = reloj.ahora()
        coordinador.responder(self.db, d, aceptar, ahora)
        if aceptar:
            evento(self.db, d.id, NOMBRE, f"El receptor aceptó la donación #{d.id}: la turno al Logístico.")
            logistico.proponer(self.db, d, ahora)
        else:
            evento(self.db, d.id, NOMBRE, f"Donación #{d.id} rechazada por el receptor: pido al Coordinador otro receptor.")
            coordinador.ofrecer(self.db, d, ahora)
        self.db.commit()
        return d

    def responder_voluntario(self, donacion_id: int, aceptar: bool) -> Donacion:
        d = self._donacion(donacion_id)
        logistico.responder(self.db, d, aceptar)
        if not aceptar:
            evento(self.db, d.id, NOMBRE, f"El voluntario rechazó la donación #{d.id}: pido al Logístico otro voluntario.")
            logistico.proponer(self.db, d, reloj.ahora())
        self.db.commit()
        return d

    def avanzar(self, donacion_id: int, nuevo: str) -> Donacion:
        d = self._donacion(donacion_id)
        logistico.avanzar(self.db, d, nuevo, reloj.ahora())
        if nuevo == "entregada":
            evento(self.db, d.id, NOMBRE, f"Donación #{d.id} entregada: espero la confirmación del receptor.")
        self.db.commit()
        return d

    # --------------------------------------------------------------------------------------- cierre
    def confirmar(self, donacion_id: int, kg_recibidos: float | None = None) -> Donacion:
        d = self._donacion(donacion_id)
        if d.estado != Estado.ENTREGADA:
            raise ValueError(f"La donación #{d.id} aún no ha sido entregada ({d.estado})")
        if kg_recibidos is not None:
            if kg_recibidos <= 0:
                raise ValueError("Los kg recibidos deben ser mayores que cero")
            d.kg_recibidos = round(kg_recibidos, 2)
        ahora = reloj.ahora()
        d.estado, d.completada_en = Estado.COMPLETADA, ahora
        evento(self.db, d.id, NOMBRE, f"{d.receptor.nombre} confirmó la recepción de la donación #{d.id}: la turno al Agente de Impacto.")
        impacto.registrar(self.db, d, ahora)
        self.db.commit()
        return d
