"""Catalog state engine: one sequence per state (1-20) and per wait kind.

Uses a simulated clock so time-based states (program wait, idle, rest,
short-lived states) are checked without sleeping.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from app.core.agent_state_engine import (
    STATE_NAMES,
    AgentStateEngine,
    Thresholds,
    account_for_transcript,
    network_command_match,
)
from app.models.events import AnyEvent, EventAdapter

T0 = datetime(2026, 10, 9, 12, 0, 0, tzinfo=UTC)
SID = "sess_1"


class FakeClock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now

    def at(self, seconds: float) -> datetime:
        self.now = T0 + timedelta(seconds=seconds)
        return self.now


class Browsers:
    def __init__(self, count: int = 0) -> None:
        self.count = count

    def __call__(self) -> int:
        return self.count


def ev(event_type: str, at: float, session_id: str = SID, **data: Any) -> AnyEvent:
    return EventAdapter.validate_python(
        {
            "event_type": event_type,
            "session_id": session_id,
            "timestamp": T0 + timedelta(seconds=at),
            "data": data,
        }
    )


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def browsers() -> Browsers:
    return Browsers(1)  # user present unless a test says otherwise


@pytest.fixture
def engine(clock: FakeClock, browsers: Browsers) -> AgentStateEngine:
    return AgentStateEngine(Thresholds(), clock=clock, browsers_provider=browsers)


def wait_totals(engine: AgentStateEngine, timeout: float = 30) -> None:
    """Wait for the background transcript totals of every session."""
    import time

    end = time.monotonic() + timeout
    while time.monotonic() < end:
        logs = list(engine.sessions.values())
        if all(log.totals is None or log.totals.ready for log in logs) and not any(
            engine._totals_busy.values()  # pyright: ignore[reportPrivateUsage]
        ):
            return
        time.sleep(0.05)


def feed(engine: AgentStateEngine, *events: AnyEvent) -> None:
    for e in events:
        engine.ingest(e)


def state_at(engine: AgentStateEngine, clock: FakeClock, seconds: float) -> tuple[int, str | None]:
    clock.at(seconds)
    engine.tick()
    st = engine.state_for(SID)
    return st.number, st.wait


def start(at: float = 0) -> AnyEvent:
    return ev("session_start", at, transcript_path="C:/Users/x/.claude/projects/p/s.jsonl")


def pre(tool: str, at: float, tid: str, **tool_input: Any) -> AnyEvent:
    return ev(
        "pre_tool_use",
        at,
        tool_name=tool,
        tool_use_id=tid,
        agent_id="main",
        tool_input=tool_input,
    )


def post(tool: str, at: float, tid: str) -> AnyEvent:
    return ev("post_tool_use", at, tool_name=tool, tool_use_id=tid, agent_id="main", success=True)


# ---------------------------------------------------------------------------
# Work cycle (1-12)
# ---------------------------------------------------------------------------


def test_catalog_has_twenty_one_states() -> None:
    assert sorted(STATE_NAMES) == list(range(1, 22))
    assert STATE_NAMES[21] == "Cerrado"


def test_1_llega(engine: AgentStateEngine, clock: FakeClock) -> None:
    feed(engine, start(0))
    assert state_at(engine, clock, 5) == (1, None)


def test_2_recibe_encargo_then_3_pensando(engine: AgentStateEngine, clock: FakeClock) -> None:
    feed(engine, start(0), ev("user_prompt_submit", 10, prompt="Haz algo"))
    assert state_at(engine, clock, 11) == (2, None)
    assert state_at(engine, clock, 20) == (3, None)


def test_3_pensando_between_tools(engine: AgentStateEngine, clock: FakeClock) -> None:
    feed(engine, start(0), pre("Read", 1, "t1", file_path="a.py"), post("Read", 2, "t1"))
    assert state_at(engine, clock, 3) == (3, None)


@pytest.mark.parametrize(
    ("tool", "expected"),
    [
        ("Read", 4),
        ("Grep", 4),
        ("Glob", 4),
        ("Edit", 5),
        ("Write", 5),
        ("Bash", 6),
        ("WebSearch", 7),
        ("WebFetch", 7),
        ("mcp__claude_ai_ClickUp__clickup_get_task", 8),
        ("TodoWrite", 9),
    ],
)
def test_4_to_9_running_tool(
    engine: AgentStateEngine, clock: FakeClock, tool: str, expected: int
) -> None:
    feed(engine, start(0), pre(tool, 1, "t1", command="ls"))
    assert state_at(engine, clock, 2) == (expected, None)


def test_10_compactando(engine: AgentStateEngine, clock: FakeClock) -> None:
    feed(engine, start(0), ev("context_compaction", 5))
    assert state_at(engine, clock, 6) == (10, None)


def test_11_termino_turno_then_18_without_question(
    engine: AgentStateEngine, clock: FakeClock
) -> None:
    feed(
        engine,
        start(0),
        ev("user_prompt_submit", 1, prompt="x"),
        ev("stop", 5, last_assistant_message="Listo, terminé el cambio."),
    )
    assert state_at(engine, clock, 6) == (11, None)
    assert state_at(engine, clock, 5 + 299) == (11, None)
    assert state_at(engine, clock, 5 + 301) == (18, None)


def test_12_se_va(engine: AgentStateEngine, clock: FakeClock) -> None:
    feed(engine, start(0), ev("session_end", 5, reason="exit"))
    assert state_at(engine, clock, 6) == (12, None)


def test_21_cerrado_by_session_end_after_se_va(engine: AgentStateEngine, clock: FakeClock) -> None:
    feed(engine, start(0), ev("session_end", 5, reason="prompt_input_exit"))
    assert state_at(engine, clock, 6) == (12, None)
    assert state_at(engine, clock, 5 + engine.th.exit_visible + 1) == (21, None)
    agent = engine.tick()["agentes"][0]
    assert agent["cierre"]["motivo"] == "session_end"
    # Closed agents stay visible for 24 h.
    clock.at(5 + 23 * 3600)
    assert len(engine.tick()["agentes"]) == 1
    clock.at(5 + 25 * 3600)
    assert engine.tick()["agentes"] == []


# ---------------------------------------------------------------------------
# Waiting (13-17) and each wait kind
# ---------------------------------------------------------------------------


def test_13_te_espera_permiso(engine: AgentStateEngine, clock: FakeClock) -> None:
    feed(
        engine,
        start(0),
        pre("Bash", 1, "t1", command="rm -rf build"),
        ev(
            "permission_request",
            2,
            tool_name="Bash",
            agent_id="main",
            tool_input={"command": "rm -rf build"},
        ),
    )
    assert state_at(engine, clock, 3) == (13, "tu_permiso")
    ev_data = engine.tick()["agentes"][0]["espera"]["evidencia"]
    assert ev_data["herramienta"] == "Bash"
    assert ev_data["comando"] == "rm -rf build"
    # Approved: the tool finishes and the wait clears.
    feed(engine, post("Bash", 4, "t1"))
    assert state_at(engine, clock, 5) == (3, None)


def test_13_permission_notification(engine: AgentStateEngine, clock: FakeClock) -> None:
    feed(
        engine,
        start(0),
        ev("notification", 2, notification_type="permission_prompt", message="needs permission"),
    )
    assert state_at(engine, clock, 3) == (13, "tu_permiso")


def test_idle_notification_does_not_mean_waiting(
    engine: AgentStateEngine, clock: FakeClock
) -> None:
    feed(
        engine,
        start(0),
        ev("stop", 1, last_assistant_message="Hecho."),
        ev("notification", 61, notification_type="idle_prompt", message="Claude is waiting"),
    )
    assert state_at(engine, clock, 62) == (11, None)


def test_14_stop_with_question(engine: AgentStateEngine, clock: FakeClock) -> None:
    feed(
        engine,
        start(0),
        ev("stop", 5, last_assistant_message="¿Quieres que también actualice los tests?"),
    )
    assert state_at(engine, clock, 6) == (14, "tu_respuesta")
    assert state_at(engine, clock, 3600) == (14, "tu_respuesta")


def test_14_question_read_from_transcript_tail(
    engine: AgentStateEngine, clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcript = tmp_path / "s.jsonl"
    lines = [
        {"type": "user", "message": {"role": "user", "content": "hola"}},
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "¿Sigo con la fase 2?**"}],
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        },
    ]
    transcript.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    monkeypatch.setattr("app.core.transcript_tail.is_safe_transcript_path", lambda _p: True)
    feed(
        engine,
        ev("session_start", 0, transcript_path=str(transcript)),
        ev("stop", 5, transcript_path=str(transcript)),
    )
    assert state_at(engine, clock, 6) == (14, "tu_respuesta")


def test_14_ask_user_question_tool(engine: AgentStateEngine, clock: FakeClock) -> None:
    feed(engine, start(0), pre("AskUserQuestion", 1, "t1"))
    assert state_at(engine, clock, 2) == (14, "tu_respuesta")


def test_15_espera_programa_after_threshold(engine: AgentStateEngine, clock: FakeClock) -> None:
    feed(engine, start(0), pre("Bash", 10, "t1", command="npm test"))
    assert state_at(engine, clock, 39) == (6, None)
    assert state_at(engine, clock, 41) == (15, "programa")
    st = engine.state_for(SID)
    assert st.since == T0 + timedelta(seconds=40)
    feed(engine, post("Bash", 50, "t1"))
    assert state_at(engine, clock, 51) == (3, None)


@pytest.mark.parametrize(
    "command",
    [
        "git push origin main",
        "git -C repo pull",
        "git fetch --all",
        "git clone https://x/y.git",
        "scp a.txt host:/tmp",
        "rsync -av . host:/srv",
        "docker push img:1",
        "docker pull img:1",
        "eas submit -p ios",
        "eas build --platform all",
        "npm publish",
        "gh release upload v1 a.zip",
        "curl -T file https://x",
        "curl --upload-file f https://x",
    ],
)
def test_16_espera_subida(engine: AgentStateEngine, clock: FakeClock, command: str) -> None:
    feed(engine, start(0), pre("Bash", 1, "t1", command=command))
    assert state_at(engine, clock, 2) == (16, "subida")


@pytest.mark.parametrize("command", ["git status", "ls && git log", "curl https://x", "npm test"])
def test_not_network_commands(command: str) -> None:
    assert network_command_match(command) is None


def test_17_espera_agentes(engine: AgentStateEngine, clock: FakeClock) -> None:
    feed(
        engine,
        start(0),
        ev("subagent_start", 1, agent_id="subagent_a", task_description="Revisar"),
        ev("subagent_start", 2, agent_id="subagent_b", task_description="Probar"),
    )
    assert state_at(engine, clock, 3) == (17, "agentes")
    assert engine.tick()["agentes"][0]["subagentes_activos"] == 2
    feed(engine, ev("subagent_stop", 4, agent_id="subagent_a"))
    assert engine.tick()["agentes"][0]["subagentes_activos"] == 1
    feed(engine, ev("subagent_stop", 5, agent_id="subagent_b"))
    assert state_at(engine, clock, 6) == (3, None)


def test_17_native_subagent_stop_links_by_native_id(
    engine: AgentStateEngine, clock: FakeClock
) -> None:
    feed(
        engine,
        start(0),
        ev("subagent_start", 1, agent_id="subagent_t1"),
        ev("subagent_info", 2, native_agent_id="n1"),
        ev("subagent_stop", 3, native_agent_id="n1"),
    )
    assert engine.tick()["agentes"][0]["subagentes_activos"] == 0


# ---------------------------------------------------------------------------
# Absence and return (18-20)
# ---------------------------------------------------------------------------


def test_18_inactivo_contigo_presente(engine: AgentStateEngine, clock: FakeClock) -> None:
    feed(engine, start(0), pre("Read", 1, "t1"), post("Read", 2, "t1"))
    assert state_at(engine, clock, 2 + 299) == (3, None)
    assert state_at(engine, clock, 2 + 301) == (18, None)


def test_19_descansando_sin_ti(
    engine: AgentStateEngine, clock: FakeClock, browsers: Browsers
) -> None:
    browsers.count = 0
    feed(engine, start(0), pre("Read", 1, "t1"), post("Read", 2, "t1"))
    # Idle after 5 min, but the engine started at T0: disconnected < 10 min.
    assert state_at(engine, clock, 400) == (18, None)
    assert state_at(engine, clock, 601) == (19, None)


def test_waiting_agent_does_not_rest(
    engine: AgentStateEngine, clock: FakeClock, browsers: Browsers
) -> None:
    browsers.count = 0
    feed(
        engine,
        start(0),
        ev("user_prompt_submit", 1, prompt="x"),
        ev("stop", 2, last_assistant_message="¿Lo subo?"),
    )
    assert state_at(engine, clock, 3600) == (14, "tu_respuesta")


def test_turn_done_without_question_rests_when_disconnected(
    engine: AgentStateEngine, clock: FakeClock, browsers: Browsers
) -> None:
    browsers.count = 0
    feed(engine, start(0), ev("stop", 2, last_assistant_message="Terminado."))
    assert state_at(engine, clock, 100) == (11, None)
    assert state_at(engine, clock, 400) == (18, None)
    assert state_at(engine, clock, 700) == (19, None)


def test_20_regresa_al_trabajo_when_office_opens(
    engine: AgentStateEngine, clock: FakeClock, browsers: Browsers
) -> None:
    browsers.count = 0
    feed(engine, start(0), pre("Read", 1, "t1"), post("Read", 2, "t1"))
    assert state_at(engine, clock, 700) == (19, None)
    browsers.count = 1  # the user opens the office
    assert state_at(engine, clock, 701) == (20, None)
    assert state_at(engine, clock, 703) == (20, None)
    # After the short return window it shows the state that applies (idle, present).
    assert state_at(engine, clock, 707) == (18, None)


def test_20_regresa_al_trabajo_on_new_prompt(
    engine: AgentStateEngine, clock: FakeClock, browsers: Browsers
) -> None:
    browsers.count = 0
    feed(engine, start(0), pre("Read", 1, "t1"), post("Read", 2, "t1"))
    assert state_at(engine, clock, 700) == (19, None)
    feed(engine, ev("user_prompt_submit", 701, prompt="sigue"))
    assert state_at(engine, clock, 701.5) == (20, None)
    assert state_at(engine, clock, 710) == (3, None)


# ---------------------------------------------------------------------------
# Presence, identity and indicators
# ---------------------------------------------------------------------------


def test_presence_by_recent_prompt(
    engine: AgentStateEngine, clock: FakeClock, browsers: Browsers
) -> None:
    browsers.count = 0
    feed(engine, start(0), ev("user_prompt_submit", 10, prompt="x"))
    clock.at(100)
    assert engine.tick()["presencia"]["estado"] == "conectado"
    clock.at(10 + 601)
    snap = engine.tick()["presencia"]
    assert snap["estado"] == "desconectado"
    assert "Sin navegadores" in snap["motivo"]


def test_presence_by_browser(engine: AgentStateEngine, clock: FakeClock) -> None:
    feed(engine, start(0))
    snap = engine.tick()["presencia"]
    assert snap["estado"] == "conectado"
    assert snap["navegadores_conectados"] == 1


def test_presence_by_office_heartbeat(
    engine: AgentStateEngine, clock: FakeClock, browsers: Browsers
) -> None:
    # An open /oficina page (PC or phone) counts like a WebSocket browser.
    browsers.count = 0
    feed(engine, start(0))
    clock.at(100)
    assert engine.tick()["presencia"]["estado"] == "desconectado"
    engine.heartbeat("pagina-1", "celular")
    snap = engine.tick()["presencia"]
    assert snap["estado"] == "conectado"
    assert snap["navegadores_conectados"] == 1
    assert snap["dispositivos"] == ["celular"]
    clock.at(100 + 76)  # no heartbeat for more than 75 s: the page is closed
    snap = engine.tick()["presencia"]
    assert snap["navegadores_conectados"] == 0
    assert snap["dispositivos"] == []


def test_account_from_transcript_path() -> None:
    assert account_for_transcript("C:\\Users\\w\\.claude\\projects\\a.jsonl") == "personal"
    assert account_for_transcript("C:/Users/w/.claude-demo/projects/a.jsonl") == "demo"
    assert account_for_transcript(None) is None


def test_agent_view_fields(engine: AgentStateEngine, clock: FakeClock) -> None:
    feed(
        engine,
        ev(
            "session_start",
            0,
            project_dir="E:/proyecto",
            transcript_path="C:/Users/w/.claude-demo/projects/p/s.jsonl",
        ),
        ev(
            "pre_tool_use",
            30,
            tool_name="Read",
            tool_use_id="t1",
            agent_id="main",
            input_tokens=1000,
            output_tokens=200,
        ),
        ev(
            "post_tool_use",
            40,
            tool_name="Read",
            tool_use_id="t1",
            agent_id="main",
            success=True,
            input_tokens=5000,
            output_tokens=500,
        ),
    )
    clock.at(60)
    agent = engine.tick()["agentes"][0]
    assert agent["agente"] == {"session_id": SID, "proyecto": "E:/proyecto", "cuenta": "demo"}
    assert agent["ultimo_evento"]["tipo"] == "post_tool_use"
    ind = agent["indicadores"]
    assert ind["herramientas_por_minuto"] == 0.2  # 1 tool in a 5-min window
    assert ind["tokens_totales"] == 5500
    assert ind["tokens_por_minuto"] == pytest.approx(4300 / 5, rel=0.01)
    assert ind["minutos_con_actividad"] == 1
    assert ind["contexto_usado_pct"] is not None
    assert ind["errores_seguidos"] is None
    assert "PostToolUseFailure" in ind["errores_motivo"]
    assert len(agent["eventos_recientes"]) == 3


def test_consecutive_errors_when_failures_are_reported(
    engine: AgentStateEngine, clock: FakeClock
) -> None:
    feed(
        engine,
        start(0),
        ev("post_tool_use", 1, tool_name="Bash", agent_id="main", success=False),
        ev("post_tool_use", 2, tool_name="Bash", agent_id="main", success=False),
    )
    assert engine.tick()["agentes"][0]["indicadores"]["errores_seguidos"] == 2
    feed(engine, ev("post_tool_use", 3, tool_name="Bash", agent_id="main", success=True))
    assert engine.tick()["agentes"][0]["indicadores"]["errores_seguidos"] == 0


def test_out_of_order_events_are_sorted(engine: AgentStateEngine, clock: FakeClock) -> None:
    feed(engine, pre("Read", 5, "t1"), start(0), post("Read", 6, "t1"))
    agent = engine.tick()["agentes"][0]
    assert [e["tipo"] for e in agent["eventos_recientes"]] == [
        "post_tool_use",
        "pre_tool_use",
        "session_start",
    ]


def test_subagent_tools_do_not_change_main_state(
    engine: AgentStateEngine, clock: FakeClock
) -> None:
    feed(
        engine,
        start(0),
        ev("subagent_start", 1, agent_id="subagent_a"),
        ev("pre_tool_use", 2, tool_name="Edit", tool_use_id="s1", agent_id="subagent_a"),
    )
    assert state_at(engine, clock, 3) == (17, "agentes")


def test_pending_tool_closed_by_a_later_main_tool(
    engine: AgentStateEngine, clock: FakeClock
) -> None:
    # A failed command never gets PostToolUse; the next tool call proves it ended.
    feed(
        engine,
        start(0),
        pre("PowerShell", 10, "t1", command="scp a host:/b"),
        pre("Read", 60, "t2", file_path="x"),
        post("Read", 61, "t2"),
    )
    assert state_at(engine, clock, 62) == (3, None)


def test_parallel_tool_calls_stay_pending(engine: AgentStateEngine, clock: FakeClock) -> None:
    feed(
        engine,
        start(0),
        pre("Bash", 10, "t1", command="npm test"),
        pre("Read", 10.5, "t2", file_path="x"),
        post("Read", 11, "t2"),
    )
    assert state_at(engine, clock, 50) == (15, "programa")


def test_background_subagent_after_stop_keeps_turn_done(
    engine: AgentStateEngine, clock: FakeClock
) -> None:
    feed(
        engine,
        start(0),
        ev("subagent_start", 1, agent_id="subagent_a"),
        ev("stop", 2, last_assistant_message="¿Revisas el resultado?"),
        ev("subagent_stop", 30, agent_id="subagent_a"),
    )
    assert state_at(engine, clock, 40) == (14, "tu_respuesta")


def test_backend_cleanup_is_not_activity(engine: AgentStateEngine, clock: FakeClock) -> None:
    feed(
        engine,
        start(0),
        ev("subagent_start", 1, agent_id="subagent_a"),
        ev("subagent_stop", 2, agent_id="subagent_a"),
        ev("cleanup", 1000, agent_id="subagent_a"),
    )
    assert state_at(engine, clock, 1001) == (18, None)


# ---------------------------------------------------------------------------
# Subagent expiry, failures and attribution (hook data)
# ---------------------------------------------------------------------------


def test_subagent_has_no_time_limit(clock: FakeClock, browsers: Browsers) -> None:
    engine = AgentStateEngine(
        Thresholds(), clock=clock, browsers_provider=browsers, process_alive=lambda p, c: True
    )
    feed(
        engine,
        ev("session_start", 0, claude_pid=7, claude_pid_created=1.0),
        ev("subagent_start", 1, agent_id="subagent_a", claude_pid=7, claude_pid_created=1.0),
    )
    assert state_at(engine, clock, 3 * 3600) == (17, "agentes")
    assert engine.tick()["agentes"][0]["subagentes_activos"] == 1


def test_main_stop_ends_its_subagents(engine: AgentStateEngine, clock: FakeClock) -> None:
    feed(
        engine,
        start(0),
        ev("subagent_start", 1, agent_id="subagent_a"),
        ev("stop", 5, last_assistant_message="Listo."),
    )
    assert state_at(engine, clock, 6) == (11, None)
    assert engine.tick()["agentes"][0]["subagentes_activos"] == 0


def test_poller_zombie_stop_does_not_end_a_subagent(
    engine: AgentStateEngine, clock: FakeClock
) -> None:
    feed(engine, start(0), ev("subagent_start", 1, agent_id="subagent_a"))
    engine.ingest(ev("subagent_stop", 100, agent_id="subagent_a"), origin="poller")
    assert state_at(engine, clock, 101) == (17, "agentes")
    engine.ingest(ev("subagent_stop", 200, agent_id="subagent_a"), origin="hook")
    assert engine.tick()["agentes"][0]["subagentes_activos"] == 0


def test_errors_in_a_row_from_post_tool_use_failure(
    engine: AgentStateEngine, clock: FakeClock
) -> None:
    feed(
        engine,
        ev("session_start", 0, reports_tool_failures=True),
        pre("Bash", 1, "t1", command="npm test"),
    )
    assert engine.tick()["agentes"][0]["indicadores"]["errores_seguidos"] == 0
    feed(
        engine,
        ev(
            "post_tool_use_failure",
            2,
            tool_name="Bash",
            tool_use_id="t1",
            agent_id="main",
            error="Exit code 1",
            reports_tool_failures=True,
        ),
        pre("Bash", 3, "t2", command="npm test"),
        ev(
            "post_tool_use_failure",
            4,
            tool_name="Bash",
            tool_use_id="t2",
            agent_id="main",
            error="Exit code 1",
        ),
    )
    ind = engine.tick()["agentes"][0]["indicadores"]
    assert ind["errores_seguidos"] == 2
    assert ind["errores_motivo"] is None
    # The failure closed the pending Bash: not "espera un programa".
    assert state_at(engine, clock, 60) == (3, None)
    feed(engine, pre("Read", 61, "t3"), post("Read", 62, "t3"))
    assert engine.tick()["agentes"][0]["indicadores"]["errores_seguidos"] == 0


def test_user_interrupt_is_not_an_error(engine: AgentStateEngine, clock: FakeClock) -> None:
    feed(
        engine,
        ev("session_start", 0, reports_tool_failures=True),
        pre("Bash", 1, "t1", command="sleep 100"),
        ev(
            "post_tool_use_failure",
            2,
            tool_name="Bash",
            tool_use_id="t1",
            agent_id="main",
            is_interrupt=True,
        ),
    )
    assert engine.tick()["agentes"][0]["indicadores"]["errores_seguidos"] == 0


def test_failed_task_call_ends_its_subagent(engine: AgentStateEngine, clock: FakeClock) -> None:
    feed(
        engine,
        start(0),
        ev("subagent_start", 1, agent_id="subagent_t9", tool_use_id="t9"),
        ev(
            "post_tool_use_failure",
            2,
            tool_name="Task",
            tool_use_id="t9",
            agent_id="main",
        ),
    )
    assert engine.tick()["agentes"][0]["subagentes_activos"] == 0


def test_tools_attributed_to_the_subagent_that_used_them(
    engine: AgentStateEngine, clock: FakeClock
) -> None:
    feed(
        engine,
        start(0),
        ev("subagent_start", 1, agent_id="subagent_t1"),
        ev("subagent_info", 2, native_agent_id="n1"),
        # Hook: agent_id stays "main" for older consumers, tool_agent_id names
        # the subagent. The main agent is still waiting on its subagent.
        ev(
            "pre_tool_use",
            3,
            tool_name="Edit",
            tool_use_id="x1",
            agent_id="main",
            tool_agent_id="n1",
            tool_agent_type="general-purpose",
        ),
    )
    assert state_at(engine, clock, 4) == (17, "agentes")
    agent = engine.tick()["agentes"][0]
    assert agent["herramienta_actual"] == "Task/Agent"
    assert agent["indicadores"]["herramientas_por_minuto"] == 0.4  # Task + Edit


def test_tokens_from_tail_of_a_large_transcript(
    engine: AgentStateEngine, clock: FakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcript = tmp_path / "big.jsonl"
    filler = json.dumps({"type": "user", "message": {"content": "x" * 1000}}) + "\n"
    last = {
        "type": "assistant",
        "message": {
            "model": "claude-opus-4-7",
            "content": [{"type": "text", "text": "ok"}],
            "usage": {
                "input_tokens": 100,
                "cache_read_input_tokens": 400_000,
                "cache_creation_input_tokens": 0,
                "output_tokens": 900,
            },
        },
    }
    with open(transcript, "w", encoding="utf-8") as f:
        for _ in range(60_000):  # ~60 MB, above the old 50 MB limit
            f.write(filler)
        f.write(json.dumps(last) + "\n")
    monkeypatch.setattr("app.core.transcript_tail.is_safe_transcript_path", lambda _p: True)
    feed(engine, ev("session_start", 0, transcript_path=str(transcript)))
    wait_totals(engine)
    ind = engine.tick()["agentes"][0]["indicadores"]
    assert ind["tokens_contexto"] == 401_000
    assert ind["contexto_usado_pct"] == 40.1
    assert ind["tokens_motivo"] is None


# ---------------------------------------------------------------------------
# Closed sessions (21): process ended, pending question, reopening
# ---------------------------------------------------------------------------


class FakeProcesses:
    """pid -> creation time of live processes."""

    def __init__(self) -> None:
        self.live: dict[int, float] = {}

    def __call__(self, pid: int, created: float | None) -> bool | None:
        if pid not in self.live:
            return False
        return created is None or abs(self.live[pid] - created) <= 1


@pytest.fixture
def procs() -> FakeProcesses:
    return FakeProcesses()


@pytest.fixture
def pengine(clock: FakeClock, browsers: Browsers, procs: FakeProcesses) -> AgentStateEngine:
    return AgentStateEngine(
        Thresholds(), clock=clock, browsers_provider=browsers, process_alive=procs
    )


def pev(event_type: str, at: float, pid: int = 4242, created: float = 1000.0, **data: Any):
    return ev(event_type, at, claude_pid=pid, claude_pid_created=created, **data)


def test_21_cerrado_when_process_ends(
    pengine: AgentStateEngine, clock: FakeClock, procs: FakeProcesses
) -> None:
    procs.live[4242] = 1000.0
    feed(pengine, pev("session_start", 0), pev("user_prompt_submit", 1, prompt="x"))
    assert state_at(pengine, clock, 10)[0] == 3
    del procs.live[4242]  # Claude Code closed (VS Code closed, PC restarted...)
    assert state_at(pengine, clock, 45) == (21, None)  # next 30 s check
    agent = pengine.tick()["agentes"][0]
    assert agent["cierre"]["motivo"] == "proceso_terminado"
    assert agent["proceso"] == {"pid": 4242, "creado": 1000.0}


def test_closure_time_survives_a_backend_restart(
    clock: FakeClock, browsers: Browsers, procs: FakeProcesses
) -> None:
    # The window was closed long ago; the backend restarts and finds the
    # process already gone: the closure keeps the time of the last event
    # instead of "now", on every restart.
    events = [pev("session_start", 0), pev("user_prompt_submit", 5, prompt="x")]
    desde = []
    for reinicio in (2 * 3600, 3 * 3600):
        clock.at(reinicio)
        engine = AgentStateEngine(
            Thresholds(), clock=clock, browsers_provider=browsers, process_alive=procs
        )
        feed(engine, *events)
        agent = engine.tick()["agentes"][0]
        assert agent["cierre"]["motivo"] == "proceso_terminado"
        desde.append(agent["cierre"]["desde"])
    assert desde[0] == desde[1] == (T0 + timedelta(seconds=5)).isoformat()


def test_closure_time_is_the_check_when_the_process_was_seen_alive(
    pengine: AgentStateEngine, clock: FakeClock, procs: FakeProcesses
) -> None:
    procs.live[4242] = 1000.0
    feed(pengine, pev("session_start", 0), pev("user_prompt_submit", 1, prompt="x"))
    state_at(pengine, clock, 10)  # first check: alive
    del procs.live[4242]
    state_at(pengine, clock, 45)  # next check: gone
    agent = pengine.tick()["agentes"][0]
    assert agent["cierre"]["desde"] == (T0 + timedelta(seconds=45)).isoformat()


def test_pending_question_is_kept_when_closed(
    pengine: AgentStateEngine, clock: FakeClock, procs: FakeProcesses
) -> None:
    procs.live[4242] = 1000.0
    feed(
        pengine,
        pev("session_start", 0),
        pev("stop", 5, last_assistant_message="Encontré un duplicado. ¿Lo borro también?"),
    )
    assert state_at(pengine, clock, 6) == (14, "tu_respuesta")
    del procs.live[4242]
    assert state_at(pengine, clock, 40) == (21, None)  # closed: not waiting anymore
    agent = pengine.tick()["agentes"][0]
    assert agent["pregunta_pendiente"].endswith("¿Lo borro también?")
    assert agent["espera"] is None


def test_reopen_with_pending_question_goes_20_then_14(
    pengine: AgentStateEngine, clock: FakeClock, procs: FakeProcesses
) -> None:
    procs.live[4242] = 1000.0
    feed(pengine, pev("session_start", 0), pev("stop", 5, last_assistant_message="¿Sigo?"))
    del procs.live[4242]
    assert state_at(pengine, clock, 40) == (21, None)
    # claude --resume: new process, same session id.
    procs.live[5151] = 2000.0
    feed(pengine, pev("session_start", 100, pid=5151, created=2000.0, source="resume"))
    assert state_at(pengine, clock, 100.5) == (20, None)
    assert state_at(pengine, clock, 107) == (14, "tu_respuesta")
    # The user answers: the question is gone.
    feed(pengine, pev("user_prompt_submit", 110, pid=5151, created=2000.0, prompt="sí"))
    assert state_at(pengine, clock, 111) == (2, None)
    assert pengine.tick()["agentes"][0]["pregunta_pendiente"] is None


def test_reopen_without_question_goes_20_then_its_state(
    pengine: AgentStateEngine, clock: FakeClock, procs: FakeProcesses
) -> None:
    procs.live[4242] = 1000.0
    feed(pengine, pev("session_start", 0), pev("stop", 5, last_assistant_message="Listo."))
    del procs.live[4242]
    assert state_at(pengine, clock, 40) == (21, None)
    procs.live[5151] = 2000.0
    feed(pengine, pev("session_start", 100, pid=5151, created=2000.0, source="resume"))
    assert state_at(pengine, clock, 101) == (20, None)
    assert state_at(pengine, clock, 107) == (1, None)
    assert pengine.tick()["agentes"][0]["cierre"] is None


def test_reopen_after_session_end(
    pengine: AgentStateEngine, clock: FakeClock, procs: FakeProcesses
) -> None:
    procs.live[4242] = 1000.0
    feed(pengine, pev("session_start", 0), pev("session_end", 5, reason="other"))
    assert state_at(pengine, clock, 200) == (21, None)
    procs.live[6000] = 3000.0
    feed(pengine, pev("session_start", 300, pid=6000, created=3000.0, source="resume"))
    assert state_at(pengine, clock, 300.5) == (20, None)
    assert state_at(pengine, clock, 307) == (1, None)


def test_reused_pid_with_another_creation_time_is_closed(
    pengine: AgentStateEngine, clock: FakeClock, procs: FakeProcesses
) -> None:
    procs.live[4242] = 1000.0
    feed(pengine, pev("session_start", 0), pev("user_prompt_submit", 1, prompt="x"))
    assert state_at(pengine, clock, 5)[0] == 3
    procs.live[4242] = 9999.0  # Windows gave PID 4242 to another process
    assert state_at(pengine, clock, 40) == (21, None)
    assert pengine.tick()["agentes"][0]["cierre"]["motivo"] == "proceso_terminado"


def test_unknown_process_state_does_not_close(clock: FakeClock, browsers: Browsers) -> None:
    engine = AgentStateEngine(
        Thresholds(), clock=clock, browsers_provider=browsers, process_alive=lambda p, c: None
    )
    feed(engine, pev("session_start", 0))
    assert state_at(engine, clock, 40)[0] == 1


def test_session_without_pid_closes_after_configured_24h(
    clock: FakeClock, browsers: Browsers
) -> None:
    # Default is 1 h (see test_agent_event_store); the threshold is configurable.
    pengine = AgentStateEngine(
        Thresholds(no_pid_close=24 * 3600), clock=clock, browsers_provider=browsers
    )
    feed(pengine, start(0), ev("stop", 5, last_assistant_message="¿Lo borro también?"))
    assert state_at(pengine, clock, 23 * 3600) == (14, "tu_respuesta")
    assert state_at(pengine, clock, 5 + 24 * 3600 + 1) == (21, None)
    agent = pengine.tick()["agentes"][0]
    assert agent["cierre"]["motivo"] == "sin_pid_antiguo"
    assert agent["pregunta_pendiente"] == "¿Lo borro también?"
    # Visible 24 h after closing, then gone.
    clock.at(5 + 47 * 3600)
    assert len(pengine.tick()["agentes"]) == 1
    clock.at(5 + 49 * 3600)
    assert pengine.tick()["agentes"] == []


def test_closed_sessions_do_not_count_for_presence(
    pengine: AgentStateEngine, clock: FakeClock, browsers: Browsers, procs: FakeProcesses
) -> None:
    browsers.count = 0
    procs.live[4242] = 1000.0
    feed(pengine, pev("session_start", 0), pev("user_prompt_submit", 10, prompt="x"))
    clock.at(20)
    assert pengine.tick()["presencia"]["estado"] == "conectado"
    del procs.live[4242]
    clock.at(50)
    pengine.tick()  # process check closes the session
    assert pengine.tick()["presencia"]["estado"] == "desconectado"
