"""Lectura de las transcripciones de Claude Code (JSONL) en esta máquina.

Copia fiel de lo que hacía el backend (``backend/app/core/transcript_tail.py``):
nunca carga el archivo completo salvo para el acumulado de tokens, que se lee
de forma incremental (solo lo agregado desde la última lectura).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, cast

TAIL_BYTES = 256_000


def _tail(path: Path, tail_bytes: int = TAIL_BYTES) -> list[dict[str, Any]]:
    with open(path, "rb") as f:
        f.seek(0, 2)
        size = f.tell()
        start = max(0, size - tail_bytes)
        f.seek(start)
        chunk = f.read()
    lines = chunk.split(b"\n")
    if start > 0:
        lines = lines[1:]
    out: list[dict[str, Any]] = []
    for raw in lines:
        raw = raw.strip()
        if not raw.startswith(b"{"):
            continue
        try:
            obj = json.loads(raw.decode("utf-8", errors="ignore"))
        except ValueError:
            continue
        if isinstance(obj, dict):
            out.append(cast(dict[str, Any], obj))
    return out


def _mensaje(e: dict[str, Any]) -> dict[str, Any]:
    m = e.get("message")
    return cast(dict[str, Any], m) if isinstance(m, dict) else {}


def _ts(e: dict[str, Any]) -> datetime | None:
    raw = e.get("timestamp")
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _textos(content: object) -> list[str]:
    if isinstance(content, str):
        return [content]
    if isinstance(content, list):
        return [
            str(cast(dict[str, Any], b).get("text", ""))
            for b in cast(list[Any], content)
            if isinstance(b, dict) and cast(dict[str, Any], b).get("type") == "text"
        ]
    return []


def _es_resultado(content: object) -> bool:
    return isinstance(content, list) and any(
        isinstance(b, dict) and cast(dict[str, Any], b).get("type") == "tool_result"
        for b in cast(list[Any], content)
    )


def resumen_cola(path: Path) -> dict[str, Any]:
    """Lo que dice el final de la transcripción: contexto, modelo, textos, turno."""
    entradas = _tail(path)
    datos: dict[str, Any] = {}
    for e in reversed(entradas):
        m = _mensaje(e)
        uso = m.get("usage")
        if isinstance(uso, dict):
            u = cast(dict[str, Any], uso)
            datos["contexto_tokens"] = (
                int(u.get("input_tokens", 0) or 0)
                + int(u.get("cache_creation_input_tokens", 0) or 0)
                + int(u.get("cache_read_input_tokens", 0) or 0)
                + int(u.get("output_tokens", 0) or 0)
            )
            if isinstance(m.get("model"), str):
                datos["modelo"] = m["model"]
            break
    for e in reversed(entradas):
        if e.get("type") != "assistant":
            continue
        texto = "\n".join(t for t in _textos(_mensaje(e).get("content")) if t.strip())
        if texto:
            datos["ultimo_texto_asistente"] = texto[-4000:]
            break
    for e in reversed(entradas):
        if e.get("type") != "user":
            continue
        contenido = _mensaje(e).get("content")
        if _es_resultado(contenido):
            continue
        texto = "\n".join(t for t in _textos(contenido) if t.strip())
        if texto:
            datos["ultimo_texto_usuario"] = texto[-4000:]
            break
    conversacion = [e for e in entradas if e.get("type") in ("user", "assistant")]
    if conversacion:
        primero, ultimo = _ts(conversacion[0]), _ts(conversacion[-1])
        if primero:
            datos["primer_ts"] = primero.isoformat()
        if ultimo:
            datos["ultimo_ts"] = ultimo.isoformat()
        m = _mensaje(conversacion[-1])
        datos["turno_terminado"] = (
            conversacion[-1].get("type") == "assistant" and m.get("stop_reason") == "end_turn"
        )
    return datos


class Totales:
    """Tokens de salida acumulados, una vez por id de mensaje (lectura incremental)."""

    def __init__(self, path: Path, desde: datetime | None = None) -> None:
        self.path = path
        self.desde = desde
        self.offset = 0
        self.vistos: set[str] = set()
        self.salida = 0
        self.entrada_nueva = 0

    def leer(self) -> int:
        try:
            size = self.path.stat().st_size
        except OSError:
            return self.salida
        if size < self.offset:  # archivo reemplazado
            self.offset, self.salida, self.entrada_nueva = 0, 0, 0
            self.vistos.clear()
        if size > self.offset:
            with open(self.path, "rb") as f:
                f.seek(self.offset)
                chunk = f.read(size - self.offset)
            fin = chunk.rfind(b"\n")
            if fin >= 0:
                self.offset += fin + 1
                self._consumir(chunk[: fin + 1])
        return self.salida

    def _consumir(self, datos: bytes) -> None:
        for raw in datos.split(b"\n"):
            if b'"usage"' not in raw:
                continue
            try:
                obj = json.loads(raw.decode("utf-8", errors="ignore"))
            except ValueError:
                continue
            if not isinstance(obj, dict):
                continue
            m = _mensaje(cast(dict[str, Any], obj))
            uso, mid = m.get("usage"), m.get("id")
            if not isinstance(uso, dict) or not isinstance(mid, str) or mid in self.vistos:
                continue
            self.vistos.add(mid)
            if self.desde is not None:
                ts = _ts(cast(dict[str, Any], obj))
                if ts is not None and ts < self.desde:
                    continue
            u = cast(dict[str, Any], uso)
            self.salida += int(u.get("output_tokens", 0) or 0)
            self.entrada_nueva += int(u.get("input_tokens", 0) or 0) + int(
                u.get("cache_creation_input_tokens", 0) or 0
            )
