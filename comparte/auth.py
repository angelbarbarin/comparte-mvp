"""Roles por token: un ``Depends`` sencillo que revisa quién hace cada petición.

No es un inicio de sesión real (no hay contraseñas, JWT ni sesiones): cada petición manda la cabecera
``X-Comparte-Token`` y el token se traduce a un ``Actor`` (rol + id).

* **Tokens configurados**: variable ``COMPARTE_TOKENS`` con un JSON ``{"token": "rol:id"}``; el administrador
  va sin id: ``{"s3cr3t0": "admin", "tok-oxxo": "donante:3"}``.
* **Modo demo**: además valen los tokens fijos ``demo-admin``, ``demo-donante-<id>``, ``demo-receptor-<id>`` y
  ``demo-voluntario-<id>``, para que la interfaz pueda "actuar como" cualquiera. Fuera del modo demo no valen.

Sin token o con uno inválido -> 401. Con un rol que no corresponde -> 403. La verificación de *propiedad* (que el
receptor sea el de esa donación, por ejemplo) se hace en ``api.py`` con ``exigir_propiedad``.

Nota técnica: sin ``from __future__ import annotations`` para que FastAPI resuelva bien las dependencias.
"""

import json
import os
import re
from dataclasses import dataclass
from typing import Literal

from fastapi import Depends, HTTPException, Request

Rol = Literal["donante", "receptor", "voluntario", "admin"]
ROLES = ("donante", "receptor", "voluntario", "admin")
CABECERA = "X-Comparte-Token"
_DEMO = re.compile(r"^demo-(?:(admin)|(donante|receptor|voluntario)-(\d+))$")


@dataclass(frozen=True)
class Actor:
    rol: Rol
    id: int | None = None


def _actor_desde_texto(valor: str) -> Actor:
    """``"admin"`` o ``"rol:id"`` -> Actor. ``ValueError`` si no tiene ese formato."""
    rol, _, id_ = valor.strip().partition(":")
    if rol == "admin" and not id_:
        return Actor("admin")
    if rol in ROLES and rol != "admin" and id_.isdigit():
        return Actor(rol, int(id_))
    raise ValueError(f"Rol inválido en COMPARTE_TOKENS: {valor!r} (usa \"admin\" o \"rol:id\")")


def cargar_tokens(texto: str | None = None) -> dict:
    """Lee ``COMPARTE_TOKENS`` (o el texto dado). Un token mal escrito detiene el arranque: mejor que fallar en silencio."""
    texto = os.getenv("COMPARTE_TOKENS", "") if texto is None else texto
    if not texto.strip():
        return {}
    try:
        crudo = json.loads(texto)
    except json.JSONDecodeError as e:
        raise ValueError(f"COMPARTE_TOKENS no es un JSON válido: {e}") from None
    if not isinstance(crudo, dict):
        raise ValueError('COMPARTE_TOKENS debe ser un objeto JSON: {"token": "rol:id"}')
    return {str(token): _actor_desde_texto(str(valor)) for token, valor in crudo.items()}


def resolver(token: str | None, tokens: dict, modo_demo: bool) -> Actor | None:
    if not token:
        return None
    if token in tokens:
        return tokens[token]
    if modo_demo:
        m = _DEMO.match(token)
        if m:
            return Actor("admin") if m.group(1) else Actor(m.group(2), int(m.group(3)))
    return None


def actor_actual(request: Request) -> Actor:
    """Dependencia de FastAPI: el actor de la petición, según la cabecera ``X-Comparte-Token``."""
    estado = request.app.state
    actor = resolver(request.headers.get(CABECERA), getattr(estado, "tokens", {}), getattr(estado, "modo_demo", False))
    if actor is None:
        raise HTTPException(status_code=401, detail="Falta un token válido en la cabecera X-Comparte-Token",
                            headers={"WWW-Authenticate": "X-Comparte-Token"})
    return actor


def requiere(*roles: str):
    """``Depends`` que deja pasar solo a los roles dados: ``actor: Actor = requiere("receptor", "admin")``."""
    desconocidos = set(roles) - set(ROLES)
    if desconocidos:
        raise ValueError(f"Roles desconocidos: {sorted(desconocidos)}")

    def dependencia(actor: Actor = Depends(actor_actual)) -> Actor:
        if actor.rol not in roles:
            raise HTTPException(status_code=403, detail=f"Esta acción es para {' o '.join(roles)}; tu rol es {actor.rol}")
        return actor

    return Depends(dependencia)


def exigir_propiedad(actor: Actor, rol: str, dueno_id: int | None, que: str) -> None:
    """403 si el actor tiene ``rol`` pero no es el dueño (el admin siempre pasa)."""
    if actor.rol == rol and actor.id != dueno_id:
        raise HTTPException(status_code=403, detail=f"{que} le corresponde a otro {rol}")
