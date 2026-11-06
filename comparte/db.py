"""Base de datos (SQLAlchemy). SQLite en ``data/comparte.db`` por defecto; ``COMPARTE_DB_URL`` la cambia."""

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

RAIZ = Path(__file__).resolve().parent.parent


class Base(DeclarativeBase):
    pass


def crear_motor(url: str | None = None):
    url = url or os.getenv("COMPARTE_DB_URL") or f"sqlite:///{(RAIZ / 'data' / 'comparte.db').as_posix()}"
    args: dict = {}
    if url.startswith("sqlite"):
        args["connect_args"] = {"check_same_thread": False}
        if url in ("sqlite://", "sqlite:///:memory:"):
            args["poolclass"] = StaticPool
        else:
            (RAIZ / "data").mkdir(exist_ok=True)
    return create_engine(url, **args)


def crear_fabrica(motor):
    return sessionmaker(bind=motor, expire_on_commit=False)


def crear_tablas(motor):
    from . import modelos  # noqa: F401  (registra los modelos)

    Base.metadata.create_all(motor)


def reiniciar_tablas(motor):
    from . import modelos  # noqa: F401

    Base.metadata.drop_all(motor)
    Base.metadata.create_all(motor)
