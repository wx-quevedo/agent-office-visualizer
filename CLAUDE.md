# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Claude Office Visualizer transforms Claude Code operations into a real-time pixel art office simulation. A "boss" character (main Claude agent) manages work, spawns "employee" agents (subagents), and orchestrates tasks visually.

See [README.md](README.md) for the architecture (monitor, VPS, web) and [PROJECT.md](PROJECT.md) for the plan, decisions and history.

## Commands

```bash
# Root
make install       # Install all dependencies
make dev-tmux      # Run in tmux (recommended) - backend :8000, frontend :3000
make dev-tmux-kill # Kill tmux session
make checkall      # Lint, typecheck, test all components
make simulate      # Run event simulation

# Component-specific (run from backend/ or frontend/)
make dev           # Start dev server
make checkall      # Check single component (faster)
uv run pytest tests/test_file.py::test_name  # Single backend test

# Hooks (cd hooks/)
./install.sh       # Install hooks
./uninstall.sh     # Remove hooks

# OpenCode Plugin (cd opencode-plugin/)
bun run build      # Build plugin
bun run typecheck  # Type check
```

## Development Workflow

**Preferred:** Use `make dev-tmux` - creates separate windows for backend/frontend.
- Read logs: `tmux capture-pane -t claude-office:backend -p`
- Switch windows: `Ctrl-b n` / `Ctrl-b p`
- Hot reload enabled on both servers

**Debugging:** Hook logs at `~/.claude/claude-office-hooks.log` (enable with `CLAUDE_OFFICE_DEBUG=1`)

## Project Skills

- **/office-sprite** - Generate office furniture sprites
- **/character-sprite** - Generate character sprite sheets
- **/desk-accessory** - Generate tintable desk items

See `.claude/skills/*/SKILL.md` for details.

## Workflow Guidelines

**Commit after every batch of work:** Always commit after completing each logical unit.

**Test projects:** when you (or another agent) create a project with a team only to test something, always name it `prueba-<algo>` (the server then marks it as a test project: no alerts, no Decisiones, and it stops itself after 30 min without activity) and stop it (Detener) when you finish.

**Use subagents for validation:** Spawn a Bash subagent to run `make checkall` and commit:
```
"Run 'make checkall' from the project root. If successful, commit with message: '<message>'"
```

## Version Management

**Keep all version locations in sync** when bumping versions:

| Location | File |
|----------|------|
| Root package | `pyproject.toml` |
| Backend | `backend/pyproject.toml` |
| Backend OpenAPI | `backend/app/config.py` (`VERSION` — derived via `importlib.metadata`, no manual bump needed) |
| Hooks | `hooks/pyproject.toml` |
| Hooks CLI | `hooks/src/claude_office_hooks/main.py` (`__version__` — derived via `importlib.metadata`, no manual bump needed) |
| Frontend package | `frontend/package.json` |
| OpenCode plugin | `opencode-plugin/package.json` |

To bump all manual locations at once: `make bump-version VERSION=x.y.z` (rewrites the
manual rows above; the two derived rows — backend `VERSION` and hooks `__version__` —
follow the installed package automatically). CI cross-check: `make version-check` (ARC-021).

## Plan vivo (plan.json)

El plan del proyecto vive en `plan.json`, en la raíz. Se mantiene con el kit plan vivo, instalado una sola vez en `<plan-vivo path>`. El kit no se copia a este proyecto. Antes de tocar el plan, lee `<plan-vivo path>\AGENTES.md`: es obligatorio seguirlo y es la fuente de verdad.

- Si `plan.json` no existe y hay un plan acordado, créalo desde `<plan-vivo path>\ejemplos\plan-inicial.json`, con `"schema_version": 1` y el formato de `<plan-vivo path>\schema\plan.schema.json`.
- Cada prompt empieza con su identificador ("F1 · P2: ..."). Lo que aparezca sin planear se agrega como item `unplanned` en la fase donde ocurrió.
- Al cerrar cada prompt, actualiza a mano:
  - del item: `status`, `summary` (una línea), `steps` (lista corta), `files_changed` y `notes`;
  - de la raíz: `updated_at`.

  Las fases no llevan `status`.
- Los comandos se corren desde el kit, apuntando a este plan con `--plan`:
  - `pnpm --dir <plan-vivo path> tiempos -- --plan <project path>\plan.json`: revisa la tabla de diferencias, los mensajes sin asignar y los commits fuera de tramo; luego aplica con el mismo comando y `--aplicar`;
  - `pnpm --dir <plan-vivo path> validar -- --plan <project path>\plan.json` después de editar el plan; si da error, corrígelo antes del commit;
  - `pnpm --dir <plan-vivo path> migrar -- --plan <project path>\plan.json` si validar avisa que falta `schema_version` o el kit cambió de versión: revisa los cambios y aplica con `--aplicar`.
- El `work_log` no se escribe a mano. Las excepciones van en `asignaciones.json`, junto a `plan.json`, nunca en el `work_log`.
- Cuando necesites que la persona haga algo (un comando, una confirmación, una decisión), pídelo con AskUserQuestion: es la señal de espera que reconoce el script.
- Visor: `pnpm --dir <plan-vivo path> visor -- --plan <project path>\plan.json` (http://localhost:5190). Un solo visor sirve todos los proyectos: si ya está abierto, el comando le suma este plan y muestra su dirección. No lo detengas ni levantes otro en otro puerto.
- Fallos o mejoras del kit: no los arregles aquí ni copies el kit a este proyecto. Anótalos en `<plan-vivo path>\PENDIENTES.md`, con el formato fijo del archivo (fecha, proyecto de origen, qué pasa, cómo reproducirlo, prioridad), avisa en una línea y sigue con tu trabajo.
