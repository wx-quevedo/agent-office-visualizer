"""Reglas de la casa y comandos seguros (etapa 4, Prompt 39)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core import acceso as acceso_mod
from app.core.acceso import Acceso
from app.core.agent_state_engine import AgentStateEngine, Thresholds, override_state_engine
from app.core.proyectos_equipo import (
    REGLAS_INICIALES,
    ProyectoError,
    ProyectosEquipo,
    set_proyectos_equipo,
)

T0 = datetime(2026, 10, 12, 15, 0, tzinfo=UTC)
HAIKU = {"modelo": "haiku", "esfuerzo": "low"}
ACTIVOS = [
    {"nombre": "orquestador", "estado": "activo"},
    {"nombre": "agente", "estado": "activo"},
]


def _activo(r: ProyectosEquipo, nombre: str = "prueba-39") -> str:
    p = r.crear(nombre, "alienware", "personal", "web", HAIKU, [HAIKU], False, "E:\\Agents")
    [enc] = r.encargos_pendientes("alienware")
    r.informar_encargo("alienware", enc["id"], True, None, None, ACTIVOS)
    return p["id"]


def test_reglas_y_comandos_iniciales(tmp_path: Path) -> None:
    r = ProyectosEquipo(tmp_path, clock=lambda: T0)
    assert r.version() == 6
    reglas = r.reglas()
    assert [x["id"] for x in reglas] == [i for i, *_ in REGLAS_INICIALES]
    assert reglas[0]["texto"].startswith("Escribir en español latino neutro")
    autoskills = next(x for x in reglas if x["id"] == "autoskills")
    assert autoskills["activa_por_defecto"] is False and autoskills["tipo"] == "herramientas"
    assert all(x["activa_por_defecto"] for x in reglas if x["id"] != "autoskills")
    assert [c["comando"] for c in r.comandos()] == [
        "git status",
        "git diff",
        "git log",
        "npm test",
        "npm run build",
        "npm run lint",
        "pytest",
    ]
    # Una segunda apertura no las duplica.
    assert len(ProyectosEquipo(tmp_path).reglas()) == len(reglas)


def test_el_encargo_de_crear_lleva_reglas_y_comandos(tmp_path: Path) -> None:
    r = ProyectosEquipo(tmp_path, clock=lambda: T0)
    r.crear("prueba-39", "alienware", "personal", "web", HAIKU, [HAIKU], False, "E:\\Agents")
    [enc] = r.encargos_pendientes("alienware")
    assert enc["reglas"][0].startswith("Escribir en español latino neutro")
    assert len(enc["reglas"]) == len(REGLAS_INICIALES) - 1  # autoskills, apagada
    assert enc["comandos"][0] == "git status" and enc["autoskills"] is False


def test_editar_la_lista_global(tmp_path: Path) -> None:
    r = ProyectosEquipo(tmp_path, clock=lambda: T0)
    pid = _activo(r)
    nueva = r.crear_regla("  Usar   pnpm  ", "herramientas", True)
    assert nueva["texto"] == "Usar pnpm" and nueva["orden"] == len(REGLAS_INICIALES)
    # Cada cambio global le llega al monitor de cada proyecto con equipo.
    [enc] = r.encargos_pendientes("alienware")
    assert enc["tipo"] == "reglas" and enc["proyecto_id"] == pid and "Usar pnpm" in enc["reglas"]
    r.cambiar_regla(nueva["id"], texto="Usar pnpm siempre", activa_por_defecto=False)
    [enc] = r.encargos_pendientes("alienware")
    assert "Usar pnpm siempre" not in enc["reglas"]
    for malo in ({"texto": " "}, {"tipo": "nada"}):
        with pytest.raises(ProyectoError) as e:
            r.cambiar_regla(nueva["id"], **malo)  # type: ignore[arg-type]
        assert e.value.status == 422
    r.borrar_regla(nueva["id"])
    with pytest.raises(ProyectoError) as e:
        r.borrar_regla(nueva["id"])
    assert e.value.status == 404
    # Comandos.
    c = r.crear_comando(" npm   run  e2e ", True)
    assert c["comando"] == "npm run e2e"
    with pytest.raises(ProyectoError) as e:
        r.crear_comando("npm run e2e", True)
    assert e.value.status == 409
    for malo in (
        "rm -rf *",
        "git status && rm x",
        "npm test; ls",
        "echo $HOME",
        "(x)",
        "a | b",
        "",
    ):
        with pytest.raises(ProyectoError) as e:
            r.crear_comando(malo, True)
        assert e.value.status == 422
    r.cambiar_comando(c["id"], activo_por_defecto=False)
    r.borrar_comando(c["id"])
    tipos = [x["tipo"] for x in r.encargos_pendientes("alienware")]
    assert set(tipos) == {"reglas"}


def test_ajustes_por_proyecto(tmp_path: Path) -> None:
    r = ProyectosEquipo(tmp_path, clock=lambda: T0)
    pid = _activo(r)
    otro = _activo(r, "otro")
    v = r.ajustar_regla(pid, "tema-claro", False)
    tema = next(x for x in v["reglas"] if x["id"] == "tema-claro")
    assert tema["activa"] is False and tema["ajustada"] is True
    v = r.ajustar_regla(pid, "autoskills", True)
    assert next(x for x in v["reglas"] if x["id"] == "autoskills")["activa"] is True
    v = r.ajustar_comando(pid, "pytest", False)
    assert next(x for x in v["comandos"] if x["id"] == "pytest")["activo"] is False
    # Solo el proyecto ajustado recibe encargos; el otro sigue con los valores globales.
    encargos = r.encargos_pendientes("alienware")
    assert {e["proyecto_id"] for e in encargos} == {pid}
    ultimo = encargos[-1]
    assert "Tema claro por defecto." not in ultimo["reglas"] and ultimo["autoskills"] is True
    assert "pytest" not in ultimo["comandos"]
    assert "Tema claro por defecto." in [
        x["texto"] for x in r.reglas_de(otro)["reglas"] if x["activa"]
    ]
    # Volver al valor global deja de contar como ajustada.
    v = r.ajustar_regla(pid, "tema-claro", True)
    assert next(x for x in v["reglas"] if x["id"] == "tema-claro")["ajustada"] is False
    for llamada in (
        lambda: r.ajustar_regla("nada", "tema-claro", True),
        lambda: r.ajustar_regla(pid, "nada", True),
        lambda: r.ajustar_comando(pid, "nada", True),
    ):
        with pytest.raises(ProyectoError) as e:
            llamada()
        assert e.value.status == 404


@pytest.fixture
def cliente(tmp_path: Path) -> Iterator[tuple[TestClient, ProyectosEquipo]]:
    from app.main import app

    acc = Acceso(tmp_path / "acceso.db", secreto="s", clock=lambda: T0)
    acc.registrar_maquina("alienware", "Alienware", "windows")
    acceso_mod.set_acceso(acc)
    reg = ProyectosEquipo(tmp_path, clock=lambda: T0)
    set_proyectos_equipo(reg)
    override_state_engine(AgentStateEngine(Thresholds(), clock=lambda: T0 + timedelta(seconds=30)))
    try:
        yield TestClient(app), reg
    finally:
        acceso_mod.set_acceso(None)
        set_proyectos_equipo(None)
        override_state_engine(None)


def test_rutas(cliente: tuple[TestClient, ProyectosEquipo]) -> None:
    c, reg = cliente
    pid = _activo(reg)
    api = "/api/v1"
    d = c.get(f"{api}/reglas").json()
    assert len(d["reglas"]) == len(REGLAS_INICIALES) and "idioma" in d["tipos"]
    r = c.post(f"{api}/reglas", json={"texto": "Una regla", "tipo": "otra"})
    assert r.status_code == 201 and r.json()["activa_por_defecto"] is True
    rid = r.json()["id"]
    assert c.post(f"{api}/reglas", json={"texto": "x", "tipo": "nada"}).status_code == 422
    assert c.patch(f"{api}/reglas/{rid}", json={"tipo": "git"}).json()["tipo"] == "git"
    assert c.delete(f"{api}/reglas/{rid}").json() == {"ok": True}
    assert c.delete(f"{api}/reglas/{rid}").status_code == 404
    r = c.post(f"{api}/comandos", json={"comando": "cargo test"})
    assert r.status_code == 201
    r2 = c.post(f"{api}/comandos", json={"comando": "rm -rf /tmp && x"})
    assert r2.status_code == 422 and "operadores" in r2.json()["detail"]
    assert c.post(f"{api}/comandos", json={"comando": "cargo test"}).status_code == 409
    assert len(c.get(f"{api}/comandos").json()["comandos"]) == 8
    v = c.post(f"{api}/proyectos-creados/{pid}/reglas/emojis", json={"activa": False}).json()
    assert next(x for x in v["reglas"] if x["id"] == "emojis")["activa"] is False
    v = c.post(f"{api}/proyectos-creados/{pid}/comandos/git-log", json={"activo": False}).json()
    assert next(x for x in v["comandos"] if x["id"] == "git-log")["ajustado"] is True
    assert c.get(f"{api}/proyectos-creados/{pid}/reglas").status_code == 200
    assert c.get(f"{api}/proyectos-creados/nada/reglas").status_code == 404
