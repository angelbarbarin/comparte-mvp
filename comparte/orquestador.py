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

Concurrencia: los cambios de estado son atómicos (``agentes.base.transicionar``, ``UPDATE ... WHERE estado =
:esperado``), así que con un doble clic solo cuenta el primero. Las ofertas a receptores y las propuestas a
voluntarios vencen; ``expirar_vencidas()`` las pasa al siguiente candidato y se ejecuta al inicio de cada
operación que cambia el estado (la API puede llamarla también de forma periódica).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from . import reloj
from .agentes import coordinador, impacto, logistico
from .agentes.base import avisar_donante, evento, transicionar
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
        """Mensaje del donante. Si el Captador registra una donación, se enruta de inmediato.

        La conversación tiene bloqueo optimista (``Conversacion.version``): si llegan dos mensajes a la vez, por
        ejemplo un doble "sí", el segundo se descarta en lugar de registrar la donación dos veces.
        """
        try:
            conv = self.captador.iniciar(donante_id)
            d = self.captador.procesar(conv, texto)
            if d is not None:
                self._enrutar(d)
            self.db.commit()
        except StaleDataError:
            self.db.rollback()
            raise ValueError("Llegaron dos mensajes al mismo tiempo; revisa la conversación e intenta de nuevo") from None
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

    # ------------------------------------------------------------------------------------ vencimientos
    def expirar_vencidas(self) -> int:
        """Retira las ofertas y propuestas cuyo tiempo límite pasó y busca otro receptor o voluntario.

        Devuelve cuántas expiró. Es seguro llamarla en paralelo: cada retiro es un ``UPDATE`` atómico.
        """
        ahora = reloj.ahora()
        n = 0
        ofertas = self.db.scalars(select(Donacion).where(
            Donacion.estado == Estado.OFRECIDA, Donacion.oferta_vence_en <= ahora).order_by(Donacion.id)).all()
        for d in ofertas:
            if coordinador.expirar(self.db, d, ahora):
                evento(self.db, d.id, NOMBRE, f"La oferta de la donación #{d.id} venció: pido al Coordinador otro receptor.")
                coordinador.ofrecer(self.db, d, ahora)
                n += 1
        propuestas = self.db.scalars(select(Donacion).where(
            Donacion.estado == Estado.ASIGNADA, Donacion.voluntario_id.is_not(None),
            Donacion.propuesta_vence_en <= ahora).order_by(Donacion.id)).all()
        for d in propuestas:
            if logistico.expirar(self.db, d, ahora):
                evento(self.db, d.id, NOMBRE, f"La propuesta de recolección de la donación #{d.id} venció: "
                       "pido al Logístico otro voluntario.")
                logistico.proponer(self.db, d, ahora)
                n += 1
        if n:
            self.db.commit()
        return n

    # ------------------------------------------------------------------------------ supervisión humana
    def revision(self, donacion_id: int, aprobar: bool) -> Donacion:
        self.expirar_vencidas()
        d = self._donacion(donacion_id)
        if d.estado != Estado.PENDIENTE_VALIDACION:
            raise ValueError(f"La donación #{d.id} no está pendiente de validación ({d.estado})")
        transicionar(self.db, d, Estado.PENDIENTE_VALIDACION,
                     {"estado": Estado.REGISTRADA if aprobar else Estado.RECHAZADA},
                     error=f"La donación #{d.id} ya fue revisada")
        if aprobar:
            evento(self.db, d.id, "humano", f"Una persona aprobó la donación #{d.id}.")
            avisar_donante(self.db, d, "humano", "Una persona del equipo revisó y aprobó tu donación.")
            coordinador.ofrecer(self.db, d, reloj.ahora())
        else:
            evento(self.db, d.id, "humano", f"Una persona rechazó la donación #{d.id}.")
            avisar_donante(self.db, d, "humano", "Una persona del equipo revisó tu donación y no pudimos aceptarla.")
        self.db.commit()
        return d

    # ------------------------------------------------------------------------------------ asignación
    def responder_receptor(self, donacion_id: int, aceptar: bool, receptor_id: int | None = None) -> Donacion:
        """``receptor_id`` (opcional): quien responde; la API con roles lo pasa para que nadie responda por otro."""
        self.expirar_vencidas()
        d = self._donacion(donacion_id)
        ahora = reloj.ahora()
        coordinador.responder(self.db, d, aceptar, ahora, receptor_id)
        if aceptar:
            evento(self.db, d.id, NOMBRE, f"El receptor aceptó la donación #{d.id}: la turno al Logístico.")
            logistico.proponer(self.db, d, ahora)
        else:
            evento(self.db, d.id, NOMBRE, f"Donación #{d.id} rechazada por el receptor: pido al Coordinador otro receptor.")
            coordinador.ofrecer(self.db, d, ahora)
        self.db.commit()
        return d

    def responder_voluntario(self, donacion_id: int, aceptar: bool, voluntario_id: int | None = None) -> Donacion:
        self.expirar_vencidas()
        d = self._donacion(donacion_id)
        logistico.responder(self.db, d, aceptar, reloj.ahora(), voluntario_id)
        if not aceptar:
            evento(self.db, d.id, NOMBRE, f"El voluntario rechazó la donación #{d.id}: pido al Logístico otro voluntario.")
            logistico.proponer(self.db, d, reloj.ahora())
        self.db.commit()
        return d

    def avanzar(self, donacion_id: int, nuevo: str, voluntario_id: int | None = None) -> Donacion:
        d = self._donacion(donacion_id)
        logistico.avanzar(self.db, d, nuevo, reloj.ahora(), voluntario_id)
        if nuevo == "entregada":
            evento(self.db, d.id, NOMBRE, f"Donación #{d.id} entregada: espero la confirmación del receptor.")
        self.db.commit()
        return d

    # --------------------------------------------------------------------------------------- cierre
    def confirmar(self, donacion_id: int, kg_recibidos: float | None = None, receptor_id: int | None = None) -> Donacion:
        d = self._donacion(donacion_id)
        if d.estado != Estado.ENTREGADA:
            raise ValueError(f"La donación #{d.id} aún no ha sido entregada ({d.estado})")
        if receptor_id is not None and receptor_id != d.receptor_id:
            raise ValueError(f"La donación #{d.id} es para otro receptor")
        if kg_recibidos is not None and kg_recibidos <= 0:
            raise ValueError("Los kg recibidos deben ser mayores que cero")
        ahora = reloj.ahora()
        valores = {"estado": Estado.COMPLETADA, "completada_en": ahora}
        if kg_recibidos is not None:
            valores["kg_recibidos"] = round(kg_recibidos, 2)
        # Atómico: con un doble clic el impacto se registraría dos veces.
        transicionar(self.db, d, Estado.ENTREGADA, valores, error=f"La donación #{d.id} ya fue confirmada")
        evento(self.db, d.id, NOMBRE, f"{d.receptor.nombre} confirmó la recepción de la donación #{d.id}: la turno al Agente de Impacto.")
        impacto.registrar(self.db, d, ahora)
        self.db.commit()
        return d
