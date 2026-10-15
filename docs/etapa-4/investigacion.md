# Etapa 4: investigación para crear proyectos y trabajar con un orquestador

Fecha: 2026-10-11. Claude Code 2.1.296 en la Alienware (Windows). Todas las fuentes son de la documentación oficial (https://code.claude.com/docs/en/...); cada afirmación lleva su página y sección.

## 1. Hallazgos

### 1.1 Lanzar y controlar una sesión desde otro programa

**Modo headless (`claude -p`)**
- **Qué es:** ejecuta Claude Code sin interfaz ([headless](https://code.claude.com/docs/en/headless), "Basic usage").
- **Formatos:** con `--input-format stream-json` y `--output-format stream-json`, la entrada y la salida son líneas JSON ([cli-reference](https://code.claude.com/docs/en/cli-reference), "CLI flags"; [headless](https://code.claude.com/docs/en/headless), "Get structured output").
- **Varios mensajes por proceso:** una misma ejecución acepta varios mensajes de usuario seguidos y los procesa en orden ([cli-reference](https://code.claude.com/docs/en/cli-reference), `--max-turns`: "a message still queued ... starts a new turn"; [streaming-vs-single-mode](https://code.claude.com/docs/en/agent-sdk/streaming-vs-single-mode), "Benefits").
- **Fin de cada turno:** termina con un mensaje `result` que trae el texto, el costo y el `session_id` ([headless](https://code.claude.com/docs/en/headless), "Stream responses").
- **Formato de entrada:** la línea exacta no está documentada para la CLI. Se usa la del SDK (`SDKUserMessage`: `{"type":"user","message":{"role":"user","content":...}}`, [agent-sdk/typescript](https://code.claude.com/docs/en/agent-sdk/typescript), "SDKUserMessage"). La prueba de la sección 2 confirma que funciona.
- **Protocolo de control:** el de stdin y stdout (`control_request`, interrupción) no está documentado; es interno del SDK.

**Agent SDK (Python y TypeScript)**
- **Por debajo:** ejecuta el mismo binario de Claude Code ([agent-sdk/overview](https://code.claude.com/docs/en/agent-sdk/overview)).
- **`canUseTool`:** recibe los permisos y las preguntas de `AskUserQuestion` y puede esperar sin límite de tiempo. La respuesta a una pregunta es `updatedInput` con `questions` y `answers` ([agent-sdk/user-input](https://code.claude.com/docs/en/agent-sdk/user-input)).
- **Otros controles:** tiene `interrupt()`, `setModel()` y `setPermissionMode()` en modo de entrada por streaming ([agent-sdk/typescript](https://code.claude.com/docs/en/agent-sdk/typescript), "Query object").
- **Autenticación:** la documentación dice que "Anthropic does not allow third party developers to offer claude.ai login or rate limits for their products, including agents built on the Claude Agent SDK" ([agent-sdk/overview](https://code.claude.com/docs/en/agent-sdk/overview), nota). No aclara el caso de una herramienta personal que usa la CLI instalada del mismo usuario.

**Retomar sesiones**
- **Opciones:** `--resume <id o nombre>`, `--continue`, `--session-id <uuid>`, `--fork-session` y `--no-session-persistence`, esta última solo en `-p` ([cli-reference](https://code.claude.com/docs/en/cli-reference), "CLI flags").
- **Transcripciones:** van en `~/.claude/projects/<proyecto>/<sesión>.jsonl`, con un formato interno que cambia entre versiones ([sessions](https://code.claude.com/docs/en/sessions), "Where transcripts are stored").
- **Retomar por ID:** funciona desde cualquier carpeta ([headless](https://code.claude.com/docs/en/headless), "Continue conversations").

**Remote Control**
- **Qué es:** conecta claude.ai/code o la app de Claude con una sesión local ([remote-control](https://code.claude.com/docs/en/remote-control), introducción). Existe `claude remote-control` (modo servidor) y `--remote-control` ([cli-reference](https://code.claude.com/docs/en/cli-reference), "CLI commands").
- **Requisitos:** Pro, Max, Team o Enterprise, sin claves de API ([remote-control](https://code.claude.com/docs/en/remote-control), "Requirements").
- **Cliente propio:** no hay una API pública para un cliente propio; solo se mencionan claude.ai/code, la app, VS Code y Desktop. Por eso no sirve para el chat dentro de la oficina.

**Sesiones en segundo plano (agent view)**
- **`claude --bg`:** arranca una sesión en segundo plano y devuelve su ID. No se combina con `-p` ([cli-reference](https://code.claude.com/docs/en/cli-reference)).
- **`claude agents --json`:** lista las sesiones activas con `waitingFor` ("permission prompt", "input needed") ([agent-view](https://code.claude.com/docs/en/agent-view)).
- **Administración:** `claude attach`, `logs`, `respawn` y `stop`. Un supervisor las mantiene vivas aunque se cierre la terminal ([agent-view](https://code.claude.com/docs/en/agent-view), "The supervisor process").
- **Mandarles un mensaje:** con `claude --resume <id> --bg "<prompt>"` ([agent-view](https://code.claude.com/docs/en/agent-view), "From your shell"). Con la salida redirigida o con `--output-format`, retomar una sesión que sigue corriendo "sends nothing and exits with status 1" ([sessions](https://code.claude.com/docs/en/sessions), "Resume a running background session").

**Otros mecanismos**
- **Channels** (versión preliminar): un servidor MCP que empuja eventos a una sesión y puede reenviar los permisos. Los canales propios necesitan `--dangerously-load-development-channels`, que `-p` ignora ([channels-reference](https://code.claude.com/docs/en/channels-reference); [cli-reference](https://code.claude.com/docs/en/cli-reference)).
- **`--cloud`, entornos autoalojados y gateway:** son para la nube o para administradores; no aplican aquí.

### 1.2 Mensajes entre sesiones

**Cross-session messaging**
- **Disponibilidad:** viene activada y no hay que configurar nada. Requiere la versión 2.1.234 o posterior en Windows nativo ([cross-session-messaging](https://code.claude.com/docs/en/cross-session-messaging), nota inicial).
- **Herramientas:** Claude busca la sesión destino con `ListAgents` y le escribe con `SendMessage` ("Message another session").
- **Sesiones `-p`:** también reciben mensajes ("Claude Code binds an inbox socket for a `claude -p` session like an interactive one"). Para aceptarlos sin nadie presente hay que arrancarlas con `crossSessionInbound: accept` en `--settings` ("Non-interactive sessions"). En modo `--bare` no hay buzón.
- **Entrega:**
  - Si la sesión destino está ocupada, lee el mensaje entre dos herramientas.
  - Si está libre, empieza un turno nuevo con el mensaje ("Message delivery").
- **Permisos:** un mensaje de otra sesión no cuenta como consentimiento y no puede contestar un permiso pendiente ("How a session treats an incoming message").
- **Script externo:** un programa externo puede escribir en el buzón (en Windows, un named pipe con una línea de autenticación `{"type":"auth","token":...}`), pero no se documenta el formato del mensaje ni cómo encuentra la ruta un programa que no es hijo de la sesión ("The session's inbox socket").

**Agent teams**
- Están desactivados por defecto (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`).
- No funcionan con `-p` ni con el SDK.
- Los permisos de los compañeros se aprueban en la sesión líder.
- Admiten un solo equipo por sesión y no se pueden anidar ([agent-teams](https://code.claude.com/docs/en/agent-teams), "Enable agent teams", "Permissions" y "Limitations").

### 1.3 Permisos y hooks en sesiones lanzadas así

- **Hooks:** una sesión `-p` sin `--bare` carga lo mismo que una interactiva, incluidos los hooks de `~/.claude/settings.json` ([headless](https://code.claude.com/docs/en/headless), "Start faster with bare mode"). El SDK los carga si `settingSources` incluye `user`, que viene por defecto ([agent-sdk/claude-code-features](https://code.claude.com/docs/en/agent-sdk/claude-code-features), "Hooks"). **El monitor actual ve estas sesiones con sus hooks; la prueba lo confirma.**
- **Permisos:**
  - En `-p` sin "permission host" (`canUseTool` o `--permission-prompt-tool`), un permiso que nadie decide se deniega ([headless](https://code.claude.com/docs/en/headless), "Turn off permission prompts in unattended runs").
  - El hook PermissionRequest sigue corriendo y puede decidir: "Claude Code still runs these hooks, and if no hook returns a decision, it denies the tool call" ([hooks](https://code.claude.com/docs/en/hooks), "PermissionRequest").
  - Por eso el hook de permisos del visualizador sirve para que los permisos lleguen a Washington. Sin decisión, se deniega; no pasa como en VS Code, donde queda el diálogo.
- **AskUserQuestion:** en `-p` solo se ofrece si hay un permission host ([hooks](https://code.claude.com/docs/en/hooks), "Defer a tool call for later"). Coincide con la prueba del Prompt 33 ("No such tool available").
- **Modo de permisos:** el inicial de `-p` puede ser `default` o `auto` según la sesión ([permission-modes](https://code.claude.com/docs/en/permission-modes), "Which mode a session starts in"). Conviene pasarlo siempre con `--permission-mode`.

### 1.4 Cuenta, modelo, esfuerzo y carpeta

- **Cuenta:** `CLAUDE_CONFIG_DIR` (Demo Org: `%USERPROFILE%\.claude-demo`). La personal usa la carpeta por defecto, sin la variable ([env-vars](https://code.claude.com/docs/en/env-vars)).
- **Modelo:** `--model` con un alias (`opus`, `sonnet`, `haiku`, `fable`, `opusplan`...) o un nombre completo como `claude-opus-5-5` ([model-config](https://code.claude.com/docs/en/model-config), "Model aliases").
- **Esfuerzo:** `--effort low|medium|high|xhigh|max|ultracode`; los niveles dependen del modelo. `CLAUDE_CODE_EFFORT_LEVEL` tiene prioridad sobre la opción ([cli-reference](https://code.claude.com/docs/en/cli-reference); [env-vars](https://code.claude.com/docs/en/env-vars)).
- **Carpeta:** el directorio de trabajo del proceso (y `--add-dir` para otras carpetas).

### 1.5 Visibilidad en VS Code y en la terminal

- **Sesiones `-p` y del SDK:** no aparecen en el selector de `claude --resume` ni en `--continue`, pero se pueden retomar con su ID ([sessions](https://code.claude.com/docs/en/sessions), "/loop, -p, Agent SDK, and background sessions").
- **Sesiones `--bg`:** sí aparecen en el selector, con la marca `bg`, y en agent view ([sessions](https://code.claude.com/docs/en/sessions), "Where the session picker looks").
- **VS Code:**
  - Comparte el historial con la CLI ([vs-code](https://code.claude.com/docs/en/vs-code), "Switch between extension and CLI").
  - No está documentado si su lista de sesiones muestra las de `-p`.
  - Si una conversación está abierta en otro lado, avisa "This conversation is still open somewhere else ... Open here anyway" ([vs-code](https://code.claude.com/docs/en/vs-code), "Resume past conversations").
- **Retomar en dos lugares a la vez:** se puede, pero los mensajes se mezclan en la misma transcripción ([sessions](https://code.claude.com/docs/en/sessions), "Branch a session").

## 2. Pruebas reales

Las dos se hicieron en carpetas temporales (`%USERPROFILE%\AppData\Local\Temp\prueba-*`) con la cuenta personal, Haiku, esfuerzo bajo y `--no-session-persistence`. El entorno no tenía las variables `CLAUDE*`, así que no eran sesiones hijas de esta, y no tenía historial de prompts. Los guiones imitan al monitor lanzando `claude.exe` con `subprocess`.

### Prueba 1: una sesión, dos mensajes, la oficina la ve

Comando: `claude -p --input-format stream-json --output-format stream-json --verbose --model haiku --effort low --no-session-persistence --allowedTools Read --permission-mode default`. El proceso quedó vivo y recibió dos mensajes por stdin.

| | Mensaje | Respuesta | Total | Primera salida | API | Tokens (entrada / creación de caché / lectura de caché / salida) | Costo informado |
|---|---|---|---|---|---|---|---|
| Turno 1 | "Lee el archivo nota.txt de esta carpeta y dime en una frase corta cuál es la clave del día." | "La clave del día es **"girasol azul"**." (usó Read) | 7,56 s | 3,05 s | 1,8 s | 4 / 22 609 / 47 828 / 102 | USD 0,0051 |
| Turno 2 | "Segundo mensaje en la misma sesión: repite la clave que leíste antes, en mayúsculas, sin leer nada." | "GIRASOL AZUL" | 4,80 s | 1,47 s | 2,7 s | 2 / 6 676 / 38 640 / 12 | USD 0,0068 (parece acumulado) |

- **Sesión:** duró 13,4 s en total y el proceso cerró con código 0.
- **Lo que reporta `system/init`:** modelo `claude-haiku-5-5`, `permissionMode: default` y `apiKeySource: none`, o sea que usa la sesión de la suscripción.
- **Herramientas disponibles:** entre otras `ListAgents` y `SendMessage`, y las de los conectores de claude.ai.
- **En la oficina** (servidor real, `GET /api/v1/agents/state`): la sesión apareció como proyecto `%USERPROFILE%/AppData/Local/Temp/prueba-orquestador`, cuenta personal, máquina alienware.
  - Eventos, en orden: `session_start`, `user_prompt_submit` (mensaje 1), `pre_tool_use` y `post_tool_use` de Read, `stop`, `user_prompt_submit` (mensaje 2), `stop` y `session_end`.
  - El modelo salió vacío: en `-p` no corre la barra de estado, que es la que lo informa.
- **Rastros fuera de la carpeta:**
  - Quedaron dos carpetas vacías: `~/.claude/projects/<carpeta>/memory` y `~/.claude/session-env/<sesión>`. Las borré.
  - No hubo transcripción, ni cambios en `history.jsonl`, ni sesión nueva en `~/.claude/sessions`, ni proyecto nuevo en `~/.claude.json`.

### Prueba 2: el orquestador le da una orden al agente

1. Se lanzó la sesión "agente" (`--name agente-prueba`, `--allowedTools Read,Write`, `--settings {"crossSessionInbound":"accept"}`) y respondió "listo".
2. Después se lanzó la sesión "orquestador" (`--name orquestador-prueba`, `--allowedTools ListAgents,SendMessage`) con este pedido: buscar a agente-prueba y mandarle la orden "Crea en tu carpeta el archivo orden.txt con el texto: hecho por orden del orquestador".

| Momento | Segundos desde el inicio |
|---|---|
| Agente listo (primer `result`) | 6,4 |
| Orquestador: `ListAgents` | 9,6 |
| Orquestador: `SendMessage` a `agente-prueba` ("success": true, queda en el buzón) | 11,9 |
| Agente: empieza un turno nuevo (nuevo `system/init`, misma sesión) | 12,9 |
| Agente: `Glob` y `Write` de `orden.txt` | 14,7 y 16,5 |
| Agente: responde "Creé `orden.txt` ... con el texto "hecho por orden del orquestador"" | 18,1 |

- **Tiempo de la orden:** del pedido al orquestador hasta la orden cumplida pasaron 14,9 s; del envío hasta que el agente reaccionó, 1 s.
- **Archivo:** `orden.txt` quedó con "hecho por orden del orquestador".
- **Tokens por resultado** (entrada / creación de caché / lectura de caché / salida):

| Resultado | Tokens | Costo |
|---|---|---|
| Agente, "listo" | 2 / 15 770 / 16 031 / 4 | USD 0,0033 |
| Orquestador | 6 / 31 476 / 95 033 / 327 | USD 0,0074 |
| Agente, la orden | 6 / 26 298 / 109 184 / 482 | USD 0,0099 |

- **Hallazgo importante:** `ListAgents` le mostró al orquestador **todas** las sesiones de la máquina ("Peer sessions (5)"), incluidas las sesiones reales e interactivas de Washington. Un orquestador podría escribirle a cualquier sesión abierta; hay que limitarlo.
- **Rastros:** los mismos de la prueba 1 (carpetas vacías por sesión), borrados al final. Las carpetas temporales también se borraron.

## 3. Arquitecturas posibles

Las tres comparten lo mismo para crear un proyecto:
1. La web o la app manda la orden al servidor.
2. El monitor de la máquina elegida la recoge, como hoy recoge los avisos.
3. El monitor crea la carpeta en su ruta base (`E:\Agents\<nombre>`) y lanza las sesiones con la cuenta (`CLAUDE_CONFIG_DIR` para Demo Org), el modelo (`--model`) y el esfuerzo (`--effort`) elegidos.

Los permisos siguen llegando por el hook PermissionRequest que ya existe.

### A. Procesos `claude -p` con stream-json y mensajería entre sesiones

**Cómo funciona.**
- **Procesos:** el monitor mantiene vivo un proceso `claude -p --input-format stream-json --output-format stream-json` por sesión: el orquestador y cada agente de código.
- **Chat:** lo que Washington escribe en la oficina viaja servidor → monitor → stdin del orquestador. La salida del orquestador (texto, herramientas, `result`) vuelve monitor → servidor → web y app.
- **Órdenes:** el orquestador las da con `SendMessage`. Los agentes arrancan con `crossSessionInbound: accept`.
- **Aprobar cada orden:**
  - El orquestador arranca con un hook `PreToolUse` propio para `SendMessage`, pasado con `--settings` solo a esa sesión; no toca la configuración del usuario.
  - El hook registra la orden en el servidor y espera el botón de Washington, igual que un permiso.
  - El mismo hook rechaza cualquier destino que no sea un agente de ese proyecto.
  - Después, el interruptor automático por proyecto deja pasar las órdenes sin esperar.
- **Permisos:** el hook PermissionRequest actual, con la política "siempre esperar" para estas sesiones (en `-p`, sin decisión se deniega).
- **Sesiones:** se guardan (sin `--no-session-persistence`) para poder retomarlas.

**Ventajas.**
- Todo está documentado y probado en esta máquina: varios mensajes en un proceso, órdenes entre sesiones en 1 s, hooks y oficina.
- Usa la suscripción, sin claves de API.
- La aprobación de cada orden y el límite de destinos quedan en un hook propio.
- No hay dependencias nuevas.

**Riesgos.**
- La línea de entrada de stream-json y el protocolo de control no están documentados para la CLI. Hoy funcionan, pero pueden cambiar entre versiones.
- Si el monitor se reinicia, los procesos mueren. Hay que relanzarlos con `--resume <id>`.
- `AskUserQuestion` no está disponible en `-p` sin un permission host. El orquestador pregunta por texto en el chat, que para conversar alcanza.
- `ListAgents` ve las sesiones reales; lo controla el hook.

**Qué ve VS Code.** Las sesiones no aparecen en el selector ni en `--continue`. Washington puede abrirlas en la terminal con `claude --resume <id>`; en VS Code no está documentado. Retomarlas mientras el monitor las usa mezcla los mensajes.

### B. Sesiones en segundo plano (`claude --bg`) y agent view

**Cómo funciona.**
- **Lanzamiento:** el monitor ejecuta `claude --bg "<primer mensaje>"` en la carpeta. El supervisor de Claude Code mantiene viva la sesión.
- **Mensajes nuevos:** con `claude --resume <id> --bg "<mensaje>"`, o escribiendo en el buzón de la sesión.
- **Estado:** el monitor lo lee con `claude agents --json`.
- **Chat:** la salida se lee de la transcripción o de `claude logs`.
- **Órdenes al agente:** por mensajería entre sesiones, con el mismo hook de aprobación que en A.

**Ventajas.**
- Las sesiones son de Claude Code de verdad.
- Aparecen en el selector (`bg`) y en agent view, y Washington puede entrar con `claude attach` desde una terminal.
- Sobreviven si el monitor se reinicia.

**Riesgos.**
- La salida del chat sale de la transcripción, cuyo formato es interno y cambia, o de `claude logs`, que es texto para personas.
- Mandar mensajes con la salida redirigida no está permitido para una sesión que sigue corriendo ("sends nothing and exits with status 1"). El buzón por named pipe no tiene un formato de mensaje documentado.
- El supervisor es otro proceso que administrar.
- No está documentado si en `--bg` corren todos los hooks de `settings.json`.

**Qué ve VS Code.** Las sesiones aparecen en el historial compartido. La terminal y agent view las muestran y permiten entrar. VS Code avisa si la conversación está abierta en otro lado.

### C. Agent SDK de Python dentro del monitor

**Cómo funciona.**
- **Sesiones:** el monitor usa `ClaudeSDKClient` (entrada por streaming, varios turnos), un cliente por sesión.
- **Permisos y preguntas:**
  - `canUseTool` recibe los permisos y también las preguntas de `AskUserQuestion`, y espera la respuesta de Washington sin límite de tiempo.
  - Con esto se podría contestar preguntas desde el iPhone, lo que en el Prompt 33 no fue posible.
- **Aprobar órdenes:** con un hook programático del SDK para `SendMessage`.
- **Controles:** `interrupt()` y `setModel()` están documentados.

**Ventajas.**
- Es la interfaz programática oficial y documentada (mensajes tipados, permisos, interrupción).
- Resuelve `AskUserQuestion`.

**Riesgos.**
- La documentación dice que los productos de terceros hechos con el SDK no deben ofrecer el inicio de sesión de claude.ai. Para uso personal no está aclarado, y si hubiera que pasar a clave de API, cambia el costo.
- Suma una dependencia grande al monitor: el SDK trae su propio binario de Claude Code.
- Las sesiones tampoco aparecen en el selector.
- Hay que reempaquetar el monitor.

**Qué ve VS Code.** Lo mismo que en A: se retoman por ID y no aparecen en el selector.

## 4. Recomendación

**Empezar con A** y dejar C como evolución para las preguntas.

- **Es lo único probado de punta a punta en esta máquina.** Una sesión lanzada por un programa con dos mensajes y la oficina viéndola con los hooks actuales, y una orden de un orquestador cumplida por un agente en 1 s, con la suscripción y sin dependencias nuevas.
- **Usa lo que Claude Code ya trae**, sin duplicarlo: la sesión `-p`, la mensajería entre sesiones para las órdenes, los hooks para los permisos y la aprobación, y `--resume` para retomar.
- **El chat queda dentro de la oficina**, a diferencia de Remote Control, que no tiene una API para un cliente propio.
- **La aprobación de cada orden** y el límite de destinos se resuelven con un hook propio pasado por `--settings` solo a la sesión del orquestador. Eso evita el riesgo de que escriba a las sesiones reales que ve `ListAgents`.
- **B sirve de complemento**, no de base: si Washington quiere entrar a una sesión del orquestador desde la terminal, se puede abrir con `claude --resume <id>`. La parte frágil de B (leer el chat de la transcripción) no hace falta en A.
- **C se puede evaluar después**, cuando haga falta contestar `AskUserQuestion` desde la oficina, si se aclara el uso de la suscripción con el SDK.

**Primeros pasos sugeridos para construir A:**
1. Ruta base por máquina y "crear proyecto" (carpeta y PROJECT.md inicial).
2. Lanzador en el monitor (proceso vivo, entrada y salida stream-json, relanzar con `--resume`).
3. Chat con el orquestador en la web y la app.
4. Hook de aprobación de órdenes (`PreToolUse` para `SendMessage`) con destinos limitados.
5. Agentes de código enlazados.
6. Interruptor automático por proyecto.

## 5. Lo que la documentación no aclara

- La línea exacta de entrada de stream-json para la CLI y el protocolo de control (`control_request`).
- El formato de un mensaje escrito directamente en el buzón (named pipe) y cómo obtiene su ruta un programa que no es hijo de la sesión.
- Si VS Code muestra las sesiones `-p`.
- Si en `--bg` corren todos los hooks de `settings.json`.
- El uso de la suscripción con un programa propio que lanza la CLI o el SDK del mismo usuario.
- Si hay un bloqueo cuando dos procesos escriben la misma transcripción.
