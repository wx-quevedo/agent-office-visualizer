"""Equipos de proyectos (etapa 4, Prompt 37): carpeta segura, plantillas, lanzar,
pausar, reanudar y retomar con un `claude` falso."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import pytest

from visualizador_monitor.cliente import Respuesta
from visualizador_monitor.equipos import (
    REANUDADO,
    EquipoError,
    Equipos,
    HiloEncargos,
    Miembro,
    Proyecto,
    carpeta_segura,
    comando_sesion,
    entorno_sesion,
    miembros_de,
    preparar_carpeta,
    validar_nombre,
)

FALSO = [sys.executable, str(Path(__file__).with_name("claude_falso.py"))]


def _equipo() -> list[dict[str, str]]:
    return [
        {
            "rol": "orquestador",
            "nombre": "orquestador",
            "modelo": "haiku",
            "esfuerzo": "low",
            "session_id": str(uuid.uuid4()),
        },
        {
            "rol": "agente",
            "nombre": "agente",
            "modelo": "haiku",
            "esfuerzo": "low",
            "session_id": str(uuid.uuid4()),
        },
    ]


def _encargo(tipo: str = "crear", nombre: str = "prueba-37", **extra: Any) -> dict[str, Any]:
    return {
        "id": uuid.uuid4().hex,
        "tipo": tipo,
        "proyecto_id": extra.pop("proyecto_id", "a" * 32),
        "nombre": nombre,
        "cuenta": "personal",
        "plantilla": "vacia",
        "equipo": _equipo(),
        **extra,
    }


# -- carpeta ------------------------------------------------------------------------------


def test_carpeta_segura(tmp_path: Path) -> None:
    base = tmp_path / "Agents"
    c = carpeta_segura(base, "prueba-37")
    assert c == base.resolve() / "prueba-37" and base.is_dir()
    (base / "existe").mkdir()
    with pytest.raises(EquipoError, match="Ya existe"):
        carpeta_segura(base, "existe")
    for malo in ("..", "../fuera", "a/b", "a\\b", "C:", "Con-Mayus", "con", "x.y", ""):
        with pytest.raises(EquipoError):
            carpeta_segura(base, malo)
    with pytest.raises(EquipoError, match="absoluta"):
        carpeta_segura(Path("relativa"), "x")
    with pytest.raises(EquipoError, match="red"):
        carpeta_segura(Path("\\\\servidor\\c"), "x")


def test_ruta_fuera_de_la_base_por_un_enlace(tmp_path: Path) -> None:
    """Si la ruta base es un enlace, cuenta la ruta real; una carpeta que por un enlace
    quedaría fuera de la base real se rechaza."""
    real = tmp_path / "real"
    real.mkdir()
    enlace = tmp_path / "enlace"
    try:
        enlace.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("Esta máquina no permite crear enlaces simbólicos sin privilegios")
    c = carpeta_segura(enlace, "dentro")
    assert c.parent == real.resolve()
    afuera = tmp_path / "afuera"
    afuera.mkdir()
    (real / "escapa").symlink_to(afuera, target_is_directory=True)
    with pytest.raises(EquipoError):
        carpeta_segura(enlace, "escapa")


@pytest.mark.parametrize(
    ("plantilla", "linea", "ignora"),
    [
        ("vacia", None, None),
        ("web", "Plantilla: Web", "node_modules/"),
        ("unity", "Plantilla: Unity", "[Ll]ibrary/"),
        ("expo", "Plantilla: App Expo", ".expo/"),
    ],
)
def test_preparar_carpeta(
    tmp_path: Path, plantilla: str, linea: str | None, ignora: str | None
) -> None:
    gits: list[Path] = []
    c = tmp_path / "p"
    preparar_carpeta(c, "p", plantilla, "2026-10-12", gits.append)
    assert gits == [c]
    md = (c / "PROJECT.md").read_text(encoding="utf-8")
    assert md.startswith("# p\n") and "2026-10-12" in md
    if linea is None:
        assert not (c / ".gitignore").exists() and "Plantilla" not in md
    else:
        assert ignora is not None
        assert linea in md and ignora in (c / ".gitignore").read_text(encoding="utf-8")
    with pytest.raises(EquipoError):
        preparar_carpeta(tmp_path / "q", "q", "django", "x", gits.append)


def test_git_init_real(tmp_path: Path) -> None:
    from visualizador_monitor.equipos import git_init

    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("Sin git")
    git_init(tmp_path)
    assert (tmp_path / ".git").is_dir()


# -- sesiones -------------------------------------------------------------------------------


def test_comando_y_entorno() -> None:
    p = Proyecto("a" * 32, "prueba-37", "E:\\Agents\\prueba-37", "personal")
    orq = Miembro("orquestador", "orquestador", "opus", "high", str(uuid.uuid4()))
    ag = Miembro("agente", "agente", "sonnet", "medium", str(uuid.uuid4()))
    c = comando_sesion(["claude.exe"], p, orq, False)
    assert c[:2] == ["claude.exe", "-p"]
    for par in (
        ("--input-format", "stream-json"),
        ("--output-format", "stream-json"),
        ("--model", "opus"),
        ("--effort", "high"),
        ("--session-id", orq.session_id),
        ("--disallowedTools", "SendMessage,ListAgents"),
        ("--name", "prueba-37-orquestador"),
    ):
        assert c[c.index(par[0]) + 1] == par[1]
    assert "todavía no das órdenes" in c[c.index("--append-system-prompt") + 1].lower()
    assert "--settings" not in c and "--resume" not in c
    a = comando_sesion(["claude.exe"], p, ag, True)
    assert a[a.index("--resume") + 1] == ag.session_id and "--session-id" not in a
    assert json.loads(a[a.index("--settings") + 1]) == {"crossSessionInbound": "accept"}
    assert "--disallowedTools" not in a
    assert "esperas las órdenes" in a[a.index("--append-system-prompt") + 1].lower()
    home = Path("C:/Users/w")
    base = {
        "PATH": "x",
        "CLAUDECODE": "1",
        "CLAUDE_CODE_CHILD_SESSION": "1",
        "CLAUDE_CONFIG_DIR": "otra",
        "ANTHROPIC_API_KEY": "k",
    }
    personal = entorno_sesion(home / ".claude", base, home)
    assert personal == {"PATH": "x"}
    assert entorno_sesion(home / ".claude-demo", base, home)["CLAUDE_CONFIG_DIR"] == str(
        home / ".claude-demo"
    )


def test_miembros_de_valida() -> None:
    assert [m.rol for m in miembros_de(_equipo())] == ["orquestador", "agente"]
    for malo in (
        [],
        None,
        [{"rol": "jefe"}],
        [{**_equipo()[0], "session_id": "x"}],
        [{**_equipo()[0], "modelo": "a b; rm"}],
        [{**_equipo()[0], "esfuerzo": "turbo"}],
    ):
        with pytest.raises(EquipoError):
            miembros_de(malo)
    assert validar_nombre("ok") == "ok"


# -- gestor con un claude falso ---------------------------------------------------------------


def _eventos(registro: Path) -> list[dict[str, Any]]:
    if not registro.is_file():
        return []
    return [json.loads(x) for x in registro.read_text(encoding="utf-8").splitlines() if x.strip()]


def _esperar(cond: Any, s: float = 10.0) -> bool:
    fin = time.monotonic() + s
    while time.monotonic() < fin:
        if cond():
            return True
        time.sleep(0.05)
    return bool(cond())


def _gestor(tmp_path: Path, registro: Path, **extra: Any) -> Equipos:
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True, exist_ok=True)
    (home / ".claude-demo").mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("CLAUDE", "ANTHROPIC"))}
    env["FALSO_REGISTRO"] = str(registro)
    env.update(extra.pop("env", {}))
    return Equipos(
        tmp_path / "monitor",
        tmp_path / "Agents",
        [str(home / ".claude"), str(home / ".claude-demo")],
        claude=FALSO,
        entorno_base=env,
        home=home,
        git=lambda c: None,
        arranque=extra.pop("arranque", 1.0),
        espera_cierre=5.0,
    )


def test_crear_pausar_reanudar_y_retomar(tmp_path: Path) -> None:
    registro = tmp_path / "registro.jsonl"
    g = _gestor(tmp_path, registro)
    # Un proceso ajeno que no se debe tocar nunca.
    ajeno = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        enc = _encargo(cuenta="demo")
        r = g.procesar(enc)
        assert r["ok"], r
        assert r["miembros"] == [
            {"nombre": "orquestador", "estado": "activo"},
            {"nombre": "agente", "estado": "activo"},
        ]
        carpeta = tmp_path / "Agents" / "prueba-37"
        assert (carpeta / "PROJECT.md").is_file()
        # Las dos sesiones arrancaron en la carpeta, con la cuenta Demo Org y su saludo.
        assert _esperar(lambda: sum(e["evento"] == "mensaje" for e in _eventos(registro)) == 2)
        inicios = [e for e in _eventos(registro) if e["evento"] == "inicio"]
        assert {Path(e["cwd"]).resolve() for e in inicios} == {carpeta.resolve()}
        assert all(e["config"] and e["config"].endswith(".claude-demo") for e in inicios)
        sids = {e["args"][e["args"].index("--session-id") + 1] for e in inicios}
        assert sids == {m["session_id"] for m in enc["equipo"]}
        # Reentrega del mismo encargo: no duplica nada.
        assert g.procesar(enc)["ok"]
        assert len([e for e in _eventos(registro) if e["evento"] == "inicio"]) == 2
        # Pausar: las sesiones terminan solas al cerrar su entrada.
        r = g.procesar(_encargo("pausar"))
        assert r["ok"] and {m["estado"] for m in r["miembros"]} == {"pausado"}
        assert len([e for e in _eventos(registro) if e["evento"] == "fin"]) == 2
        assert ajeno.poll() is None
        # Reanudar: con --resume y el mensaje de reanudación.
        r = g.procesar(_encargo("reanudar"))
        assert r["ok"] and {m["estado"] for m in r["miembros"]} == {"activo"}
        reanudados = [e for e in _eventos(registro) if e["evento"] == "inicio"][2:]
        assert {e["args"][e["args"].index("--resume") + 1] for e in reanudados} == sids
        assert _esperar(
            lambda: (
                sum(
                    e.get("texto") == REANUDADO.format(nombre="prueba-37")
                    for e in _eventos(registro)
                )
                == 2
            )
        )
        # El monitor se reinicia: otro gestor con el mismo estado retoma el equipo activo.
        g.detener_todo()
        g2 = _gestor(tmp_path, registro)
        mensajes_antes = sum(e["evento"] == "mensaje" for e in _eventos(registro))
        assert g2.retomar() == 1
        assert {m["estado"] for m in g2.estado_equipos()[0]["miembros"]} == {"activo"}
        retomados = [e for e in _eventos(registro) if e["evento"] == "inicio"][4:]
        assert len(retomados) == 2 and all("--resume" in e["args"] for e in retomados)
        # Al retomar tras un reinicio no se manda saludo: quedan "En espera".
        time.sleep(0.5)
        assert sum(e["evento"] == "mensaje" for e in _eventos(registro)) == mensajes_antes
        g2.detener_todo()
        assert ajeno.poll() is None
    finally:
        ajeno.kill()


def test_errores_de_encargos(tmp_path: Path) -> None:
    registro = tmp_path / "registro.jsonl"
    g = _gestor(tmp_path, registro)
    (tmp_path / "Agents").mkdir()
    (tmp_path / "Agents" / "existe").mkdir()
    r = g.procesar(_encargo(nombre="existe"))
    assert not r["ok"] and "Ya existe" in r["error"]
    assert not g.procesar(_encargo(nombre="../fuera"))["ok"]
    assert not g.procesar(_encargo(tipo="pausar", proyecto_id="b" * 32))["ok"]
    assert not g.procesar(_encargo(tipo="borrar"))["ok"]
    assert not g.procesar(_encargo(cuenta="otra"))["ok"]
    # Una sesión que no arranca: el encargo falla con el nombre de quién no arrancó.
    g2 = _gestor(tmp_path / "otro", registro, env={"FALSO_CAER": "1"})
    r = g2.procesar(_encargo(proyecto_id="c" * 32))
    assert not r["ok"] and "No arrancó" in r["error"]
    assert {m["estado"] for m in r["miembros"]} == {"detenido"}


class ServidorFalso:
    def __init__(self, encargos: list[dict[str, Any]]) -> None:
        self.encargos = encargos
        self.posts: list[tuple[str, dict[str, Any]]] = []

    def pedir(
        self,
        metodo: str,
        ruta: str,
        cuerpo: bytes | None = None,
        timeout: float = 5.0,
        cabeceras: Any = None,
    ) -> Respuesta:
        assert (metodo, ruta) == ("GET", "/api/v1/maquinas/encargos")
        encargos, self.encargos = self.encargos, []
        return Respuesta(200, {"encargos": encargos})

    def post_json(self, ruta: str, datos: dict[str, Any], timeout: float = 5.0) -> Respuesta:
        self.posts.append((ruta, datos))
        return Respuesta(200, {})


def test_hilo_de_encargos(tmp_path: Path) -> None:
    registro = tmp_path / "registro.jsonl"
    g = _gestor(tmp_path, registro)
    enc = _encargo()
    falso = ServidorFalso([enc])
    hilo = HiloEncargos(falso, g)  # type: ignore[arg-type]
    try:
        assert hilo.ronda() == 1
        rutas = [r for r, _ in falso.posts]
        assert rutas == [f"/api/v1/maquinas/encargos/{enc['id']}", "/api/v1/maquinas/equipos"]
        assert falso.posts[0][1]["ok"] is True
        assert falso.posts[1][1]["equipos"][0]["proyecto_id"] == "a" * 32
        assert hilo.ronda() == 0  # sin encargos nuevos y antes del próximo informe
    finally:
        g.detener_todo()
