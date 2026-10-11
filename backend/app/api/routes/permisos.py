"""Permission requests answered from the office (state 13).

- POST /permisos/solicitudes: the hook registers a request; the answer says
  whether it should wait for a decision (policy and presence) and how long.
- GET /permisos/solicitudes/{id}?espera=20: long-poll until it is decided,
  expires or the wait ends.
- POST /permisos/solicitudes/{id}/decision: approve, or reject with a short
  reason; only once and only while the request waits (409/410 otherwise).
- GET/PUT /permisos/config: policy, wait time and the commands that ask for
  confirmation on the phone.

Only clients the backend middleware allows (loopback and Tailscale).
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.agent_state_engine import get_state_engine
from app.core.permisos import (
    ESPERA_MAXIMA,
    ESPERA_MINIMA,
    MAX_MOTIVO,
    POLITICAS,
    PermisoError,
    get_registro,
    validar_config,
)

router = APIRouter(prefix="/permisos", tags=["permisos"])

# Longest single long-poll (the hook asks again until its own deadline).
_ESPERA_LARGA = 25.0


class NuevaSolicitud(BaseModel):
    id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    session_id: str = Field(min_length=1, max_length=128)
    herramienta: str = Field(min_length=1, max_length=128)
    entrada: dict[str, Any] = Field(default_factory=dict)
    cuenta: str | None = Field(default=None, max_length=32)
    proyecto: str | None = Field(default=None, max_length=256)


class Decision(BaseModel):
    decision: Literal["aprobar", "rechazar"]
    motivo: str | None = Field(default=None, max_length=MAX_MOTIVO)
    dispositivo: Literal["pc", "celular"] = "pc"


@router.post("/solicitudes")
async def crear_solicitud(body: NuevaSolicitud) -> dict[str, Any]:
    """Register a PermissionRequest. ``esperar``: the hook waits for a decision."""
    registro = get_registro()
    s = registro.crear(
        body.id,
        body.session_id,
        body.herramienta,
        body.entrada,
        body.cuenta,
        body.proyecto,
        en_la_pc=get_state_engine().en_la_pc(),
    )
    vista = s.vista(registro.clock())
    vista["esperar"] = vista["esperando"]
    vista["politica"] = registro.config.politica
    return vista


@router.get("/solicitudes/{id_}")
async def leer_solicitud(id_: str, espera: float = Query(default=0, ge=0, le=60)) -> dict[str, Any]:
    """State of a request; with ``espera`` > 0 waits for a decision (long-poll)."""
    registro = get_registro()
    s = (
        await registro.esperar(id_, min(espera, _ESPERA_LARGA))
        if espera > 0
        else registro.obtener(id_)
    )
    if s is None:
        raise HTTPException(status_code=404, detail="La solicitud no existe.")
    return s.vista(registro.clock())


@router.post("/solicitudes/{id_}/decision")
async def decidir(id_: str, body: Decision) -> dict[str, Any]:
    """Approve or reject from the office (PC or phone): once, while it waits."""
    registro = get_registro()
    try:
        s = registro.decidir(id_, body.decision == "aprobar", body.motivo, body.dispositivo)
    except PermisoError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.mensaje) from exc
    return s.vista(registro.clock())


@router.get("/config")
async def leer_config() -> dict[str, Any]:
    cfg = asdict(get_registro().config)
    cfg["limites"] = {
        "espera_min": ESPERA_MINIMA,
        "espera_max": ESPERA_MAXIMA,
        "politicas": list(POLITICAS),
    }
    return cfg


@router.put("/config")
async def guardar_config(body: dict[str, Any]) -> dict[str, Any]:
    try:
        cfg = validar_config(body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    get_registro().guardar_config(cfg)
    return await leer_config()


@router.get("/historial")
async def historial(limite: int = Query(default=50, ge=1, le=500)) -> list[dict[str, Any]]:
    """Latest requests and decisions of the log (who, when, what)."""
    return get_registro().historial(limite)
