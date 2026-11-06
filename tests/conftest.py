from datetime import datetime

import pytest

from comparte import reloj
from comparte.datos import sembrar
from comparte.db import crear_fabrica, crear_motor, crear_tablas

HORA = datetime(2026, 11, 10, 16, 0)  # martes por la tarde: los receptores están abiertos


@pytest.fixture(autouse=True)
def reloj_congelado():
    reloj.congelar(HORA)
    yield
    reloj.restablecer()


@pytest.fixture
def db():
    motor = crear_motor("sqlite://")
    crear_tablas(motor)
    sesion = crear_fabrica(motor)()
    sembrar(sesion)
    yield sesion
    sesion.close()
    motor.dispose()
