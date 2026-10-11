"""Avisos resumidos (etapa 2.4).

- GET  /maquinas/avisos: los avisos vigentes de las sesiones de esa máquina que
  todavía no tienen resumen (token de máquina). Solo datos que la máquina ya mandó.
- POST /maquinas/resumenes: la frase del auxiliar (o el fallo) y su consumo.
- GET/PUT /avisos/config: el interruptor de los resúmenes (sesión de usuario).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.agent_state_engine import get_state_engine
from app.core.permisos import get_registro
from app.core.resumenes import (
    TERMINO_RECIENTE,
    avisos_del_agente,
    get_resumenes,
    nombre_proyecto,
)

router = APIRouter(tags=["avisos"])
_MAX_AVISOS = 20


def _maquina(request: Request) -> str:
    return getattr(request.state, "maquina", None) or get_settings().MAQUINA_LOCAL_ID


def ultimo_turno(session_id: str) -> dict[str, Any] | None:
    hist = get_state_engine().historial(session_id, 1, 1)
    return hist["turnos"][0] if hist and hist["turnos"] else None


@router.get("/maquinas/avisos")
async def avisos_por_resumir(request: Request) -> dict[str, Any]:
    resumenes = get_resumenes()
    if not resumenes.activos:
        return {"activos": False, "avisos": []}
    maquina = _maquina(request)
    motor = get_state_engine()
    vista = motor.snapshot()
    permisos = get_registro().vistas_por_sesion()
    ahora = motor.clock()
    salida: list[dict[str, Any]] = []
    for a in vista["agentes"]:
        sid = a["agente"]["session_id"]
        log = motor.sessions.get(sid)
        if log is None or (log.machine_id or get_settings().MAQUINA_LOCAL_ID) != maquina:
            continue
        numero = a["estado"]["numero"]
        turno = None
        if numero == 11:
            desde = datetime.fromisoformat(a["estado"]["desde"])
            if ahora - desde > TERMINO_RECIENTE:
                continue
            turno = ultimo_turno(sid)
        for av in avisos_del_agente(a, permisos.get(sid), turno):
            if resumenes.obtener(av["clave"]) is not None:
                continue
            salida.append(
                {
                    **av,
                    "session_id": sid,
                    "proyecto": nombre_proyecto(a["agente"]["proyecto"]),
                    # La cuenta sale de la carpeta de la transcripción; la ruta
                    # completa no viaja.
                    "cuenta": a["agente"].get("cuenta"),
                }
            )
    return {"activos": True, "avisos": salida[:_MAX_AVISOS]}


class Metricas(BaseModel):
    llamo: bool = False
    segundos: float = Field(default=0, ge=0, le=600)
    tokens_entrada: int = Field(default=0, ge=0)
    tokens_salida: int = Field(default=0, ge=0)
    costo_usd: float = Field(default=0, ge=0)
    modelo: str | None = Field(default=None, max_length=60)
    cuenta: str | None = Field(default=None, max_length=40)
    motivo: str | None = Field(default=None, max_length=80)


class Resumen(BaseModel):
    clave: str = Field(min_length=1, max_length=300)
    texto: str | None = Field(default=None, max_length=600)
    metricas: Metricas = Field(default_factory=Metricas)


@router.post("/maquinas/resumenes")
async def recibir_resumen(request: Request, body: Resumen) -> dict[str, Any]:
    """Solo para un aviso vigente de una sesión de esa misma máquina."""
    maquina = _maquina(request)
    motor = get_state_engine()
    sid = body.clave.split(":", 1)[0]
    log = motor.sessions.get(sid)
    if log is None or (log.machine_id or get_settings().MAQUINA_LOCAL_ID) != maquina:
        raise HTTPException(status_code=403, detail="Esa sesión no es de esta máquina.")
    agente = next(
        (a for a in motor.snapshot()["agentes"] if a["agente"]["session_id"] == sid), None
    )
    permiso = get_registro().vistas_por_sesion().get(sid)
    vigentes: set[str] = (
        {str(av["clave"]) for av in avisos_del_agente(agente, permiso)} if agente else set()
    )
    if body.clave not in vigentes:
        # El aviso ya pasó: se anota el consumo pero no hay frase que guardar.
        if body.metricas.llamo:
            get_resumenes().registrar(
                f"vencido:{body.clave}", None, maquina, body.metricas.model_dump()
            )
        return {"estado": "vencido"}
    fila = get_resumenes().registrar(body.clave, body.texto, maquina, body.metricas.model_dump())
    return {"estado": fila["estado"]}


class ConfigAvisos(BaseModel):
    resumenes: bool


@router.get("/avisos/config")
async def leer_config() -> dict[str, Any]:
    return get_resumenes().config()


@router.put("/avisos/config")
async def cambiar_config(body: ConfigAvisos) -> dict[str, Any]:
    return get_resumenes().cambiar(body.resumenes)
