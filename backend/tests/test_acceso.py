"""Stage 1.1: user, sessions, machines, machine tokens, CSRF, sign-in limit, migration."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api import acceso_middleware as mw
from app.api.acceso_middleware import COOKIE_SESION, AccesoMiddleware, ws_autorizado
from app.api.middleware import LocalhostOnlyMiddleware
from app.api.routes import acceso as rutas_acceso
from app.api.routes import agents_state, events
from app.api.routes import permisos as rutas_permisos
from app.config import get_settings
from app.core import acceso as acceso_mod
from app.core import permisos as permisos_mod
from app.core.acceso import Acceso, AccesoError, LimiteIntentos
from app.core.migracion_maquinas import NOMBRE, migrar
from app.core.permisos import RegistroPermisos

CONTRASENA = "prueba-temporal-123"


class Reloj:
    def __init__(self) -> None:
        self.t = datetime(2026, 10, 10, 18, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.t

    def avanzar(self, **kw: float) -> None:
        self.t += timedelta(**kw)


# -- Acceso (unit) ---------------------------------------------------------------------


@pytest.fixture
def reloj() -> Reloj:
    return Reloj()


@pytest.fixture
def acceso(tmp_path: Path, reloj: Reloj) -> Acceso:
    return Acceso(tmp_path / "acceso.db", secreto="secreto-de-prueba", clock=reloj)


def test_contrasena_con_argon2_y_minimo(acceso: Acceso) -> None:
    assert not acceso.hay_contrasena()
    assert not acceso.verificar_contrasena(CONTRASENA)
    with pytest.raises(AccesoError):
        acceso.fijar_contrasena("corta")
    acceso.fijar_contrasena(CONTRASENA)
    assert acceso.verificar_contrasena(CONTRASENA)
    assert not acceso.verificar_contrasena(CONTRASENA + "x")
    with closing(sqlite3.connect(acceso.ruta)) as db:
        h = db.execute("SELECT hash FROM usuario").fetchone()[0]
    assert h.startswith("$argon2") and CONTRASENA not in h


def test_sesiones_web_y_app(acceso: Acceso, reloj: Reloj) -> None:
    acceso.fijar_contrasena(CONTRASENA)
    web, s = acceso.crear_sesion("web", "Chrome en la PC", "127.0.0.1")
    app, _ = acceso.crear_sesion("app", "iPhone", "100.1.2.3")
    assert web.startswith("vas_") and app.startswith("vap_")
    assert acceso.validar_sesion(web, tipo="web").id == s.id  # type: ignore[union-attr]
    assert acceso.validar_sesion(web, tipo="app") is None  # a cookie is not an app token
    assert acceso.validar_sesion(app, tipo="app") is not None
    # only hashes are stored
    with closing(sqlite3.connect(acceso.ruta)) as db:
        guardado = " ".join(r[0] for r in db.execute("SELECT hash FROM sesiones"))
    assert web not in guardado and app not in guardado
    # 30 days for the web, 365 for the app
    reloj.avanzar(days=31)
    assert acceso.validar_sesion(web) is None
    assert acceso.validar_sesion(app) is not None
    # revoke
    assert acceso.revocar_sesion(acceso.sesiones_activas()[0].id)
    assert acceso.validar_sesion(app) is None


def test_cambiar_la_contrasena_cierra_todo(acceso: Acceso) -> None:
    acceso.fijar_contrasena(CONTRASENA)
    web, _ = acceso.crear_sesion("web", None, None)
    acceso.fijar_contrasena(CONTRASENA + "-nueva")
    assert acceso.validar_sesion(web) is None


def test_otro_secreto_invalida_los_tokens(tmp_path: Path) -> None:
    a = Acceso(tmp_path / "a.db", secreto="uno")
    token, _ = a.crear_sesion("web", None, None)
    assert Acceso(tmp_path / "a.db", secreto="dos").validar_sesion(token) is None


def test_maquinas_y_tokens(acceso: Acceso) -> None:
    acceso.registrar_maquina("alienware", "Alienware", "windows", "BPRGRAMUTUIO")
    with pytest.raises(AccesoError):
        acceso.registrar_maquina("Con Espacios", "x", "windows")
    with pytest.raises(AccesoError):
        acceso.registrar_maquina("mac-mini", "Mac", "beos")
    with pytest.raises(AccesoError):
        acceso.crear_token_maquina("no-existe")
    token, id_ = acceso.crear_token_maquina("alienware")
    assert token.startswith("vam_")
    assert acceso.validar_token_maquina(token) == "alienware"
    assert acceso.validar_token_maquina("vam_inventado") is None
    assert acceso.validar_sesion(token) is None  # a machine token is not a session
    with closing(sqlite3.connect(acceso.ruta)) as db:
        assert token not in db.execute("SELECT hash FROM tokens_maquina").fetchone()[0]
    m = acceso.latido_maquina("alienware", "1.2.0", None)
    assert m is not None and m["version_monitor"] == "1.2.0" and m["ultima_conexion"]
    assert m["hostname"] == "BPRGRAMUTUIO"
    assert acceso.revocar_token_maquina(id_)
    assert acceso.validar_token_maquina(token) is None


def test_limite_de_intentos_progresivo(reloj: Reloj) -> None:
    lim = LimiteIntentos(clock=reloj)
    for _ in range(4):
        assert lim.fallo("1.2.3.4") == 0
    assert lim.fallo("1.2.3.4") == 5
    assert lim.espera("1.2.3.4") == 5
    assert lim.espera("5.6.7.8") == 0  # per IP
    assert lim.fallo("1.2.3.4") == 10
    assert lim.fallo("1.2.3.4") == 20
    reloj.avanzar(seconds=20)
    assert lim.espera("1.2.3.4") == 0
    for _ in range(20):
        lim.fallo("1.2.3.4")
    assert lim.espera("1.2.3.4") == 900  # at most 15 min
    lim.exito("1.2.3.4")
    assert lim.espera("1.2.3.4") == 0


# -- migration ----------------------------------------------------------------------------


def _bases_viejas(d: Path) -> dict[str, Path]:
    ev = d / "agent_events.db"
    with closing(sqlite3.connect(ev)) as db, db:
        db.execute(
            "CREATE TABLE events (id INTEGER PRIMARY KEY, session_id TEXT, event_type TEXT, "
            "event_ts TEXT, received_ts TEXT, origin TEXT, payload TEXT)"
        )
        db.executemany(
            "INSERT INTO events (session_id, event_type, event_ts, received_ts, origin, payload) "
            "VALUES (?, 'stop', 't', 't', 'hook', '{}')",
            [("s1",), ("s2",)],
        )
    vis = d / "visualizer.db"
    with closing(sqlite3.connect(vis)) as db, db:
        db.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY)")
        db.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, session_id TEXT)")
        db.execute("INSERT INTO sessions VALUES ('s1')")
        db.execute("INSERT INTO events (session_id) VALUES ('s1')")
    RegistroPermisos(d).crear("solicitud-1", "s1", "Bash", {"command": "ls"}, None, None)
    return {
        "agent_events": ev,
        "visualizer": vis,
        "permisos": d / "permisos.db",
        "no_existe": d / "nada.db",
    }


def test_migracion_con_respaldo_e_idempotente(tmp_path: Path, acceso: Acceso) -> None:
    bases = _bases_viejas(tmp_path)
    respaldos = tmp_path / "respaldos"
    r = migrar(acceso, bases, respaldos, "alienware", "Alienware", "windows", "BPRGRAMUTUIO")
    assert r["aplicada"] is True
    carpeta = Path(r["carpeta"])
    assert sorted(p.name for p in carpeta.iterdir()) == [
        "agent_events.db",
        "permisos.db",
        "visualizer.db",
    ]
    # the backup is the data before the migration
    with closing(sqlite3.connect(carpeta / "agent_events.db")) as db:
        cols = {c[1] for c in db.execute("PRAGMA table_info(events)")}
        assert "machine_id" not in cols
        assert db.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 2
    for ruta, tabla in [
        (bases["agent_events"], "events"),
        (bases["visualizer"], "sessions"),
        (bases["visualizer"], "events"),
        (bases["permisos"], "permisos"),
    ]:
        with closing(sqlite3.connect(ruta)) as db:
            valores = {v[0] for v in db.execute(f"SELECT machine_id FROM {tabla}")}
        assert valores == {"alienware"}, (ruta, tabla)
    m = acceso.maquina("alienware")
    assert m is not None and (m["nombre"], m["sistema"], m["hostname"]) == (
        "Alienware",
        "windows",
        "BPRGRAMUTUIO",
    )
    assert acceso.migracion_aplicada(NOMBRE)
    # a second run does nothing (no new backup)
    r2 = migrar(acceso, bases, respaldos, "alienware", "Alienware", "windows", "BPRGRAMUTUIO")
    assert r2["aplicada"] is False
    assert len(list(respaldos.iterdir())) == 1


def test_migracion_sin_bases_registra_la_maquina(tmp_path: Path, acceso: Acceso) -> None:
    r = migrar(acceso, {}, tmp_path / "r", "alienware", "Alienware", "windows")
    assert r["aplicada"] is True
    assert acceso.maquina("alienware") is not None


# -- HTTP: both modes ----------------------------------------------------------------------


class MotorFalso:
    def __init__(self) -> None:
        self.eventos: list[Any] = []
        self.duenas: dict[str, str] = {}
        self.ids: set[str] = set()
        self.observaciones: list[tuple[str, dict[str, Any]]] = []

    def maquina_de(self, session_id: str) -> str | None:
        return self.duenas.get(session_id)

    def snapshot(self) -> dict[str, Any]:
        return {"generado": "x", "presencia": {}, "agentes": []}

    def accept(self, event: Any, origin: str = "hook") -> None:
        self.eventos.append(event)
        self.duenas.setdefault(event.session_id, event.machine_id)

    def dispositivos_vigentes(self) -> tuple[bool, bool]:
        return False, True

    def ya_recibido(self, evento_id: str | None) -> bool:
        return evento_id in self.ids

    def marcar_recibido(self, evento_id: str | None) -> None:
        if evento_id:
            self.ids.add(evento_id)

    def observar(self, machine_id: str, obs: dict[str, Any]) -> bool:
        if self.duenas.get(obs["session_id"]) != machine_id:
            return False
        self.observaciones.append((machine_id, obs))
        return True


class ProcesadorFalso:
    async def process_event(self, event: Any) -> None:
        return None


@pytest.fixture
def entorno(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reloj: Reloj):
    acc = Acceso(tmp_path / "acceso.db", secreto="s", clock=reloj)
    acc.fijar_contrasena(CONTRASENA)
    acc.registrar_maquina("alienware", "Alienware", "windows", "BPRGRAMUTUIO")
    acc.registrar_maquina("tower", "Tower", "windows", "TOWER")
    acceso_mod.set_acceso(acc)
    acceso_mod.set_limite(LimiteIntentos())
    motor = MotorFalso()
    reg = RegistroPermisos(tmp_path, presencia=motor.dispositivos_vigentes)
    permisos_mod.set_registro(reg)
    monkeypatch.setattr(agents_state, "get_state_engine", lambda: motor)
    monkeypatch.setattr(events, "get_state_engine", lambda: motor)
    monkeypatch.setattr(events, "get_registro", lambda: reg)

    app = FastAPI()
    app.add_middleware(AccesoMiddleware)
    app.add_middleware(LocalhostOnlyMiddleware)
    api = get_settings().API_V1_STR
    app.include_router(rutas_acceso.router, prefix=api)
    app.include_router(agents_state.router, prefix=api)
    app.include_router(rutas_permisos.router, prefix=api)
    app.include_router(events.router, prefix=api)
    app.dependency_overrides[events.get_event_processor] = lambda: ProcesadorFalso()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # a page of the frontend served by the backend (no data)
    @app.get("/entrar")
    async def pagina_entrar() -> dict[str, str]:
        return {"pagina": "entrar"}

    @app.get("/_next/static/app.js")
    async def estatico() -> dict[str, str]:
        return {"js": "x"}

    @app.websocket("/ws/prueba")
    async def ws_prueba(websocket: WebSocket) -> None:
        if not ws_autorizado(websocket):
            await websocket.close(code=4401)
            return
        await websocket.accept()
        await websocket.send_text("hola")
        await websocket.close()

    events.reset_rate_limiter()
    yield app, acc, motor, reg
    acceso_mod.set_acceso(None)
    permisos_mod.set_registro(None)


@pytest.fixture
def activado(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "VISUALIZADOR_AUTH", "activado")


@pytest.fixture
def desactivado(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "VISUALIZADOR_AUTH", "desactivado")


API = "/api/v1"
EVENTO = {
    "event_type": "stop",
    "session_id": "prueba-maquinas",
    "data": {},
    "machine_id": "otra-falsa",
}
SOLICITUD = {
    "id": "solicitud-maq-1",
    "session_id": "prueba-maquinas",
    "herramienta": "Bash",
    "entrada": {"command": "git status"},
}


def entrar(c: TestClient, contrasena: str = CONTRASENA):
    return c.post(
        f"{API}/auth/entrar",
        json={"contrasena": contrasena, "dispositivo": "pruebas"},
        headers={"X-Visualizador": "1"},
    )


def test_desactivado_todo_funciona_como_hoy(entorno, desactivado) -> None:  # type: ignore[no-untyped-def]
    app, acc, motor, reg = entorno
    c = TestClient(app)
    assert c.get(f"{API}/auth/estado").json() == {
        "modo": "desactivado",
        "sesion": False,
        "expira": None,
    }
    assert c.get(f"{API}/agents/state").status_code == 200
    # hook without token: the event gets the local machine (a client value is replaced)
    assert c.post(f"{API}/events", json=EVENTO).status_code == 200
    assert motor.eventos[-1].machine_id == "alienware"
    r = c.post(f"{API}/permisos/solicitudes", json=SOLICITUD)
    assert r.status_code == 200 and r.json()["maquina"] == "alienware"
    assert c.put(f"{API}/permisos/config", json={"politica": "siempre"}).status_code == 200
    assert c.post(f"{API}/maquinas/latido", json={"version_monitor": "x"}).status_code == 200
    # sign-in is off in this mode
    assert entrar(c).status_code == 409


def test_desactivado_con_token_de_maquina_usa_esa_maquina(entorno, desactivado) -> None:  # type: ignore[no-untyped-def]
    app, acc, motor, _ = entorno
    token, _ = acc.crear_token_maquina("tower")
    c = TestClient(app)
    c.post(f"{API}/events", json=EVENTO, headers={"Authorization": f"Bearer {token}"})
    assert motor.eventos[-1].machine_id == "tower"


def test_activado_sin_sesion_solo_lo_publico(entorno, activado) -> None:  # type: ignore[no-untyped-def]
    app, *_ = entorno
    c = TestClient(app)
    assert c.get("/health").status_code == 200
    assert c.get(f"{API}/auth/estado").json()["modo"] == "activado"
    assert c.get(f"{API}/agents/state").status_code == 401
    assert c.get(f"{API}/permisos/config").status_code == 401
    assert c.get(f"{API}/maquinas").status_code == 401
    # ingest without a machine token
    assert c.post(f"{API}/events", json=EVENTO).status_code == 401
    assert c.post(f"{API}/permisos/solicitudes", json=SOLICITUD).status_code == 401


def test_activado_entrar_cookie_y_salir(entorno, activado) -> None:  # type: ignore[no-untyped-def]
    app, acc, *_ = entorno
    c = TestClient(app)
    r = entrar(c)
    assert r.status_code == 200
    cookie = r.headers["set-cookie"]
    assert COOKIE_SESION in cookie
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert "Max-Age=2592000" in cookie  # 30 days
    assert "Secure" not in cookie  # plain http, COOKIE_SEGURA=auto
    assert c.get(f"{API}/agents/state").status_code == 200
    estado = c.get(f"{API}/auth/estado").json()
    assert estado["sesion"] is True and estado["expira"]
    lista = c.get(f"{API}/auth/sesiones").json()
    assert len(lista) == 1 and lista[0]["actual"] is True
    assert c.post(f"{API}/auth/salir", headers={"X-Visualizador": "1"}).status_code == 200
    assert c.get(f"{API}/agents/state").status_code == 401
    assert acc.sesiones_activas() == []


def test_cookie_segura_con_https(entorno, activado) -> None:  # type: ignore[no-untyped-def]
    app, *_ = entorno
    c = TestClient(app, base_url="https://testserver")
    assert "Secure" in entrar(c).headers["set-cookie"]


def test_cookie_segura_detras_de_nginx(entorno, activado, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    app, *_ = entorno
    monkeypatch.setattr(get_settings(), "CONFIAR_PROXY", True)
    c = TestClient(app)
    r = c.post(
        f"{API}/auth/entrar",
        json={"contrasena": CONTRASENA},
        headers={"X-Visualizador": "1", "X-Forwarded-Proto": "https"},
    )
    assert "Secure" in r.headers["set-cookie"]


def test_activado_contrasena_incorrecta_y_limite(entorno, activado) -> None:  # type: ignore[no-untyped-def]
    app, *_ = entorno
    c = TestClient(app)
    for _ in range(4):
        r = entrar(c, "incorrecta-123")
        assert r.status_code == 401
        assert r.json()["detail"]["mensaje"] == "Contraseña incorrecta."
    r = entrar(c, "incorrecta-123")
    assert r.status_code == 401 and r.json()["detail"]["segundos"] >= 5
    # now even the right password waits
    r = entrar(c)
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) >= 1
    assert "Demasiados intentos" in r.json()["detail"]["mensaje"]


def test_limite_por_ip_detras_de_nginx(entorno, activado, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    app, *_ = entorno
    monkeypatch.setattr(get_settings(), "CONFIAR_PROXY", True)
    c = TestClient(app)
    for _ in range(5):
        c.post(
            f"{API}/auth/entrar",
            json={"contrasena": "incorrecta-123"},
            headers={"X-Visualizador": "1", "X-Forwarded-For": "203.0.113.9"},
        )
    otra = c.post(
        f"{API}/auth/entrar",
        json={"contrasena": CONTRASENA},
        headers={"X-Visualizador": "1", "X-Forwarded-For": "198.51.100.7"},
    )
    assert otra.status_code == 200


def test_activado_csrf_con_cookie(entorno, activado) -> None:  # type: ignore[no-untyped-def]
    app, _, _, reg = entorno
    c = TestClient(app)
    entrar(c)
    cfg = {"politica": "siempre", "espera_seg": 60, "confirmar": ["rm"]}
    r = c.put(f"{API}/permisos/config", json=cfg)
    assert r.status_code == 403 and "CSRF" in r.json()["detail"]
    assert (
        c.put(f"{API}/permisos/config", json=cfg, headers={"X-Visualizador": "1"}).status_code
        == 200
    )
    # a decision too
    reg.crear("solicitud-x", "s", "Bash", {"command": "ls"}, None, None, machine_id="alienware")
    url = f"{API}/permisos/solicitudes/solicitud-x/decision"
    assert c.post(url, json={"decision": "aprobar"}).status_code == 403
    assert (
        c.post(url, json={"decision": "aprobar"}, headers={"X-Visualizador": "1"}).status_code
        == 200
    )
    # reading needs no header
    assert c.get(f"{API}/permisos/config").status_code == 200


def test_token_de_maquina_solo_ingesta(entorno, activado) -> None:  # type: ignore[no-untyped-def]
    app, acc, motor, reg = entorno
    token, _ = acc.crear_token_maquina("tower")
    h = {"Authorization": f"Bearer {token}"}
    c = TestClient(app)
    # ingest: events get the machine of the token, never the one the client sends
    assert c.post(f"{API}/events", json=EVENTO, headers=h).status_code == 200
    assert motor.eventos[-1].machine_id == "tower"
    r = c.post(f"{API}/permisos/solicitudes", json=SOLICITUD, headers=h)
    assert r.status_code == 200 and r.json()["maquina"] == "tower"
    assert c.get(f"{API}/permisos/solicitudes/solicitud-maq-1", headers=h).status_code == 200
    r = c.post(f"{API}/maquinas/latido", json={"version_monitor": "0.1.0"}, headers=h)
    assert r.status_code == 200 and r.json()["id"] == "tower"
    # never read the state, decide permissions or change settings
    assert c.get(f"{API}/agents/state", headers=h).status_code == 403
    assert (
        c.post(
            f"{API}/permisos/solicitudes/solicitud-maq-1/decision",
            json={"decision": "aprobar"},
            headers=h,
        ).status_code
        == 403
    )
    assert c.put(f"{API}/permisos/config", json={}, headers=h).status_code == 403
    assert c.get(f"{API}/permisos/historial", headers=h).status_code == 403
    assert c.get(f"{API}/maquinas", headers=h).status_code == 403
    assert c.get(f"{API}/auth/sesiones", headers=h).status_code == 403


def test_una_maquina_no_ve_las_solicitudes_de_otra(entorno, activado) -> None:  # type: ignore[no-untyped-def]
    app, acc, *_ = entorno
    tower, _ = acc.crear_token_maquina("tower")
    alien, _ = acc.crear_token_maquina("alienware")
    c = TestClient(app)
    c.post(
        f"{API}/permisos/solicitudes", json=SOLICITUD, headers={"Authorization": f"Bearer {tower}"}
    )
    otra = {"Authorization": f"Bearer {alien}"}
    assert c.get(f"{API}/permisos/solicitudes/solicitud-maq-1", headers=otra).status_code == 404
    assert c.post(f"{API}/permisos/solicitudes", json=SOLICITUD, headers=otra).status_code == 409


def test_token_revocado_ya_no_entra(entorno, activado) -> None:  # type: ignore[no-untyped-def]
    app, acc, *_ = entorno
    token, id_ = acc.crear_token_maquina("tower")
    acc.revocar_token_maquina(id_)
    c = TestClient(app)
    r = c.post(f"{API}/events", json=EVENTO, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_token_de_app_para_el_celular(entorno, activado) -> None:  # type: ignore[no-untyped-def]
    app, acc, *_ = entorno
    c = TestClient(app)
    assert c.post(f"{API}/auth/app/token", json={"contrasena": "mala-12345"}).status_code == 401
    r = c.post(f"{API}/auth/app/token", json={"contrasena": CONTRASENA, "dispositivo": "iPhone"})
    assert r.status_code == 200
    token = r.json()["token"]
    assert token.startswith("vap_") and "set-cookie" not in r.headers
    h = {"Authorization": f"Bearer {token}"}
    nuevo = TestClient(app)  # no cookies
    assert nuevo.get(f"{API}/agents/state", headers=h).status_code == 200
    # no ambient credential: no CSRF header needed
    assert (
        nuevo.put(f"{API}/permisos/config", json={"politica": "nunca"}, headers=h).status_code
        == 200
    )
    # revocable from the session list
    sid = r.json()["sesion"]["id"]
    cookie = TestClient(app)
    entrar(cookie)
    assert (
        cookie.delete(f"{API}/auth/sesiones/{sid}", headers={"X-Visualizador": "1"}).status_code
        == 200
    )
    assert nuevo.get(f"{API}/agents/state", headers=h).status_code == 401


def test_un_token_de_app_no_sirve_como_cookie(entorno, activado) -> None:  # type: ignore[no-untyped-def]
    app, acc, *_ = entorno
    token, _ = acc.crear_sesion("app", None, None)
    c = TestClient(app, cookies={COOKIE_SESION: token})
    assert c.get(f"{API}/agents/state").status_code == 401


def test_websocket_con_y_sin_sesion(entorno, activado) -> None:  # type: ignore[no-untyped-def]
    app, acc, *_ = entorno
    c = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as e, c.websocket_connect("/ws/prueba") as ws:
        ws.receive_text()
    assert e.value.code == 4401
    entrar(c)
    with c.websocket_connect("/ws/prueba") as ws:
        assert ws.receive_text() == "hola"
    app_token, _ = acc.crear_sesion("app", None, None)
    h = {"Authorization": f"Bearer {app_token}"}
    with TestClient(app).websocket_connect("/ws/prueba", headers=h) as ws:
        assert ws.receive_text() == "hola"
    # never in the URL (it would end up in access logs)
    with (
        pytest.raises(WebSocketDisconnect),
        TestClient(app).websocket_connect(f"/ws/prueba?token={app_token}") as ws,
    ):
        ws.receive_text()
    maquina, _ = acc.crear_token_maquina("tower")
    with (
        pytest.raises(WebSocketDisconnect),
        TestClient(app).websocket_connect(
            "/ws/prueba", headers={"Authorization": f"Bearer {maquina}"}
        ) as ws,
    ):
        ws.receive_text()


def test_websocket_desactivado_abierto(entorno, desactivado) -> None:  # type: ignore[no-untyped-def]
    app, *_ = entorno
    with TestClient(app).websocket_connect("/ws/prueba") as ws:
        assert ws.receive_text() == "hola"


def test_rutas_publicas_e_ingesta_son_las_esperadas() -> None:
    assert mw.es_ingesta("POST", "/api/v1/events")
    assert mw.es_ingesta("POST", "/api/v1/maquinas/observaciones")
    assert not mw.es_ingesta("GET", "/api/v1/maquinas/observaciones")
    assert mw.es_ingesta("GET", "/api/v1/permisos/solicitudes/abc-123")
    assert not mw.es_ingesta("POST", "/api/v1/permisos/solicitudes/abc-123/decision")
    assert not mw.es_ingesta("GET", "/api/v1/permisos/historial")
    assert not mw.es_ingesta("GET", "/api/v1/agents/state")
    assert mw.es_publica("POST", "/api/v1/auth/entrar")
    assert not mw.es_publica("GET", "/api/v1/auth/sesiones")


def test_comandos_de_consola(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:  # type: ignore[no-untyped-def]
    from app import acceso_cli

    acc = Acceso(tmp_path / "acceso.db")
    acceso_mod.set_acceso(acc)
    try:
        respuestas = iter([CONTRASENA, CONTRASENA])
        monkeypatch.setattr(acceso_cli.getpass, "getpass", lambda _: next(respuestas))
        assert acceso_cli.main(["contrasena"]) == 0
        assert acc.verificar_contrasena(CONTRASENA)
        assert (
            acceso_cli.main(
                ["maquina-crear", "--id", "tower", "--nombre", "Tower", "--sistema", "windows"]
            )
            == 0
        )
        assert acceso_cli.main(["token-crear", "--maquina", "tower"]) == 0
        salida = capsys.readouterr().out
        token = next(linea for linea in salida.splitlines() if linea.startswith("vam_"))
        assert acc.validar_token_maquina(token) == "tower"
        id_ = acc.tokens_maquina()[0]["id"]
        assert acceso_cli.main(["token-revocar", id_]) == 0
        assert acc.validar_token_maquina(token) is None
        acc.crear_sesion("web", "PC", None)
        assert acceso_cli.main(["sesiones"]) == 0
        assert acceso_cli.main(["sesion-revocar", acc.sesiones_activas()[0].id]) == 0
        assert acc.sesiones_activas() == []
        respuestas = iter(["una-contrasena-1", "otra-contrasena-2"])
        assert acceso_cli.main(["contrasena"]) == 1  # do not match
    finally:
        acceso_mod.set_acceso(None)


# -- fixes of the security review ------------------------------------------------------


def test_ip_real_detras_de_nginx_no_se_puede_falsificar(entorno, activado, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The client controls the first X-Forwarded-For entries; nginx appends the real IP."""
    app, *_ = entorno
    monkeypatch.setattr(get_settings(), "CONFIAR_PROXY", True)
    c = TestClient(app)
    for i in range(5):
        c.post(
            f"{API}/auth/entrar",
            json={"contrasena": "incorrecta-123"},
            headers={"X-Visualizador": "1", "X-Forwarded-For": f"10.0.0.{i}, 203.0.113.9"},
        )
    r = c.post(
        f"{API}/auth/entrar",
        json={"contrasena": CONTRASENA},
        headers={"X-Visualizador": "1", "X-Forwarded-For": "10.9.9.9, 203.0.113.9"},
    )
    assert r.status_code == 429
    # X-Real-IP (set by nginx to $remote_addr) wins
    r = c.post(
        f"{API}/auth/entrar",
        json={"contrasena": CONTRASENA},
        headers={
            "X-Visualizador": "1",
            "X-Real-IP": "198.51.100.7",
            "X-Forwarded-For": "203.0.113.9",
        },
    )
    assert r.status_code == 200


def test_tope_global_de_fallos(reloj: Reloj) -> None:
    lim = LimiteIntentos(clock=reloj)
    for i in range(31):
        lim.fallo(f"10.0.{i}.1")  # many IPs, none blocked on its own
    assert lim.espera("10.0.99.1") == 0
    assert lim.espera_global() == 60
    reloj.avanzar(seconds=61)
    assert lim.espera_global() == 0


def test_tope_global_cierra_la_entrada(entorno, activado) -> None:  # type: ignore[no-untyped-def]
    app, *_ = entorno
    lim = acceso_mod.get_limite()
    for i in range(31):
        lim.fallo(f"10.1.{i}.1")
    r = entrar(TestClient(app))
    assert r.status_code == 429


def test_paginas_del_frontend_publicas_y_la_api_protegida(entorno, activado) -> None:  # type: ignore[no-untyped-def]
    app, *_ = entorno
    c = TestClient(app)
    assert c.get("/entrar").status_code == 200
    assert c.get("/_next/static/app.js").status_code == 200
    assert c.get(f"{API}/agents/state").status_code == 401
    assert c.get(f"{API}").status_code in (401, 404)
    assert c.get("/openapi.json").status_code in (401, 404)


def test_una_maquina_no_puede_tomar_la_sesion_de_otra(entorno, activado) -> None:  # type: ignore[no-untyped-def]
    app, acc, motor, _ = entorno
    tower, _ = acc.crear_token_maquina("tower")
    alien, _ = acc.crear_token_maquina("alienware")
    c = TestClient(app)
    assert (
        c.post(
            f"{API}/events", json=EVENTO, headers={"Authorization": f"Bearer {tower}"}
        ).status_code
        == 200
    )
    r = c.post(f"{API}/events", json=EVENTO, headers={"Authorization": f"Bearer {alien}"})
    assert r.status_code == 409
    assert [e.machine_id for e in motor.eventos] == ["tower"]


def test_cookie_host_con_https_y_salir_la_borra(entorno, activado) -> None:  # type: ignore[no-untyped-def]
    app, acc, *_ = entorno
    c = TestClient(app, base_url="https://testserver")
    r = entrar(c)
    assert "__Host-visualizador_sesion=" in r.headers["set-cookie"]
    assert "Secure" in r.headers["set-cookie"]
    assert c.get(f"{API}/agents/state").status_code == 200
    # sign-out works even with an expired session and always clears the cookie
    acc.revocar_sesion(acc.sesiones_activas()[0].id)
    r = c.post(f"{API}/auth/salir")
    assert r.status_code == 200
    assert "__Host-visualizador_sesion=" in r.headers.get("set-cookie", "")


def test_ingesta_con_salto_de_linea_no_pasa(entorno, activado) -> None:  # type: ignore[no-untyped-def]
    assert not mw.es_ingesta("POST", "/api/v1/events\n")
    assert not mw.es_ingesta("GET", "/api/v1/permisos/solicitudes/abc\n")


def test_activado_exige_secreto() -> None:
    from types import SimpleNamespace

    from app.core.acceso import exigir_secreto

    for malo in ("", "corto", "COMPLETAR"):
        with pytest.raises(RuntimeError):
            exigir_secreto(SimpleNamespace(auth_activa=True, VISUALIZADOR_SECRETO=malo))
    exigir_secreto(SimpleNamespace(auth_activa=True, VISUALIZADOR_SECRETO="x" * 40))
    exigir_secreto(SimpleNamespace(auth_activa=False, VISUALIZADOR_SECRETO=""))


def test_clave_de_la_vista_clasica_no_hace_falta_con_sesion(entorno, activado) -> None:  # type: ignore[no-untyped-def]
    """With sign-in on, the per-launch key of the classic view is not required."""
    from app.api.middleware import ApiKeyMiddleware

    app, *_ = entorno

    @app.delete(f"{API}/sessions")
    async def borrar() -> dict[str, bool]:
        return {"ok": True}

    app.add_middleware(ApiKeyMiddleware)
    c = TestClient(app)
    entrar(c)
    assert c.delete(f"{API}/sessions", headers={"X-Visualizador": "1"}).status_code == 200


def test_reenvio_del_monitor_no_duplica_eventos(entorno, activado) -> None:  # type: ignore[no-untyped-def]
    app, acc, motor, _ = entorno
    token, _ = acc.crear_token_maquina("tower")
    h = {"Authorization": f"Bearer {token}", "X-Evento-Id": "evento-1"}
    c = TestClient(app)
    assert c.post(f"{API}/events", json=EVENTO, headers=h).json()["status"] == "accepted"
    r = c.post(f"{API}/events", json=EVENTO, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "duplicado"
    assert len(motor.eventos) == 1
    # without an id (hooks of today) nothing changes
    sin_id = {"Authorization": f"Bearer {token}"}
    c.post(f"{API}/events", json=EVENTO, headers=sin_id)
    c.post(f"{API}/events", json=EVENTO, headers=sin_id)
    assert len(motor.eventos) == 3


def test_evento_rechazado_no_gasta_su_id(entorno, activado) -> None:  # type: ignore[no-untyped-def]
    app, acc, motor, _ = entorno
    tower, _ = acc.crear_token_maquina("tower")
    alien, _ = acc.crear_token_maquina("alienware")
    c = TestClient(app)
    c.post(f"{API}/events", json=EVENTO, headers={"Authorization": f"Bearer {tower}"})
    h = {"Authorization": f"Bearer {alien}", "X-Evento-Id": "evento-2"}
    assert c.post(f"{API}/events", json=EVENTO, headers=h).status_code == 409
    assert "alienware:evento-2" not in motor.ids and not any("evento-2" in i for i in motor.ids)


def test_observaciones_y_latido_del_monitor(entorno, activado, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.core import agent_state_engine

    app, acc, motor, _ = entorno
    monkeypatch.setattr(agent_state_engine, "get_state_engine", lambda: motor)
    token, _ = acc.crear_token_maquina("tower")
    h = {"Authorization": f"Bearer {token}"}
    c = TestClient(app)
    c.post(f"{API}/events", json=EVENTO, headers=h)
    cuerpo = {
        "sesiones": [
            {"session_id": "prueba-maquinas", "proceso_vivo": True, "contexto_tokens": 10},
            {"session_id": "prueba-ajena", "proceso_vivo": False},
        ]
    }
    r = c.post(f"{API}/maquinas/observaciones", json=cuerpo, headers=h)
    assert r.status_code == 200 and r.json() == {"recibidas": 2, "aplicadas": 1}
    assert motor.observaciones == [
        ("tower", {"session_id": "prueba-maquinas", "proceso_vivo": True, "contexto_tokens": 10})
    ]
    # invalid data is rejected, and a session cookie is not a machine
    malo = {"sesiones": [{"session_id": "x\ny"}]}
    assert c.post(f"{API}/maquinas/observaciones", json=malo, headers=h).status_code == 422
    assert c.post(f"{API}/maquinas/observaciones", json=cuerpo).status_code == 401
    r = c.post(
        f"{API}/maquinas/latido",
        json={"version_monitor": "0.1.0", "hostname": "TOWER", "sistema": "windows"},
        headers=h,
    )
    assert r.status_code == 200
    assert next(m for m in acc.maquinas() if m["id"] == "tower")["sistema"] == "windows"


def test_id_de_evento_por_maquina(entorno, activado) -> None:  # type: ignore[no-untyped-def]
    """The same id sent by another machine is not taken as a resend."""
    app, acc, motor, _ = entorno
    tower, _ = acc.crear_token_maquina("tower")
    alien, _ = acc.crear_token_maquina("alienware")
    c = TestClient(app)
    ev_tower = {**EVENTO, "session_id": "prueba-maq-t"}
    ev_alien = {**EVENTO, "session_id": "prueba-maq-a"}
    h_t = {"Authorization": f"Bearer {tower}", "X-Evento-Id": "mismo-id"}
    h_a = {"Authorization": f"Bearer {alien}", "X-Evento-Id": "mismo-id"}
    assert c.post(f"{API}/events", json=ev_tower, headers=h_t).json()["status"] == "accepted"
    assert c.post(f"{API}/events", json=ev_alien, headers=h_a).json()["status"] == "accepted"
    assert len(motor.eventos) == 2
