from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from conftest import TOKEN, ServidorFalso

from visualizador_monitor.cliente import Servidor
from visualizador_monitor.lector import Lector
from visualizador_monitor.transcripcion import Totales, resumen_cola


def _linea(**kw: Any) -> str:
    return json.dumps(kw) + "\n"


def _transcripcion(ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(
        _linea(
            type="user", timestamp="2026-10-10T12:00:00Z", message={"content": "Hola, revisa esto"}
        )
        + _linea(
            type="assistant",
            timestamp="2026-10-10T12:00:05Z",
            message={
                "id": "m1",
                "model": "claude-opus-5-5",
                "content": [{"type": "text", "text": "Reviso."}],
                "usage": {"input_tokens": 10, "cache_read_input_tokens": 100, "output_tokens": 7},
            },
        )
        + _linea(
            type="user",
            timestamp="2026-10-10T12:00:06Z",
            message={"content": [{"type": "tool_result", "content": "ok"}]},
        )
        + _linea(
            type="assistant",
            timestamp="2026-10-10T12:00:09Z",
            message={
                "id": "m2",
                "model": "claude-opus-5-5",
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "¿Sigo con el resto?"}],
                "usage": {"input_tokens": 5, "cache_read_input_tokens": 120, "output_tokens": 30},
            },
        ),
        encoding="utf-8",
    )


def test_resumen_de_la_cola(tmp_path: Path) -> None:
    ruta = tmp_path / "t.jsonl"
    _transcripcion(ruta)
    r = resumen_cola(ruta)
    assert r["contexto_tokens"] == 155
    assert r["modelo"] == "claude-opus-5-5"
    assert r["ultimo_texto_asistente"] == "¿Sigo con el resto?"
    assert r["ultimo_texto_usuario"] == "Hola, revisa esto"
    assert r["turno_terminado"] is True
    assert r["primer_ts"].startswith("2026-10-10T12:00:00")


def test_totales_incrementales_y_sin_repetir_mensajes(tmp_path: Path) -> None:
    ruta = tmp_path / "t.jsonl"
    _transcripcion(ruta)
    t = Totales(ruta)
    assert t.leer() == 37
    with open(ruta, "a", encoding="utf-8") as f:
        # el mismo mensaje repetido (Claude Code escribe un bloque por línea) no suma
        f.write(_linea(type="assistant", message={"id": "m2", "usage": {"output_tokens": 30}}))
        f.write(_linea(type="assistant", message={"id": "m3", "usage": {"output_tokens": 3}}))
    assert t.leer() == 40


def test_totales_desde_el_primer_evento(tmp_path: Path) -> None:
    ruta = tmp_path / "t.jsonl"
    _transcripcion(ruta)
    t = Totales(ruta, desde=datetime(2026, 10, 10, 12, 0, 7, tzinfo=UTC))
    assert t.leer() == 30


def test_observaciones_solo_de_las_cuentas_configuradas(
    tmp_path: Path, servidor: ServidorFalso
) -> None:
    cuenta = tmp_path / ".claude"
    dentro = cuenta / "projects" / "p" / "s1.jsonl"
    fuera = tmp_path / "otro" / "s2.jsonl"
    _transcripcion(dentro)
    _transcripcion(fuera)
    lector = Lector(Servidor(servidor.url, TOKEN), [str(cuenta)])
    lector.vio_evento(
        {
            "session_id": "prueba-l1",
            "timestamp": "2026-10-10T11:59:59Z",
            "data": {
                "transcript_path": str(dentro),
                "claude_pid": os.getpid(),
                "claude_pid_created": None,
            },
        }
    )
    lector.vio_evento({"session_id": "prueba-l2", "data": {"transcript_path": str(fuera)}})
    assert lector.ciclo() == 2
    enviado = next(p for p in servidor.pedidos if p.ruta == "/api/v1/maquinas/observaciones").json()
    por_id = {o["session_id"]: o for o in enviado["sesiones"]}
    assert por_id["prueba-l1"]["contexto_tokens"] == 155
    assert por_id["prueba-l1"]["tokens_salida_total"] == 37
    assert por_id["prueba-l1"]["proceso_vivo"] is True
    assert "contexto_tokens" not in por_id["prueba-l2"]  # fuera de las cuentas: no se lee
    assert lector.ultimo_envio is not None


def test_latido_con_sistema_y_version(servidor: ServidorFalso) -> None:
    lector = Lector(Servidor(servidor.url, TOKEN), [])
    assert lector.latido() is True
    datos = next(p for p in servidor.pedidos if p.ruta == "/api/v1/maquinas/latido").json()
    assert datos["sistema"] in ("windows", "mac", "linux")
    assert datos["version_monitor"] and datos["hostname"]


def test_sin_servidor_el_ciclo_no_falla(tmp_path: Path) -> None:
    lector = Lector(Servidor("http://127.0.0.1:9", TOKEN), [])
    lector.vio_evento({"session_id": "prueba-l3"})
    assert lector.ciclo() == 0
    assert lector.latido() is False


def test_primer_evento_sobrevive_al_reinicio(tmp_path: Path) -> None:
    from visualizador_monitor.cola import Cola

    cola = Cola(tmp_path / "c.db")
    primero = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
    assert cola.primer_evento("s1", primero) == primero
    otra = Cola(tmp_path / "c.db")  # reinicio
    lector = Lector(Servidor("http://127.0.0.1:9", TOKEN), [], otra)
    lector.vio_evento({"session_id": "s1", "timestamp": "2026-10-10T15:00:00Z"})
    assert lector.sesiones["s1"].primer_evento == primero


def test_rutas_de_red_no_se_abren(tmp_path: Path) -> None:
    """Una ruta UNC haría que Windows se autentique ante otro equipo: ni se toca."""
    lector = Lector(Servidor("http://127.0.0.1:9", TOKEN), [str(tmp_path / ".claude")])
    for ruta in (
        r"\\atacante.example\share\x.jsonl",
        "//atacante.example/share/x.jsonl",
        r"\\?\UNC\atacante.example\share\x.jsonl",
        str(tmp_path / "fuera.jsonl"),
        str(tmp_path / ".claude" / ".." / "fuera.jsonl"),
    ):
        assert lector._permitida(ruta) is None  # pyright: ignore[reportPrivateUsage]
