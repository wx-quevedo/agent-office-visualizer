"""Lectura tolerante del PROJECT.md (plan, posición, siguiente paso, decisiones, commit)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

from visualizador_monitor import proyecto_md
from visualizador_monitor.proyecto_md import leer_resumen, resumir

RAIZ = Path(__file__).parents[2]


def _plan(r: dict[str, Any]) -> dict[str, str]:
    return {i["nombre"]: i["estado"] for i in r["plan"]}


def _que_empieza(r: dict[str, Any], prefijo: str) -> dict[str, str]:
    for item in r["plan"]:
        if item["nombre"] == prefijo or item["nombre"].startswith((prefijo + ",", prefijo + " ")):
            return item
    raise AssertionError(f"no hay ítem {prefijo!r} en {r['plan']}")


# --- El PROJECT.md real del repositorio ---------------------------------------


def test_project_md_real() -> None:
    texto = (RAIZ / "PROJECT.md").read_text(encoding="utf-8")
    r = resumir(texto)
    assert r["titulo"] and "PROJECT.md" in r["titulo"]
    for etapa in ("Etapa 0", "Etapa 1.1", "Etapa 1.2", "Etapa 1.3", "Etapa 1.4", "Etapa 2"):
        assert _que_empieza(r, etapa)["estado"] == "hecho", etapa
    assert _que_empieza(r, "Etapa 3")["estado"] != "hecho"
    # la posición es la primera etapa no hecha después de la última hecha
    nombres = [i["nombre"] for i in r["plan"]]
    ultimo_hecho = max(i for i, it in enumerate(r["plan"]) if it["estado"] == "hecho")
    siguiente = next(it for it in r["plan"][ultimo_hecho + 1 :] if it["estado"] != "hecho")
    assert r["posicion"] == siguiente["nombre"]
    assert r["posicion"] in nombres
    assert r["posicion"].startswith("Etapa 3")
    assert r["siguiente_paso"] is not None
    assert len(r["siguiente_paso"]) <= 300
    assert isinstance(r["espera_decision"], list)
    # el registro trae commits entre comillas invertidas
    assert r["ultimo_commit"] is not None
    assert len(r["ultimo_commit"]["hash"]) >= 7


def test_project_md_real_desde_disco_con_git() -> None:
    if shutil.which("git") is None or not (RAIZ / ".git").exists():
        pytest.skip("sin git o fuera del repositorio")
    r = leer_resumen(RAIZ)
    assert r["tiene_project_md"] is True
    assert r["ultimo_commit"] is not None
    assert set(r["ultimo_commit"]) == {"hash", "mensaje", "fecha"}
    assert r["ultimo_commit"]["fecha"][:2] == "20"
    assert r["modificado"]
    assert r["posicion"] is not None


# --- Otros formatos -----------------------------------------------------------


def test_roadmap_en_ingles_con_casillas() -> None:
    texto = """# My App

## Roadmap

- [x] Phase 1: setup
- [ ] Phase 2: API
  - [x] nested sub-item that must be ignored
- [ ] Phase 3: UI

## Next steps

1. Write the **API** handlers for [users](https://example.com)
2. Deploy

## Open questions

* Which database?
* `Auth` provider
"""
    r = resumir(texto)
    assert r["titulo"] == "My App"
    assert r["plan"] == [
        {"nombre": "Phase 1", "estado": "hecho"},
        {"nombre": "Phase 2", "estado": "pendiente"},
        {"nombre": "Phase 3", "estado": "pendiente"},
    ]
    assert r["posicion"] == "Phase 2"
    assert r["siguiente_paso"] == "Write the API handlers for users"
    assert r["espera_decision"] == ["Which database?", "Auth provider"]
    assert r["ultimo_commit"] is None


def test_plan_en_subtitulos_sin_listas() -> None:
    texto = """# Proyecto

## Fases del proyecto

### Fase 1 (terminada)

Se hizo la base.

### Fase 2 (en curso)

Texto.

### Fase 3

#### Detalle que no es una fase

## Otra sección
"""
    r = resumir(texto)
    assert r["plan"] == [
        {"nombre": "Fase 1", "estado": "hecho"},
        {"nombre": "Fase 2", "estado": "en_curso"},
        {"nombre": "Fase 3", "estado": "pendiente"},
    ]
    assert r["posicion"] == "Fase 2"


def test_estados_y_nombres_variados() -> None:
    texto = """### Hoja de ruta
1) **Etapa A** — completada
2) Etapa B: diseño ✓
3) *Etapa C*: trabajando ahora
4) Etapa D: la tarea terminada por otro equipo se revisa en esta etapa, que es larga
5) Etapa E. Algo
"""
    r = resumir(texto)
    assert _plan(r) == {
        "Etapa A": "hecho",
        "Etapa B": "hecho",
        "Etapa C": "en_curso",
        "Etapa D": "pendiente",
        "Etapa E": "pendiente",
    }
    assert r["posicion"] == "Etapa C"


def test_etapa_general_hecha_si_sus_subetapas_lo_estan() -> None:
    texto = """## Plan
- Etapa 1: publicar
- Etapa 1.1 (hecha)
- Etapa 1.2 (hecha)
- Etapa 2: ver bien
"""
    r = resumir(texto)
    assert _plan(r)["Etapa 1"] == "hecho"
    assert r["posicion"] == "Etapa 2"


def test_sin_secciones_conocidas() -> None:
    r = resumir("Solo un párrafo.\n\n- algo\n- otra cosa\n\n| a | b |\n|---|---|\n")
    assert r == {
        "titulo": None,
        "plan": [],
        "posicion": None,
        "prompts": [],
        "siguiente_paso": None,
        "espera_decision": [],
        "ultimo_commit": None,
    }


@pytest.mark.parametrize(
    "texto",
    ["", "\x00\x01", "#", "## Plan\n", "## Plan\n-\n- \n* [x]\n", "```\n## Plan\n- a\n", "|||"],
)
def test_entradas_raras_no_lanzan(texto: str) -> None:
    r = resumir(texto)
    assert isinstance(r["plan"], list)


def test_titulos_dentro_de_bloques_de_codigo_se_ignoran() -> None:
    texto = "```bash\n# no es título\n```\n# Título real\n"
    assert resumir(texto)["titulo"] == "Título real"


def test_decisiones_sueltas_sin_seccion() -> None:
    texto = """# X

## Pendientes

- Decidir si usamos Postgres
- **Qué decidir**: el nombre
- Otra cosa
"""
    r = resumir(texto)
    assert r["espera_decision"] == ["Decidir si usamos Postgres", "Qué decidir: el nombre"]


def test_siguiente_paso_en_parrafo() -> None:
    texto = "## Próximo paso\n\nTerminar la **ficha** del agente.\n\nOtro párrafo.\n"
    assert resumir(texto)["siguiente_paso"] == "Terminar la ficha del agente."


# --- Disco -------------------------------------------------------------------


def _sin_git(monkeypatch: pytest.MonkeyPatch, carpeta: Path) -> None:
    # git no debe subir a carpetas padre que sí sean repositorios
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(carpeta.parent))


def test_carpeta_sin_project_md(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _sin_git(monkeypatch, tmp_path)
    (tmp_path / "README.md").write_text("# Hola", encoding="utf-8")
    assert leer_resumen(tmp_path) == {"tiene_project_md": False, "ultimo_commit": None}


def test_carpeta_inexistente(tmp_path: Path) -> None:
    r = leer_resumen(tmp_path / "no-existe")
    assert r["tiene_project_md"] is False


def test_project_md_en_minusculas(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _sin_git(monkeypatch, tmp_path)
    (tmp_path / "project.md").write_text("# Minúsculas\n\n## Plan\n- [x] Uno\n", encoding="utf-8")
    r = leer_resumen(tmp_path)
    assert r["tiene_project_md"] is True
    assert r["titulo"] == "Minúsculas"
    assert r["plan"] == [{"nombre": "Uno", "estado": "hecho"}]
    assert r["modificado"]


@pytest.mark.parametrize(
    "ruta",
    [
        r"\\servidor\recurso\proyecto",
        "//servidor/recurso",
        r"\\?\C:\proyecto",
        r"\\.\PhysicalDrive0",
    ],
)
def test_ruta_de_red_rechazada_sin_tocar_el_disco(
    ruta: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def prohibido(*_a: object, **_k: object) -> Any:
        raise AssertionError("no debe tocar el disco ni ejecutar git")

    monkeypatch.setattr(Path, "iterdir", prohibido)
    monkeypatch.setattr(Path, "is_dir", prohibido)
    monkeypatch.setattr(Path, "stat", prohibido)
    monkeypatch.setattr(proyecto_md.subprocess, "run", prohibido)
    assert leer_resumen(Path(ruta)) == {"error": "ruta no permitida"}


def test_ruta_relativa_rechazada() -> None:
    assert leer_resumen(Path("algo/relativo")) == {"error": "ruta no permitida"}


def test_archivo_demasiado_grande(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _sin_git(monkeypatch, tmp_path)
    (tmp_path / "PROJECT.md").write_text("# Grande\n" + "x" * 5000, encoding="utf-8")
    r = leer_resumen(tmp_path, max_bytes=1000)
    assert r["error"] == "PROJECT.md demasiado grande"
    assert "plan" not in r


def test_bom_y_bytes_invalidos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _sin_git(monkeypatch, tmp_path)
    contenido = "\ufeff# Con BOM\n\n## Next step\n- Probar \xff\n".encode("utf-8")
    (tmp_path / "PROJECT.md").write_bytes(contenido.replace(b"\xc3\xbf", b"\xff"))
    r = leer_resumen(tmp_path)
    assert r["titulo"] == "Con BOM"
    assert r["siguiente_paso"] is not None and r["siguiente_paso"].startswith("Probar")


def test_commit_del_registro_sin_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _sin_git(monkeypatch, tmp_path)
    texto = """# Proyecto

## Registro

| Fecha | Avance |
| --- | --- |
| 2026-10-01 | Primer paso. Commit `abc1234` |
| 2026-10-05 | Puerto `8100` y la base. Commits `def5678` y `0a1b2c3d` |
| 2026-10-06 | Sin commit todavía |
"""
    (tmp_path / "PROJECT.md").write_text(texto, encoding="utf-8")
    r = leer_resumen(tmp_path)
    assert r["ultimo_commit"] == {
        "hash": "0a1b2c3d",
        "mensaje": "Puerto 8100 y la base. Commits def5678 y 0a1b2c3d",
        "fecha": "2026-10-05",
    }


def test_git_que_falla_no_rompe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def falla(*_a: object, **_k: object) -> Any:
        raise FileNotFoundError("git")

    monkeypatch.setattr(proyecto_md.subprocess, "run", falla)
    assert proyecto_md.ultimo_commit_git(tmp_path) is None


# --- Prompts de la etapa actual (etapa 2.3) ------------------------------------

_CON_PROMPTS = """# Proyecto

## Plan por etapas
- Etapa 1 (hecha)
- **Etapa 2, ver bien**, en 4 prompts:
  - 26: datos y API (hecho el 2026-10-11).
  - Prompt 27 · bocetos de la ficha
  - 28) ficha en curso
  - Alcance: no es un prompt
- Etapa 3, app

## Registro
| Fecha | Qué |
|---|---|
| 2026-10-11 | Etapa 2.1 (Prompt 26), datos. Commit `ac740e2` |
| 2026-10-12 | Otra cosa `bbbbbbb` |
"""


def test_prompts_de_la_etapa_actual() -> None:
    r = resumir(_CON_PROMPTS)
    assert r["posicion"] == "Etapa 2, ver bien"
    assert [(p["numero"], p["nombre"], p["estado"]) for p in r["prompts"]] == [
        (26, "datos y API", "hecho"),
        (27, "bocetos de la ficha", "pendiente"),
        (28, "ficha en curso", "en_curso"),
    ]
    assert r["prompts"][0]["fecha"] == "2026-10-11"
    assert r["prompts"][0]["commits"] == ["ac740e2"]
    assert r["prompts"][1]["commits"] == []


def test_sin_prompts_lista_vacia() -> None:
    r = resumir("# P\n\n## Plan\n- Fase 1\n- Fase 2\n")
    assert r["prompts"] == []
    assert resumir("")["prompts"] == []


def test_prompts_del_project_md_real() -> None:
    # La etapa 2 (cerrada) anota sus prompts 26 a 29 con el commit del registro.
    doc = proyecto_md._Doc((RAIZ / "PROJECT.md").read_text(encoding="utf-8"))  # pyright: ignore[reportPrivateUsage]
    prompts = proyecto_md._prompts(doc, "Etapa 2, ver bien")  # pyright: ignore[reportPrivateUsage]
    assert [p["numero"] for p in prompts] == [26, 27, 28, 29]
    assert all(p["estado"] == "hecho" for p in prompts)
    assert prompts[0]["commits"] == ["ac740e2"]
