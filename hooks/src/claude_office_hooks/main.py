#!/usr/bin/env python3
"""
Claude Office Hooks - Event handler for Claude Code lifecycle events.

CRITICAL: This hook must NEVER interfere with Claude Code:
- Never print to stdout (would inject context into Claude's conversation),
  except the decision JSON of a PermissionRequest answered from the office
  (permisos.py), written to the real stdout
- Never print to stderr (would show errors to user)
- Always exit 0 (non-zero blocks Claude actions)

All output is suppressed and errors are logged to the debug file.
"""

import io
import sys

# Suppress ALL output immediately - before any imports that might fail
sys.stdout = io.StringIO()
sys.stderr = io.StringIO()

# debug_logger defines DEBUG_LOG_PATH and is safe to import here because
# it never writes to stdout/stderr.
from claude_office_hooks.debug_logger import log_error  # noqa: E402

# Wrap ALL remaining logic in try/except to guarantee exit 0
try:
    import argparse
    import json
    import os
    import threading
    import time
    import urllib.request
    from typing import Any, cast

    from claude_office_hooks.config import (
        ALLOW_REMOTE,
        API_URL,
        EXTRA_BUDGET,
        EXTRA_TIMEOUT,
        SEND_BUDGET,
        TIMEOUT,
        _log_clamp,  # pyright: ignore[reportPrivateUsage]
        auth_headers,
        event_targets,
        load_config,
        principal_es_visualizador,
        resolve_extra_urls,
    )
    from claude_office_hooks.debug_logger import debug_log
    from claude_office_hooks.event_mapper import NEW_EVENT_TYPES, map_event
    from claude_office_hooks.peligrosos import decision_pre_tool_use
    from claude_office_hooks.permisos import pedir_decision
    from claude_office_hooks.process_info import find_claude_process

    # Derived from package metadata; fallback covers the uninstalled case (ARC-021).
    try:
        from importlib.metadata import version as _pkg_version

        __version__ = _pkg_version("claude-office-hooks")
    except Exception:
        __version__ = "0.0.0+unknown"

    # Load config at module init so DEBUG flag is available immediately
    _config = load_config()
    DEBUG = _config.get("CLAUDE_OFFICE_DEBUG", "0") == "1"

    # Extra destinations (e.g. the development copy on 8100), from the env var
    # or the config file. They receive every event, including types the main
    # destination may not know (NEW_EVENT_TYPES).
    EXTRA_API_URLS = resolve_extra_urls(
        os.environ.get(
            "CLAUDE_OFFICE_EXTRA_API_URLS", _config.get("CLAUDE_OFFICE_EXTRA_API_URLS", "")
        ),
        ALLOW_REMOTE,
        _log_clamp,
    )

    # CLAUDE_OFFICE_PRINCIPAL=visualizador: the main destination (8000) is the
    # visualizer, not the original claude-office, so it also gets the newer
    # event types. Unset: compatible with claude-office (they go to extras only).
    MAIN_GETS_ALL = principal_es_visualizador(
        os.environ.get("CLAUDE_OFFICE_PRINCIPAL", _config.get("CLAUDE_OFFICE_PRINCIPAL", ""))
    )

    def _open_request(req: "urllib.request.Request", url: str, timeout: float) -> Any:
        """Open *req* without ever creating an SSL context for http URLs.

        On some Windows setups the bundled OpenSSL aborts the whole process
        (``OPENSSL_Uplink: no OPENSSL_Applink``) the moment an SSL context is
        created, because reading the OpenSSL config/cert file via stdio needs
        an applink shim the standalone python launcher does not export. The
        default backend is local plain http, so for http URLs we build an
        opener with urllib's standard HTTP handlers **except** ``HTTPSHandler``
        — that keeps proxy support (``ProxyHandler``) and redirect following
        (``HTTPRedirectHandler``) for remote http backends while never
        constructing an SSL context, so the crash can't happen. ``https`` URLs
        keep the standard opener (SSL expected) so remote deployments still
        work. (Remote backends are opt-in: ``config.py`` clamps
        ``CLAUDE_OFFICE_API_URL`` to localhost unless
        ``CLAUDE_OFFICE_ALLOW_REMOTE=1`` is set — ARC-020.)

        ``build_opener()`` is intentionally avoided: it always adds
        ``HTTPSHandler``, which would re-trigger the context creation.
        """
        if url.lower().startswith("https"):
            return urllib.request.urlopen(req, timeout=timeout)
        opener = urllib.request.OpenerDirector()
        for handler in (
            urllib.request.ProxyHandler(),
            urllib.request.HTTPHandler(),
            urllib.request.HTTPDefaultErrorHandler(),
            urllib.request.HTTPRedirectHandler(),
            urllib.request.HTTPErrorProcessor(),
        ):
            opener.add_handler(handler)
        return opener.open(req, timeout=timeout)

    def _post(url: str, body: bytes, headers: dict[str, str], timeout: float, quiet: bool) -> None:
        """POST one payload to one destination; never raises."""
        try:
            req = urllib.request.Request(url, data=body, headers=headers)
            with _open_request(req, url, timeout) as response:
                if response.status >= 300:
                    log_error(
                        RuntimeError(f"backend {url} returned HTTP {response.status}"),
                        "send_event",
                    )
        except Exception as exc:
            # An extra destination that is turned off is expected: not an error.
            if not quiet:
                log_error(exc, f"send_event to {url} failed")

    def _json_request(
        url: str, body: dict[str, Any] | None, timeout: float
    ) -> dict[str, Any] | None:
        """GET (body None) or POST JSON to the main backend; None on any error."""
        try:
            headers: dict[str, str] = {"Content-Type": "application/json", **auth_headers()}
            data = json.dumps(body).encode("utf-8") if body is not None else None
            req = urllib.request.Request(url, data=data, headers=headers)
            with _open_request(req, url, timeout) as response:
                if response.status >= 300:
                    return None
                result = json.loads(response.read().decode("utf-8"))
                return cast(dict[str, Any], result) if isinstance(result, dict) else None
        except Exception as exc:
            log_error(exc, f"permisos: {url}")
            return None

    def write_decision(decision: dict[str, Any]) -> None:
        """The only output of the hook: the PermissionRequest decision, on the real stdout."""
        real_stdout = sys.__stdout__
        if real_stdout is not None:
            real_stdout.write(json.dumps(decision))
            real_stdout.flush()

    def send_event(payload: dict[str, Any]) -> None:
        """POST *payload* to every destination in parallel.

        The main destination gets the event unless its type is one older
        backends reject (or always, with CLAUDE_OFFICE_PRINCIPAL=visualizador);
        extra destinations get every event. The hook waits up
        to SEND_BUDGET for the main destination and EXTRA_BUDGET for the extra
        ones, then returns (pending requests run in daemon threads and are
        dropped at exit). Errors are always swallowed.
        """
        try:
            body = json.dumps(payload).encode("utf-8")
            # The machine token goes only to the main backend, never to extras.
            principal: dict[str, str] = {"Content-Type": "application/json", **auth_headers()}
            extra: dict[str, str] = {
                "Content-Type": "application/json",
                **auth_headers(con_token=False),
            }
            # (url, request timeout, quiet errors, wait budget)
            targets: list[tuple[str, float, bool, float]] = [
                (url, TIMEOUT, False, SEND_BUDGET)
                if is_main
                else (url, EXTRA_TIMEOUT, True, EXTRA_BUDGET)
                for url, is_main in event_targets(
                    payload.get("event_type"),
                    API_URL,
                    EXTRA_API_URLS,
                    NEW_EVENT_TYPES,
                    MAIN_GETS_ALL,
                )
            ]
            started = time.monotonic()
            threads = [
                (
                    threading.Thread(
                        target=_post,
                        args=(url, body, extra if q else principal, t, q),
                        daemon=True,
                    ),
                    budget,
                )
                for url, t, q, budget in targets
            ]
            for th, _ in threads:
                th.start()
            for th, budget in threads:
                th.join(max(0.0, started + budget - time.monotonic()))
        except Exception as exc:
            log_error(exc, "send_event failed")

    def main() -> None:
        """Parse arguments, read stdin, map the event, and POST to backend."""
        # Handle --version before argparse (which requires event_type positional arg)
        if "--version" in sys.argv or "-V" in sys.argv:
            real_stdout = sys.__stdout__
            if real_stdout is not None:
                real_stdout.write(f"claude-office-hook {__version__}\n")
                real_stdout.flush()
            sys.exit(0)

        # The summaries' helper agent of the monitor (stage 2.4) never reaches the
        # office: it runs without hooks, and if one ran anyway it sends nothing.
        if os.environ.get("VISUALIZADOR_AUXILIAR"):
            sys.exit(0)

        parser = argparse.ArgumentParser(description="Claude Office hook event handler")
        parser.add_argument(
            "event_type",
            nargs="?",
            help="The type of event (session_start, pre_tool_use, etc.)",
        )
        parser.add_argument(
            "-V",
            "--version",
            action="version",
            version=f"claude-office-hook {__version__}",
        )
        parser.add_argument(
            "--strip-prefixes",
            type=str,
            default=None,
            help=(
                "Comma-separated list of prefixes to strip from project names. "
                "Example: --strip-prefixes '-Users-myuser-Repos-,-Users-myuser-'"
            ),
        )
        args = parser.parse_args()

        if not args.event_type:
            real_stderr = sys.__stderr__
            if real_stderr is not None:
                real_stderr.write("error: event_type is required\n")
                real_stderr.flush()
            sys.exit(1)

        # Resolve strip prefixes: CLI arg > env var > config file > built-in defaults
        strip_prefixes: list[str] | None = None
        prefixes_str = (
            args.strip_prefixes
            or os.environ.get("CLAUDE_OFFICE_STRIP_PREFIXES")
            or _config.get("CLAUDE_OFFICE_STRIP_PREFIXES")
        )
        if prefixes_str:
            strip_prefixes = [p.strip() for p in prefixes_str.split(",") if p.strip()]

        # Read event JSON from the real stdin (our suppressed sys.stdin is a StringIO)
        raw_data: dict[str, Any] = {}
        try:
            real_stdin = sys.__stdin__
            if (
                real_stdin is not None
                and not real_stdin.closed
                and hasattr(real_stdin, "isatty")
                and not real_stdin.isatty()
            ):
                raw_input = real_stdin.buffer.read().decode("utf-8-sig", errors="replace")
                if raw_input.strip():
                    raw_data = cast(dict[str, Any], json.loads(raw_input))
        except Exception as exc:
            log_error(exc, "stdin read skipped")

        session_id = os.environ.get("CLAUDE_SESSION_ID", "default")
        payload = map_event(args.event_type, raw_data, session_id, strip_prefixes)

        if payload is None:
            if DEBUG:
                debug_log(
                    args.event_type,
                    raw_data,
                    {"skipped": True, "reason": "event returns None"},
                    enabled=DEBUG,
                )
            return

        # Claude Code process that owns the session (PID + creation time, so a
        # reused PID is not mistaken for it). None when it cannot be found.
        proc = find_claude_process()
        payload["data"]["claude_pid"] = proc[0] if proc else None
        payload["data"]["claude_pid_created"] = proc[1] if proc else None

        debug_log(args.event_type, raw_data, payload, enabled=DEBUG)
        send_event(payload)

        # Dangerous commands always ask for approval, even in Auto mode.
        if args.event_type == "pre_tool_use":
            pregunta = decision_pre_tool_use(raw_data)
            if pregunta is not None:
                write_decision(pregunta)

        # Permission requests: the office may approve or reject them (the
        # backend decides whether to wait, by policy and presence).
        if args.event_type == "permission_request":
            decision = pedir_decision(
                raw_data,
                payload,
                API_URL,
                post_json=lambda url, body, t: _json_request(url, body, t),
                get_json=lambda url, t: _json_request(url, None, t),
            )
            if decision is not None:
                write_decision(decision)

    if __name__ == "__main__":
        try:
            main()
        except SystemExit:
            # argparse calls sys.exit() on --help / errors — let it propagate
            raise
        except Exception as e:
            log_error(e, "Error in main()")
        # ALWAYS exit 0 when run as script — never let the hook block Claude
        sys.exit(0)

except Exception as e:
    log_error(e, "Error during module initialization")
    sys.exit(0)  # Exit cleanly even on import errors
