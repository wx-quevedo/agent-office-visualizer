"""Backend de la oficina de agentes.

Recibe los eventos de los hooks y de los monitores (``/api/v1/events``), mantiene
el motor de estados con su propio registro, atiende los permisos, el acceso
(sesiones, máquinas y tokens) y la distribución de la oficina 3D.
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from rich.logging import RichHandler

from app.api.acceso_middleware import AccesoMiddleware
from app.api.middleware import ApiKeyMiddleware, LocalhostOnlyMiddleware
from app.api.routes import (
    acceso,
    agents_state,
    avisos,
    bandejas,
    events,
    oficina3d,
    permisos,
    ver_bien,
)
from app.config import get_settings
from app.core.acceso import exigir_secreto
from app.core.agent_state_engine import bootstrap, get_state_engine, run_tick_loop
from app.core.migracion_maquinas import migrar_esta_copia

settings = get_settings()

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=settings.LOG_RICH_TRACEBACKS)],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Manage application startup and shutdown lifecycle."""
    # Sign-in on needs a real secret for the token hashes.
    exigir_secreto(settings)
    # Stage 1.1: existing data gets the local machine (backup first, once).
    try:
        resultado = await asyncio.to_thread(migrar_esta_copia)
        if resultado.get("aplicada"):
            logger.info("Datos asignados a la máquina local: %s", resultado)
    except Exception:
        logger.exception("No se pudo aplicar la migración de máquinas")
        raise

    # Catalog state engine: reload recent sessions, then recompute every second
    # so time-based states (program wait, idle, rest) change without events.
    state_engine = get_state_engine()
    try:
        loaded = await bootstrap(state_engine)
        logger.info("Agent state engine start-up from its event log: %s", loaded)
    except Exception:
        logger.exception("Agent state engine bootstrap failed")
    state_ticker = asyncio.create_task(run_tick_loop(state_engine))

    yield

    state_ticker.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await state_ticker
    if state_engine.store is not None:
        state_engine.store.flush()
        state_engine.store.close()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)


app.add_middleware(AccesoMiddleware)
app.add_middleware(LocalhostOnlyMiddleware)
app.add_middleware(ApiKeyMiddleware)
# Added last = outermost: every answer (also a 401/403 of the access checks)
# carries the CORS headers, so the browser can read it and go to /entrar.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    # Credentials: the session cookie (VISUALIZADOR_AUTH=activado). The origins
    # are an explicit list, never "*".
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(acceso.router, prefix=f"{settings.API_V1_STR}")
app.include_router(agents_state.router, prefix=f"{settings.API_V1_STR}")
app.include_router(oficina3d.router, prefix=f"{settings.API_V1_STR}/oficina3d")
app.include_router(permisos.router, prefix=f"{settings.API_V1_STR}")
app.include_router(events.router, prefix=f"{settings.API_V1_STR}")
app.include_router(ver_bien.router, prefix=f"{settings.API_V1_STR}")
app.include_router(avisos.router, prefix=f"{settings.API_V1_STR}")
app.include_router(bandejas.router, prefix=f"{settings.API_V1_STR}")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled route exceptions: log with context, generic 500."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
