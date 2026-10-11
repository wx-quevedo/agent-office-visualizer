"""Stage 1.2: what a machine monitor sends (observations) and LECTURA_LOCAL.

The engine reads transcripts and processes only for sessions of its own
machine; for the others it uses what their monitor observes.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from app.core.agent_event_store import AgentEventStore
from app.core.agent_state_engine import AgentStateEngine, Thresholds
from app.models.events import AnyEvent, EventAdapter

T0 = datetime(2026, 10, 10, 12, 0, 0, tzinfo=UTC)


class Reloj:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now


def ev(tipo: str, s: float, sid: str, maquina: str | None, **data: Any) -> AnyEvent:
    e = EventAdapter.validate_python(
        {
            "event_type": tipo,
            "session_id": sid,
            "timestamp": T0 + timedelta(seconds=s),
            "data": data,
        }
    )
    e.machine_id = maquina
    return e


def _transcripcion(ruta: Path) -> Path:
    ruta.write_text(
        json.dumps(
            {
                "type": "assistant",
                "timestamp": T0.isoformat(),
                "message": {
                    "id": "m1",
                    "model": "claude-opus-4-1",
                    "content": [{"type": "text", "text": "hola"}],
                    "usage": {"input_tokens": 1, "output_tokens": 999},
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return ruta


class Procesos:
    def __init__(self) -> None:
        self.consultas: list[int] = []

    def __call__(self, pid: int, creado: float | None) -> bool | None:
        self.consultas.append(pid)
        return True


@pytest.fixture
def procesos() -> Procesos:
    return Procesos()


def motor(procesos: Procesos, lectura_local: bool = True) -> AgentStateEngine:
    return AgentStateEngine(
        Thresholds(),
        clock=Reloj(),
        browsers_provider=lambda: 1,
        process_alive=procesos,
        lectura_local=lectura_local,
        maquina_local="alienware",
    )


def test_sesion_de_otra_maquina_no_se_lee_aqui(tmp_path: Path, procesos: Procesos) -> None:
    m = motor(procesos)
    t = str(_transcripcion(tmp_path / "t.jsonl"))
    m.accept(ev("session_start", 0, "remota", "tower", transcript_path=t, claude_pid=4242))
    m.accept(ev("session_start", 0, "local", "alienware", transcript_path=t, claude_pid=4343))
    remota, local = m.sessions["remota"], m.sessions["local"]
    assert not m.lee_local(remota) and m.lee_local(local)
    assert m._transcript(remota, t) == (None, None)  # pyright: ignore[reportPrivateUsage]
    # the local one goes through resolve_transcript (it may still refuse a path out of ~/.claude)
    assert m._transcript(local, t) != (None, None)  # pyright: ignore[reportPrivateUsage]
    m.check_processes()
    assert procesos.consultas == [4343]  # the PID of the other machine is not looked up here


def test_en_el_vps_no_se_lee_nada_local(tmp_path: Path, procesos: Procesos) -> None:
    m = motor(procesos, lectura_local=False)
    t = str(_transcripcion(tmp_path / "t.jsonl"))
    m.accept(ev("session_start", 0, "s", "alienware", transcript_path=t, claude_pid=1))
    assert not m.lee_local(m.sessions["s"])
    m.check_processes()
    assert procesos.consultas == []


def test_observacion_del_monitor_cierra_el_proceso(procesos: Procesos) -> None:
    m = motor(procesos)
    m.accept(ev("session_start", 0, "s", "tower", claude_pid=4242, claude_pid_created=1.0))
    assert m.observar("tower", {"session_id": "s", "proceso_vivo": True})
    m.check_processes()
    assert m.sessions["s"].closed_process_at is None
    m.observar("tower", {"session_id": "s", "proceso_vivo": False})
    m.check_processes()
    assert m.sessions["s"].closed_process_at is not None


def test_observacion_de_otra_maquina_o_sesion_desconocida_se_ignora(procesos: Procesos) -> None:
    m = motor(procesos)
    m.accept(ev("session_start", 0, "s", "tower"))
    assert not m.observar("alienware", {"session_id": "s", "proceso_vivo": False})
    assert not m.observar("tower", {"session_id": "no-existe"})
    assert m.sessions["s"].proceso_observado is None


def test_tokens_y_contexto_del_monitor(procesos: Procesos) -> None:
    m = motor(procesos)
    m.accept(ev("session_start", 0, "s", "tower"))
    m.accept(ev("pre_tool_use", 5, "s", "tower", tool_name="Bash"))
    m.observar(
        "tower",
        {
            "session_id": "s",
            "tokens_salida_total": 1200,
            "contexto_tokens": 50_000,
            "modelo": "claude-opus-4-1",
        },
        now=T0 + timedelta(seconds=10),
    )
    log = m.sessions["s"]
    vista = m._indicators(log, T0 + timedelta(seconds=10))  # pyright: ignore[reportPrivateUsage]
    assert vista["tokens_totales"] == 1200
    assert vista["tokens_contexto"] == 50_000
    assert vista["contexto_usado_pct"] is not None
    assert vista["tokens_motivo"] is None


def test_pregunta_del_turno_desde_el_texto_observado(procesos: Procesos) -> None:
    m = motor(procesos)
    m.accept(ev("session_start", 0, "s", "tower"))
    m.accept(ev("stop", 30, "s", "tower"))
    viejo = (T0 - timedelta(seconds=60)).isoformat()
    texto_viejo = {"ultimo_texto_asistente": "¿Algo más?", "ultimo_ts": viejo}
    m.observar("tower", {"session_id": "s", **texto_viejo})
    stop = m.sessions["s"].records[-1]
    assert stop.question is None  # older than the turn: ignored
    m.observar(
        "tower",
        {
            "session_id": "s",
            "ultimo_texto_asistente": "Listo. ¿Quieres que siga con las pruebas?",
            "ultimo_ts": (T0 + timedelta(seconds=29)).isoformat(),
        },
    )
    assert stop.question is True


def test_ids_de_evento_sobreviven_al_reinicio(tmp_path: Path, procesos: Procesos) -> None:
    store = AgentEventStore(tmp_path / "e.db")
    store.start()
    m = AgentStateEngine(Thresholds(), store=store)
    assert not m.ya_recibido("abc")
    m.marcar_recibido("abc")
    assert m.ya_recibido("abc")
    otro = AgentStateEngine(Thresholds(), store=store)  # backend restarted
    assert otro.ya_recibido("abc")
    assert not otro.ya_recibido(None)
    store.close()
