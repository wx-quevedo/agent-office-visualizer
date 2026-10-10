"""Tests for config._resolve_api_url — the ARC-020 loopback clamp + opt-in remote."""

from claude_office_hooks.config import _DEFAULT_API_URL, _resolve_api_url


def _no_clamp(_host: str | None) -> None:
    """Clamp callback that records nothing; use when the clamp path is irrelevant."""
    raise AssertionError("expected no clamp")


def test_localhost_url_passes_through():
    url = "http://localhost:8000/api/v1/events"
    assert _resolve_api_url(url, False, _no_clamp) == url


def test_loopback_ipv4_and_ipv6_pass_through():
    assert (
        _resolve_api_url("http://127.0.0.1:8000/api/v1/events", False, _no_clamp)
        == "http://127.0.0.1:8000/api/v1/events"
    )
    assert (
        _resolve_api_url("http://[::1]:8000/api/v1/events", False, _no_clamp)
        == "http://[::1]:8000/api/v1/events"
    )


def test_remote_url_clamped_by_default():
    clamped: list[str | None] = []
    result = _resolve_api_url(
        "https://office.example.com/api/v1/events",
        False,
        clamped.append,
    )
    assert result == _DEFAULT_API_URL
    assert clamped == ["office.example.com"]


def test_remote_url_allowed_when_flag_set():
    clamped = []
    remote = "https://office.example.com/api/v1/events"
    result = _resolve_api_url(remote, True, clamped.append)
    assert result == remote
    assert clamped == []


def test_remote_hostname_with_port_clamps_on_host_only():
    clamped: list[str | None] = []
    result = _resolve_api_url("http://10.0.0.5:9000/api/v1/events", False, clamped.append)
    assert result == _DEFAULT_API_URL
    assert clamped == ["10.0.0.5"]


def test_localhost_becomes_ipv4_loopback() -> None:
    from claude_office_hooks.config import _ipv4_loopback

    assert _ipv4_loopback("http://localhost:8000/api/v1/events") == (
        "http://127.0.0.1:8000/api/v1/events"
    )
    assert _ipv4_loopback("http://127.0.0.1:8100/x") == "http://127.0.0.1:8100/x"


def test_extra_urls_parsed_clamped_and_deduplicated() -> None:
    from claude_office_hooks.config import resolve_extra_urls

    clamped: list[str | None] = []
    urls = resolve_extra_urls(
        "http://127.0.0.1:8100/api/v1/events, http://localhost:8100/api/v1/events,"
        " http://evil.example.com/x,,",
        False,
        clamped.append,
    )
    assert urls == ["http://127.0.0.1:8100/api/v1/events"]
    assert clamped == ["evil.example.com"]


def test_principal_visualizador_flag() -> None:
    from claude_office_hooks.config import principal_es_visualizador

    assert principal_es_visualizador("visualizador")
    assert principal_es_visualizador(' "Visualizador" ')
    assert not principal_es_visualizador("")
    assert not principal_es_visualizador("claude-office")


def test_event_targets_new_types_reach_main_only_when_it_is_the_visualizer() -> None:
    from claude_office_hooks.config import event_targets

    main = "http://127.0.0.1:8000/api/v1/events"
    extra = ["http://127.0.0.1:8100/api/v1/events", main]
    nuevos = frozenset({"post_tool_use_failure"})
    # claude-office as main (default): new types only to the extra destination.
    assert event_targets("post_tool_use_failure", main, extra, nuevos, False) == [
        ("http://127.0.0.1:8100/api/v1/events", False)
    ]
    # Visualizer as main: every event to both, the duplicated extra skipped.
    assert event_targets("post_tool_use_failure", main, extra, nuevos, True) == [
        (main, True),
        ("http://127.0.0.1:8100/api/v1/events", False),
    ]
    assert event_targets("pre_tool_use", main, extra, nuevos, False) == [
        (main, True),
        ("http://127.0.0.1:8100/api/v1/events", False),
    ]
