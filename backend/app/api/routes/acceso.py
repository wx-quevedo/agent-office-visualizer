"""Sign-in, sessions and machines (stage 1.1).

- GET  /auth/estado: mode (activado/desactivado) and whether this browser has a session. Public.
- POST /auth/entrar: password -> web session (httpOnly cookie, 30 days). Public, limited per IP.
- POST /auth/salir: closes this session.
- GET  /auth/sesiones, DELETE /auth/sesiones/{id}: active sessions and app tokens.
- POST /auth/app/token: password -> long-lived token for one device (future iOS app). Public,
  limited per IP; the token is shown only once.
- GET  /maquinas: registered machines (user).
- POST /maquinas/latido: heartbeat of a machine monitor (machine token).
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.api.acceso_middleware import (
    COOKIE_SESION,
    COOKIE_SESION_SEGURA,
    bearer,
    cookie_de,
    cookie_segura,
    ip_cliente,
    nombre_cookie,
)
from app.config import get_settings
from app.core.acceso import DURACION_WEB, get_acceso, get_limite

router = APIRouter(tags=["acceso"])


class Entrada(BaseModel):
    contrasena: str = Field(min_length=1, max_length=256)
    dispositivo: str | None = Field(default=None, max_length=120)


class Latido(BaseModel):
    version_monitor: str | None = Field(default=None, max_length=40)
    hostname: str | None = Field(default=None, max_length=120)
    sistema: str | None = Field(default=None, max_length=10)


class ObservacionSesion(BaseModel):
    """What a monitor reads on its machine about one session (stage 1.2)."""

    session_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    proceso_vivo: bool | None = None
    pid: int | None = None
    tokens_salida_total: int | None = Field(default=None, ge=0)
    contexto_tokens: int | None = Field(default=None, ge=0)
    modelo: str | None = Field(default=None, max_length=80)
    ultimo_texto_asistente: str | None = Field(default=None, max_length=4000)
    ultimo_texto_usuario: str | None = Field(default=None, max_length=4000)
    turno_terminado: bool | None = None
    primer_ts: str | None = Field(default=None, max_length=40)
    ultimo_ts: str | None = Field(default=None, max_length=40)
    tamano_transcripcion: int | None = Field(default=None, ge=0)


class Observaciones(BaseModel):
    sesiones: list[ObservacionSesion] = Field(default_factory=lambda: [], max_length=200)


def _comprobar_contrasena(request: Request, body: Entrada) -> None:
    """Password check with the per-IP limit (429 with the wait, 401 when wrong)."""
    ip = ip_cliente(request)
    limite = get_limite()
    espera = max(limite.espera(ip), limite.espera_global())
    if espera > 0:
        raise HTTPException(
            status_code=429,
            detail={
                "mensaje": "Demasiados intentos. Espera antes de volver a probar.",
                "segundos": int(espera) + 1,
            },
            headers={"Retry-After": str(int(espera) + 1)},
        )
    if not get_acceso().verificar_contrasena(body.contrasena):
        nueva = limite.fallo(ip)
        detalle: dict[str, Any] = {"mensaje": "Contraseña incorrecta."}
        if nueva > 0:
            detalle["segundos"] = int(nueva) + 1
        raise HTTPException(status_code=401, detail=detalle)
    limite.exito(ip)


def _dispositivo(request: Request, body: Entrada) -> str:
    return (body.dispositivo or request.headers.get("user-agent") or "")[:120]


@router.get("/auth/estado")
async def estado(request: Request) -> dict[str, Any]:
    settings = get_settings()
    acceso = get_acceso()
    sesion = None
    cookie = cookie_de(request.cookies)
    if cookie:
        sesion = acceso.validar_sesion(cookie, tipo="web")
    token = bearer(request.headers)
    if sesion is None and token:
        sesion = acceso.validar_sesion(token, tipo="app")
    return {
        "modo": "activado" if settings.auth_activa else "desactivado",
        "sesion": sesion is not None,
        "expira": sesion.expira.isoformat() if sesion else None,
    }


@router.post("/auth/entrar")
async def entrar(request: Request, response: Response, body: Entrada) -> dict[str, Any]:
    if not get_settings().auth_activa:
        raise HTTPException(
            status_code=409,
            detail={"mensaje": "El inicio de sesión está desactivado en esta copia."},
        )
    # argon2 is slow on purpose: outside the event loop (ingest and WebSockets go on).
    await asyncio.to_thread(_comprobar_contrasena, request, body)
    token, sesion = get_acceso().crear_sesion(
        "web", _dispositivo(request, body), ip_cliente(request)
    )
    response.set_cookie(
        nombre_cookie(request),
        token,
        max_age=int(DURACION_WEB.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=cookie_segura(request),
        path="/",
    )
    return {"ok": True, "sesion": sesion.vista(actual=True)}


@router.post("/auth/salir")
async def salir(request: Request, response: Response) -> dict[str, Any]:
    """Closes this session (if still valid) and always removes the cookie."""
    cookie = cookie_de(request.cookies)
    sesion = get_acceso().validar_sesion(cookie, tipo="web") if cookie else None
    if sesion is not None:
        get_acceso().revocar_sesion(sesion.id)
    response.delete_cookie(COOKIE_SESION, path="/")
    response.delete_cookie(COOKIE_SESION_SEGURA, path="/", secure=True)
    return {"ok": True}


@router.get("/auth/sesiones")
async def sesiones(request: Request) -> list[dict[str, Any]]:
    actual = getattr(request.state, "sesion", None)
    return [
        s.vista(actual=actual is not None and s.id == actual.id)
        for s in get_acceso().sesiones_activas()
    ]


@router.delete("/auth/sesiones/{id_}")
async def cerrar_sesion(id_: str) -> dict[str, Any]:
    if not get_acceso().revocar_sesion(id_):
        raise HTTPException(status_code=404, detail="No hay una sesión activa con ese id.")
    return {"ok": True}


@router.post("/auth/app/token")
async def token_app(request: Request, body: Entrada) -> dict[str, Any]:
    """Long-lived token for one device (the future iOS app): shown only once."""
    if not get_settings().auth_activa:
        raise HTTPException(
            status_code=409,
            detail={"mensaje": "El inicio de sesión está desactivado en esta copia."},
        )
    await asyncio.to_thread(_comprobar_contrasena, request, body)
    token, sesion = get_acceso().crear_sesion(
        "app", _dispositivo(request, body), ip_cliente(request)
    )
    return {"token": token, "sesion": sesion.vista()}


@router.get("/maquinas")
async def maquinas() -> list[dict[str, Any]]:
    return get_acceso().maquinas()


@router.post("/maquinas/latido")
async def latido(request: Request, body: Latido) -> dict[str, Any]:
    """Heartbeat of a machine monitor: last connection, monitor version, hostname."""
    machine_id = getattr(request.state, "maquina", None) or get_settings().MAQUINA_LOCAL_ID
    m = get_acceso().latido_maquina(machine_id, body.version_monitor, body.hostname, body.sistema)
    if m is None:
        raise HTTPException(status_code=404, detail="La máquina no está registrada.")
    return m


@router.post("/maquinas/observaciones")
async def observaciones(request: Request, body: Observaciones) -> dict[str, Any]:
    """Transcript and process data read by a machine monitor (machine token)."""
    from app.core.agent_state_engine import get_state_engine

    machine_id = getattr(request.state, "maquina", None) or get_settings().MAQUINA_LOCAL_ID
    motor = get_state_engine()
    aplicadas = sum(
        1 for o in body.sesiones if motor.observar(machine_id, o.model_dump(exclude_none=True))
    )
    return {"recibidas": len(body.sesiones), "aplicadas": aplicadas}
