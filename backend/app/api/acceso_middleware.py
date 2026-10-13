"""Access control (stage 1.1): sessions, machine tokens and CSRF.

With VISUALIZADOR_AUTH=desactivado (default, local) every request goes on as
before; the request only learns its machine: the one of a valid machine token
or the local one (MAQUINA_LOCAL_ID).

With VISUALIZADOR_AUTH=activado:

- Only the API (/api/...) and the API docs are guarded. Pages
  and static files of the frontend carry no data and stay public, so /entrar
  loads when the backend itself serves the frontend.
- Public: health, sign-in state, sign-in (web and app token), sign-out.
- Ingest (events, register and wait for permissions, machine heartbeat): only
  with a machine token (``Authorization: Bearer vam_...``). Machine tokens
  are refused everywhere else (403): a machine never reads the state or
  decides permissions.
- Everything else: a user session, the httpOnly cookie of the web or an app
  token (``Authorization: Bearer vap_...``). With the cookie, requests that
  change something must also send ``X-Visualizador: 1`` (CSRF: a page of
  another site cannot add that header without CORS approval).
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.core.acceso import Sesion, get_acceso

COOKIE_SESION = "visualizador_sesion"
# With https the cookie is "__Host-" (browser-enforced: Secure, path /, no domain).
COOKIE_SESION_SEGURA = "__Host-visualizador_sesion"
ENCABEZADO_CSRF = "X-Visualizador"
_METODOS_SEGUROS = frozenset({"GET", "HEAD", "OPTIONS"})

_API = get_settings().API_V1_STR
PUBLICAS: tuple[tuple[str, str], ...] = (
    ("GET", "/health"),
    ("GET", f"{_API}/auth/estado"),
    ("POST", f"{_API}/auth/entrar"),
    ("POST", f"{_API}/auth/app/token"),
    ("POST", f"{_API}/auth/salir"),
)
_INGESTA: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("POST", re.compile(rf"{_API}/events")),
    ("POST", re.compile(rf"{_API}/permisos/solicitudes")),
    ("GET", re.compile(rf"{_API}/permisos/solicitudes/[A-Za-z0-9_-]+")),
    ("POST", re.compile(rf"{_API}/maquinas/latido")),
    ("POST", re.compile(rf"{_API}/maquinas/observaciones")),
    ("POST", re.compile(rf"{_API}/maquinas/limites")),
    ("POST", re.compile(rf"{_API}/maquinas/proyectos")),
    # Etapa 2.4: avisos de sus propias sesiones por resumir (excepción a "solo envía
    # datos": devuelve, enmascarado, lo que esa misma máquina mandó) y las frases.
    ("GET", re.compile(rf"{_API}/maquinas/avisos")),
    ("POST", re.compile(rf"{_API}/maquinas/resumenes")),
    # Etapa 4: encargos de sus proyectos (crear, pausar, reanudar) y estado de sus equipos.
    ("GET", re.compile(rf"{_API}/maquinas/encargos")),
    ("POST", re.compile(rf"{_API}/maquinas/encargos/[A-Za-z0-9]+")),
    ("POST", re.compile(rf"{_API}/maquinas/equipos")),
    # Prompt 38: respuestas del orquestador, órdenes que propone (quedan por aprobar:
    # la máquina nunca aprueba) y el avance de las aprobadas.
    ("POST", re.compile(rf"{_API}/maquinas/chat")),
    # Prompt 45: leído, respondiendo y el texto parcial de la respuesta en curso.
    ("POST", re.compile(rf"{_API}/maquinas/chat/en-vivo")),
    ("POST", re.compile(rf"{_API}/maquinas/ordenes")),
    ("POST", re.compile(rf"{_API}/maquinas/ordenes/[A-Za-z0-9]+")),
)
# Guarded with access on: the API and its docs.
_PROTEGIDAS = (f"{_API}/", "/docs", "/redoc", "/openapi.json")


def es_ingesta(method: str, path: str) -> bool:
    return any(m == method and r.fullmatch(path) for m, r in _INGESTA)


def es_protegida(path: str) -> bool:
    return path.startswith(_PROTEGIDAS) or path == _API


def es_publica(method: str, path: str) -> bool:
    return (method, path) in PUBLICAS


def bearer(request_headers: Mapping[str, str]) -> str | None:
    valor = request_headers.get("authorization") or ""
    if valor.lower().startswith("bearer "):
        return valor[7:].strip() or None
    return None


def ip_cliente(request: Request) -> str:
    """Client IP. Behind nginx (CONFIAR_PROXY): X-Real-IP ($remote_addr, set by
    nginx), or else the LAST X-Forwarded-For entry (the one nginx appends): the
    first entries come from the client and can be forged."""
    if get_settings().CONFIAR_PROXY:
        real = request.headers.get("x-real-ip", "").strip()
        if real:
            return real[:64]
        reenviada = request.headers.get("x-forwarded-for", "")
        if reenviada:
            return reenviada.split(",")[-1].strip()[:64]
    return request.client.host if request.client else "desconocida"


def es_https(request: Request) -> bool:
    if request.url.scheme == "https":
        return True
    return (
        get_settings().CONFIAR_PROXY
        and request.headers.get("x-forwarded-proto", "").lower() == "https"
    )


def cookie_segura(request: Request) -> bool:
    modo = get_settings().COOKIE_SEGURA.strip().lower()
    if modo == "si":
        return True
    if modo == "no":
        return False
    return es_https(request)


def nombre_cookie(request: Request) -> str:
    return COOKIE_SESION_SEGURA if cookie_segura(request) else COOKIE_SESION


def cookie_de(cookies: Mapping[str, str]) -> str | None:
    """Session cookie of a request (secure name first)."""
    return cookies.get(COOKIE_SESION_SEGURA) or cookies.get(COOKIE_SESION)


def _no(status: int, detalle: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": detalle})


class AccesoMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        settings = get_settings()
        metodo = request.method
        ruta = request.url.path
        token = bearer(request.headers)
        acceso = get_acceso()
        maquina = (
            acceso.validar_token_maquina(token) if token and token.startswith("vam_") else None
        )
        request.state.sesion = None

        if not settings.auth_activa:
            request.state.maquina = maquina or settings.MAQUINA_LOCAL_ID
            return await call_next(request)

        request.state.maquina = None
        if metodo == "OPTIONS" or es_publica(metodo, ruta) or not es_protegida(ruta):
            return await call_next(request)

        if es_ingesta(metodo, ruta):
            if maquina is None:
                return _no(401, "Esta ruta necesita un token de máquina válido.")
            request.state.maquina = maquina
            return await call_next(request)

        if maquina is not None:
            return _no(403, "Un token de máquina solo puede enviar datos.")

        sesion: Sesion | None = None
        por_cookie = False
        if token and token.startswith("vap_"):
            sesion = acceso.validar_sesion(token, tipo="app")
        else:
            cookie = cookie_de(request.cookies)
            if cookie:
                sesion = acceso.validar_sesion(cookie, tipo="web")
                por_cookie = sesion is not None
        if sesion is None:
            return _no(401, "Inicia sesión para continuar.")
        if (
            por_cookie
            and metodo not in _METODOS_SEGUROS
            and request.headers.get(ENCABEZADO_CSRF) != "1"
        ):
            return _no(403, "Falta el encabezado X-Visualizador (protección contra CSRF).")
        request.state.sesion = sesion
        return await call_next(request)
