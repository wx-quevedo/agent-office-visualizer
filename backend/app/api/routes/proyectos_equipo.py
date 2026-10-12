"""Proyectos con equipo (etapa 4, Prompts 37 y 38).

Usuario:
- GET  /proyectos-creados: proyectos con su equipo y lo que está haciendo cada miembro.
- GET  /proyectos-creados/maquinas: máquinas con su ruta base y si se pueden elegir.
- POST /proyectos-creados: crea uno (deja un encargo para el monitor de la máquina).
- GET  /proyectos-creados/{id}: un proyecto con su equipo.
- POST /proyectos-creados/{id}/pausar, /reanudar y /detener.
- POST /proyectos-creados/{id}/auto-aprobar: el interruptor de aprobación automática.
- POST /proyectos-creados/{id}/agentes: agrega un agente de código.
- GET  /proyectos-creados/{id}/chat: mensajes y órdenes; POST: un mensaje al orquestador.
- GET  /ordenes (?estado=por_aprobar); POST /ordenes/{id}/aprobar y /rechazar.

Máquina (token de máquina):
- GET  /maquinas/encargos: sus encargos pendientes (quedan tomados).
- POST /maquinas/encargos/{id}: resultado de un encargo.
- POST /maquinas/equipos: estado de las sesiones que tiene lanzadas.
- POST /maquinas/chat: una respuesta del orquestador.
- POST /maquinas/ordenes: una orden que propuso el orquestador (queda por aprobar).
- POST /maquinas/ordenes/{id}: en curso, terminada o fallida, con el resumen.
"""

from __future__ import annotations

from typing import Any, Literal, cast

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.acceso import get_acceso
from app.core.agent_state_engine import get_state_engine
from app.core.datos_maquinas import carpeta_normal, get_datos_maquinas
from app.core.proyectos_equipo import (
    ESFUERZOS,
    MAX_AGENTES,
    TIPOS_REGLA,
    ProyectoError,
    get_proyectos_equipo,
    vista_lanzada,
)

router = APIRouter(tags=["proyectos con equipo"])

Esfuerzo = Literal["low", "medium", "high", "xhigh", "max"]
assert set(ESFUERZOS) == {"low", "medium", "high", "xhigh", "max"}


def _error(e: ProyectoError) -> HTTPException:
    return HTTPException(status_code=e.status, detail=e.mensaje)


def _maquina(request: Request) -> str:
    return getattr(request.state, "maquina", None) or get_settings().MAQUINA_LOCAL_ID


def maquinas_vista() -> list[dict[str, Any]]:
    return get_proyectos_equipo().vista_maquinas(get_acceso().maquinas())


def con_estado(p: dict[str, Any]) -> dict[str, Any]:
    """El proyecto con lo que muestra la oficina de cada miembro (estado y espera)."""
    lanzadas = get_proyectos_equipo().sesiones_lanzadas()
    agentes = {
        a["agente"]["session_id"]: vista_lanzada(a, lanzadas.get(a["agente"]["session_id"]))
        for a in get_state_engine().snapshot()["agentes"]
    }
    haciendo: str | None = None
    equipo: list[dict[str, Any]] = []
    for m in p["equipo"]:
        a = agentes.get(m.get("session_id") or "")
        oficina = None
        if a is not None:
            detalle = a.get("espera_detalle")
            espera = (
                cast(dict[str, Any], detalle).get("texto") if isinstance(detalle, dict) else None
            )
            oficina = {
                "numero": a["estado"]["numero"],
                "nombre": a["estado"]["nombre"],
                "desde": a["estado"]["desde"],
                "espera": espera,
            }
            if haciendo is None and a["estado"]["numero"] not in (11, 12, 18, 19, 20, 21):
                haciendo = f"{m['nombre']}: {espera or a['estado']['nombre']}"
        equipo.append({**m, "oficina": oficina})
    return {
        **p,
        "equipo": equipo,
        "haciendo": haciendo,
        "ordenes_por_aprobar": get_proyectos_equipo().por_aprobar().get(p["id"], 0),
        "donde_quedamos_id": donde_quedamos_de(p),
    }


def donde_quedamos_de(p: dict[str, Any]) -> str | None:
    """El id de la entrada de "Dónde quedamos" (GET /proyectos) de este proyecto: la de
    su máquina y su carpeta. None mientras el monitor no la haya informado."""
    ruta = p.get("ruta")
    if not ruta:
        return None
    buscada = carpeta_normal(str(ruta))
    for d in get_datos_maquinas().vista_proyectos():
        if (
            d.get("maquina") == p["maquina"]
            and carpeta_normal(str(d.get("carpeta") or "")) == buscada
        ):
            return str(d["id"])
    return None


@router.get("/proyectos-creados")
async def listar() -> dict[str, Any]:
    return {"proyectos": [con_estado(p) for p in get_proyectos_equipo().proyectos()]}


@router.get("/proyectos-creados/maquinas")
async def maquinas() -> dict[str, Any]:
    return {"maquinas": maquinas_vista()}


class Miembro(BaseModel):
    modelo: str = Field(min_length=2, max_length=60)
    esfuerzo: Esfuerzo


class NuevoProyecto(BaseModel):
    nombre: str = Field(min_length=1, max_length=50)
    maquina: str = Field(min_length=1, max_length=64)
    cuenta: Literal["personal", "demo"]
    plantilla: Literal["web", "unity", "expo", "vacia"] = "vacia"
    orquestador: Miembro
    agentes: list[Miembro] = Field(min_length=1, max_length=MAX_AGENTES)
    auto_aprobar: bool = False


@router.post("/proyectos-creados", status_code=201)
async def crear(body: NuevoProyecto) -> dict[str, Any]:
    maquina = next((m for m in maquinas_vista() if m["id"] == body.maquina), None)
    if maquina is None:
        raise HTTPException(status_code=404, detail="No existe esa máquina.")
    if not maquina["disponible"]:
        raise HTTPException(
            status_code=409, detail=f"No se puede usar esa máquina: {maquina['motivo']}."
        )
    try:
        p = get_proyectos_equipo().crear(
            body.nombre,
            body.maquina,
            body.cuenta,
            body.plantilla,
            body.orquestador.model_dump(),
            [a.model_dump() for a in body.agentes],
            body.auto_aprobar,
            maquina["ruta_base"],
        )
    except ProyectoError as e:
        raise _error(e) from None
    return con_estado(p)


@router.get("/proyectos-creados/{id_}")
async def ver(id_: str) -> dict[str, Any]:
    p = get_proyectos_equipo().proyecto(id_)
    if p is None:
        raise HTTPException(status_code=404, detail="No existe ese proyecto.")
    return con_estado(p)


@router.post("/proyectos-creados/{id_}/pausar")
async def pausar(id_: str) -> dict[str, Any]:
    try:
        return con_estado(get_proyectos_equipo().pausar(id_))
    except ProyectoError as e:
        raise _error(e) from None


@router.post("/proyectos-creados/{id_}/reanudar")
async def reanudar(id_: str) -> dict[str, Any]:
    try:
        return con_estado(get_proyectos_equipo().reanudar(id_))
    except ProyectoError as e:
        raise _error(e) from None


@router.post("/proyectos-creados/{id_}/detener")
async def detener(id_: str) -> dict[str, Any]:
    try:
        return con_estado(get_proyectos_equipo().detener(id_))
    except ProyectoError as e:
        raise _error(e) from None


class Interruptor(BaseModel):
    activo: bool


@router.post("/proyectos-creados/{id_}/auto-aprobar")
async def auto_aprobar(id_: str, body: Interruptor) -> dict[str, Any]:
    try:
        return con_estado(get_proyectos_equipo().auto_aprobar(id_, body.activo))
    except ProyectoError as e:
        raise _error(e) from None


@router.post("/proyectos-creados/{id_}/agentes", status_code=201)
async def agregar_agente(id_: str, body: Miembro) -> dict[str, Any]:
    try:
        return con_estado(get_proyectos_equipo().agregar_agente(id_, body.modelo, body.esfuerzo))
    except ProyectoError as e:
        raise _error(e) from None


# -- reglas de la casa y comandos seguros (Prompt 39) --------------------------------------

TipoRegla = Literal[
    "idioma",
    "interfaz",
    "git",
    "documentacion",
    "ordenes",
    "entrega",
    "herramientas",
    "pruebas",
    "otra",
]
assert set(TIPOS_REGLA) == set(TipoRegla.__args__)


@router.get("/reglas")
async def reglas() -> dict[str, Any]:
    return {"reglas": get_proyectos_equipo().reglas(), "tipos": list(TIPOS_REGLA)}


class NuevaRegla(BaseModel):
    texto: str = Field(min_length=1, max_length=500)
    tipo: TipoRegla
    activa_por_defecto: bool = True


@router.post("/reglas", status_code=201)
async def crear_regla(body: NuevaRegla) -> dict[str, Any]:
    try:
        return get_proyectos_equipo().crear_regla(body.texto, body.tipo, body.activa_por_defecto)
    except ProyectoError as e:
        raise _error(e) from None


class CambioRegla(BaseModel):
    texto: str | None = Field(default=None, min_length=1, max_length=500)
    tipo: TipoRegla | None = None
    activa_por_defecto: bool | None = None


@router.patch("/reglas/{id_}")
async def cambiar_regla(id_: str, body: CambioRegla) -> dict[str, Any]:
    try:
        return get_proyectos_equipo().cambiar_regla(
            id_, body.texto, body.tipo, body.activa_por_defecto
        )
    except ProyectoError as e:
        raise _error(e) from None


@router.delete("/reglas/{id_}")
async def borrar_regla(id_: str) -> dict[str, Any]:
    try:
        get_proyectos_equipo().borrar_regla(id_)
    except ProyectoError as e:
        raise _error(e) from None
    return {"ok": True}


@router.get("/comandos")
async def comandos() -> dict[str, Any]:
    return {"comandos": get_proyectos_equipo().comandos()}


class NuevoComando(BaseModel):
    comando: str = Field(min_length=1, max_length=80)
    activo_por_defecto: bool = True


@router.post("/comandos", status_code=201)
async def crear_comando(body: NuevoComando) -> dict[str, Any]:
    try:
        return get_proyectos_equipo().crear_comando(body.comando, body.activo_por_defecto)
    except ProyectoError as e:
        raise _error(e) from None


class CambioComando(BaseModel):
    comando: str | None = Field(default=None, min_length=1, max_length=80)
    activo_por_defecto: bool | None = None


@router.patch("/comandos/{id_}")
async def cambiar_comando(id_: str, body: CambioComando) -> dict[str, Any]:
    try:
        return get_proyectos_equipo().cambiar_comando(id_, body.comando, body.activo_por_defecto)
    except ProyectoError as e:
        raise _error(e) from None


@router.delete("/comandos/{id_}")
async def borrar_comando(id_: str) -> dict[str, Any]:
    try:
        get_proyectos_equipo().borrar_comando(id_)
    except ProyectoError as e:
        raise _error(e) from None
    return {"ok": True}


@router.get("/proyectos-creados/{id_}/reglas")
async def reglas_de(id_: str) -> dict[str, Any]:
    try:
        return get_proyectos_equipo().reglas_de(id_)
    except ProyectoError as e:
        raise _error(e) from None


class AjusteRegla(BaseModel):
    activa: bool


@router.post("/proyectos-creados/{id_}/reglas/{regla_id}")
async def ajustar_regla(id_: str, regla_id: str, body: AjusteRegla) -> dict[str, Any]:
    try:
        return get_proyectos_equipo().ajustar_regla(id_, regla_id, body.activa)
    except ProyectoError as e:
        raise _error(e) from None


class AjusteComando(BaseModel):
    activo: bool


@router.post("/proyectos-creados/{id_}/comandos/{comando_id}")
async def ajustar_comando(id_: str, comando_id: str, body: AjusteComando) -> dict[str, Any]:
    try:
        return get_proyectos_equipo().ajustar_comando(id_, comando_id, body.activo)
    except ProyectoError as e:
        raise _error(e) from None


# -- chat y órdenes (Prompt 38) -----------------------------------------------------------


EstadoOrden = Literal["por_aprobar", "aprobada", "rechazada", "en_curso", "terminada", "fallida"]


@router.get("/proyectos-creados/{id_}/ordenes")
async def ordenes_de(id_: str, estado: EstadoOrden | None = None) -> dict[str, Any]:
    """Solo las órdenes de un proyecto (las más nuevas primero), sin los mensajes del chat:
    título, estado, estimado, dificultad, quién decidió y cuándo, motivo y resumen."""
    reg = get_proyectos_equipo()
    if reg.proyecto(id_) is None:
        raise HTTPException(status_code=404, detail="No existe ese proyecto.")
    return {"ordenes": reg.ordenes(id_, estado=estado)}


@router.get("/proyectos-creados/{id_}/chat")
async def chat(id_: str) -> dict[str, Any]:
    reg = get_proyectos_equipo()
    if reg.proyecto(id_) is None:
        raise HTTPException(status_code=404, detail="No existe ese proyecto.")
    return {"mensajes": reg.mensajes(id_), "ordenes": list(reversed(reg.ordenes(id_)))}


class NuevoMensaje(BaseModel):
    texto: str = Field(min_length=1, max_length=8000)


@router.post("/proyectos-creados/{id_}/chat", status_code=201)
async def escribir(id_: str, body: NuevoMensaje) -> dict[str, Any]:
    try:
        return get_proyectos_equipo().escribir(id_, body.texto)
    except ProyectoError as e:
        raise _error(e) from None


Dispositivo = Literal["web", "app", "celular", "pc"]


@router.get("/ordenes")
async def ordenes(estado: EstadoOrden | None = None) -> dict[str, Any]:
    return {"ordenes": get_proyectos_equipo().ordenes(estado=estado)}


class Aprobacion(BaseModel):
    texto: str | None = Field(default=None, max_length=20000)
    dispositivo: Dispositivo = "web"


@router.post("/ordenes/{id_}/aprobar")
async def aprobar(id_: str, body: Aprobacion) -> dict[str, Any]:
    try:
        return get_proyectos_equipo().aprobar(id_, body.texto, body.dispositivo)
    except ProyectoError as e:
        raise _error(e) from None


class Rechazo(BaseModel):
    motivo: str = Field(min_length=1, max_length=500)
    dispositivo: Dispositivo = "web"


@router.post("/ordenes/{id_}/rechazar")
async def rechazar(id_: str, body: Rechazo) -> dict[str, Any]:
    try:
        return get_proyectos_equipo().rechazar(id_, body.motivo, body.dispositivo)
    except ProyectoError as e:
        raise _error(e) from None


# -- el monitor -------------------------------------------------------------------------


@router.get("/maquinas/encargos")
async def encargos(request: Request) -> dict[str, Any]:
    return {"encargos": get_proyectos_equipo().encargos_pendientes(_maquina(request))}


class EstadoMiembro(BaseModel):
    nombre: str = Field(min_length=1, max_length=40)
    estado: Literal["pendiente", "activo", "pausado", "detenido", "error"]


class ResultadoEncargo(BaseModel):
    ok: bool
    error: str | None = Field(default=None, max_length=500)
    ruta: str | None = Field(default=None, max_length=400)
    miembros: list[EstadoMiembro] = Field(default_factory=lambda: [], max_length=10)


@router.post("/maquinas/encargos/{id_}")
async def resultado_encargo(request: Request, id_: str, body: ResultadoEncargo) -> dict[str, Any]:
    try:
        return get_proyectos_equipo().informar_encargo(
            _maquina(request),
            id_,
            body.ok,
            body.error,
            body.ruta,
            [m.model_dump() for m in body.miembros],
        )
    except ProyectoError as e:
        raise _error(e) from None


class Equipo(BaseModel):
    proyecto_id: str = Field(min_length=1, max_length=64)
    miembros: list[EstadoMiembro] = Field(max_length=10)


class Equipos(BaseModel):
    equipos: list[Equipo] = Field(max_length=50)


@router.post("/maquinas/equipos")
async def equipos(request: Request, body: Equipos) -> dict[str, Any]:
    n = get_proyectos_equipo().informar_equipos(
        _maquina(request), [e.model_dump() for e in body.equipos]
    )
    return {"actualizados": n}


class RespuestaOrquestador(BaseModel):
    proyecto_id: str = Field(min_length=1, max_length=64)
    origen_id: str = Field(min_length=8, max_length=64)
    texto: str = Field(min_length=1, max_length=20000)


@router.post("/maquinas/chat")
async def respuesta_orquestador(request: Request, body: RespuestaOrquestador) -> dict[str, Any]:
    try:
        return get_proyectos_equipo().respuesta_orquestador(
            _maquina(request), body.proyecto_id, body.origen_id, body.texto
        )
    except ProyectoError as e:
        raise _error(e) from None


class OrdenPropuesta(BaseModel):
    proyecto_id: str = Field(min_length=1, max_length=64)
    origen_id: str = Field(min_length=8, max_length=64)
    agente: str = Field(min_length=1, max_length=40)
    texto: str = Field(min_length=1, max_length=20000)
    estimado: str | None = Field(default=None, max_length=60)
    dificultad: str | None = Field(default=None, max_length=60)
    titulo: str | None = Field(default=None, max_length=200)


@router.post("/maquinas/ordenes")
async def proponer_orden(request: Request, body: OrdenPropuesta) -> dict[str, Any]:
    try:
        o = get_proyectos_equipo().proponer_orden(
            _maquina(request),
            body.proyecto_id,
            body.origen_id,
            body.agente,
            body.texto,
            body.estimado,
            body.dificultad,
            body.titulo,
        )
    except ProyectoError as e:
        raise _error(e) from None
    return {"id": o["id"], "numero": o["numero"], "estado": o["estado"]}


class AvanceOrden(BaseModel):
    estado: Literal["en_curso", "terminada", "fallida"]
    resumen: str | None = Field(default=None, max_length=4000)


@router.post("/maquinas/ordenes/{id_}")
async def avance_orden(request: Request, id_: str, body: AvanceOrden) -> dict[str, Any]:
    try:
        return get_proyectos_equipo().informar_orden(
            _maquina(request), id_, body.estado, body.resumen
        )
    except ProyectoError as e:
        raise _error(e) from None
