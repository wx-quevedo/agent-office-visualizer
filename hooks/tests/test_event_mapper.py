"""Tests for event_mapper subagent event handling."""

from claude_office_hooks.event_mapper import map_event

SESSION_ID = "test-session-001"
TRANSCRIPT = "/home/user/.claude/projects/myproject/session.jsonl"


def _pre_tool_use_agent(tool_use_id: str = "tu_123") -> dict:
    return {
        "tool_name": "Agent",
        "tool_use_id": tool_use_id,
        "tool_input": {"prompt": "do something", "description": "Test Agent"},
        "session_id": SESSION_ID,
        "transcript_path": TRANSCRIPT,
    }


def _pre_tool_use_task(tool_use_id: str = "tu_456") -> dict:
    return {
        "tool_name": "Task",
        "tool_use_id": tool_use_id,
        "tool_input": {"prompt": "do something", "description": "Test Task"},
        "session_id": SESSION_ID,
        "transcript_path": TRANSCRIPT,
    }


def _post_tool_use_agent(
    tool_use_id: str = "tu_123",
    agent_id: str | None = "a5a60c7",
    run_in_background: bool = False,
) -> dict:
    tool_input: dict = {"prompt": "do something"}
    if run_in_background:
        tool_input["run_in_background"] = True
    resp = {}
    if agent_id is not None:
        resp["agentId"] = agent_id
    return {
        "tool_name": "Agent",
        "tool_use_id": tool_use_id,
        "tool_input": tool_input,
        "tool_response": resp,
        "session_id": SESSION_ID,
        "transcript_path": TRANSCRIPT,
    }


def _post_tool_use_task(tool_use_id: str = "tu_456") -> dict:
    return {
        "tool_name": "Task",
        "tool_use_id": tool_use_id,
        "tool_input": {"prompt": "do something"},
        "tool_response": {"content": "done"},
        "session_id": SESSION_ID,
        "transcript_path": TRANSCRIPT,
    }


class TestPreToolUseSubagentStart:
    """PreToolUse for Agent/Task tools should remap to subagent_start."""

    def test_agent_tool_creates_subagent_start(self) -> None:
        result = map_event("pre_tool_use", _pre_tool_use_agent(), SESSION_ID)
        assert result is not None
        assert result["event_type"] == "subagent_start"
        assert result["data"]["agent_id"] == "subagent_tu_123"

    def test_task_tool_creates_subagent_start(self) -> None:
        result = map_event("pre_tool_use", _pre_tool_use_task(), SESSION_ID)
        assert result is not None
        assert result["event_type"] == "subagent_start"
        assert result["data"]["agent_id"] == "subagent_tu_456"

    def test_extracts_description_and_prompt(self) -> None:
        result = map_event("pre_tool_use", _pre_tool_use_agent(), SESSION_ID)
        assert result is not None
        assert result["data"]["agent_name"] == "Test Agent"
        assert result["data"]["task_description"] == "do something"


class TestPostToolUseAgentAsync:
    """PostToolUse for Agent tool with agentId in response (async, v2.1+)."""

    def test_agent_with_agent_id_does_not_send_subagent_stop(self) -> None:
        """Agent tool with agentId in response means agent is still running async."""
        result = map_event("post_tool_use", _post_tool_use_agent(), SESSION_ID)
        assert result is not None
        assert result["event_type"] == "post_tool_use"
        assert result["data"]["agent_id"] == "main"

    def test_agent_with_agent_id_preserves_native_id(self) -> None:
        result = map_event("post_tool_use", _post_tool_use_agent(), SESSION_ID)
        assert result is not None
        assert result["data"]["native_agent_id"] == "a5a60c7"

    def test_agent_with_agent_id_preserves_transcript_path(self) -> None:
        result = map_event("post_tool_use", _post_tool_use_agent(), SESSION_ID)
        assert result is not None
        assert result["data"]["agent_transcript_path"] is not None
        assert "subagents/agent-a5a60c7" in result["data"]["agent_transcript_path"]

    def test_agent_without_agent_id_sends_subagent_stop(self) -> None:
        """Agent tool without agentId in response means sync completion (legacy)."""
        result = map_event("post_tool_use", _post_tool_use_agent(agent_id=None), SESSION_ID)
        assert result is not None
        assert result["event_type"] == "subagent_stop"
        assert result["data"]["agent_id"] == "subagent_tu_123"


class TestPostToolUseTaskSync:
    """PostToolUse for Task tool (always sync, no agentId)."""

    def test_task_sends_subagent_stop(self) -> None:
        result = map_event("post_tool_use", _post_tool_use_task(), SESSION_ID)
        assert result is not None
        assert result["event_type"] == "subagent_stop"
        assert result["data"]["agent_id"] == "subagent_tu_456"


class TestPostToolUseBackground:
    """PostToolUse with run_in_background should not send subagent_stop."""

    def test_background_agent_sends_main_id(self) -> None:
        result = map_event(
            "post_tool_use",
            _post_tool_use_agent(run_in_background=True),
            SESSION_ID,
        )
        assert result is not None
        assert result["event_type"] == "post_tool_use"
        assert result["data"]["agent_id"] == "main"


class TestNativeSubagentStart:
    """Native SubagentStart hook should remap to subagent_info."""

    def test_native_subagent_start_maps_to_info(self) -> None:
        raw = {
            "agent_id": "a5a60c7",
            "agent_type": "general-purpose",
            "session_id": SESSION_ID,
            "transcript_path": TRANSCRIPT,
        }
        result = map_event("subagent_start", raw, SESSION_ID)
        assert result is not None
        assert result["event_type"] == "subagent_info"
        assert result["data"]["native_agent_id"] == "a5a60c7"

    def test_native_subagent_start_without_agent_id_returns_none(self) -> None:
        raw = {
            "session_id": SESSION_ID,
            "transcript_path": TRANSCRIPT,
        }
        result = map_event("subagent_start", raw, SESSION_ID)
        assert result is None


class TestNativeSubagentStop:
    """Native SubagentStop hook should pass through with native_agent_id."""

    def test_native_subagent_stop_includes_native_id(self) -> None:
        raw = {
            "agent_id": "a5a60c7",
            "session_id": SESSION_ID,
            "transcript_path": TRANSCRIPT,
        }
        result = map_event("subagent_stop", raw, SESSION_ID)
        assert result is not None
        assert result["event_type"] == "subagent_stop"
        assert result["data"]["native_agent_id"] == "a5a60c7"

    def test_native_subagent_stop_without_agent_id_returns_none(self) -> None:
        raw = {
            "session_id": SESSION_ID,
            "transcript_path": TRANSCRIPT,
        }
        result = map_event("subagent_stop", raw, SESSION_ID)
        assert result is None


class TestHookDataForStateEngine:
    """Fields added for the agent state engine (compatible with older backends)."""

    def test_post_tool_use_failure_is_mapped(self) -> None:
        payload = map_event(
            "post_tool_use_failure",
            {
                "session_id": SESSION_ID,
                "tool_name": "Bash",
                "tool_use_id": "t1",
                "tool_input": {"command": "npm test"},
                "error": "Exit code 1\n" + "x" * 2000,
                "is_interrupt": False,
                "duration_ms": 4187,
            },
            SESSION_ID,
        )
        assert payload is not None
        assert payload["event_type"] == "post_tool_use_failure"
        data = payload["data"]
        assert data["success"] is False
        assert data["agent_id"] == "main"
        assert data["error"].startswith("Exit code 1")
        assert len(data["error"]) <= 500
        assert data["is_interrupt"] is False

    def test_subagent_tool_keeps_main_agent_id_and_adds_tool_agent(self) -> None:
        for event in ("pre_tool_use", "post_tool_use", "permission_request"):
            payload = map_event(
                event,
                {
                    "session_id": SESSION_ID,
                    "tool_name": "Read",
                    "tool_use_id": "t1",
                    "agent_id": "agent-abc123",
                    "agent_type": "Explore",
                },
                SESSION_ID,
            )
            assert payload is not None
            assert payload["data"]["agent_id"] == "main"
            assert payload["data"]["tool_agent_id"] == "agent-abc123"
            assert payload["data"]["tool_agent_type"] == "Explore"

    def test_main_thread_tool_has_no_tool_agent(self) -> None:
        payload = map_event(
            "pre_tool_use", {"session_id": SESSION_ID, "tool_name": "Read"}, SESSION_ID
        )
        assert payload is not None
        assert "tool_agent_id" not in payload["data"]

    def test_notification_type_field(self) -> None:
        payload = map_event(
            "notification",
            {"session_id": SESSION_ID, "notification_type": "idle_prompt", "message": "m"},
            SESSION_ID,
        )
        assert payload is not None
        assert payload["data"]["notification_type"] == "idle_prompt"

    def test_stop_sends_tail_of_last_message(self) -> None:
        payload = map_event(
            "stop",
            {"session_id": SESSION_ID, "last_assistant_message": "a" * 1000 + " ¿Sigo?"},
            SESSION_ID,
        )
        assert payload is not None
        msg = payload["data"]["last_assistant_message"]
        assert msg.endswith("¿Sigo?")
        assert len(msg) == 300

    def test_every_event_declares_failure_reporting(self) -> None:
        payload = map_event("session_start", {"session_id": SESSION_ID}, SESSION_ID)
        assert payload is not None
        assert payload["data"]["reports_tool_failures"] is True


def test_prompt_without_injected_blocks() -> None:
    payload = map_event(
        "user_prompt_submit",
        {
            "session_id": SESSION_ID,
            "prompt": "<browser_instruction># Claude in Chrome\nlargo</browser_instruction>\n\n"
            "Corre el comando ping",
        },
        SESSION_ID,
    )
    assert payload is not None
    assert payload["data"]["prompt"] == "Corre el comando ping"
