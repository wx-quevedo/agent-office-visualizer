"""Reglas de la casa, comandos seguros y entrevista inicial (etapa 4, Prompt 39), con un
`claude` falso: el bloque de CLAUDE.md sin tocar lo demás, reglas apagadas por proyecto,
aviso a las sesiones vivas, plantillas y comandos seguros."""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

import pytest
from test_equipos import _encargo, _eventos, _gestor
from test_ordenes import Servidor, _girar, _mensajes, _sids

from visualizador_monitor.equipos import (
    FIN_REGLAS,
    INICIO_REGLAS,
    EquipoError,
    Equipos,
    con_bloque,
    escribir_reglas,
)

PID = "c" * 32
REGLAS = ["Escribir en español latino neutro.", "Sin emojis.", "Tema claro por defecto."]
COMANDOS = ["git status", "npm test"]


def test_bloque_sin_tocar_lo_demas() -> None:
    propio = "# Mi proyecto\n\nNotas mías que el monitor no toca.\n"
    con = con_bloque(propio, ["Una."])
    assert con.startswith(propio) and "- Una." in con
    assert con.count(INICIO_REGLAS) == 1 and con.count(FIN_REGLAS) == 1
    # Lo de después del bloque también se conserva al actualizarlo.
    con += "\n## Más notas\n\nDespués del bloque.\n"
    nuevo = con_bloque(con, ["Dos.", "Tres."])
    assert nuevo.startswith(propio) and nuevo.endswith("Después del bloque.\n")
    assert "- Una." not in nuevo and "- Dos.\n- Tres." in nuevo
    assert con_bloque(nuevo, ["Dos.", "Tres."]) == nuevo  # sin cambios, igual
    assert "(Ninguna regla activa" in con_bloque(nuevo, [])
    # Con una marca rota (sin fin), no se borra nada: se agrega un bloque al final.
    roto = f"# x\n\n{INICIO_REGLAS}\n- vieja\n"
    assert con_bloque(roto, ["Nueva."]).startswith(roto.rstrip("\n"))


def test_no_escribe_por_un_enlace(tmp_path: Path) -> None:
    carpeta = tmp_path / "p"
    carpeta.mkdir()
    afuera = tmp_path / "afuera.md"
    afuera.write_text("no tocar\n", encoding="utf-8")
    try:
        (carpeta / "CLAUDE.md").symlink_to(afuera)
    except OSError:
        pytest.skip("Esta máquina no permite crear enlaces simbólicos sin privilegios")
    with pytest.raises(EquipoError):
        escribir_reglas(carpeta, ["x"])
    assert afuera.read_text(encoding="utf-8") == "no tocar\n"


def _crear(tmp_path: Path, **extra: Any) -> tuple[Equipos, Servidor, Path, dict[str, Any]]:
    registro = tmp_path / "registro.jsonl"
    g = _gestor(tmp_path, registro)
    enc = _encargo(
        proyecto_id=PID,
        nombre="prueba-39",
        plantilla="web",
        reglas=REGLAS,
        comandos=COMANDOS,
        autoskills=extra.pop("autoskills", False),
    )
    assert g.procesar(enc)["ok"]
    srv = Servidor()
    assert _girar(g, srv, lambda: not any(s.ocupada() for s in g.sesiones.values()))
    return g, srv, registro, enc


def _inicios(registro: Path, sid: str) -> list[list[str]]:
    salida: list[list[str]] = []
    for e in _eventos(registro):
        if e["evento"] != "inicio":
            continue
        args = e["args"]
        for op in ("--session-id", "--resume"):
            if op in args and args[args.index(op) + 1] == sid:
                salida.append(args)
    return salida


def test_crear_con_plantilla_reglas_y_entrevista(tmp_path: Path) -> None:
    g, _, registro, enc = _crear(tmp_path)
    orq, agente = _sids(enc)
    try:
        carpeta = tmp_path / "Agents" / "prueba-39"
        claude = (carpeta / "CLAUDE.md").read_text(encoding="utf-8")
        assert "## Plantilla Web (Next.js)" in claude
        assert "- Escribir en español latino neutro.\n- Sin emojis.\n" in claude
        assert (carpeta / ".gitignore").is_file() and "## Siguiente paso" in (
            carpeta / "PROJECT.md"
        ).read_text(encoding="utf-8")
        # El orquestador abre la entrevista; sin autoskills no la menciona.
        [saludo] = _mensajes(registro, orq)
        assert "entrevista inicial" in saludo and "autoskills" not in saludo
        # El agente, con los comandos seguros; el orquestador, sin terminal ni lista.
        [args_agente] = _inicios(registro, agente)
        assert args_agente[args_agente.index("--allowedTools") :] == [
            "--allowedTools",
            "Bash(git status *)",
            "Bash(npm test *)",
        ]
        [args_orq] = _inicios(registro, orq)
        assert "--allowedTools" not in args_orq
        assert args_orq[args_orq.index("--permission-mode") + 1] == "acceptEdits"
    finally:
        g.detener_todo()


def test_autoskills_encendida(tmp_path: Path) -> None:
    g, _, registro, enc = _crear(tmp_path, autoskills=True)
    orq, _ = _sids(enc)
    try:
        [saludo] = _mensajes(registro, orq)
        assert "npx autoskills --dry-run" in saludo and "-a claude-code" in saludo
    finally:
        g.detener_todo()


def test_regla_apagada_aviso_y_comandos(tmp_path: Path) -> None:
    g, srv, registro, enc = _crear(tmp_path)
    orq, agente = _sids(enc)
    carpeta = tmp_path / "Agents" / "prueba-39"
    try:
        # Washington agrega notas propias a CLAUDE.md: el monitor no las toca.
        ruta = carpeta / "CLAUDE.md"
        ruta.write_text(
            ruta.read_text(encoding="utf-8") + "\n## Notas mías\n\nNo tocar.\n", "utf-8"
        )
        # Se apaga "Tema claro" en el proyecto.
        cambio = {**_encargo("reglas", proyecto_id=PID), "reglas": REGLAS[:2], "comandos": COMANDOS}
        assert g.procesar(cambio)["ok"]
        claude = ruta.read_text(encoding="utf-8")
        assert "Tema claro" not in claude and claude.endswith("## Notas mías\n\nNo tocar.\n")
        assert "## Plantilla Web (Next.js)" in claude
        # Las dos sesiones vivas reciben el aviso una sola vez.
        avisos = lambda sid: [  # noqa: E731
            t for t in _mensajes(registro, sid) if t.startswith("Se actualizaron las reglas")
        ]
        assert _girar(g, srv, lambda: len(avisos(orq)) == 1 and len(avisos(agente)) == 1)
        assert "Tema claro" not in avisos(orq)[0] and "- Sin emojis." in avisos(orq)[0]
        assert g.procesar(cambio)["ok"]  # reentrega: sin cambios, sin aviso nuevo
        time.sleep(0.3)
        g.atender()
        assert len(avisos(orq)) == 1
        # Cambian los comandos: solo el agente se relanza (con --resume) con la lista nueva.
        nuevos = {**cambio, "id": uuid.uuid4().hex, "comandos": ["git status", "pytest"]}
        assert g.procesar(nuevos)["ok"]
        assert _girar(g, srv, lambda: len(_inicios(registro, agente)) == 2)
        ultimo = _inicios(registro, agente)[-1]
        assert "--resume" in ultimo and ultimo[-2:] == ["Bash(git status *)", "Bash(pytest *)"]
        assert len(_inicios(registro, orq)) == 1
        assert {m["estado"] for m in g.estado_equipos()[0]["miembros"]} == {"activo"}
    finally:
        g.detener_todo()


def test_reglas_cambiadas_con_el_monitor_apagado(tmp_path: Path) -> None:
    """Si las reglas cambian mientras el equipo está pausado, al reanudar cada sesión
    recibe el aviso una vez (CLAUDE.md solo se lee al empezar la sesión)."""
    g, srv, registro, enc = _crear(tmp_path)
    orq, _ = _sids(enc)
    try:
        assert g.procesar(_encargo("pausar", proyecto_id=PID))["ok"]
        reanudar = {
            **_encargo("reanudar", proyecto_id=PID),
            "reglas": ["Solo esta regla."],
            "comandos": COMANDOS,
        }
        assert g.procesar(reanudar)["ok"]
        assert _girar(
            g,
            srv,
            lambda: any("- Solo esta regla." in t for t in _mensajes(registro, orq)),
        )
        claude = (tmp_path / "Agents" / "prueba-39" / "CLAUDE.md").read_text(encoding="utf-8")
        assert "- Solo esta regla." in claude and "Sin emojis" not in claude
    finally:
        g.detener_todo()


def test_un_servidor_viejo_no_borra_las_reglas(tmp_path: Path) -> None:
    g, _, _, _ = _crear(tmp_path)
    try:
        assert g.procesar(_encargo("reanudar", proyecto_id=PID))["ok"]  # sin "reglas"
        claude = (tmp_path / "Agents" / "prueba-39" / "CLAUDE.md").read_text(encoding="utf-8")
        assert "- Sin emojis." in claude and g.proyectos[PID].comandos == COMANDOS
    finally:
        g.detener_todo()
