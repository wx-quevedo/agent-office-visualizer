"""Static server for the compiled frontend of the daily copy (port 3000).

The frontend is a Next.js static export (``frontend/out``). This small
Starlette app serves it with the same trust boundary as the backend (loopback
and the Tailscale network only) and maps clean URLs to the exported files:
``/oficina`` → ``oficina.html``, ``/oficina/3d`` → ``oficina/3d.html``.

Why this and not ``python -m http.server`` or a Node server: it runs with the
backend's own virtualenv (no extra install), handles the clean URLs of the
export (http.server would list the ``oficina/`` folder instead of serving
``oficina.html``), sets correct MIME types on Windows (the registry can map
``.js`` to ``text/plain``, which browsers refuse for modules) and does not
reload or watch files.

Run: python -m app.servidor_frontend --dir ../frontend/out --port 3000
"""

from __future__ import annotations

import argparse
import ipaddress
import mimetypes
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, PlainTextResponse, Response
from starlette.routing import Route

# Windows reads MIME types from the registry; force the ones the export uses.
for _tipo, _ext in (
    ("text/javascript", ".js"),
    ("text/javascript", ".mjs"),
    ("text/css", ".css"),
    ("application/json", ".json"),
    ("image/svg+xml", ".svg"),
    ("image/png", ".png"),
    ("image/x-icon", ".ico"),
    ("font/woff2", ".woff2"),
    ("font/woff", ".woff"),
    ("text/plain", ".txt"),
    ("text/html", ".html"),
):
    mimetypes.add_type(_tipo, _ext)

_LOOPBACK = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})
_TAILNET = ipaddress.ip_network("100.64.0.0/10")


def cliente_permitido(host: str | None) -> bool:
    """Loopback or the Tailscale network (same rule as the backend middleware)."""
    if host is None:
        return False
    if host in _LOOPBACK:
        return True
    try:
        return ipaddress.ip_address(host) in _TAILNET
    except ValueError:
        return False


def _segmento_rsc(rel: str) -> list[str]:
    """Next 16 asks for ``oficina/__next.oficina.__PAGE__.txt`` (client
    navigation data) but the static export writes it as
    ``oficina/__next.oficina/__PAGE__.txt``: dots of the segment → folders.
    """
    carpeta, _, nombre = rel.rpartition("/")
    if not (nombre.startswith("__next.") and nombre.endswith(".txt")):
        return []
    nucleo = nombre[len("__next.") : -len(".txt")]
    alterno = "__next." + nucleo.replace(".", "/") + ".txt"
    return [f"{carpeta}/{alterno}" if carpeta else alterno]


def resolver(raiz: Path, ruta: str) -> Path | None:
    """Exported file for a URL path, or None. Never leaves ``raiz``."""
    base = raiz.resolve()
    rel = ruta.lstrip("/")
    if not rel:
        candidatos = ["index.html"]
    else:
        sin_barra = rel.rstrip("/")
        candidatos = [rel, f"{sin_barra}.html", f"{sin_barra}/index.html"]
    candidatos += _segmento_rsc(rel)
    for c in candidatos:
        p = (base / c).resolve()
        if p.is_relative_to(base) and p.is_file():
            return p
    return None


def crear_app(raiz: Path) -> Starlette:
    async def servir(request: Request) -> Response:
        if not cliente_permitido(request.client.host if request.client else None):
            return PlainTextResponse("Acceso denegado: solo localhost o Tailscale", status_code=403)
        archivo = resolver(raiz, request.url.path)
        if archivo is None:
            no_encontrado = raiz / "404.html"
            if no_encontrado.is_file():
                return FileResponse(
                    no_encontrado, status_code=404, headers={"Cache-Control": "no-cache"}
                )
            return PlainTextResponse("No encontrado", status_code=404)
        # Hashed build assets can be cached; pages always revalidate (updates).
        cache = (
            "public, max-age=31536000, immutable"
            if "/_next/static/" in request.url.path
            else "no-cache"
        )
        return FileResponse(archivo, headers={"Cache-Control": cache})

    return Starlette(routes=[Route("/{ruta:path}", servir, methods=["GET", "HEAD"])])


def main() -> None:
    parser = argparse.ArgumentParser(description="Servidor del frontend compilado (copia diaria)")
    parser.add_argument("--dir", required=True, help="Carpeta del export estático (frontend/out)")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=3000)
    args = parser.parse_args()
    raiz = Path(args.dir)
    if not (raiz / "index.html").is_file():
        raise SystemExit(f"No hay un frontend compilado en {raiz} (falta index.html)")
    import uvicorn

    # Selector loop: on Windows the default Proactor loop closes the listening
    # socket when an accept fails (WinError 64) and the server stops answering.
    uvicorn.run(
        crear_app(raiz),
        host=args.host,
        port=args.port,
        log_level="warning",
        loop="asyncio:SelectorEventLoop",
    )


if __name__ == "__main__":
    main()
