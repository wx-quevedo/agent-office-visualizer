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
| 2026-10-10 | Estado 14 "Te espera: respuesta" solo con pregunta explícita (`AskUserQuestion`/`ExitPlanMode` pendiente o último mensaje del asistente que termina en "?"); si no, `Stop` lleva a 11 y tras 5 min a 18 o 19 | Un agente que terminó sin preguntar no te está esperando |
| 2026-10-10 | Descanso: 10 min desde la última señal del usuario; un reinicio del backend lo atrasa | Se acepta la interpretación del motor |
| 2026-10-10 | Un subagente sin actividad por 30 min se da por terminado (`STATE_SUBAGENT_EXPIRY_SECONDS`) | Evita subagentes eternos en sesiones cerradas a la fuerza |
| 2026-10-10 | El hook envía cada evento a la oficina diaria (8000) y a la de desarrollo (8100) | La copia de desarrollo ve la actividad real sin instalar otro hook |
| 2026-10-10 | Todo cambio al hook debe ser compatible con la oficina diaria (`<project path>`), que usa el mismo `claude-office-hook` | Un solo comando instalado sirve a las dos oficinas |
| 2026-10-10 | Un agente cuya sesión de Claude Code se cerró no está activo: pasa a 21 "Cerrado" aunque tenga una pregunta pendiente, que se guarda como dato | Una sesión cerrada no puede esperar a nadie |
| 2026-10-10 | Al reabrir una sesión cerrada vuelve al trabajo (20) y, si su pregunta seguía sin respuesta, pasa a 14 | La pregunta sigue vigente al volver |
| 2026-10-10 | La espera de los destinos extra del hook baja de 0,1 s a 0,08 s | Más margen para el tiempo del hook |
| 2026-10-10 | Sesiones sin PID: se dan por cerradas tras 1 h sin eventos (antes 24 h) | Desde el hook nuevo toda sesión viva envía PID |
| 2026-10-10 | El motor tiene su propio registro de eventos (`backend/agent_events.db`), independiente de la base heredada, que queda solo para la vista clásica. No se corrige la carrera de `_persist_event` | La base heredada pierde eventos en ráfagas; el motor no puede depender de ella |
| 2026-10-10 | Subagentes sin límite de tiempo: siguen activos hasta su `SubagentStop`, el `Stop` del agente principal o la muerte del proceso (reemplaza la expiración de 30 min) | Un subagente real puede durar mucho más; la expiración los cerraba antes de tiempo |
| 2026-10-10 | Pregunta explícita: el último párrafo del mensaje contiene una pregunta (no solo el último carácter); AskUserQuestion y ExitPlanMode son 14 aunque lleguen como pedido de permiso | Claude suele preguntar y después dar las opciones; la prueba en vivo lo mostró |
| 2026-10-10 | Toda prueba contra el backend de desarrollo usa `session_id` con prefijo `prueba-` y se borra al terminar (`scripts/borrar_sesiones_prueba.py`) | El listado no debe mostrar sesiones falsas |
| 2026-10-10 | Primera versión de la oficina en componentes React con cajas; el motor de dibujo se elige al pasar a pixel art | Validar agrupación, orden y textos sin comprometer la técnica de dibujo |
| 2026-10-10 | "Tokens totales" = tokens de salida desde el primer evento de la sesión que vio el motor (una vez por id de mensaje) | Sumar la creación de caché y la historia de una conversación retomada inflaba el número (97,5 M en 164 min) |
| 2026-10-10 | Tener `/oficina` abierta (PC o celular) cuenta como presencia, con un latido cada 30 s que vence a los 75 s; `/datos` no cuenta | La oficina es la pantalla que Washington mira; el celular no usa el WebSocket |
| 2026-10-10 | Avisos con voz y notificaciones del navegador desde /oficina, como módulo independiente para reutilizar en la escena 3D | Washington necesita enterarse de permisos y preguntas sin mirar la pantalla; la escena 3D usará el mismo `useAvisos` |
| 2026-10-10 | Estilo visual: escena 3D basada en Agent Office 3D (MIT), sin pixel art; personajes intercambiables por GLB más adelante | Washington eligió esa escena como base; los modelos GLB con animaciones de Mixamo quedan para el prompt 3 del port |
| 2026-10-10 | La distribución de la oficina se guarda en el repo (`frontend/public/oficina3d/distribucion.json`) | Versionada y igual en PC y celular; el editor de muebles se portará después |
| 2026-10-10 | Etiquetas 3D: solo dicen lo que la postura no muestra (caminando = libre, sentado = trabajando); sin "Inactivo" ni similares. Libre: solo el proyecto; trabajando: proyecto y actividad corta; te espera: "Te pide permiso" o "Te preguntó" con borde oscuro; "Con errores" si hay errores seguidos | Menos texto en la escena; la postura ya comunica si trabaja |
| 2026-10-10 | Cuentas: la personal no lleva marca; la de Demo Org lleva el isotipo (`frontend/public/logos/isotipo-demo.png`, ~16 px) en la etiqueta 3D y en los escritorios de `/oficina`, y el logo completo (`logo-demo.png`) solo donde hay espacio (detalle). "Demo Org" como texto solo en tooltips y `alt` | Se distingue la cuenta sin texto extra |
| 2026-10-10 | Voces: Washington usará las voces de Google en Chrome (no Edge) | En Edge y en Playwright solo aparecen voces de Microsoft de España; pendiente buscar mejores voces o un sistema de lectura |

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
| 2026-10-09 | Motor de estados del catálogo (`backend/app/core/agent_state_engine.py`), endpoint `GET /api/v1/agents/state` y página sin estilos `/datos`. Probado con el simulador y con los eventos reales de las dos cuentas (copia de `visualizer.db`). Skills de autoskills fuera de git. Commit `5a77aa6` |
| 2026-10-10 | Espera explícita (14 solo con pregunta), tokens leídos de la cola de la transcripción (sin límite de tamaño), expiración de subagentes a los 30 min, errores seguidos con `PostToolUseFailure` y herramientas atribuidas al subagente. Hook: `PostToolUseFailure`, `tool_agent_id`, `notification_type`, `last_assistant_message`, envío en paralelo a 8000 y 8100 (`CLAUDE_OFFICE_EXTRA_API_URLS`) y `127.0.0.1` en lugar de `localhost`. Hook reinstalado y registrado en las dos cuentas. Commit `d81492e` |
| 2026-10-10 | Estado 21 "Cerrado" (por `SessionEnd`, por proceso de Claude Code terminado o sin PID tras 24 h), pregunta pendiente guardada, reapertura (20 y luego 14), sesiones cerradas fuera de la presencia. Hook: PID y hora de creación del proceso de Claude Code en cada evento, espera extra de 0,08 s. Probado con un proceso de prueba: 21 a los 14 s del cierre. Commit `64802c5` |
| 2026-10-10 | Registro propio de eventos del motor (SQLite en WAL, solo agregado, un único escritor en orden de llegada), arranque desde ese registro, importación inicial única desde la base heredada, retención de 7 días y cierre sin PID a 1 h. Ráfaga de 2 000 eventos: 2 000 en el registro propio frente a 520 en la base heredada; tras reiniciar, estados, esperas y preguntas coinciden. Commit `a2793fd` |
| 2026-10-10 | Prueba en vivo de Washington con `/datos` (sesión 8f5f7ede en `E:\Test\prueba-visualizador`, cuenta personal, y 5f41c31c de vive-demo, cuenta demo): funcionaron aparición de sesiones, Write, ping de 46 s, error en Read (errores seguidos 1 y luego 0), cierre de ventana (21 `proceso_terminado` en ~15 s), retomar la conversación (PID nuevo, cierre borrado) y la cuenta demo. Correcciones: AskUserQuestion/ExitPlanMode como 14, pregunta en el último párrafo, texto del encargo sin bloques inyectados, conciliación con la transcripción, subagentes sin límite de tiempo, PID con el ejecutable renombrado por la actualización (hook; Washington lo reinstaló el 2026-10-10 a las 11:06), sesiones de prueba borradas y script `scripts/borrar_sesiones_prueba.py`, tokens totales acumulados. Commit `ad1b144` |
| 2026-10-10 | Página `/oficina` v1 en cajas (blanco, grises y negro, IBM Plex Sans y Mono): vista por urgencia (te esperan, trabajando, inactivos y descanso, cerrados), vista por proyecto (una sala por carpeta), detalle por agente (`/oficina?agente=<session_id>`) y celular (< 700 px, una columna). Latido de presencia `POST /api/v1/agents/presence` cada 30 s (PC o celular); "Tokens totales" pasa a ser tokens de salida desde que la sesión llegó al motor (la sesión de Demo Org 5f41c31c bajó de 97,5 M a ~0,38 M). Capturas en `docs/capturas/oficina-v1/`. Commit `3ce9936` |
| 2026-10-10 | Estudio de Agent Office 3D (thomasarisu.agent-office, MIT) en `E:\referencias\agent-office`, fuera del repositorio; plan de port en 3 prompts aprobado por Washington. Sin commit |
| 2026-10-10 | Avisos con voz y notificaciones de Windows desde `/oficina` (`frontend/src/components/avisos/`): te pide permiso (13), te hizo una pregunta (14), terminó (11), recordatorio cada 2, 5 o 10 min mientras espera, cerrado con pregunta (21, apagado por defecto); panel con interruptores, voz en español, velocidad, volumen, sonido y pruebas. Captura en `docs/capturas/avisos-v1/`. Commit `cd06200` |
| 2026-10-10 | Prompt 1 del port de Agent Office 3D: escena 3D en `/oficina/3d` (`frontend/src/components/oficina3d/`, código MIT adaptado) con los agentes reales del motor, puestos estables por sesión, etiquetas con proyecto, cuenta y estado, más datos al pasar el mouse, clic al detalle de `/oficina`, barra propia en tema claro con contadores, "Vista de cajas" y Avisos (mismo `useAvisos`), latido de presencia, distribución desde `frontend/public/oficina3d/distribucion.json`, modo celular (calidad baja, sin sombras, cámara a lo largo). three 0.185.1, @react-three/fiber 9.8.1 y @react-three/drei 10.7.8 solo en el chunk de `/oficina/3d`. Capturas en `docs/capturas/oficina3d-v1/`. Commit `543ec55` |
| 2026-10-10 | Prompt 2 del port de Agent Office 3D: capa de comportamiento (`oficina3d/comportamiento.ts`) separada del estado; 13 alza un brazo, 14 globo con la pregunta y mira a la cámara, 19 va a la sala de descanso y se sienta en el sofá (4 lugares; los demás de pie cerca), 1 y los agentes nuevos entran por la puerta oeste, 12 y los que se cierran salen por ella, 15 reloj de arena y 16 barra de progreso dibujados sobre el monitor, 21 con pregunta deja una nota en su escritorio (sin pregunta, el escritorio queda reservado una hora). Etiquetas simples (libre = solo el proyecto, trabajando = actividad corta, te espera = borde oscuro, con errores). Isotipo y logo de Demo Org (`frontend/public/logos/`) en la escena 3D y en `/oficina`; sin texto "personal". Capturas en `docs/capturas/oficina3d-v2/` (hash en el registro del commit siguiente) |

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

- Umbrales (segundos, configurables en `backend/.env`): `STATE_PROGRAM_WAIT_SECONDS=30` (espera un programa), `STATE_IDLE_SECONDS=300` (inactivo), `STATE_PRESENCE_WINDOW_SECONDS=600` (presencia por encargo reciente), `STATE_REST_AFTER_DISCONNECT_SECONDS=600` (descanso), `STATE_PROMPT_SECONDS=3` (recibe encargo), `STATE_RETURN_SECONDS=5` (regresa al trabajo), `STATE_RECONCILE_AFTER_SECONDS=120` (conciliación con la transcripción), `STATE_PROCESS_CHECK_SECONDS=30` (revisión del proceso de Claude Code), `STATE_NO_PID_CLOSE_HOURS=1` (cierre de sesiones sin PID), `STATE_EVENT_LOG_LOAD_HOURS=24` (sesiones que se cargan al arrancar), `STATE_EVENT_LOG_RETENTION_DAYS=7` (retención del registro), `STATE_EVENT_LOG_PATH` (por defecto `backend/agent_events.db`), `STATE_EXIT_VISIBLE_SECONDS=120` (se va), `STATE_SESSION_MAX_AGE_HOURS=24`.
- Comandos de red ("espera una subida o descarga"), en Bash o PowerShell: `git push/pull/fetch/clone`, `scp`, `rsync`, `sftp`, `docker`/`podman push/pull`, `eas submit/build/update`, `npm`/`pnpm`/`yarn publish`, `gh release upload/download`, `curl -T`/`--upload-file`, `curl -o`/`-O` (descarga), `wget`, `aws s3 cp/sync/mv`, `gsutil cp/rsync`, `rclone copy/sync/move`, `huggingface-cli`/`hf upload/download`, `firebase`/`vercel`/`netlify deploy`.
- Herramientas → estado: `Read`, `Grep`, `Glob`, `LS`, `NotebookRead`, `ToolSearch`, `Skill` = 4; `Edit`, `Write`, `MultiEdit`, `NotebookEdit` = 5; `Bash`, `PowerShell`, `BashOutput`, `KillShell`, `TaskOutput`, `TaskStop`, `Monitor` = 6; `WebSearch`, `WebFetch` = 7; `mcp__*` = 8; `TodoWrite`, `TaskCreate`, `TaskUpdate`, `TaskList`, `TaskGet`, `EnterPlanMode` = 9; `AskUserQuestion`, `ExitPlanMode` = 14 (te espera respuesta); otras = 3.
- Presencia: "conectado" si hay un navegador en cualquier WebSocket o un `UserPromptSubmit` en los últimos 10 min. El descanso exige 10 min desde la última evidencia del usuario (último navegador visto o último encargo); como antes de arrancar el backend no se sabe, la hora de arranque cuenta como evidencia.
- Pregunta explícita (14): `AskUserQuestion`/`ExitPlanMode` pendiente (aunque llegue como pedido de permiso), o `Stop` cuyo último párrafo contiene una pregunta (ver el ajuste más abajo). El texto sale de `last_assistant_message` del hook; con eventos viejos se lee de los últimos 256 KB de la transcripción.
- Tokens: uso del último mensaje leído de los últimos 256 KB de la transcripción (`backend/app/core/transcript_tail.py`), sin límite de tamaño total; solo se relee si el archivo cambió de tamaño.
- Errores seguidos: `PostToolUseFailure` consecutivos (las interrupciones del usuario no cuentan); vuelve a 0 con un `PostToolUse`. Si la sesión viene de un hook sin `reports_tool_failures`, devuelve `null` con el motivo.
- Subagentes: el hook manda `tool_agent_id`/`tool_agent_type` (el `agent_id` de Claude Code) en cada evento de herramienta de un subagente; el motor no las toma como del agente principal.
- Interpretaciones propias: después de un `PostToolUse` el agente está "pensando" (3); las notificaciones (salvo las de permiso) no cambian el estado; un agente que espera (13 a 17) no pasa a inactivo ni a descansar; una herramienta sin cierre se da por terminada si el agente principal inicia otra más de 2 s después; los `cleanup` que genera el backend no cuentan como actividad; un subagente que termina después de `Stop` no cambia el estado.
- Cierre (21): `SessionEnd` muestra 12 "Se va" durante 2 min y luego 21; si el proceso de Claude Code registrado (PID + hora de creación) ya no existe, 21 en la siguiente revisión (cada 30 s); sin PID, 24 h sin eventos (`sin_pid_antiguo`). El JSON trae `cierre` (`motivo`, `desde`), `pregunta_pendiente` y `proceso`. Un agente cerrado sigue visible 24 h desde el cierre. Cualquier evento posterior al cierre (o de un proceso nuevo) lo reabre: 20 y luego su estado, o 14 si su pregunta seguía sin respuesta. Las sesiones cerradas no cuentan para la presencia.
- Registro propio (`backend/app/core/agent_event_store.py`, archivo `backend/agent_events.db`, ignorado por git): tabla de solo agregado con id, sesión, tipo, hora del evento, hora de recepción, origen (`hook`, `poller`, `importacion`) y el JSON completo. Los eventos del hook entran en la ruta `POST /api/v1/events`, en orden de llegada y antes del pipeline clásico; los sondeados de transcripciones, en `_handle_polled_event`. Un único hilo escritor guarda en lotes (WAL); si falla, registra el error y el motor sigue en memoria. Al arrancar: borra lo que tenga más de 7 días, y carga completas las sesiones con eventos en las últimas 24 h; si el registro está vacío, importa una sola vez esas sesiones desde la base heredada y lo anota en el log. Un cierre forzado del backend puede perder lo que estaba en la cola en ese instante (milisegundos).
- Pregunta explícita (ajuste 2026-10-10): `Stop` cuenta como pregunta si el último párrafo del mensaje contiene "?" o "¿" (sin URLs ni código), porque Claude suele preguntar y luego dar las opciones ("¿Qué hago? Puedo buscarlo, crearlo o dejarlo así."). AskUserQuestion y ExitPlanMode llegan como `permission_request` + notificación de permiso, pero son preguntas: 14 con la pregunta como pendiente, no 13.
- Subagentes (ajuste 2026-10-10): siguen activos hasta su `SubagentStop`, el `Stop` del agente principal o la muerte del proceso, sin límite de tiempo. Se ignoran los `SubagentStop`/`cleanup` sintéticos del sondeo de transcripciones de la vista clásica (origen `poller`, se disparaban por inactividad).
- Conciliación: sesiones abiertas en un estado de trabajo o espera (herramienta sin cierre, pensando) sin eventos por 2 min se comparan con la cola de su transcripción (al arrancar y cada 30 s). Si la herramienta tiene su `tool_result`, si es más vieja que todo lo que hay en la cola mientras la transcripción muestra actividad posterior, o si el turno terminó (`end_turn`), se actualiza el estado y se anota en `conciliado`. No se agrega ningún evento al registro.
- Texto del encargo: se quitan los bloques inyectados (`<browser_instruction>`, `<system-reminder>`, `<ide_selection>`…). Si no queda texto (el hook anterior recortaba a 50 caracteres antes de limpiarlos), se busca en la transcripción el mensaje del usuario de esa hora (hasta 30 intentos, uno por segundo). La misma búsqueda reintenta la pregunta de un `Stop` que llega sin texto.
- Tokens totales (ajuste de `/oficina`): suma, una vez por id de mensaje, los tokens de salida de los mensajes escritos desde el primer evento de la sesión que vio el motor, leída de forma incremental en segundo plano. No se suma la entrada: la creación de caché vuelve a escribir el mismo contexto cada vez que el caché vence o hay compactación, y una conversación retomada trae semanas de historia. Revisión de 5f41c31c (Demo Org): la transcripción va del 29-08 al 10-10, 17 357 mensajes únicos (16 597 líneas repetidas ya se descartaban, 62 compactaciones); salida 16,4 M, entrada 0,03 M y creación de caché 81,1 M = 97,5 M. Desde su llegada al motor (09-10 19:42): ~0,38 M de salida. Tokens por minuto sale del mismo acumulado. Tokens en el contexto: uso del último mensaje.
- Presencia por `/oficina`: la página manda `POST /api/v1/agents/presence` con `{cliente, dispositivo}` al abrir y cada 30 s (`celular` si el ancho es menor a 700 px o el user agent es de móvil). El motor cuenta cada cliente con latido en los últimos 75 s como navegador conectado y publica `presencia.dispositivos` (`pc`, `celular`, `navegador` para el WebSocket). No requiere clave.
- Sesiones de prueba: toda prueba contra el backend de desarrollo usa `session_id` con prefijo `prueba-` y al terminar se borran con `cd backend && uv run python ../scripts/borrar_sesiones_prueba.py` (con el backend detenido; acepta otros prefijos).

## Oficina v1 (`/oficina`)

Cajas sin arte (`frontend/src/components/oficina/`): `logica.ts` (agrupación, orden, regla de cerrados; probada en `frontend/tests/oficina.test.ts`), `Oficina.tsx` y `oficina.module.css`. Lee `GET /api/v1/agents/state` cada 2 s. La vista elegida se recuerda en `localStorage` (`oficina-vista`).

- Por urgencia, en este orden: Te esperan (13, 14), Trabajando (1 a 10, 12, 15, 16, 17), Inactivos y en la sala de descanso (11, 18, 19, 20), Cerrados (21). Dentro de cada sección, primero el que más tiempo lleva en su estado.
- Contadores: Te esperan, Trabajando, Inactivos (11, 18), Descansando (19, 20), Cerrados.
- Por proyecto: una sala por carpeta del proyecto (última parte de la ruta). Primero las salas con agentes que te esperan, luego las que tienen agentes trabajando, luego el resto (por nombre). Dentro de la sala, el orden de urgencia y luego el tiempo en el estado.
- Cerrados: sin pregunta pendiente se muestran 1 h desde el cierre (`cierre.desde`) con la nota "Desaparece en N min" y luego se ocultan; con pregunta pendiente se quedan hasta que la sesión se reabre (sale del 21). El motor los sigue enviando 24 h.
- Detalle: `/oficina?agente=<session_id>` (el botón atrás del navegador vuelve). En celular ocupa toda la pantalla sin la lista lateral.
- Barra de esfuerzo: tokens de salida por minuto sobre una referencia de 3 000 tok/min.
- En desarrollo, abrir la página por `http://localhost:3100/oficina`: Next bloquea sus recursos de desarrollo para `127.0.0.1` (no está en `allowedDevOrigins`) y la página no se hidrata.

## Avisos (`frontend/src/components/avisos/`)

Módulo independiente de la vista: `deteccion.ts` (lógica pura, probada en `frontend/tests/avisos.test.ts`), `useAvisos.ts` (voz con `speechSynthesis`, sonido con Web Audio, notificaciones con la Notification API) y `PanelAvisos.tsx`. `/oficina` lo usa con el botón "Avisos"; la escena 3D usará el mismo hook.

- Detección en el cliente, comparando el estado anterior y el nuevo de cada agente (revisión cada segundo con los datos que llegan cada 2 s). Al cargar la página solo se registran los estados actuales; un agente que ya esperaba recibe su primer recordatorio un intervalo después.
- Un cambio avisa solo si el nuevo estado se mantiene 3 s; volver al estado anterior antes de eso no avisa. Enfriamiento de 30 s por agente y tipo de aviso. Las sesiones `prueba-` nunca avisan.
- Avisos: 13 "<proyecto> te pide permiso" (lee herramienta y comando, hasta 120 caracteres); 14 "<proyecto> te hizo una pregunta" (lee la pregunta sin código, URLs ni rutas, hasta 200); 11 sin pregunta "<proyecto> terminó" (solo voz salvo que se active la notificación); recordatorio "Sigue esperando: …" cada 2, 5 o 10 min mientras siga en 13 o 14; 21 con pregunta pendiente (apagado por defecto). Si dos agentes comparten proyecto se agrega la cuenta ("vive-demo, cuenta Demo Org").
- La voz va en cola (un aviso detrás de otro, sin cortarse), con un sonido corto opcional antes. Voz automática: es-MX, luego es-US, es-419 y cualquier es-*. El navegador solo deja hablar a la página después de un clic: tras recargar, la voz se habilita con el primer clic o tecla.
- Notificaciones con `tag` por agente (el recordatorio reemplaza la anterior); al hacer clic enfocan la pestaña y abren `/oficina?agente=<session_id>`. Solo funcionan en `localhost` o https (por la IP de Tailscale en http no hay notificaciones, solo voz).
- Configuración en `localStorage` (`oficina-avisos`).

## Oficina 3D (`/oficina/3d`)

Basada en Agent Office 3D (thomasarisu.agent-office v0.1.6, https://github.com/SaidislomSaidazimovv/agent-office, licencia MIT; aviso en `frontend/src/components/oficina3d/LICENSE-agent-office` y en `THIRD_PARTY_NOTICES.md`). Se copió solo la escena (`escena/`: personajes, avatar y movimiento, navegación, choques, presencia, decoración, puestos, recursos); se reemplazaron su store, i18n (8 idiomas) y layout por `store.ts`, `textos.ts` (español, `t(clave)` tipado) y `distribucion.ts`. Sin su extensión, CLI, tablero de costos, gira, botón "+ Agent", vista en primera persona ni editor de muebles.

- Ruta cargada solo en el navegador (`next/dynamic` con `ssr: false`): three, R3F y drei van en su propio chunk; `/oficina` y `/datos` no los cargan (comprobado midiendo los JS que descarga cada ruta del build estático).
- Capa de comportamiento (`comportamiento.ts`, probada en `frontend/tests/oficina3d.test.ts`): cada estado da destino (escritorio, pasear, sofá, salida), pose y distintivo del monitor. 1, 2, 3, 4, 7, 9, 10 → escritorio, pensando (mano al mentón); 5, 6, 8 → teclea; 13 → sentado con un brazo alzado mientras dure; 14 → sentado mirando a la cámara con un globo que muestra la pregunta (80 caracteres; completa al pasar el mouse); 15 → quieto con reloj de arena sobre el monitor; 16 → quieto con barra de progreso; 17 → teclea con ayudantes; 20 → vuelve caminando a su escritorio; 11 y 18 → pasea; 19 → sala de descanso, sentado en el sofá (2 sofás, 4 lugares; si hay más agentes, se quedan de pie cerca, asignados por número de escritorio); 12 → camina a la puerta de entrada (pared oeste) y desaparece; 21 → no aparece. Errores seguidos ≥ 1 en trabajo → con errores (tiembla); 13 y 14 tienen prioridad. Esperando 3 min o más → "Te espera hace rato".
- Llegada y salida (`adaptador.ts`): al cargar la página cada agente aparece en su lugar; los que aparecen después entran por la puerta y caminan a su escritorio. Un agente que pasa a 12 o se cierra (21) estando en escena camina a la puerta y desaparece; la escena lo marca como salido y deja de dibujarlo. Si se reabre, vuelve a entrar por la puerta. Nunca se teletransporta salvo en la primera carga; se levanta y se sienta con animación (y se desliza el último tramo al sofá).
- Escritorios de los cerrados (21): con pregunta pendiente, una nota de papel sobre el escritorio (al pasar el mouse, proyecto y pregunta), sin límite de tiempo; sin pregunta, el escritorio queda vacío y reservado una hora desde el cierre y luego se libera (misma regla que `/oficina`).
- Puestos estables: un agente conserva su escritorio mientras exista; uno nuevo toma el libre más bajo.
- Sin emojis: los emotes originales son distintivos de texto (Error, Te espera hace rato, Contexto lleno, Pensando mucho, Listo, Charlando). Contadores de la barra: Te esperan, Trabajando y Libres (antes "Inactivos").
- Tema claro: fondo gris claro y luz de día constante; el ciclo día/noche del original queda apagado (se fuerza con `?hour=N`).
- Etiquetas: contenedor fijo (`escena/capaEtiquetas.ts`) para los `<Html>` de drei; sin él, drei recreaba la raíz al montar la escena y la etiqueta de un agente desaparecía. La etiqueta del hover es un `<Html>` aparte con z-index alto (drei solo lo recalcula cuando algo se mueve).
- Lint: las reglas del React Compiler (`react-hooks/refs`, `immutability`, `purity`, `set-state-in-effect`) se apagan solo para `oficina3d/escena/**` y `Escena3D.tsx`, porque R3F modifica objetos de three y refs dentro de `useFrame`.
- @react-three/fiber 9.8.1 en lugar de 9.7.0 (la de la referencia): 9.7.0 pide React < 19.3 y el proyecto usa 19.3.0.
- Dependencias instaladas con npm (el Makefile usa npm si no hay bun, y `package-lock.json` está ignorado). `frontend/bun.lock` sigue sin las dependencias de three (three, @react-three/fiber, @react-three/drei, @types/three) porque bun no está instalado en esta PC: pendiente regenerarlo con `bun install` donde haya bun.

## Hook compartido (oficina diaria y desarrollo)

El comando `claude-office-hook` se instala una sola vez desde `E:\visualizador-agentes\hooks` (`uv tool install --force -p 3.14 E:\visualizador-agentes\hooks`) y lo usan las dos cuentas (`~/.claude` y `~/.claude-demo`).

- Destinos: `CLAUDE_OFFICE_API_URL` (por defecto la oficina diaria, `http://127.0.0.1:8000/api/v1/events`) y `CLAUDE_OFFICE_EXTRA_API_URLS` (lista separada por comas) en `C:\Users\<user>\.claude\claude-office-config.env`. Hoy: `http://127.0.0.1:8100/api/v1/events`.
- Envío en paralelo: espera hasta 0,25 s al destino principal y 0,08 s a los extra; un destino apagado se ignora sin error y el hook siempre termina con código 0.
- Tipos nuevos (`post_tool_use_failure`) solo van a los destinos extra; la oficina diaria los rechazaría con 422.
- Campos nuevos (`tool_agent_id`, `tool_agent_type`, `error`, `is_interrupt`, `last_assistant_message`, `reports_tool_failures`, `claude_pid`, `claude_pid_created`): la oficina diaria los ignora (comprobado: guarda el evento sin esos campos).
- Proceso de Claude Code (`hooks/src/claude_office_hooks/process_info.py`): el hook sube por sus ancestros con la API de Windows (`NtQueryInformationProcess` para el padre, `QueryFullProcessImageNameW` para el nombre, `GetProcessTimes` para la hora de creación) pasando por los intérpretes intermedios (`claude-office-hook.exe`, `bash`/`cmd`/`powershell`) hasta el primer `claude.exe` (instalación nativa) o `node.exe` (instalación por npm). Se detiene en `Code.exe`, `explorer.exe` o `WindowsTerminal.exe`, y si un padre es más nuevo que su hijo (PID reutilizado) devuelve `null`. Cuesta ~12 ms (importar ctypes) más ~0,5 ms.

### Cómo volver atrás

Respaldos del 2026-10-10 (junto a cada original): `settings.json.respaldo-2026-10-10-0737` en `C:\Users\<user>\.claude` y en `C:\Users\<user>\.claude-demo`, y `claude-office-config.env.respaldo-2026-10-10-0737` en `C:\Users\<user>\.claude`. En Git Bash:

```bash
cp /c/Users/<user>/.claude/settings.json.respaldo-2026-10-10-0737 /c/Users/<user>/.claude/settings.json
cp /c/Users/<user>/.claude-demo/settings.json.respaldo-2026-10-10-0737 /c/Users/<user>/.claude-demo/settings.json
cp /c/Users/<user>/.claude/claude-office-config.env.respaldo-2026-10-10-0737 /c/Users/<user>/.claude/claude-office-config.env
uv tool install --force -p 3.14 '<project path>\hooks'   # reinstala el hook original
```

Después, abrir sesiones nuevas de Claude Code para que tomen la configuración restaurada.

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
| El hook no enviaba `PostToolUseFailure`: no había datos de errores y una herramienta fallida quedaba sin cierre | Resuelto (2026-10-10): el hook lo mapea y lo envía solo a los destinos extra (la oficina diaria responde 422 a tipos que no conoce) |
| El hook marcaba como `agent_id="main"` las herramientas que usan los subagentes | Resuelto (2026-10-10): `agent_id` sigue en "main" por compatibilidad y el subagente va en `tool_agent_id`/`tool_agent_type` |
| Transcripciones de más de 50 MB (vive-demo 428 MB, SkyNest 75 MB): token_tracker no las lee | Resuelto en el motor (2026-10-10): lee la cola de 256 KB; la vista clásica sigue con el límite de token_tracker |
| `Stop` sin nuevo encargo = "te espera respuesta" para siempre | Resuelto (2026-10-10): 14 solo con pregunta explícita |
| Sesiones sin `SessionEnd` (cerradas a la fuerza) quedan activas hasta 24 h, con sus subagentes | Subagentes: resuelto (2026-10-10, expiran a los 30 min sin actividad); la sesión sigue visible hasta 24 h |
| El hook tardaba ≥0,5 s por evento: `localhost` prueba IPv6 primero y espera el timeout | Resuelto (2026-10-10): el hook usa `127.0.0.1`; con 8000 y 8100 encendidos tarda ~180 ms y con 8100 apagado ~260 ms (de eso, ~155 ms es el arranque de Python) |
| El campo de tipo de `Notification` es `notification_type`, no `type` | Resuelto (2026-10-10): el hook lee `notification_type` (con `type` de respaldo) |
| PowerShell 5.1 antepone un BOM al pasar texto por tubería a un programa | El hook acepta stdin con BOM (`utf-8-sig`); para pruebas manuales usar `cmd /c "claude-office-hook evento < archivo.json"` |
| Con la salida de `make dev-local` redirigida a un archivo, rich registra miles de "Logging error" | Solo afecta a la captura del log en archivo; en la terminal no aparece |
| Al reproducir miles de eventos muy rápido, el pipeline clásico registró una vez "No row was found" en `session_start` | Carrera de la base de datos de la vista clásica; no afecta al motor |
| La base de datos de la vista clásica pierde eventos cuando llegan seguidos (ráfaga de 2 000: guardó 520; en la reproducción real perdió p. ej. el `post_tool_use` y el `stop` de Películas) | No se corrige (decisión 2026-10-10): el motor usa su propio registro. La importación inicial copió los huecos que ya tenía la base heredada (Películas quedó sin su pregunta pendiente) |
| Prueba en vivo: AskUserQuestion salía como 13 "te espera: permiso" | Claude Code lo pide como `permission_request` + notificación de permiso; ahora es 14 con la pregunta pendiente (igual ExitPlanMode) |
| Prueba en vivo: pregunta en texto normal no detectada (8f5f7ede, 15:15:47) | El `Stop` sí traía el texto; la pregunta estaba en el último párrafo pero seguida de las opciones ("…o dejarlo así."). Ahora se busca en todo el último párrafo; si el `Stop` llega sin texto, se reintenta con la transcripción |
| Prueba en vivo: el encargo mostraba "<browser_instruction># Claude in Chrome browser..." | El hook recortaba a 50 caracteres antes de quitar el bloque inyectado. El motor limpia los bloques y recupera el texto de la transcripción; el hook del repositorio ya los quita antes de recortar (reinstalado el 2026-10-10 a las 11:06) |
| Prueba en vivo: 01152d34 congelada en 15 desde las 9:23 (se perdió el `post_tool_use` con el backend apagado) | Conciliación con la cola de la transcripción |
| Prueba en vivo: un subagente pasaba a terminado a los 30 min sin actividad | Sin límite de tiempo: termina con su `SubagentStop`, el `Stop` del agente principal o la muerte del proceso |
| Prueba en vivo: la CLI de demo (5f41c31c) no enviaba PID y quedó 12 h como 21 `sin_pid_antiguo` estando abierta | La actualización automática de Claude Code renombra el ejecutable en uso (`claude.exe.old.1791575871902.47796`) y `process_info` buscaba el nombre exacto `claude.exe`. Corregido en el repositorio; Washington reinstaló el hook el 2026-10-10 a las 11:06 (`uv tool install --force -p 3.14 E:\visualizador-agentes\hooks`) |
| Sesiones de prueba (rafaga-*, reinicio-*) en el listado | Borradas (13 del registro propio, 11 de la base clásica de desarrollo); desde ahora prefijo `prueba-` y `scripts/borrar_sesiones_prueba.py` |
| "Tokens totales" igual a "Tokens en el contexto" | Ahora es el acumulado real de la transcripción (salida + entrada nueva) |
| "Tokens totales" de 5f41c31c (Demo Org) en 97,5 M tras 164 min | Sumaba toda la historia de la conversación retomada (6 semanas) y la creación de caché (81 M, contexto reescrito tras cada vencimiento o compactación). Ahora: salida desde la llegada al motor (~0,38 M) |
| `npm run lint` completo marca 10 errores de `react-hooks` (`set-state-in-effect`, `refs`) | Son previos y están en archivos de la vista clásica (`SettingsModal.tsx`, `BuildingTab.tsx`, `useSessions.ts`, `useWebSocketEvents.ts`); no se tocan. Los archivos de `/oficina` y de avisos pasan el lint |
| `/oficina` en `http://127.0.0.1:3100` no carga datos en desarrollo | Next bloquea `/_next/*` de desarrollo para orígenes fuera de `allowedDevOrigins`; usar `localhost:3100` (sin cambiar la configuración) |
| El tiempo del hook depende de la carga de la PC: con Unity y Chrome abiertos, el mismo hook anterior pasó de ~180 a ~250 ms (8100 encendido) y de ~260 a ~320 ms (8100 apagado) | Se mide comparando la versión anterior y la nueva intercaladas; la detección del proceso suma ~5-10 ms |
| Next.js 16.3 genera `frontend/AGENTS.md` y `frontend/CLAUDE.md` al arrancar | Se versionan (decisión 2026-10-09) para que `next dev` no los vuelva a dejar como cambios sueltos |
| `npm install` del frontend reporta 6 vulnerabilidades (5 altas, 1 crítica) | Pendiente: revisar con `npm audit`; herramienta local, no bloquea |
| autoskills no permite elegir skills sueltas por línea de comandos; sin terminal interactiva instala todas las sugeridas | Washington las instaló con el selector interactivo; las de `frontend/` se movieron a la raíz (Windows pide administrador para enlaces simbólicos, se usaron uniones de directorio) |
| Command Center con agentes al doble: solo caben 2×2 puestos por columna (antes 2×4) | Los demás se resumen en "+N más"; revisar si hace falta más capacidad |

## Próximos pasos

1. Resolver los pendientes del motor de estados (errores de herramientas, `agent_id` de subagentes, tokens de transcripciones grandes, cuándo "te espera respuesta").
2. Port de Agent Office 3D: prompt 3 (personajes GLB con Mixamo, editor de la distribución, prueba en el iPhone). Regenerar `frontend/bun.lock` donde haya bun. Buscar mejores voces o un sistema de lectura para los avisos.
3. Avisos (sonido y notificación del sistema) y app móvil con notificaciones.
