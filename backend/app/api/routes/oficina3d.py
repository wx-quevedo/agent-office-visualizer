"""Office layout of /oficina/3d (furniture and colour theme).

GET and PUT /api/v1/oficina3d/distribucion read and write a JSON file in the
data folder of each copy (next to the engine event log, or
OFICINA3D_DISTRIBUCION_PATH). When it does not exist yet, the base layout of
the repository (frontend/public/oficina3d/distribucion.json) is returned.
The JSON is validated (known furniture, office limits, maximum size) before
saving; clients are limited by the backend middleware (loopback/Tailscale).
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Must match frontend/src/components/oficina3d/escena/furniture.tsx (BUILTIN).
TIPOS_MUEBLE = ("plant", "desk", "sofa", "coffee", "meeting", "shelf", "lamp")
# Inside the outer walls (x ±23, z ±16) with room for the piece.
LIMITE_X = 22.5
LIMITE_Z = 15.5
MAX_MUEBLES = 200
MAX_BYTES = 64 * 1024
_COLOR = r"^#[0-9a-fA-F]{6}$"

_BACKEND_DIR = Path(__file__).resolve().parents[3]
BASE_REPO = _BACKEND_DIR.parent / "frontend" / "public" / "oficina3d" / "distribucion.json"


class Mueble(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    type: Literal["plant", "desk", "sofa", "coffee", "meeting", "shelf", "lamp"]
    x: float = Field(ge=-LIMITE_X, le=LIMITE_X, allow_inf_nan=False)
    z: float = Field(ge=-LIMITE_Z, le=LIMITE_Z, allow_inf_nan=False)
    ry: float = Field(ge=-7, le=7, allow_inf_nan=False)


class Distribucion(BaseModel):
    # JSON keys keep the camelCase of the original layout format.
    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)

    version: int = Field(default=1, ge=1, le=99)
    items: list[Mueble] = Field(default_factory=lambda: [], max_length=MAX_MUEBLES)
    floor_color: str | None = Field(default=None, pattern=_COLOR, alias="floorColor")
    wall_color: str | None = Field(default=None, pattern=_COLOR, alias="wallColor")
    tema: str | None = Field(default=None, max_length=32, pattern=r"^[a-z]+$")

    @field_validator("items")
    @classmethod
    def _ids_unicos(cls, items: list[Mueble]) -> list[Mueble]:
        ids = [m.id for m in items]
        if len(ids) != len(set(ids)):
            raise ValueError("hay muebles con el mismo id")
        return items


def ruta_distribucion() -> Path:
    """JSON of this copy: OFICINA3D_DISTRIBUCION_PATH or next to the event log."""
    s = get_settings()
    if s.OFICINA3D_DISTRIBUCION_PATH:
        return Path(s.OFICINA3D_DISTRIBUCION_PATH)
    return Path(s.STATE_EVENT_LOG_PATH).parent / "distribucion.json"


def _leer(ruta: Path) -> Distribucion | None:
    try:
        return Distribucion.model_validate(json.loads(ruta.read_text(encoding="utf-8")))
    except FileNotFoundError:
        return None
    except (OSError, ValueError, ValidationError) as exc:
        logger.warning("Distribución no válida en %s: %s", ruta, exc)
        return None


def _escribir(ruta: Path, d: Distribucion) -> None:
    """Atomic write: a temporary file in the same folder, then replace."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(d.model_dump(), ensure_ascii=False, indent=2)
    fd, tmp = tempfile.mkstemp(prefix=".distribucion-", suffix=".json", dir=ruta.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(texto)
        os.replace(tmp, ruta)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise


@router.get("/distribucion")
async def get_distribucion() -> dict[str, Any]:
    """Saved layout of this copy, or the base one of the repository."""
    guardada = _leer(ruta_distribucion())
    if guardada is not None:
        return {"origen": "guardada", "distribucion": guardada.model_dump()}
    base = _leer(BASE_REPO) or Distribucion()
    return {"origen": "base", "distribucion": base.model_dump()}


@router.put("/distribucion")
async def put_distribucion(request: Request) -> dict[str, Any]:
    """Validate and save the layout of this copy."""
    cuerpo = await request.body()
    if len(cuerpo) > MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"La distribución pasa de {MAX_BYTES} bytes")
    try:
        datos = json.loads(cuerpo or b"null")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="El cuerpo no es JSON válido") from exc
    try:
        d = Distribucion.model_validate(datos)
    except ValidationError as exc:
        errores = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:10]]
        raise HTTPException(status_code=422, detail=errores) from exc
    _escribir(ruta_distribucion(), d)
    return {"origen": "guardada", "distribucion": d.model_dump()}
