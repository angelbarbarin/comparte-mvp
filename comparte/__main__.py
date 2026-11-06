"""Línea de comandos: ``python -m comparte [--puerto 8000] [--hora-demo 16:00] [--reiniciar]``."""

import argparse

import uvicorn

from .api import crear_app
from .datos import sembrar
from .db import crear_fabrica, crear_motor, reiniciar_tablas


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m comparte", description="ComParte: rescate de alimentos con agentes (MVP)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--puerto", type=int, default=8000)
    p.add_argument("--hora-demo", metavar="HH:MM", help="Fija la hora de la aplicación (útil para grabar a cualquier hora)")
    p.add_argument("--reiniciar", action="store_true", help="Borra la base y recarga los datos de prueba antes de arrancar")
    a = p.parse_args()

    if a.reiniciar:
        motor = crear_motor()
        reiniciar_tablas(motor)
        with crear_fabrica(motor)() as db:
            sembrar(db)
        motor.dispose()
        print("Datos de prueba recargados.")
    print(f"ComParte en http://{a.host}:{a.puerto}  (API en /docs)")
    uvicorn.run(crear_app(hora_demo=a.hora_demo), host=a.host, port=a.puerto)


if __name__ == "__main__":
    main()
