"""Línea de comandos: ``python -m comparte [--puerto 8000] [--demo [--hora-demo 16:00] [--reiniciar]]``.

Sin ``--demo`` la aplicación pide tokens configurados en ``COMPARTE_TOKENS`` y no expone ``/api/demo/reiniciar``.
"""

import argparse
import os

import uvicorn

from .api import crear_app
from .datos import sembrar
from .db import crear_fabrica, crear_motor, reiniciar_tablas


def main(argv: list | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m comparte", description="ComParte: rescate de alimentos con agentes (MVP)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--puerto", type=int, default=8000)
    p.add_argument("--demo", action="store_true",
                   help="Modo demostración: tokens de prueba (demo-*) y POST /api/demo/reiniciar. También con COMPARTE_DEMO=1")
    p.add_argument("--hora-demo", metavar="HH:MM", help="Fija la hora de la aplicación (solo con --demo; útil para grabar)")
    p.add_argument("--reiniciar", action="store_true", help="Borra la base y recarga los datos de prueba (solo con --demo)")
    a = p.parse_args(argv)

    demo = a.demo or os.getenv("COMPARTE_DEMO") == "1"
    if not demo and (a.reiniciar or a.hora_demo):
        p.error("--reiniciar y --hora-demo solo se permiten junto con --demo")

    if a.reiniciar:
        motor = crear_motor()
        reiniciar_tablas(motor)
        with crear_fabrica(motor)() as db:
            sembrar(db)
        motor.dispose()
        print("Datos de prueba recargados.")
    print(f"ComParte en http://{a.host}:{a.puerto}  (API en /docs)" + ("  · modo demostración" if demo else ""))
    uvicorn.run(crear_app(hora_demo=a.hora_demo, modo_demo=demo), host=a.host, port=a.puerto)


if __name__ == "__main__":
    main()
