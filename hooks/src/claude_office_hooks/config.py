"""Configuration loading and constants for the Claude Office hooks.

IMPORTANT: This module must not produce any stdout/stderr output.
Output suppression is handled in main.py before this module is imported.
"""

import os
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse, urlunparse

# ---------------------------------------------------------------------------
# API endpoint and request constants
# ---------------------------------------------------------------------------

_LOCALHOST_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "::1", None})
_DEFAULT_API_URL = "http://localhost:8000/api/v1/events"


def _resolve_api_url(
    raw_url: str,
    allow_remote: bool,
    on_clamp: Callable[[str | None], None],
) -> str:
    """Return the API URL to use, applying the loopback clamp (ARC-020).

    Remote backends are opt-in: a non-localhost URL is reset to the local
    default unless ``allow_remote`` is True. Event payloads can carry tool
    inputs/outputs and file paths, so this guards against accidental
    exfiltration to an attacker-controlled URL. Mirrored by the OpenCode
    plugin's resolver so both producers treat ``CLAUDE_OFFICE_API_URL``
    identically. Pure + testable; the caller supplies the clamp callback so
    this module never writes to stdout/stderr at import time.
    """
    host = urlparse(raw_url).hostname
    if host in _LOCALHOST_HOSTNAMES:
        return raw_url
    if allow_remote:
        return raw_url
    on_clamp(host)
    return _DEFAULT_API_URL


def _log_clamp(host: str | None) -> None:
    """Record the loopback clamp to the debug log file (never stdout/stderr)."""
    try:
        # Lazy import keeps config.py importable in isolation.
        from claude_office_hooks.debug_logger import log_notice

        log_notice(
            f"CLAUDE_OFFICE_API_URL is non-localhost ('{host}'); clamped to the "
            f"local default. Set CLAUDE_OFFICE_ALLOW_REMOTE=1 to use a remote "
            f"backend.",
            context="config",
        )
    except Exception:
        # Logging must never break the hook.
        pass


def _ipv4_loopback(url: str) -> str:
    """Use 127.0.0.1 instead of ``localhost``.

    On Windows ``localhost`` resolves to ::1 first; the backends listen on
    IPv4 only, so every request waited for the IPv6 attempt to time out
    (~0.5 s with TIMEOUT). Same server, no delay.
    """
    parsed = urlparse(url)
    if parsed.hostname != "localhost":
        return url
    netloc = "127.0.0.1" + (f":{parsed.port}" if parsed.port else "")
    return urlunparse(parsed._replace(netloc=netloc))


def resolve_extra_urls(
    raw: str,
    allow_remote: bool,
    on_clamp: Callable[[str | None], None],
) -> list[str]:
    """Parse CLAUDE_OFFICE_EXTRA_API_URLS (comma-separated) into URLs.

    Each URL goes through the same loopback clamp as the main URL; a clamped
    remote URL is dropped instead of being reset to the default (which would
    duplicate the main destination).
    """
    urls: list[str] = []
    for part in raw.split(","):
        url = part.strip()
        if not url:
            continue
        if _resolve_api_url(url, allow_remote, on_clamp) != url:
            continue
        url = _ipv4_loopback(url)
        if url not in urls:
            urls.append(url)
    return urls


def principal_es_visualizador(raw: str) -> bool:
    """CLAUDE_OFFICE_PRINCIPAL=visualizador: the main destination is our backend.

    By default the main destination is assumed to be the original
    claude-office, which rejects the newer event types (HTTP 422), so those
    only go to the extra destinations. When the main destination is the
    visualizer (daily copy on 8000), it gets every event too.
    """
    return raw.strip().strip('"').strip("'").lower() == "visualizador"


def event_targets(
    event_type: object,
    api_url: str,
    extra_urls: list[str],
    new_event_types: frozenset[str],
    main_gets_all: bool,
) -> list[tuple[str, bool]]:
    """Destinations of one event as (url, is_main).

    The main destination gets every event when ``main_gets_all`` is set, and
    otherwise every event except ``new_event_types``. Extra destinations get
    every event; an extra equal to the main URL is skipped (no duplicates).
    """
    targets: list[tuple[str, bool]] = []
    if main_gets_all or event_type not in new_event_types:
        targets.append((api_url, True))
    for url in extra_urls:
        if url != api_url:
            targets.append((url, False))
    return targets


ALLOW_REMOTE = os.environ.get("CLAUDE_OFFICE_ALLOW_REMOTE", "") == "1"

API_URL = _ipv4_loopback(
    _resolve_api_url(
        os.environ.get("CLAUDE_OFFICE_API_URL", _DEFAULT_API_URL),
        ALLOW_REMOTE,
        _log_clamp,
    )
)

# Mutable holder for the API key — populated by load_config().
_api_key_holder: list[str] = [""]
# Seconds. Every destination is sent in parallel. The hook waits up to
# SEND_BUDGET for the main destination but only EXTRA_BUDGET for the extra
# ones: a stopped backend (a refused connection on Windows still takes
# ~0.5 s) is abandoned instead of delaying Claude. Python start-up already
# takes ~150 ms of the ~300 ms target.
TIMEOUT = 0.25
EXTRA_TIMEOUT = 0.25
SEND_BUDGET = 0.25
EXTRA_BUDGET = 0.08


def get_api_key() -> str:
    """Return the current API key (may be empty string before load_config)."""
    return _api_key_holder[0]


def _set_api_key(key: str) -> None:
    _api_key_holder[0] = key


# ---------------------------------------------------------------------------
# Config file location
# ---------------------------------------------------------------------------

CONFIG_FILE = Path.home() / ".claude" / "claude-office-config.env"

# ---------------------------------------------------------------------------
# Default project-name prefix stripping
# ---------------------------------------------------------------------------

# Prefixes to strip from project names derived from transcript paths.
# These path fragments appear because Claude names projects after the
# filesystem path where the session was started (with slashes → dashes).
# Default is empty -- configure via CLAUDE_OFFICE_STRIP_PREFIXES env var,
# the --strip-prefixes CLI flag, or the config file.
STRIP_PREFIXES: list[str] = []


def load_config() -> dict[str, str]:
    """Load key=value pairs from CONFIG_FILE.

    Returns:
        A dictionary of configuration key/value pairs.  Returns an empty
        dict if the file does not exist or cannot be read.
    """
    config: dict[str, str] = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        # Strip surrounding quotes from the value
                        value = value.strip().strip('"').strip("'")
                        config[key.strip()] = value
        except Exception:
            # Config loading must never raise — hooks must always exit 0
            pass
    # Set API key from config or env var (env var takes precedence)
    _set_api_key(os.environ.get("CLAUDE_OFFICE_API_KEY", config.get("CLAUDE_OFFICE_API_KEY", "")))
    return config
