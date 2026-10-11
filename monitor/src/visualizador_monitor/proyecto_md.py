"""Lectura tolerante del PROJECT.md de un proyecto: "dónde quedamos".

``resumir`` es puro (solo texto): título, plan por etapas con su estado, posición
actual, siguiente paso y decisiones pendientes, más el último commit anotado en el
registro. ``leer_resumen`` busca el archivo en la carpeta, lo lee con cuidado
(sin rutas de red, con tamaño máximo) y agrega el último commit de git.

Los formatos varían entre proyectos (español o inglés, con o sin tildes, títulos
de cualquier nivel, listas numeradas o con viñetas, casillas, negritas): todo se
reconoce por palabras clave y nada lanza excepciones; lo que no se entiende queda
vacío o en ``None``.
"""

from __future__ import annotations

import re
import subprocess
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

MAX_ITEMS_PLAN = 60
MAX_DECISIONES = 10
MAX_SIGUIENTE = 300
MAX_DECISION = 200
MAX_NOMBRE = 100
MAX_MENSAJE_REGISTRO = 200
MAX_COLA_ESTADO = 40
TIEMPO_GIT = 5.0
MAX_PROMPTS = 40
MAX_COMMITS_PROMPT = 10

# Palabras clave de los títulos de sección (ya normalizados: minúsculas, sin tildes).
_CLAVES_PLAN = ("plan", "etapas", "fases", "roadmap", "hoja de ruta", "milestones")
_CLAVES_SIGUIENTE = (
    "proximos pasos",
    "proximo paso",
    "siguiente paso",
    "siguientes pasos",
    "next steps",
    "next step",
    "pasos siguientes",
)
_CLAVES_DECISION = (
    "decidir",
    "decision",
    "decisiones pendientes",
    "open questions",
    "preguntas abiertas",
    "por decidir",
)
_CLAVES_REGISTRO = ("registro", "changelog", "historial", "bitacora")
_INICIOS_DECISION = ("decidir", "que decidir", "pendiente de decision", "espera decision")

_TITULO = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$")
_CERCO = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_ITEM = re.compile(r"^([ \t]*)(?:[-*+]|\d{1,3}[.)])[ \t]+(?:\[([ xX~-])\][ \t]*)?(.*)$")
_NEGRITA_INICIAL = re.compile(r"^\s*(?:\*\*|__)(.+?)(?:\*\*|__)")
_CORTE_NOMBRE = re.compile(r":|\s[—–]\s|\.(?=\s|$)")
_PARENTESIS_FINAL = re.compile(r"\s*\([^()]*\)\s*$")
_PARENTESIS = re.compile(r"\(([^()]*)\)")
_HASH = re.compile(r"`([0-9a-fA-F]{7,40})`")
_FECHA = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
# Subítem de prompt: "26: datos y API", "Prompt 27 · bocetos", "28) ficha".
_PROMPT_ITEM = re.compile(r"^(?:prompt\s+)?(\d{1,4})\s*[:.)·\-–—]\s*(.+)$", re.IGNORECASE)
_SEPARADOR_TABLA = re.compile(r"^\s*\|?\s*:?-{2,}")

_HECHO = re.compile(
    r"\b(?:hech[oa]s?|terminad\w*|completad\w*|cerrad\w*|done|finished|completed)\b"
)
_EN_CURSO_ZONA = re.compile(r"\b(?:en curso|actual|in progress|en progreso|trabajando)\b")
# "Etapa 1", "Fase 2.3", "Phase 4": palabra, número y subnúmero opcional.
_ETAPA = re.compile(r"^([a-z]+)\s+(\d+)(?:\.(\d+))?(?![\d.]*\d)")


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes y con espacios simples."""
    descompuesto = unicodedata.normalize("NFD", texto.lower())
    sin_marcas = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return " ".join(sin_marcas.split())


def quitar_markdown(texto: str) -> str:
    """Texto plano: negritas, cursivas, código en línea y enlaces (queda su texto)."""
    t = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", texto)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"`+([^`]*)`+", r"\1", t)
    t = re.sub(r"(\*\*|__)(.+?)\1", r"\2", t)
    t = re.sub(r"~~(.+?)~~", r"\1", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", t)
    t = re.sub(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)", r"\1", t)
    t = re.sub(r"</?[A-Za-z][^>]*>", "", t)
    return " ".join(t.split())


def _acortar(texto: str, maximo: int) -> str:
    return texto if len(texto) <= maximo else texto[: maximo - 1].rstrip() + "…"


def _coincide(texto: str, claves: tuple[str, ...]) -> bool:
    """Alguna clave aparece como palabra completa (admite plural en "s")."""
    norm = normalizar(texto)
    return any(re.search(rf"\b{re.escape(c)}s?\b", norm) for c in claves)


# --- Estructura del documento -------------------------------------------------


class _Doc:
    """Líneas sin los bloques de código y los títulos con su nivel."""

    def __init__(self, texto: str) -> None:
        texto = texto.removeprefix("﻿")
        crudas = texto.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        self.lineas: list[str] = []
        cerco: str | None = None
        for linea in crudas:
            m = _CERCO.match(linea)
            if cerco is not None:
                if m and m.group(1)[0] == cerco[0] and len(m.group(1)) >= len(cerco):
                    cerco = None
                self.lineas.append("")
                continue
            if m:
                cerco = m.group(1)
                self.lineas.append("")
                continue
            self.lineas.append(linea.expandtabs(4))
        self.titulos: list[tuple[int, int, str]] = []  # (línea, nivel, texto)
        for i, linea in enumerate(self.lineas):
            m = _TITULO.match(linea)
            if m:
                self.titulos.append((i, len(m.group(1)), m.group(2)))

    def secciones(self, claves: tuple[str, ...]) -> list[tuple[int, int, int]]:
        """(inicio, fin, nivel) del cuerpo de cada sección cuyo título coincide."""
        out: list[tuple[int, int, int]] = []
        for k, (linea, nivel, texto) in enumerate(self.titulos):
            if not _coincide(quitar_markdown(texto), claves):
                continue
            fin = len(self.lineas)
            for linea2, nivel2, _ in self.titulos[k + 1 :]:
                if nivel2 <= nivel:
                    fin = linea2
                    break
            out.append((linea + 1, fin, nivel))
        return out


def _items(lineas: list[str]) -> list[tuple[str, str | None]]:
    """Ítems de primer nivel (texto con sus líneas de continuación, casilla)."""
    encontrados: list[tuple[int, str, str | None]] = []  # (sangría, texto, casilla)
    en_item = False
    tras_blanco = False
    for linea in lineas:
        m = _ITEM.match(linea)
        if m:
            encontrados.append((len(m.group(1)), m.group(3).strip(), m.group(2)))
            en_item, tras_blanco = True, False
            continue
        if not linea.strip():
            tras_blanco = True
            continue
        sangrada = len(linea) - len(linea.lstrip()) >= 2
        es_bloque = _TITULO.match(linea) or linea.lstrip().startswith(("|", ">"))
        if en_item and not es_bloque and (not tras_blanco or sangrada):
            sangria, texto, casilla = encontrados[-1]
            encontrados[-1] = (sangria, f"{texto} {linea.strip()}", casilla)
            tras_blanco = False
        else:
            en_item = False
    if not encontrados:
        return []
    minimo = min(s for s, _, _ in encontrados)
    return [(t, c) for s, t, c in encontrados if s <= minimo + 1]


# --- Plan ---------------------------------------------------------------------


def _nombre(texto: str) -> str:
    m = _NEGRITA_INICIAL.match(texto)
    if m:
        nombre = quitar_markdown(m.group(1))
    else:
        plano = quitar_markdown(texto)
        corte = _CORTE_NOMBRE.search(plano)
        nombre = plano[: corte.start()] if corte else plano
        nombre = nombre[:MAX_NOMBRE]
    sin_parentesis = _PARENTESIS_FINAL.sub("", nombre).strip()
    return (sin_parentesis or nombre).strip().rstrip(":").strip()


def _estado(texto: str, casilla: str | None = None) -> str:
    if casilla is not None and casilla.lower() == "x":
        return "hecho"
    if "✓" in texto or "✔" in texto or "✅" in texto:
        return "hecho"
    # Zona de estado: la cabeza del ítem (hasta el primer separador), los paréntesis
    # que empiezan con una palabra de estado ("(hecha el 2026-10-10)") y la cola
    # corta tras el último separador ("Fase 2: API — en curso"). Así una descripción
    # larga ("tarea terminada", "tarea actual") no cambia el estado.
    plano = quitar_markdown(texto)
    m = _NEGRITA_INICIAL.match(texto)
    partes = [quitar_markdown(m.group(1))] if m else []
    corte = _CORTE_NOMBRE.search(plano)
    partes.append(plano[: corte.start()] if corte else plano[:MAX_NOMBRE])
    for contenido in _PARENTESIS.findall(plano):
        norm = normalizar(contenido)
        if _HECHO.match(norm) or _EN_CURSO_ZONA.match(norm):
            partes.append(contenido)
    cola = re.split(r":|\s[—–-]\s|\|", plano)[-1] if corte else ""
    if len(cola.strip()) <= MAX_COLA_ESTADO:
        partes.append(cola)
    zona = normalizar(" ".join(partes))
    if _HECHO.search(zona):
        return "hecho"
    if _EN_CURSO_ZONA.search(zona):
        return "en_curso"
    return "pendiente"


def _agrupar_etapas(plan: list[dict[str, str]]) -> None:
    """Una etapa general ("Etapa 1") queda hecha si todas sus subetapas (1.x) lo están."""
    claves: list[tuple[str, str, str | None] | None] = []
    for item in plan:
        m = _ETAPA.match(normalizar(item["nombre"]))
        claves.append((m.group(1), m.group(2), m.group(3)) if m else None)
    for item, clave in zip(plan, claves, strict=True):
        if clave is None or clave[2] is not None or item["estado"] != "pendiente":
            continue
        hijos = [
            plan[j]["estado"]
            for j, c in enumerate(claves)
            if c is not None and c[:2] == clave[:2] and c[2] is not None
        ]
        if hijos and all(e == "hecho" for e in hijos):
            item["estado"] = "hecho"


def _plan(doc: _Doc) -> list[dict[str, str]]:
    for inicio, fin, nivel in doc.secciones(_CLAVES_PLAN):
        plan: list[dict[str, str]] = []
        for texto, casilla in _items(doc.lineas[inicio:fin]):
            nombre = _nombre(texto)
            if nombre:
                plan.append({"nombre": nombre, "estado": _estado(texto, casilla)})
        if not plan:
            subtitulos = [(n, t) for linea, n, t in doc.titulos if inicio <= linea < fin]
            if subtitulos:
                nivel_hijo = min(n for n, _ in subtitulos)
                for n, t in subtitulos:
                    if n == nivel_hijo and n > nivel and (nombre := _nombre(t)):
                        plan.append({"nombre": nombre, "estado": _estado(t)})
        if plan:
            plan = plan[:MAX_ITEMS_PLAN]
            _agrupar_etapas(plan)
            return plan
    return []


def _posicion(plan: list[dict[str, str]]) -> str | None:
    for item in plan:
        if item["estado"] == "en_curso":
            return item["nombre"]
    ultimo_hecho = max((i for i, it in enumerate(plan) if it["estado"] == "hecho"), default=-1)
    for item in plan[ultimo_hecho + 1 :]:
        if item["estado"] == "pendiente":
            return item["nombre"]
    return None


# --- Siguiente paso, decisiones y registro ------------------------------------


def _siguiente_paso(doc: _Doc) -> str | None:
    for inicio, fin, _ in doc.secciones(_CLAVES_SIGUIENTE):
        lineas = doc.lineas[inicio:fin]
        items = _items(lineas)
        candidatos = [t for t, _ in items] if items else []
        if not candidatos:
            for linea in lineas:
                if not linea.strip() or _TITULO.match(linea) or _SEPARADOR_TABLA.match(linea):
                    continue
                candidatos.append(linea.strip().strip("|"))
                break
        for c in candidatos:
            plano = quitar_markdown(c)
            if plano:
                return _acortar(plano, MAX_SIGUIENTE)
    return None


def _espera_decision(doc: _Doc) -> list[str]:
    secciones = doc.secciones(_CLAVES_DECISION)
    salida: list[str] = []
    if secciones:
        for inicio, fin, _ in secciones:
            for texto, _ in _items(doc.lineas[inicio:fin]):
                plano = quitar_markdown(texto)
                if plano:
                    salida.append(_acortar(plano, MAX_DECISION))
        return salida[:MAX_DECISIONES]
    for linea in doc.lineas:
        m = _ITEM.match(linea)
        if not m:
            continue
        plano = quitar_markdown(m.group(3))
        if normalizar(plano).startswith(_INICIOS_DECISION):
            salida.append(_acortar(plano, MAX_DECISION))
            if len(salida) >= MAX_DECISIONES:
                break
    return salida


def _commit_registro(doc: _Doc) -> dict[str, Any] | None:
    """El último hash entre comillas invertidas de una fila del registro."""
    elegido: tuple[str, str] | None = None  # (hash, fila)
    for inicio, fin, _ in doc.secciones(_CLAVES_REGISTRO):
        for linea in doc.lineas[inicio:fin]:
            hashes = [h for h in _HASH.findall(linea) if re.search(r"[a-fA-F]", h)]
            if hashes:
                elegido = (hashes[-1].lower(), linea)
    if elegido is None:
        return None
    hash_, fila = elegido
    fecha = _FECHA.search(fila)
    if fila.lstrip().startswith("|"):
        celdas = [c.strip() for c in fila.strip().strip("|").split("|")]
        resto = [c for c in celdas if c and not (fecha and c == fecha.group(0))]
    else:
        resto = [_ITEM.sub(r"\3", fila).strip()]
    mensaje = quitar_markdown(" ".join(resto))
    return {
        "hash": hash_,
        "mensaje": _acortar(mensaje, MAX_MENSAJE_REGISTRO),
        "fecha": fecha.group(0) if fecha else None,
    }


def _prompts(doc: _Doc, posicion: str | None) -> list[dict[str, Any]]:
    """Los prompts de la etapa actual: los subítems numerados de su ítem del plan
    ("- 26: datos y API (hecho el 2026-10-11)"), con los commits de las filas del
    registro que nombran ese prompt ("Prompt 26")."""
    if not posicion:
        return []
    salida: list[dict[str, Any]] = []
    for inicio, fin, _ in doc.secciones(_CLAVES_PLAN):
        lineas = doc.lineas[inicio:fin]
        for i, linea in enumerate(lineas):
            m = _ITEM.match(linea)
            if not m or _nombre(m.group(3).strip()) != posicion:
                continue
            sangria = len(m.group(1))
            for sub in lineas[i + 1 :]:
                ms = _ITEM.match(sub)
                if ms is None:
                    if sub.strip() and len(sub) - len(sub.lstrip()) <= sangria:
                        break
                    continue
                if len(ms.group(1)) <= sangria:
                    break
                plano = quitar_markdown(ms.group(3).strip())
                mp = _PROMPT_ITEM.match(plano)
                if not mp:
                    continue
                fecha = _FECHA.search(plano)
                nombre = _PARENTESIS_FINAL.sub("", mp.group(2).strip().rstrip(".")).strip()
                salida.append(
                    {
                        "numero": int(mp.group(1)),
                        "nombre": _acortar(nombre or mp.group(2), MAX_NOMBRE),
                        "estado": _estado(ms.group(3), ms.group(2)),
                        "fecha": fecha.group(0) if fecha else None,
                        "commits": [],
                    }
                )
            break
        if salida:
            break
    if not salida:
        return []
    for inicio, fin, _ in doc.secciones(_CLAVES_REGISTRO):
        for linea in doc.lineas[inicio:fin]:
            hashes = [h.lower() for h in _HASH.findall(linea) if re.search(r"[a-fA-F]", h)]
            if not hashes:
                continue
            plano = normalizar(linea)
            for p in salida:
                if re.search(rf"\bprompt\s+{p['numero']}\b", plano):
                    p["commits"] = [h for h in [*p["commits"], *hashes] if h][-MAX_COMMITS_PROMPT:]
    return salida[:MAX_PROMPTS]


def resumir(texto: str) -> dict[str, Any]:
    """Resumen de un PROJECT.md ya leído (sin tocar el disco)."""
    try:
        return _resumir(texto if isinstance(texto, str) else "")
    except Exception:  # un texto raro nunca debe romper el monitor
        return _resumir("")


def _resumir(texto: str) -> dict[str, Any]:
    doc = _Doc(texto)
    titulo: str | None = None
    for _, nivel, t in doc.titulos:
        if nivel == 1:
            titulo = quitar_markdown(t) or None
            break
    plan = _plan(doc)
    posicion = _posicion(plan)
    return {
        "titulo": titulo,
        "plan": plan,
        "posicion": posicion,
        "prompts": _prompts(doc, posicion),
        "siguiente_paso": _siguiente_paso(doc),
        "espera_decision": _espera_decision(doc),
        "ultimo_commit": _commit_registro(doc),
    }


# --- Disco y git --------------------------------------------------------------


def ruta_permitida(carpeta: Path | str) -> bool:
    """Ruta local absoluta; nada de rutas de red (UNC) ni de dispositivo."""
    raw = str(carpeta)
    if raw.startswith(("\\\\", "//", "\\/", "/\\")):
        return False
    return Path(raw).is_absolute()


def ultimo_commit_git(carpeta: Path) -> dict[str, str] | None:
    """Último commit del repositorio que contiene la carpeta, o None."""
    try:
        r = subprocess.run(
            ["git", "-C", str(carpeta), "log", "-1", "--format=%h%x1f%s%x1f%cI"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIEMPO_GIT,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    if r.returncode != 0 or not r.stdout:
        return None
    partes = r.stdout.strip().split("\x1f")
    if len(partes) != 3 or not partes[0]:
        return None
    return {"hash": partes[0], "mensaje": partes[1], "fecha": partes[2]}


def _buscar_project_md(carpeta: Path) -> Path | None:
    try:
        candidatos = [p for p in carpeta.iterdir() if p.name.lower() == "project.md"]
    except OSError:
        return None
    candidatos.sort(key=lambda p: (p.name != "PROJECT.md", p.name))
    for p in candidatos:
        try:
            if p.is_file():
                return p
        except OSError:
            continue
    return None


def leer_resumen(carpeta: Path, max_bytes: int = 1_000_000) -> dict[str, Any]:
    """Dónde quedó el proyecto de una carpeta: su PROJECT.md y su último commit."""
    if not ruta_permitida(carpeta):
        return {"error": "ruta no permitida"}
    carpeta = Path(carpeta)
    ruta = _buscar_project_md(carpeta)
    commit = ultimo_commit_git(carpeta) if ruta is not None or carpeta.is_dir() else None
    if ruta is None:
        return {"tiene_project_md": False, "ultimo_commit": commit}
    try:
        info = ruta.stat()
        modificado = datetime.fromtimestamp(info.st_mtime).astimezone().isoformat()
        if info.st_size > max_bytes:
            return {
                "tiene_project_md": True,
                "error": "PROJECT.md demasiado grande",
                "ultimo_commit": commit,
                "modificado": modificado,
            }
        with open(ruta, "rb") as f:
            datos = f.read(max_bytes + 1)
    except OSError:
        return {"tiene_project_md": False, "ultimo_commit": commit}
    if len(datos) > max_bytes:
        return {
            "tiene_project_md": True,
            "error": "PROJECT.md demasiado grande",
            "ultimo_commit": commit,
            "modificado": modificado,
        }
    resumen = resumir(datos.decode("utf-8-sig", errors="replace"))
    if commit is not None:
        resumen["ultimo_commit"] = commit
    return {"tiene_project_md": True, **resumen, "modificado": modificado}
