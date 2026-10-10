"""Fixes from the live test (2026-10-10): one test per reported failure."""

import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from app.core.agent_event_store import AgentEventStore
from app.core.agent_state_engine import AgentStateEngine, Thresholds
from app.core.transcript_tail import TranscriptTotals, asks_question, clean_prompt
from app.models.events import AnyEvent, EventAdapter

T0 = datetime(2026, 10, 10, 15, 0, 0, tzinfo=UTC)
SID = "prueba-live"
PID = {"claude_pid": 4242, "claude_pid_created": 1000.0}


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now


def ev(event_type: str, at: float, **data: Any) -> AnyEvent:
    return EventAdapter.validate_python(
        {
            "event_type": event_type,
            "session_id": SID,
            "timestamp": T0 + timedelta(seconds=at),
            "data": {**PID, **data},
        }
    )


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def engine(clock: Clock) -> AgentStateEngine:
    return AgentStateEngine(
        Thresholds(), clock=clock, browsers_provider=lambda: 1, process_alive=lambda p, c: True
    )


@pytest.fixture
def safe_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.transcript_tail.is_safe_transcript_path", lambda _p: True)


def state(engine: AgentStateEngine, clock: Clock, at: float) -> tuple[int, str | None]:
    clock.now = T0 + timedelta(seconds=at)
    engine.tick()
    st = engine.state_for(SID)
    return st.number, st.wait


def agent(engine: AgentStateEngine) -> dict[str, Any]:
    return next(a for a in engine.tick()["agentes"] if a["agente"]["session_id"] == SID)


def write_transcript(path: Path, entries: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")


def iso(at: float) -> str:
    return (T0 + timedelta(seconds=at)).isoformat().replace("+00:00", "Z")


# 1. AskUserQuestion / ExitPlanMode arrive as a permission prompt -------------


ASK_INPUT = {
    "questions": [
        {
            "question": "El ping terminó. ¿Borro saludo.txt?",
            "header": "Borrar",
            "options": [{"label": "Sí"}, {"label": "No"}],
        }
    ]
}


def test_ask_user_question_permission_is_14_with_the_question(
    engine: AgentStateEngine, clock: Clock
) -> None:
    engine.ingest(ev("session_start", 0))
    engine.ingest(
        ev("pre_tool_use", 50, tool_name="AskUserQuestion", tool_use_id="q1", tool_input=ASK_INPUT)
    )
    engine.ingest(ev("permission_request", 52, tool_name="AskUserQuestion", tool_input=ASK_INPUT))
    engine.ingest(
        ev(
            "notification",
            58,
            notification_type="permission_prompt",
            message="Claude needs your permission to use AskUserQuestion",
        )
    )
    assert state(engine, clock, 60) == (14, "tu_respuesta")
    assert agent(engine)["pregunta_pendiente"] == "El ping terminó. ¿Borro saludo.txt?"


def test_exit_plan_mode_permission_is_14(engine: AgentStateEngine, clock: Clock) -> None:
    engine.ingest(ev("session_start", 0))
    engine.ingest(ev("pre_tool_use", 5, tool_name="ExitPlanMode", tool_use_id="p1"))
    engine.ingest(ev("permission_request", 6, tool_name="ExitPlanMode"))
    assert state(engine, clock, 7) == (14, "tu_respuesta")


def test_real_permission_is_still_13(engine: AgentStateEngine, clock: Clock) -> None:
    engine.ingest(ev("session_start", 0))
    engine.ingest(ev("pre_tool_use", 5, tool_name="Bash", tool_use_id="b1"))
    engine.ingest(ev("permission_request", 6, tool_name="Bash"))
    assert state(engine, clock, 7) == (13, "tu_permiso")


# 2. Question in plain text that is not the last character -------------------

LAST_MESSAGE_8F5F7EDE = (
    "No pude leer noexiste.txt porque no existe en `E:\\Test\\prueba-visualizador`.\n\n"
    "¿Qué hago? Puedo buscarlo en otras carpetas, crearlo con el contenido que me digas "
    "o dejarlo así."
)


def test_question_in_last_paragraph_is_detected() -> None:
    assert asks_question(LAST_MESSAGE_8F5F7EDE)
    assert not asks_question("Listo, ver https://example.com/a?b=1 y `x ? y : z`.")
    assert not asks_question("¿Qué hago? Lo resolví.\n\nTodo quedó guardado.")


def test_stop_with_question_followed_by_options_is_14(
    engine: AgentStateEngine, clock: Clock
) -> None:
    engine.ingest(ev("session_start", 0))
    engine.ingest(ev("stop", 10, last_assistant_message=LAST_MESSAGE_8F5F7EDE))
    assert state(engine, clock, 11) == (14, "tu_respuesta")


def test_stop_without_text_retries_the_transcript(
    engine: AgentStateEngine, clock: Clock, tmp_path: Path, safe_paths: None
) -> None:
    transcript = tmp_path / "t.jsonl"
    write_transcript(
        transcript, [{"type": "user", "timestamp": iso(1), "message": {"content": "x"}}]
    )
    engine.ingest(ev("session_start", 0, transcript_path=str(transcript)))
    engine.ingest(ev("stop", 10, transcript_path=str(transcript)))
    assert state(engine, clock, 11) == (11, None)  # final message not written yet
    write_transcript(
        transcript,
        [
            {"type": "user", "timestamp": iso(1), "message": {"content": "x"}},
            {
                "type": "assistant",
                "timestamp": iso(9),
                "message": {
                    "id": "m1",
                    "stop_reason": "end_turn",
                    "content": [{"type": "text", "text": LAST_MESSAGE_8F5F7EDE}],
                },
            },
        ],
    )
    assert state(engine, clock, 12) == (14, "tu_respuesta")


# 3. Prompt text without injected blocks -------------------------------------


def test_injected_blocks_are_removed_from_the_prompt() -> None:
    assert clean_prompt("<browser_instruction># Claude in Chrome browser...") is None
    assert (
        clean_prompt(
            "<system-reminder>a</system-reminder>\n<browser_instruction>b\nc</browser_instruction>\n\nHola"
        )
        == "Hola"
    )


def test_truncated_prompt_is_read_from_the_transcript(
    engine: AgentStateEngine, clock: Clock, tmp_path: Path, safe_paths: None
) -> None:
    transcript = tmp_path / "t.jsonl"
    write_transcript(
        transcript,
        [
            {
                "type": "user",
                "timestamp": iso(5),
                "message": {
                    "content": [
                        {
                            "type": "text",
                            "text": "<browser_instruction># Claude in Chrome</browser_instruction>",
                        },
                        {"type": "text", "text": "¿Qué archivos hay en esta carpeta?"},
                    ]
                },
            }
        ],
    )
    engine.ingest(ev("session_start", 0, transcript_path=str(transcript)))
    engine.ingest(
        ev(
            "user_prompt_submit",
            5,
            transcript_path=str(transcript),
            prompt="<browser_instruction># Claude in Chrome browser...",
        )
    )
    state(engine, clock, 6)
    detail = [e for e in agent(engine)["eventos_recientes"] if e["tipo"] == "user_prompt_submit"]
    assert detail[0]["detalle"] == "¿Qué archivos hay en esta carpeta?"


# 4. Reconciliation with the transcript when events were lost -----------------


def test_stuck_tool_is_reconciled_with_the_transcript(
    clock: Clock, tmp_path: Path, safe_paths: None
) -> None:
    store = AgentEventStore(tmp_path / "log.db")
    store.start()
    engine = AgentStateEngine(
        Thresholds(),
        clock=clock,
        browsers_provider=lambda: 1,
        process_alive=lambda p, c: True,
        store=store,
    )
    transcript = tmp_path / "t.jsonl"
    write_transcript(
        transcript,
        [
            {
                "type": "assistant",
                "timestamp": iso(1),
                "message": {
                    "id": "a1",
                    "stop_reason": "tool_use",
                    "content": [{"type": "tool_use", "id": "toolu_b1", "name": "Bash"}],
                },
            },
            {
                "type": "user",
                "timestamp": iso(40),
                "message": {
                    "content": [{"type": "tool_result", "tool_use_id": "toolu_b1", "content": "ok"}]
                },
            },
            {
                "type": "assistant",
                "timestamp": iso(45),
                "message": {
                    "id": "a2",
                    "stop_reason": "end_turn",
                    "content": [{"type": "text", "text": "Compilé el proyecto sin errores."}],
                },
            },
        ],
    )
    engine.accept(ev("session_start", 0, transcript_path=str(transcript)))
    engine.accept(
        ev(
            "pre_tool_use",
            1,
            tool_name="Bash",
            tool_use_id="toolu_b1",
            tool_input={"command": "npm run build"},
            transcript_path=str(transcript),
        )
    )
    store.flush()
    stored = store.count()
    # The backend missed PostToolUse and Stop: frozen in "espera un programa".
    assert state(engine, clock, 60)[0] == 15
    clock.now = T0 + timedelta(seconds=200)
    assert engine.reconcile() == 1
    assert engine.state_for(SID).number == 11
    view = agent(engine)
    assert view["conciliado"] is not None
    assert "turno terminado" in view["conciliado"]["detalle"]
    store.flush()
    assert store.count() == stored  # nothing invented in the log
    # A real event afterwards replaces the annotation.
    engine.accept(ev("user_prompt_submit", 300, prompt="sigue"))
    assert agent(engine)["conciliado"] is None
    store.close()


def test_reconciliation_keeps_an_explicit_question(
    engine: AgentStateEngine, clock: Clock, tmp_path: Path, safe_paths: None
) -> None:
    transcript = tmp_path / "t.jsonl"
    write_transcript(
        transcript,
        [
            {
                "type": "assistant",
                "timestamp": iso(20),
                "message": {
                    "id": "a2",
                    "stop_reason": "end_turn",
                    "content": [{"type": "text", "text": "Terminé. ¿Lo subo a GitHub?"}],
                },
            }
        ],
    )
    engine.ingest(ev("session_start", 0, transcript_path=str(transcript)))
    engine.ingest(ev("user_prompt_submit", 1, prompt="hazlo", transcript_path=str(transcript)))
    clock.now = T0 + timedelta(seconds=200)
    engine.reconcile()
    assert engine.state_for(SID).number == 14
    assert agent(engine)["pregunta_pendiente"] == "Terminé. ¿Lo subo a GitHub?"


def test_recent_activity_is_not_reconciled(
    engine: AgentStateEngine, clock: Clock, tmp_path: Path, safe_paths: None
) -> None:
    transcript = tmp_path / "t.jsonl"
    write_transcript(transcript, [])
    engine.ingest(ev("session_start", 0, transcript_path=str(transcript)))
    engine.ingest(
        ev("pre_tool_use", 1, tool_name="Read", tool_use_id="r1", transcript_path=str(transcript))
    )
    clock.now = T0 + timedelta(seconds=60)  # less than STATE_RECONCILE_AFTER_SECONDS
    assert engine.reconcile() == 0


# 8. Accumulated tokens differ from the context size ---------------------------


def test_totals_count_each_message_once(tmp_path: Path) -> None:
    transcript = tmp_path / "t.jsonl"
    usage1 = {
        "input_tokens": 10,
        "cache_creation_input_tokens": 1000,
        "cache_read_input_tokens": 0,
        "output_tokens": 50,
    }
    usage2 = {
        "input_tokens": 5,
        "cache_creation_input_tokens": 100,
        "cache_read_input_tokens": 1010,
        "output_tokens": 70,
    }
    write_transcript(
        transcript,
        [
            {"type": "assistant", "message": {"id": "m1", "usage": usage1, "content": []}},
            {"type": "assistant", "message": {"id": "m1", "usage": usage1, "content": []}},
            {"type": "assistant", "message": {"id": "m2", "usage": usage2, "content": []}},
        ],
    )
    totals = TranscriptTotals(transcript)
    assert totals.scan() == (50 + 70) + (10 + 1000 + 5 + 100)
    with open(transcript, "a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "id": "m3",
                        "usage": {"input_tokens": 1, "output_tokens": 9},
                        "content": [],
                    },
                }
            )
            + "\n"
        )
    assert totals.scan() == 1235 + 10  # only the appended line is read


def test_view_shows_total_and_context_separately(
    engine: AgentStateEngine, clock: Clock, tmp_path: Path, safe_paths: None
) -> None:
    transcript = tmp_path / "t.jsonl"
    write_transcript(
        transcript,
        [
            {
                "type": "assistant",
                "message": {
                    "id": "m1",
                    "model": "claude-opus-4-7",
                    "content": [],
                    "usage": {
                        "input_tokens": 10,
                        "cache_creation_input_tokens": 1000,
                        "output_tokens": 50,
                    },
                },
            },
            {
                "type": "assistant",
                "message": {
                    "id": "m2",
                    "model": "claude-opus-4-7",
                    "content": [],
                    "usage": {
                        "input_tokens": 5,
                        "cache_read_input_tokens": 1010,
                        "output_tokens": 70,
                    },
                },
            },
        ],
    )
    engine.ingest(ev("session_start", 0, transcript_path=str(transcript)))
    end = time.monotonic() + 10
    while time.monotonic() < end and not engine.sessions[SID].totals_samples:
        time.sleep(0.02)
    ind = agent(engine)["indicadores"]
    assert ind["tokens_contexto"] == 5 + 1010 + 70
    assert ind["tokens_totales"] == (50 + 70) + (10 + 1000 + 5)


# 7. Test sessions are removed from the engine log -----------------------------


def test_delete_test_sessions_from_the_log(tmp_path: Path) -> None:
    store = AgentEventStore(tmp_path / "log.db")
    store.start()
    for sid in ("prueba-a", "prueba-b", "real-1"):
        store.append(
            EventAdapter.validate_python(
                {"event_type": "session_start", "session_id": sid, "timestamp": T0, "data": {}}
            )
        )
    store.flush()
    deleted = store.delete_sessions(["prueba-"])
    assert deleted == {"prueba-a": 1, "prueba-b": 1}
    assert store.count() == 1
    store.close()
