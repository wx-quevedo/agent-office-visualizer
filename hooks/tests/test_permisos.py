"""PermissionRequest answered from the office (claude_office_hooks/permisos.py)."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from claude_office_hooks.permisos import (
    base_permisos,
    cuenta_de,
    pedir_decision,
    salida_permitir,
    salida_rechazar,
)

API = "http://127.0.0.1:8100/api/v1/events"
RAW = {
    "session_id": "prueba-hook",
    "transcript_path": "C:/Users/x/.claude-demo/projects/E--demo/abc.jsonl",
    "tool_name": "Bash",
    "tool_input": {"command": "git status", "description": "Estado"},
}
PAYLOAD = {"session_id": "prueba-hook", "data": {"project_name": "demo"}}


class Reloj:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def flujo(
    respuestas: list[dict[str, Any] | None],
    registro: dict[str, Any] | None = None,
    reloj: Reloj | None = None,
    paso: float = 5.0,
):
    """Runs pedir_decision with fake HTTP: each GET returns the next answer and takes *paso* s."""
    reloj = reloj or Reloj()
    llamadas: list[tuple[str, Any]] = []
    cola = list(respuestas)

    def post_json(url: str, body: dict[str, Any], timeout: float) -> dict[str, Any] | None:
        llamadas.append(("POST", body))
        return registro if registro is not None else {"esperar": True, "segundos_restantes": 90}

    def get_json(url: str, timeout: float) -> dict[str, Any] | None:
        llamadas.append(("GET", (url, timeout)))
        reloj.t += paso
        return cola.pop(0) if cola else {"estado": "pendiente"}

    out = pedir_decision(RAW, PAYLOAD, API, post_json, get_json, reloj=reloj, dormir=lambda s: None)
    return out, llamadas, reloj


def test_registra_la_solicitud_completa() -> None:
    _, llamadas, _ = flujo([{"estado": "aprobada"}])
    metodo, body = llamadas[0]
    assert metodo == "POST"
    assert body["session_id"] == "prueba-hook"
    assert body["herramienta"] == "Bash"
    assert body["entrada"]["command"] == "git status"
    assert body["cuenta"] == "demo"
    assert body["proyecto"] == "demo"
    assert len(body["id"]) == 32


def test_aprobada_da_allow() -> None:
    out, _, _ = flujo([{"estado": "pendiente"}, {"estado": "aprobada"}])
    assert out == salida_permitir()
    assert out["hookSpecificOutput"]["decision"] == {"behavior": "allow"}  # type: ignore[index]


def test_rechazada_da_deny_con_motivo() -> None:
    out, _, _ = flujo([{"estado": "rechazada", "motivo": "Usa la rama de prueba"}])
    assert out == salida_rechazar("Usa la rama de prueba")
    decision = out["hookSpecificOutput"]["decision"]  # type: ignore[index]
    assert decision["behavior"] == "deny"
    assert "Usa la rama de prueba" in decision["message"]


@pytest.mark.parametrize("estado", ["vencida", "resuelta_fuera", "rara"])
def test_sin_decision(estado: str) -> None:
    out, _, _ = flujo([{"estado": estado}])
    assert out is None


def test_politica_no_espera_no_consulta() -> None:
    out, llamadas, _ = flujo([], registro={"esperar": False, "segundos_restantes": 0})
    assert out is None
    assert [m for m, _ in llamadas] == ["POST"]


def test_backend_caido_al_registrar() -> None:
    def post_json(url: str, body: dict[str, Any], timeout: float) -> None:
        assert timeout <= 2.0  # the registration gives up after ~2 s
        return None

    out = pedir_decision(RAW, PAYLOAD, API, post_json, lambda u, t: {"estado": "aprobada"})
    assert out is None


def test_backend_cae_durante_la_espera() -> None:
    out, _, _ = flujo([{"estado": "pendiente"}, None, {"estado": "aprobada"}])
    assert out is None


def test_tiempo_agotado_sin_decision() -> None:
    out, llamadas, reloj = flujo([], registro={"esperar": True, "segundos_restantes": 30})
    assert out is None
    assert reloj.t <= 30
    gets = [x for m, x in llamadas if m == "GET"]
    # each long-poll asks at most 20 s and gives the backend a small margin
    assert all(float(url.split("espera=")[1]) <= 20 for url, _ in gets)
    assert all(t <= 20 + 2.5 for _, t in gets)


def test_nunca_pasa_del_limite_del_hook() -> None:
    reloj = Reloj()
    out, _, reloj = flujo([], registro={"esperar": True, "segundos_restantes": 10_000}, reloj=reloj)
    assert out is None
    assert reloj.t <= 540


def test_un_error_inesperado_termina_sin_decision() -> None:
    def explota(*a: Any) -> None:
        raise RuntimeError("x")

    assert pedir_decision(RAW, PAYLOAD, API, explota, explota) is None
    assert (
        pedir_decision(
            RAW,
            {"session_id": None},
            API,
            lambda *a: {"esperar": True, "segundos_restantes": "x"},
            explota,
        )
        is None
    )  # noqa: E501


def test_base_y_cuenta() -> None:
    assert (
        base_permisos("http://127.0.0.1:8000/api/v1/events")
        == "http://127.0.0.1:8000/api/v1/permisos"
    )
    assert cuenta_de("C:/Users/x/.claude/projects/a.jsonl") == "personal"
    assert cuenta_de(None) == "personal"


def test_servidor_que_no_responde_no_cuelga_el_hook() -> None:
    """A backend that accepts the connection and never answers: the hook gives up in time."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(8)
    port = srv.getsockname()[1]
    abiertas: list[socket.socket] = []

    def aceptar() -> None:
        try:
            while True:
                c, _ = srv.accept()
                abiertas.append(c)  # never answers
        except OSError:
            pass

    threading.Thread(target=aceptar, daemon=True).start()

    def real(url: str, body: dict[str, Any] | None, timeout: float) -> dict[str, Any] | None:
        try:
            data = json.dumps(body).encode() if body is not None else None
            cab = {"Content-Type": "application/json"}
            req = urllib.request.Request(url, data=data, headers=cab)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except Exception:
            return None

    inicio = time.monotonic()
    out = pedir_decision(
        RAW,
        PAYLOAD,
        f"http://127.0.0.1:{port}/api/v1/events",
        lambda u, b, t: real(u, b, t),
        lambda u, t: real(u, None, t),
    )
    assert out is None
    assert time.monotonic() - inicio < 3.5
    srv.close()
    for c in abiertas:
        c.close()


# -- the hook process, end to end ---------------------------------------------------------


class Backend(BaseHTTPRequestHandler):
    decision: dict[str, Any] = {"estado": "aprobada"}
    esperar = True
    recibidos: list[str] = []

    def log_message(self, *a: Any) -> None:
        pass

    def _json(self, obj: Any) -> None:
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        n = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(n)
        Backend.recibidos.append(self.path)
        if self.path.endswith("/permisos/solicitudes"):
            self._json({"esperar": Backend.esperar, "segundos_restantes": 30})
        else:
            self._json({"status": "accepted"})

    def do_GET(self) -> None:
        Backend.recibidos.append(self.path)
        self._json(Backend.decision)


@pytest.fixture
def backend():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Backend)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    Backend.recibidos = []
    yield srv.server_address[1]
    srv.shutdown()


def correr_hook(port: int, home: Path) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "CLAUDE_OFFICE_API_URL": f"http://127.0.0.1:{port}/api/v1/events",
        "CLAUDE_OFFICE_EXTRA_API_URLS": "",
        "CLAUDE_OFFICE_PRINCIPAL": "visualizador",
        "USERPROFILE": str(home),
        "HOME": str(home),
    }
    return subprocess.run(
        [sys.executable, "-m", "claude_office_hooks.main", "permission_request"],
        input=json.dumps({**RAW, "hook_event_name": "PermissionRequest"}),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


@pytest.mark.parametrize(
    ("decision", "esperar", "esperado"),
    [
        ({"estado": "aprobada"}, True, {"behavior": "allow"}),
        ({"estado": "rechazada", "motivo": "No"}, True, "deny"),
        ({"estado": "aprobada"}, False, None),
    ],
)
def test_proceso_del_hook(
    backend: int, tmp_path: Path, decision: dict[str, Any], esperar: bool, esperado: Any
) -> None:
    Backend.decision = decision
    Backend.esperar = esperar
    r = correr_hook(backend, tmp_path)
    assert r.returncode == 0
    assert r.stderr == ""
    assert any(p.endswith("/events") for p in Backend.recibidos)
    if esperado is None:
        assert r.stdout == ""
        return
    out = json.loads(r.stdout)
    d = out["hookSpecificOutput"]["decision"]
    assert out["hookSpecificOutput"]["hookEventName"] == "PermissionRequest"
    if esperado == "deny":
        assert d["behavior"] == "deny" and "No" in d["message"]
    else:
        assert d == esperado


def test_proceso_con_backend_apagado_no_escribe_nada(tmp_path: Path) -> None:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()  # nothing listens there
    inicio = time.monotonic()
    r = correr_hook(port, tmp_path)
    assert r.returncode == 0 and r.stdout == "" and r.stderr == ""
    assert time.monotonic() - inicio < 10
