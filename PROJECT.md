# Visualizador de Agentes — PROJECT.md

Documento maestro del proyecto. Registra contexto, decisiones con su razón, avances, problemas y próximos pasos. Se actualiza en cada avance relevante.

## Contexto

Visualizador para personas que trabajan con varios agentes de IA a la par, en varios proyectos. Muestra a cada agente como un personaje en una oficina estilo videojuego (pixel art) para ver de un vistazo qué hace, a quién espera, cuánto trabaja y cuándo necesita intervención, en la PC y en el celular.

- **Base:** claude-office de Paul Robello (licencia MIT), versión 0.24.1, commit `3522c16`. Repositorio original: https://github.com/paulrobello/claude-office
- **Stack heredado:** backend FastAPI (Python 3.13, uv), frontend Next.js + PixiJS + Zustand, hooks de Claude Code en Python.
- **Repositorio propio:** `wx-quevedo/visualizador-agentes` (privado). Remoto `upstream` = claude-office original.
- **Carpeta de desarrollo:** `E:\visualizador-agentes`.
- **Versión de uso diario (no se toca):** `<project path>`, puertos 3000 (frontend) y 8000 (backend), con hooks instalados en las dos cuentas de Claude Code.
- **Gestión:** ClickUp, espacio VR Things, carpeta "Visualizador de Agentes" (listas Roadmap, Problemas y errores, Investigación).
- **Documentos de diseño:** `docs/proyecto/catalogo-estados.md` y `docs/proyecto/investigacion-herramientas.md`.

## Entorno

- Windows, PowerShell y Git Bash. `make` instalado (ezwinports). Node 24, uv 0.11, Python 3.13 vía uv.
- Dos cuentas de Claude Code: personal en `C:\Users\<user>\.claude` (extensión de VS Code) y Demo Org en `C:\Users\<user>\.claude-demo` (CLI en la terminal de VS Code del proyecto vive-demo).
- Acceso desde el iPhone por Tailscale: IP de la PC `<TAILSCALE_IP>`.

## Decisiones

| Fecha | Decisión | Razón |
| --- | --- | --- |
| 2026-10-09 | Partir de claude-office | Ya funciona con las dos cuentas y el iPhone; su Command Center junta todas las sesiones en una oficina |
| 2026-10-09 | Repositorio privado propio, no fork | GitHub no permite forks privados de repos públicos; se conserva el remoto `upstream` para traer cambios a mano |
| 2026-10-09 | Desarrollar en `E:\visualizador-agentes`, separado de `<project path>` | Si algo se rompe en desarrollo, la oficina diaria sigue funcionando |
| 2026-10-09 | Pixel art durante el desarrollo; cambio de estilo al final | Con la base pixel se avanza más rápido; los estados se definen por lo que pasa, no por el dibujo |
| 2026-10-09 | El agente es el protagonista (gráfico más grande); subagentes discretos | La forma de trabajo prioriza al agente principal; no todas las tareas usan subagentes |
| 2026-10-09 | Todo en una oficina, con opción en configuración para separar por proyecto | Evita cambiar de pestaña entre proyectos |
| 2026-10-09 | Mostrar a quién espera el agente (a ti, a un programa, a una subida, a otros agentes) | Ninguna herramienta revisada lo hace; es el diferencial del proyecto |
| 2026-10-09 | Cuando el usuario se desconecta, el avatar descansa; al volver, regresa al trabajo | Da vida a la oficina y deja claro quién sigue esperando |
| 2026-10-09 | Alertas con sonido y notificación del sistema (PC y celular) | claude-office solo avisa dentro de la página |
| 2026-10-09 | Autoskills: frontend-design, python-testing-patterns y fastapi-python | Cubren interfaz y backend; python-executor descartada por advertencia de seguridad |
| 2026-10-09 | Versionar frontend/AGENTS.md y frontend/CLAUDE.md | Guías de Next.js 16.3 útiles para el agente |
| 2026-10-09 | Las 6 vulnerabilidades de npm quedan registradas para después | Herramienta local; no bloquea |
| 2026-10-09 | "Espera un programa" = comando de más de 30 s | Evita cambios de estado a cada rato |
| 2026-10-09 | "Desconectado" = sin la oficina abierta y 10 min sin responder a ningún agente | Se puede medir sin instalar nada más |
| 2026-10-09 | Subagentes como un número sobre el agente | No quitan protagonismo al agente |
| 2026-10-09 | Descanso: videojuego, lectura y siesta, rotando | Variedad sin distraer de los que esperan |
| 2026-10-09 | Tamaño del agente: el doble del actual | El agente es lo principal |
| 2026-10-09 | Cambio de enfoque: de claude-office se conservan los hooks, el backend, el registro de sesiones y el WebSocket; el lienzo se construye desde cero. La vista actual queda como "vista clásica" y no se toca | Validar primero, con datos en bruto, que los eventos alcanzan para el catálogo de estados; los gráficos se diseñan después sobre datos confiables |

## Ajustes heredados de la instalación diaria

Hechos en `<project path>` el 2026-10-09 y trasladados a este repositorio en el commit inicial:

- `backend/app/core/path_utils.py`: aceptar transcripciones en `~/.claude-demo` además de `~/.claude`.
- `hooks/src/claude_office_hooks/main.py`: leer el stdin del hook en UTF-8 (tildes correctas en Windows).
- `backend/app/api/middleware.py` y `backend/app/api/websocket.py`: aceptar clientes y orígenes de Tailscale (`100.64.0.0/10`).
- `frontend/next.config.ts`: `allowedDevOrigins` con `<TAILSCALE_IP>`.
- `frontend/src/utils/api.ts` y `frontend/src/hooks/useFloorConfig.ts`: el backend se busca en el mismo host desde el que se abre la página.

## Registro

| Fecha | Avance |
| --- | --- |
| 2026-10-09 | claude-office instalado y funcionando con ambas cuentas, en PC e iPhone (Tailscale) |
| 2026-10-09 | Investigación de herramientas similares y catálogo de estados del avatar (en `docs/proyecto/`) |
| 2026-10-09 | Creación del repositorio propio a partir de claude-office |
| 2026-10-09 | Commit inicial `7dcaffb`: base claude-office 0.24.1 (`3522c16`) con los 5 ajustes locales, PROJECT.md y `docs/proyecto/` |
| 2026-10-09 | Puertos configurables (`BACKEND_PORT`, `FRONTEND_PORT`, `NEXT_PUBLIC_BACKEND_PORT`) y `make dev-local` en 3100/8100, con resúmenes IA desactivados. Probado junto a la oficina diaria con el escenario `complex`. Commit `b690783` |
| 2026-10-09 | Registro de decisiones del catálogo de estados, `frontend/AGENTS.md` y `frontend/CLAUDE.md` versionados. Autoskills sin instalar: la herramienta no permite elegir skills sueltas sin terminal interactiva. Commit `ffdd9aa` |
| 2026-10-09 | Fase 1 "el agente como protagonista": boss al doble de tamaño en oficina y Command Center (escritorio, alfombra, colas, obstáculos y basurero recolocados); subagentes como número sobre el agente; opción "Mostrar subagentes como personajes" en Ajustes (apagada por defecto). Skills de autoskills reunidas en `.agents/skills` y `.claude/skills` de la raíz. Commit `a786511` |
| 2026-10-09 | Motor de estados del catálogo (`backend/app/core/agent_state_engine.py`), endpoint `GET /api/v1/agents/state` y página sin estilos `/datos`. Probado con el simulador y con los eventos reales de las dos cuentas (copia de `visualizer.db`). Skills de autoskills fuera de git (hash en el registro del commit siguiente) |

## Cómo levantar

Copia de desarrollo en 3100 (frontend) y 8100 (backend), en paralelo a la oficina diaria de `<project path>` en 3000/8000. Comandos para Git Bash:

```bash
cd /e/visualizador-agentes

# Solo la primera vez: dependencias (NO instala hooks en Claude)
make install

# Solo la primera vez: configuración local (no se versiona)
cp backend/.env.example backend/.env           # CORS para 3100 y SUMMARY_BACKEND=disabled
cp frontend/.env.example frontend/.env.local   # NEXT_PUBLIC_BACKEND_PORT=8100

# Levantar backend (8100) y frontend (3100); Ctrl+C para detener
make dev-local
```

Verificar y generar agentes simulados (en otra terminal):

```bash
curl http://localhost:8100/health
CLAUDE_OFFICE_API_URL=http://localhost:8100/api/v1/events uv run python scripts/simulate_events.py complex
```

Abrir http://localhost:3100 (desde el iPhone: http://<TAILSCALE_IP>:3100).

- No usar `make install-all`, `make hooks-install` ni `make opencode-install`: instalan hooks y plugins en las cuentas reales.
- `make dev` en esta carpeta usa 3000/8000 y choca con la oficina diaria; usar siempre `make dev-local`.
- Los puertos se cambian con `make dev-local DEV_BACKEND_PORT=... DEV_FRONTEND_PORT=...` (y `NEXT_PUBLIC_BACKEND_PORT` en `frontend/.env.local`).
- El log del backend imprime el enlace con `?token=` usando 3000/8000; en desarrollo, cambiar el puerto a 3100 a mano.
- En Windows usar `127.0.0.1` en lugar de `localhost` para scripts que hagan muchas peticiones: `localhost` prueba primero IPv6 y tarda unos 2 s por petición.

Datos en bruto del motor de estados: http://localhost:3100/datos (se actualiza cada 2 s) o `curl http://127.0.0.1:8100/api/v1/agents/state`.

Skills de autoskills (no se versionan: `.agents/`, `skills-lock.json` y sus enlaces en `.claude/skills/` están en `.gitignore`). Para reinstalarlas, desde una terminal interactiva (el selector no funciona sin terminal y, sin ella, instala todas las sugeridas):

```bash
cd /e/visualizador-agentes
npx autoskills -a claude-code    # dejar marcadas: frontend-design, python-testing-patterns, fastapi-python
cd frontend
npx autoskills -a claude-code    # dejar marcadas: vitest, react-best-practices, next-best-practices
```

Las de `frontend/` quedan en `frontend/.agents` y `frontend/.claude`; para usarlas desde la raíz, mover `frontend/.agents/skills/<nombre>` a `.agents/skills/` y crear en `.claude/skills/<nombre>` una unión de directorio (`New-Item -ItemType Junction`), porque los enlaces simbólicos piden administrador en Windows.

## Motor de estados

`backend/app/core/agent_state_engine.py` calcula, por sesión activa, el estado del catálogo (`docs/proyecto/catalogo-estados.md`) a partir de los eventos que ya recibe el backend, sin depender de la vista clásica. Se recalcula cada segundo.

- Umbrales (segundos, configurables en `backend/.env`): `STATE_PROGRAM_WAIT_SECONDS=30` (espera un programa), `STATE_IDLE_SECONDS=300` (inactivo), `STATE_PRESENCE_WINDOW_SECONDS=600` (presencia por encargo reciente), `STATE_REST_AFTER_DISCONNECT_SECONDS=600` (descanso), `STATE_PROMPT_SECONDS=3` (recibe encargo), `STATE_TURN_DONE_SECONDS=10` (terminó el turno, luego te espera respuesta), `STATE_RETURN_SECONDS=5` (regresa al trabajo), `STATE_EXIT_VISIBLE_SECONDS=120` (se va), `STATE_SESSION_MAX_AGE_HOURS=24`.
- Comandos de red ("espera una subida o descarga"), en Bash o PowerShell: `git push/pull/fetch/clone`, `scp`, `rsync`, `sftp`, `docker`/`podman push/pull`, `eas submit/build/update`, `npm`/`pnpm`/`yarn publish`, `gh release upload/download`, `curl -T`/`--upload-file`, `curl -o`/`-O` (descarga), `wget`, `aws s3 cp/sync/mv`, `gsutil cp/rsync`, `rclone copy/sync/move`, `huggingface-cli`/`hf upload/download`, `firebase`/`vercel`/`netlify deploy`.
- Herramientas → estado: `Read`, `Grep`, `Glob`, `LS`, `NotebookRead`, `ToolSearch`, `Skill` = 4; `Edit`, `Write`, `MultiEdit`, `NotebookEdit` = 5; `Bash`, `PowerShell`, `BashOutput`, `KillShell`, `TaskOutput`, `TaskStop`, `Monitor` = 6; `WebSearch`, `WebFetch` = 7; `mcp__*` = 8; `TodoWrite`, `TaskCreate`, `TaskUpdate`, `TaskList`, `TaskGet`, `EnterPlanMode` = 9; `AskUserQuestion`, `ExitPlanMode` = 14 (te espera respuesta); otras = 3.
- Presencia: "conectado" si hay un navegador en cualquier WebSocket o un `UserPromptSubmit` en los últimos 10 min. El descanso exige 10 min desde la última evidencia del usuario (último navegador visto o último encargo); como antes de arrancar el backend no se sabe, la hora de arranque cuenta como evidencia.
- Interpretaciones propias: después de un `PostToolUse` el agente está "pensando" (3); `Stop` muestra 11 durante 10 s y luego 14; un agente que espera (13 a 17) no pasa a inactivo ni a descansar; una herramienta sin `PostToolUse` se da por terminada si el agente principal inicia otra más de 2 s después; los `cleanup` que genera el backend no cuentan como actividad; un subagente que termina después de `Stop` no saca al agente de "te espera".

## Problemas y soluciones

| Problema | Solución |
| --- | --- |
| Sesiones abiertas antes de instalar los hooks no aparecían | La página solo lista sesiones con `session_start`; aparecen al abrir una sesión nueva |
| Tildes rotas en el registro de eventos | El hook leía stdin en cp1252; se lee en UTF-8 |
| Transcripciones de la cuenta de Demo Org rechazadas | Se agregó `~/.claude-demo` a las rutas permitidas |
| iPhone bloqueado con 403 | El backend solo aceptaba localhost; se agregó el rango de Tailscale |
| iPhone cargaba la página sin datos | Next.js en modo desarrollo bloqueaba sus recursos; se agregó `allowedDevOrigins` |
| La PC dependía de Tailscale para ver la oficina | El frontend usa el host de la página para buscar el backend |
| En Windows, la recarga del backend detiene el frontend | Pendiente: reiniciar `make dev` tras cambios de código del backend |
| En Windows, la recarga automática del backend a veces se traba y sigue respondiendo el proceso viejo | Detener 3100/8100 y volver a `make dev-local` |
| Peticiones a `localhost` tardan unos 2 s en Windows | `localhost` prueba IPv6 primero y uvicorn solo escucha IPv4; usar `127.0.0.1` |
| El hook no envía `PostToolUseFailure`: no hay datos de errores y una herramienta fallida queda sin cierre | Pendiente: mapear `PostToolUseFailure` en los hooks; el motor cierra la herramienta cuando empieza otra y devuelve `errores_seguidos = null` con el motivo |
| El hook marca como `agent_id="main"` las herramientas que usan los subagentes | Pendiente: enviar el `agent_id` real del subagente desde el hook |
| Transcripciones de más de 50 MB (vive-demo 428 MB, SkyNest 75 MB): token_tracker no las lee | El motor devuelve tokens en `null` con el motivo; pendiente leer solo la cola del archivo para los tokens |
| `Stop` sin nuevo encargo = "te espera respuesta" para siempre: un agente que terminó nunca descansa | Pendiente decidir si "te espera respuesta" requiere una pregunta explícita (notificación de inactividad o `AskUserQuestion`) |
| Sesiones sin `SessionEnd` (cerradas a la fuerza) quedan activas hasta 24 h, con sus subagentes | Pendiente: dar por terminados los subagentes sin actividad, como hace la vista clásica |
| Next.js 16.3 genera `frontend/AGENTS.md` y `frontend/CLAUDE.md` al arrancar | Se versionan (decisión 2026-10-09) para que `next dev` no los vuelva a dejar como cambios sueltos |
| `npm install` del frontend reporta 6 vulnerabilidades (5 altas, 1 crítica) | Pendiente: revisar con `npm audit`; herramienta local, no bloquea |
| autoskills no permite elegir skills sueltas por línea de comandos; sin terminal interactiva instala todas las sugeridas | Washington las instaló con el selector interactivo; las de `frontend/` se movieron a la raíz (Windows pide administrador para enlaces simbólicos, se usaron uniones de directorio) |
| Command Center con agentes al doble: solo caben 2×2 puestos por columna (antes 2×4) | Los demás se resumen en "+N más"; revisar si hace falta más capacidad |

## Próximos pasos

1. Resolver los pendientes del motor de estados (errores de herramientas, `agent_id` de subagentes, tokens de transcripciones grandes, cuándo "te espera respuesta").
2. Construir el lienzo nuevo sobre `GET /api/v1/agents/state`, dejando la vista clásica intacta.
3. Avisos (sonido y notificación del sistema) y app móvil con notificaciones.
