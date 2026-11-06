"""Reloj único del sistema.

Todo el código pide la hora con ``reloj.ahora()``. Sirve para dos cosas:

* **Pruebas**: ``congelar(...)`` detiene el tiempo.
* **Demo**: ``fijar_hora_hoy("16:00")`` hace que la aplicación crea que son las 16:00 (el tiempo sigue
  corriendo desde ahí). Así el video no depende de la hora real: de noche todos los receptores
  estarían cerrados.

Las fechas son locales y sin zona horaria (el MVP solo opera en el AMG).
"""

from datetime import datetime, timedelta

_congelado: datetime | None = None
_desfase = timedelta(0)


def ahora() -> datetime:
    if _congelado is not None:
        return _congelado
    return datetime.now().replace(microsecond=0) + _desfase


def congelar(momento: datetime) -> None:
    global _congelado
    _congelado = momento


def fijar_hora_hoy(hhmm: str) -> datetime:
    global _congelado, _desfase
    hora, minuto = (int(x) for x in hhmm.split(":"))
    real = datetime.now()
    _congelado = None
    _desfase = real.replace(hour=hora, minute=minuto, second=0, microsecond=0) - real
    return ahora()


def restablecer() -> None:
    global _congelado, _desfase
    _congelado, _desfase = None, timedelta(0)


def hay_desfase() -> bool:
    return _congelado is not None or _desfase != timedelta(0)
