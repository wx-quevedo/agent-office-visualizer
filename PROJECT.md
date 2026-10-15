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

## Visión

No es otro chat. Es una organización viva, lista para recibir un proyecto, que trabaja de forma profesional y apoyada, con formas de visualización distintas (oficina 3D, cajas, detalle, celular), y que hace el trabajo pesado más fácil que un chat.

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
| 2026-10-10 | Cuentas: la personal no lleva marca; la de Demo Org lleva el isotipo (`frontend/public/logos/isotipo-demo-org.svg`, ~16 px) en la etiqueta 3D y en los escritorios de `/oficina`, y el logo completo (`logo-demo-org.svg`) solo donde hay espacio (detalle). "Demo Org" como texto solo en tooltips y `alt` | Se distingue la cuenta sin texto extra |
| 2026-10-10 | La oficina pasa a uso diario en E:\visualizador-agentes-diario (3000/8000); claude-office queda de respaldo | Washington aprobó la oficina; dos copias independientes: la diaria estable y la de desarrollo para cambios |
| 2026-10-10 | La copia diaria se sirve compilada: backend con uvicorn sin `--reload` y el export estático del frontend con un servidor Starlette propio (`app.servidor_frontend`) en 3000 | Usa el mismo entorno del backend (nada extra que instalar), resuelve las URL limpias del export (`/oficina` → `oficina.html`), fija los tipos MIME (en Windows el registro puede dar `text/plain` a `.js`) y aplica la misma regla de acceso (solo localhost y Tailscale) |
| 2026-10-10 | La copia diaria se clona desde la copia de desarrollo local (`E:\visualizador-agentes`, rama main) | Así `actualizar-oficina.ps1` trae los commits aprobados aunque todavía no estén en GitHub; se puede cambiar el origen a GitHub con `git remote set-url` |
| 2026-10-10 | Cada copia guarda su propia distribución de la oficina 3D (muebles y tema) en su carpeta de datos, a través del backend; la del repo es solo la base. Se pasa de una copia a otra con Exportar/Importar JSON | Washington arma su oficina en la diaria sin que desarrollo la pise |
| 2026-10-10 | El editor no deja guardar mientras un mueble tape un camino de los agentes o un escritorio de trabajo | Los agentes caminan por un grafo fijo; un mueble encima los dejaría atascados |
| 2026-10-10 | Cuatro entornos para elegir viéndolos en 3D: Puente de mando, Cabinas por proyecto, Sala de control con mostrador y Estudio con jardín; el Original se conserva | El escritorio del agente es lo central y cada entorno resuelve de forma distinta el momento en que un agente te espera (13 y 14) |
| 2026-10-10 | Cabinas: máximo 6 cabinas de proyecto más la Cabina general fija; Estudio: isla propia desde 2 agentes del proyecto, los de un solo agente comparten la Isla general, y se guardan 3 islas libres para ella | Así siempre hay lugar para quien llega y nadie se cambia de puesto mientras su proyecto tenga agentes |
| 2026-10-10 | La diaria corre con el bucle Selector de asyncio (`--loop asyncio:SelectorEventLoop`) y se arranca a través de su tarea programada | En Windows el bucle Proactor cierra el puerto que escucha cuando un `accept` falla con WinError 64; el Selector solo registra el error y sigue |
| 2026-10-10 | Permisos desde la oficina con la política "solo_en_el_celular" por defecto (corrige la decisión anterior, "solo_fuera_de_la_pc"): la oficina espera tu decisión solo si hay un latido de celular vigente (75 s, como la presencia) y ninguno de la PC; sin ningún dispositivo conectado, o con la PC conectada, el hook devuelve de inmediato y responde VS Code (la solicitud se ve igual en la oficina); si el celular se desconecta mientras espera, deja de esperar. "siempre" y "nunca" se eligen en el panel Permisos; espera por defecto 90 s (10 a 540) | Con "solo_fuera_de_la_pc", si estabas en la PC con la pestaña cerrada, cada permiso esperaba hasta el límite sin que nadie pudiera responder. Claude Code espera al hook antes de seguir: solo vale la pena esperar cuando alguien puede responder desde el celular |
| 2026-10-10 | Plan por etapas (sección "Plan por etapas"): sin Tailscale; un monitor por máquina envía todo al VPS de the VPS provider y la web y la app iOS lo consumen en https://agents.example.com | Decisión de Washington: ver y manejar los agentes desde cualquier lugar sin depender de la red privada |
| 2026-10-10 | Inicio de sesión de un solo usuario con contraseña fijada por consola (hash argon2) y tokens guardados como HMAC-SHA256; desactivado por defecto en local y activado en el VPS | La diaria y el iPhone por Tailscale siguen igual hasta la etapa 1.4; en internet nada queda abierto |
| 2026-10-10 | Un token de máquina solo puede enviar datos (eventos, registro y espera de permisos, latido) y una máquina solo ve sus propias solicitudes de permiso | Si un monitor se ve comprometido, no lee el estado ni decide permisos de otras máquinas |
| 2026-10-10 | Voces: Washington usará las voces de Google en Chrome (no Edge) | En Edge y en Playwright solo aparecen voces de Microsoft de España; pendiente buscar mejores voces o un sistema de lectura |
| 2026-10-11 | App iOS: la sesión es la misma cookie de 30 días de `POST /auth/entrar` (por dispositivo), guardada en el Llavero; la API la manda como `Cookie` con `X-Visualizador: 1` y el WKWebView de la oficina 3D la recibe en su almacén de cookies | Sin cambios en el backend; con el token de app (`vap_`) el WKWebView no tendría sesión, porque la web solo acepta la cookie |
| 2026-10-11 | App iOS: datos en vivo con `GET /agents/state` cada 2 s (como la web), reintentos cada vez más espaciados hasta 15 s si se corta | La web ya no usa WebSocket (se quitó en la etapa 1.4) |
| 2026-10-11 | App iOS: proyecto con XcodeGen (`ios/VisualizadorAgentes/project.yml`, el `.xcodeproj` no se versiona), iOS 26, solo iPhone, tema claro, sin capacidades que un Personal Team no permita; se compila y prueba con Xcode 26.6 (`DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer`) en el simulador iPhone 17 Pro Max con iOS 26.5 | El simulador de Xcode 27 se quedó trabado al arrancar |
| 2026-10-12 | Las preguntas del agente (AskUserQuestion) se muestran en la bandeja de Decisiones solo para leer, con su resumen y sus opciones, y se responden en la PC | Claude Code documenta que un hook PreToolUse puede contestarlas, pero en esta instalación no es confiable: el hook PreToolUse del visualizador tiene 2 s de límite y lo pone el instalador del monitor, hay otros hooks PreToolUse para AskUserQuestion, mientras el hook espera VS Code no muestra la pregunta, y en una prueba aislada con `claude -p` la herramienta ni siquiera se ofreció (ver la sección de la etapa 3, Prompt 33) |
| 2026-10-12 | Etapa 4 con la arquitectura A: el monitor lanza y mantiene vivas sesiones `claude -p` con stream-json; el orquestador dará órdenes con la mensajería oficial entre sesiones (Prompt 38) y solo a los agentes de su proyecto; se acepta que estas sesiones no salgan en el selector de `--resume` | Es la única probada de punta a punta en la Alienware, con la suscripción y sin dependencias nuevas (`docs/etapa-4/investigacion.md`) |
| 2026-10-12 | Hasta el Prompt 38, el orquestador arranca con `SendMessage` y `ListAgents` bloqueados; los agentes aceptan mensajes de otras sesiones (`crossSessionInbound: accept`). El id de sesión de cada miembro lo decide el servidor | `ListAgents` ve todas las sesiones de la máquina; el hook que limita los destinos llega con las órdenes. Con el id decidido antes de lanzar, la oficina reconoce la sesión desde su primer evento |
| 2026-10-12 | Al reiniciar el monitor, las sesiones retomadas no reciben saludo: la oficina las muestra "En espera" hasta que alguien les escriba | Evita gastar tokens en cada reinicio; el servidor sabe por el monitor que siguen vivas aunque la oficina las haya visto terminar |
| 2026-10-12 | Solo habrá "Detener" (cierra las sesiones y deja la carpeta intacta), en el Prompt 38; borrar carpetas desde la web no se hará | Un borrado remoto de carpetas es demasiado riesgo para lo que aporta |
| 2026-10-12 | Órdenes del orquestador con el monitor de intermediario, no con `SendMessage` y un hook: el orquestador escribe un bloque `<orden agente="...">` en su respuesta, el monitor lo registra por aprobar y solo una orden aprobada (o con el interruptor automático encendido) se escribe por la entrada estándar al agente elegido de ese proyecto | Un hook no puede esperar minutos la aprobación de Washington, `ListAgents` muestra todas las sesiones de la máquina y el agente tendría que aceptar mensajes de cualquier sesión. Un bloque de texto no necesita servidor MCP ni permisos extra en `-p` |
| 2026-10-12 | Los agentes de código arrancan con `crossSessionInbound: refuse` y el orquestador sin `SendMessage`, `ListAgents`, `Bash` ni `PowerShell` | Con `refuse` puesto por `--settings`, ninguna sesión de la máquina puede escribirle al agente; solo el monitor. Sin terminal, el orquestador no puede lanzar ni retomar otra sesión por su cuenta |
| 2026-10-12 | Una orden en curso cuando se corta la sesión (pausar, detener, reinicio del monitor) se informa fallida y se le avisa al orquestador; no se repite sola. Lo aprobado en cola, los mensajes y lo pendiente de mandar al servidor se guardan y no se pierden | Repetirla sola podría duplicar trabajo que quedó a medias |
| 2026-10-12 | Encender la aprobación automática vale solo para las órdenes nuevas; reanudar ya no manda saludo (quedan "En espera") | Lo que ya esperaba a Washington no se aprueba sin que lo vea; el saludo gastaba tokens y ensuciaba el chat |
| 2026-10-12 | Los agentes de código del equipo se lanzan con `--permission-mode acceptEdits`: una vez aprobada la orden, editan archivos dentro de la carpeta del proyecto sin pedir permiso; los comandos de terminal siguen pidiéndolo. El orquestador queda en `default` | Decisión de Washington tras la prueba real: aprobar la orden ya es la decisión; pedir además cada escritura no aporta |
| 2026-10-12 | Los permisos de las sesiones del equipo esperan la decisión de Washington 540 s (lo más que admite el hook), siempre en la web o la app, aunque esté en la PC; las sesiones normales siguen con su política y sus 90 s | Una sesión `claude -p` no tiene diálogo de permisos: si el hook no espera, Claude Code rechaza el permiso al instante |
| 2026-10-12 | Reglas de la casa globales (con las 9 de Washington; autoskills apagada por defecto), editables en Ajustes y apagables por proyecto; el monitor las escribe en un bloque con marcas del CLAUDE.md del proyecto, sin tocar lo demás, y avisa una vez a las sesiones vivas | Las reglas viajan con cada proyecto sin copiarlas a mano; el aviso cubre que CLAUDE.md solo se lee al empezar la sesión |
| 2026-10-12 | Comandos seguros (git status, git diff, git log, npm test, npm run build, npm run lint, pytest) con `--allowedTools "Bash(<comando> *)"` para los agentes; sin comodines ni operadores de la terminal; si cambian, el agente se relanza al terminar su turno | Probado con Claude real: la lista se aplica al retomar y un comando fuera de ella sigue pidiendo permiso |
| 2026-10-12 | El orquestador también corre con `acceptEdits` (edita su carpeta para escribir la especificación y el plan) y sigue sin terminal, `SendMessage` ni `ListAgents`; abre la entrevista inicial por su cuenta | Pedido del Prompt 39: la entrevista termina en PROJECT.md sin pedir permisos |
| 2026-10-12 | Por ahora las sesiones del equipo siguen usando las reglas de permiso de la configuración de usuario (629 reglas); queda como pendiente de seguridad (cerrado en el Prompt 41) | Excluirlas también quitaría los hooks de la oficina; la idea es lanzarlas sin la configuración de usuario y pasarles los hooks por `--settings` |
| 2026-10-12 | Las sesiones del equipo se lanzan con `--setting-sources project,local` (sin la configuración de usuario), también al retomarlas, y con `--settings <archivo>` que el monitor genera en cada arranque con solo los hooks de la oficina de su cuenta (copiados de su settings.json, con matcher y timeout) y, para el agente, `crossSessionInbound: refuse` | Así el equipo no hereda las 629 reglas de permiso ni los demás hooks de las sesiones normales de Washington, la oficina sigue viéndolas y la cuenta no cambia (CLAUDE_CONFIG_DIR elige la carpeta y sus credenciales, que no son una fuente de configuración). Los archivos `.claude/` del proyecto son rutas protegidas: aun con `acceptEdits`, el agente no puede darse permisos sin pedirlos |
| 2026-10-12 | Los avisos de reglas a una sesión se juntan: esperan 8 s desde el último cambio y dicen qué se agregó y qué se quitó respecto de lo que la sesión conocía | Varios interruptores seguidos generaban un aviso por cambio y confundían al orquestador (prueba del Prompt 39) |
| 2026-10-12 | El chat muestra el markdown del orquestador con un parser propio que arma elementos de React (nunca HTML crudo) y enlaces solo http, https y mailto | Sin dependencias nuevas y sin forma de inyectar HTML o scripts desde la respuesta de un modelo |
| 2026-10-12 | Cada orden tiene un título corto: el orquestador lo escribe en el bloque (`titulo="..."`, obligatorio en su rol) y el backend lo guarda; si falta, se usa la primera línea del texto sin marcas, recortada a 80 caracteres (`titulo_propio` dice cuál de los dos es) | El boceto de la tarjeta lo muestra y la app no tenía con qué; el respaldo cubre las órdenes viejas y un orquestador que lo olvide |
| 2026-10-12 | Cada entrada de "Dónde quedamos" (`GET /proyectos`) tiene un `id` estable (máquina y carpeta normalizada) y cada proyecto con equipo devuelve `donde_quedamos_id` con esa entrada, o null | La app los unía por carpeta o por nombre; ahora la unión la hace el servidor, igual que la comparación de carpetas del resto de la oficina |
| 2026-10-12 | Las sesiones del equipo se lanzan con `--system-prompt-snapshot off` cuando Claude Code es 2.1.257 o posterior (el monitor lo comprueba con `claude --version`); el aviso de rol queda solo como respaldo para versiones anteriores | Probado con Claude real: una sesión retomada sin la opción respondió con su rol de nacimiento y con la opción, con el rol nuevo, sin ningún aviso |
| 2026-10-12 | El rol del orquestador dice que Washington es la persona con quien habla y que nunca se presenta con su nombre; el saludo le pide presentarse como el orquestador del proyecto | Con Haiku se presentó dos veces como "Washington" (Prompt 41); con el texto nuevo, 6 de 6 saludos reales fueron correctos |
| 2026-10-12 | Los avisos de los orquestadores los arma el servidor a partir del chat (`GET /avisos-orquestador`): una orden por aprobar o la última pregunta del orquestador sin respuesta de Washington, cada uno con una clave estable (`orden:<id>` o `mensaje:<id>`). Cada aviso trae Responder, Ignorar y Esperar; Ignorar y Esperar se guardan en el servidor (tabla `avisos_orquestador`) | Así el aviso existe solo si hay algo que hacer, vale igual en la web y en la app, y la misma pregunta no se vuelve a anunciar porque la clave no cambia. El aviso viejo salía del estado 14 de la sesión, que no se puede contestar desde la ficha y en el que un orquestador queda indefinidamente |
| 2026-10-12 | Esperar silencia el aviso hasta el siguiente mensaje del orquestador (guarda el id de su último mensaje); Ignorar descarta ese aviso para siempre. La notificación del navegador y la voz suenan una sola vez por clave (recordadas en el navegador) | Pedido del Prompt 43; con la clave por mensaje, "una vez por mensaje" no depende de temporizadores |
| 2026-10-12 | Decisiones ya no lista las preguntas de las sesiones del equipo (no se podían contestar desde ahí) ni nada de proyectos de prueba; `decisiones_pendientes` tampoco las cuenta | Para eso están los avisos del orquestador, que llevan al chat. La insignia de la app contaba esperas que no tenían acción |
| 2026-10-12 | Proyectos de prueba: campo `prueba` (casilla en Nuevo proyecto e interruptor en Equipo); un nombre que empieza con "prueba-" lo marca solo, también los existentes (migración 5). No avisan, no entran en Decisiones y se detienen solos tras 30 min sin actividad del equipo; el chat funciona igual | prueba-39 avisaba como un proyecto real. La detención la hace el servidor cuando el monitor consulta sus encargos, así no hizo falta cambiar el monitor |
| 2026-10-13 | Respuesta en vivo por Server-Sent Events (`GET /proyectos-creados/{id}/chat/eventos`) y, de respaldo, una ruta liviana (`/chat/en-vivo`) para consultar cada segundo | nginx ya tiene `proxy_buffering off` en `/api/` y no comprime `text/event-stream` (no está en `gzip_types`): los eventos pasan sin búfer y no hubo que cambiar nginx ni el despliegue. La web se autentica con su cookie (EventSource con `withCredentials`) y el backend corre en un solo proceso de uvicorn, así que el parcial puede vivir en memoria. La ruta liviana cubre a quien no pueda mantener la conexión (la app en segundo plano, una red que la corte) |
| 2026-10-13 | El texto parcial no se guarda en la base: vive en memoria del backend, por proyecto, con el id del turno. El mensaje final llega con ese id y lo reemplaza en el mismo instante (también en los `recientes` del evento); un parcial atrasado de un turno cerrado se ignora; sin noticias del monitor durante 60 s, la respuesta en curso se da por terminada | El parcial es efímero y llega cada 400 ms: guardarlo sería escribir en disco sin ganancia. Con el final y el "libre" en la misma lectura, la burbuja pasa de parcial a final sin salto. Los avisos salen solo de los mensajes guardados, así que nunca de un parcial |
| 2026-10-13 | Monitor 0.8.0: el orquestador corre con `--include-partial-messages`; un hilo propio (`HiloEnVivo`) manda cada 400 ms lo que cambió (leído, respondiendo, texto parcial sin bloques de orden) y un pulso cada 15 s; el final y el "libre" salen en orden por la cola que ya existía. Los encargos se consultan cada 1,5 s (antes 3) | Separar el hilo en vivo evita que el texto parcial espere a la ronda de encargos y no toca la cola persistente (un parcial perdido no importa; el final sí). Con 1,5 s el mensaje de Washington llega antes a la sesión y "Leído" aparece en 1 a 2 s |
| 2026-10-12 | El proyecto lleva un plan vivo (`plan.json` en la raíz, kit en `C:\xampp\htdocs\plan-vivo`, que no se copia). Fases F0 a F8; los prompts conservan su número global (P1 a P46) y las puertas también pasan a numeración global (G1 en F3, G2 a G6 en F4). Los Prompts 1 a 20 llegaron sin número y se numeraron por orden; el 30 no aparece en ninguna fuente y no se agregó | El kit exige ids únicos en todo el plan y toma del identificador «F4 · G1:» solo «G1». Decisiones de Washington en F4 · U3 |
| 2026-10-11 | App iOS: Face ID con el código del iPhone como respaldo; aprobar un comando de la lista "confirmar" de `/permisos/config` pide Face ID (si el iPhone no tiene bloqueo configurado, no hay con qué comprobar y se aprueba) | Misma regla de comandos peligrosos que la web |

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
| 2026-10-10 | Prompt 2 del port de Agent Office 3D: capa de comportamiento (`oficina3d/comportamiento.ts`) separada del estado; 13 alza un brazo, 14 globo con la pregunta y mira a la cámara, 19 va a la sala de descanso y se sienta en el sofá (4 lugares; los demás de pie cerca), 1 y los agentes nuevos entran por la puerta oeste, 12 y los que se cierran salen por ella, 15 reloj de arena y 16 barra de progreso dibujados sobre el monitor, 21 con pregunta deja una nota en su escritorio (sin pregunta, el escritorio queda reservado una hora). Etiquetas simples (libre = solo el proyecto, trabajando = actividad corta, te espera = borde oscuro, con errores). Isotipo y logo de Demo Org (`frontend/public/logos/`) en la escena 3D y en `/oficina`; sin texto "personal". Capturas en `docs/capturas/oficina3d-v2/`. Commit `5b91296` (subido a GitHub por Washington) |
| 2026-10-10 | Uso diario: copia `E:\visualizador-agentes-diario` en 3000/8000 (compilada, sin recarga, datos en `C:\Users\<user>\.visualizador-agentes\datos-diario`), servidor del frontend compilado (`backend/app/servidor_frontend.py`), scripts `scripts/diario/` (preparar, iniciar, detener, estado, actualizar, instalar y quitar arranque automático) y opción `CLAUDE_OFFICE_PRINCIPAL=visualizador` del hook. `<project path>` queda de respaldo, detenido. Capturas en `docs/capturas/diario-v1/`. Commit `2b60341` (Washington aprobó el hook con `CLAUDE_OFFICE_PRINCIPAL=visualizador`, lo reinstaló e instaló el arranque automático) |
| 2026-10-10 | Editor de la oficina 3D (catálogo, agregar, arrastrar en cuadrícula de 0,5 m, rotar, borrar, deshacer y rehacer, guardar y cancelar, exportar e importar JSON) con aviso de muebles que tapan caminos o escritorios; 9 temas de piso y pared más el claro actual; distribución por copia en `GET/PUT /api/v1/oficina3d/distribucion`. Correcciones: el cierre de un proceso muerto conserva su hora tras reiniciar el backend; `/datos` ya no da el error #418 por Tailscale. Capturas en `docs/capturas/editor-v1/`. Commit `8cbc808` |
| 2026-10-10 | Entornos intercambiables (selector "Entorno" en `/oficina/3d`, guardado por copia junto con la distribución de cada entorno): Original sin cambios, Puente de mando y Sala de control con mostrador. Tu puesto en todos los entornos (letrero "Tú", sentado si estás conectado). Capturas en `docs/capturas/entornos-v1/`. Commit `5fa222d` |
| 2026-10-10 | Entornos Cabinas por proyecto y Estudio abierto con jardín (asignación de puestos por proyecto, Cabina general e Isla general), más decoración en Puente de mando y Sala de control. La diaria arranca a través de su tarea programada y con el bucle Selector de asyncio (su backend dejaba de aceptar conexiones). Capturas en `docs/capturas/entornos-v2/`. Commit `6a8f82b` |
| 2026-10-10 | Aprobar o rechazar permisos (13) desde la oficina, el celular y la vista 3D: el hook registra cada PermissionRequest en el backend y espera la decisión según la política (por defecto, solo cuando no estás en la PC); rechazar admite un motivo que recibe Claude. Panel Permisos (política, espera, comandos que piden confirmación). Prueba real con dos sesiones de prueba de Claude Code (aprobada desde la PC, rechazada con motivo desde el celular). Capturas en `docs/capturas/permisos-v1/`. Commit `0579500` |
| 2026-10-10 | Corrección de la política de permisos: "solo_fuera_de_la_pc" se reemplaza por "solo_en_el_celular" (nueva por defecto): la oficina espera solo con el celular conectado y sin la PC; sin ningún dispositivo responde VS Code de inmediato; si el celular se desconecta durante la espera, se suelta. La política antigua guardada se convierte al cargar. Commit `8e9bba2` |
| 2026-10-10 | Prueba real de permisos con el hook instalado: Washington aprobó desde el iPhone el permiso de un comando de una sesión nueva y se ejecutó. VS Code muestra su diálogo al mismo tiempo y gana la primera respuesta (la de la oficina o la de VS Code). En modo Auto de Claude Code no se generan solicitudes de permiso. Todo hasta `8e9bba2` está en GitHub |
| 2026-10-10 | Etapa 0 (cierre): en `/oficina/3d` el clic en un agente abre su panel sobre la escena, sin salir de ella (el mismo panel que abre `?agente=<id>`); al volver de `/oficina` ya no se abre el panel de otro agente. Los scripts de la diaria muestran los acentos de git en Windows PowerShell 5.1. Plan por etapas registrado. Capturas en `docs/capturas/oficina-3d-clic/`. Commit `768cf83` |
| 2026-10-10 | Etapa 1.1: máquinas (registro, `machine_id` en eventos, sesiones, agentes y permisos; migración con respaldo de los datos existentes a "Alienware"), tokens por máquina solo para la ingesta, inicio de sesión de un usuario (argon2, cookie httpOnly de 30 días, token de app de un año, límite de intentos, CSRF, WebSocket con sesión) y pantalla `/entrar`. Desactivado en local (`VISUALIZADOR_AUTH=desactivado`): la diaria funciona igual. Capturas en `docs/capturas/entrar-v1/`. Commit `66de73f` |
| 2026-10-10 | Etapa 1.2: monitor de máquina (`monitor/`) con API local en 127.0.0.1:8765, cola SQLite sin conexión (orden, reintentos progresivos, id de evento sin duplicados), permisos reenviados (sin servidor: sin decisión al instante), lecturas de transcripciones y procesos, latido, comandos `estado`, `registro` y `reiniciar`, e instalador `.exe` de Windows (respaldo y cambio solo de las entradas de `claude-office-hook`, arranque oculto con tarea programada, desinstalación que deja todo como estaba). Comandos peligrosos siempre con aprobación, también en modo Auto. El backend recibe las observaciones de cada monitor y, con `LECTURA_LOCAL=false`, no lee nada de la máquina. Probado de punta a punta contra el backend de desarrollo con acceso activado y una carpeta de usuario simulada. Commit `ac72de4` |
| 2026-10-11 | Etapa 1.3: la oficina publicada en https://agents.example.com (VPS de the VPS provider): backend como servicio systemd con usuario sin privilegios en 127.0.0.1:8320 (acceso activado, `LECTURA_LOCAL=false`, secreto generado en el servidor), frontend estático servido por nginx, `/api` y `/ws` al backend, certificado de Let's Encrypt con renovación automática, respaldos diarios con 14 días y restauración probada, despliegue repetible desde la PC y script de estado. Los otros 12 sitios del VPS responden igual que antes. El WebSocket sin sesión ahora cierra con 4401 detrás de nginx (antes rechazaba con 403). Nuevos comandos peligrosos: `git checkout -- .`, `git restore .`, `git branch -D` y `TRUNCATE TABLE`. Instalador del monitor: dos instalaciones en el mismo segundo ya no pisan el respaldo original de `settings.json`. Commits `8ef06b5` y `67eed31` (prueba de caída con `kill -9` al proceso principal) |
| 2026-10-11 | Etapa 1.3 cerrada en el VPS: Washington ejecutó la instalación del sistema, fijó la contraseña de la oficina y corrió el respaldo con restauración en una copia y la prueba de caída (`kill -9`): todo correcto (detalle en "Resultado de los comandos de Washington"). Commit `53c1976` |
| 2026-10-11 | Etapa 1.4 cerrada: Washington creó el token de la Alienware e instaló el monitor el 2026-10-11 a las 08:30 (hora de Ecuador); primera conexión correcta con https://agents.example.com y cola en 0. Se quitó la web original de ClaudeOffice Visualizer (frontend, pipeline clásico del backend, dependencias y pruebas): `/` abre la oficina 3D y el sitio se llama "Oficina de agentes". CSP más estricta (sin wasm, workers ni WebSocket). La diaria local quedó detenida y sin arranque automático (carpeta y datos conservados como respaldo). El export copia las cargas RSC con el nombre plano que pide Next 16 (`frontend/scripts/rsc-planos.mjs`): sin 404 al precargar ni recarga completa con `router.replace`. Capturas en `docs/capturas/etapa-1-4/` (PC 1440 y celular 390, con y sin sesión). Commits `f2842d5`, `7dabd9b` y `1d686fb` (en GitHub) |
| 2026-10-11 | Etapa 2.1 (Prompt 26), datos para ver bien: esperas específicas con tabla editable, historial por turno (endpoint paginado), tokens y tiempo por turno, sesión y día (por cuenta y modelo, con trabajo continuo), límites de 5 h y semanal desde la barra de estado de Claude Code, detector de atascos y "Dónde quedamos" (el monitor lee el PROJECT.md de cada proyecto). Todo visible en `/datos` sin rediseño. Monitor 0.2.0 con `statusline` y `--actualizar` (conserva la versión anterior para las sesiones de Claude Code ya abiertas). README nuevo en español en lugar de la documentación heredada. Revisión independiente de las reglas de esperas y del detector, con correcciones. Commit `ac740e2` |
| 2026-10-11 | Etapa 2.3 (Prompt 28), ficha del agente y "Dónde quedamos" según los bocetos aprobados (`docs/bocetos/etapa-2/`): ficha en panel derecho de 460 px sobre la oficina 3D y en hoja inferior en celular, también desde `/oficina`; historial completo paginado en `/historial`; `/donde-quedamos` con plan por etapas, prompts de la etapa, lo último, lo siguiente, lo que espera decisión y el consumo de hoy; regla de las 8 horas al entrar a la oficina. Prompts de la etapa desde el PROJECT.md (monitor 0.2.1) y desde los pedidos "Prompt N" de los agentes. La vista de prompts se reemplazará por el sistema de prompts de Washington. Revisión independiente de accesibilidad y celular, con correcciones. Commit `830171e` |
| 2026-10-11 | Etapa 2.4 (Prompt 29), avisos resumidos con agente auxiliar: el monitor 0.3.0 resume cada aviso (permiso, pregunta, tarea terminada y atasco) con `claude -p`, Haiku y la cuenta del agente, totalmente aislado; la voz, las notificaciones y la ficha usan la frase, con el detalle técnico debajo. Interruptor en Avisos (encendido), consumo del auxiliar aparte, aviso nuevo de atasco y "Dónde quedamos" también en la primera visita de cada dispositivo. Pruebas reales con las cuentas personal y Demo Org. Revisión independiente del aislamiento y del enmascarado, con correcciones. Cierra la etapa 2 |
| 2026-10-11 | Etapa 3 (Prompt 31), app iOS base (`ios/VisualizadorAgentes`): Entrar (servidor y contraseña, sesión de 30 días en el Llavero, Face ID para abrir), TabView nativo con Liquid Glass (Oficina, Decisiones con insignia de pendientes reales, Dónde quedamos, Ideas; Decisiones e Ideas llegan en el Prompt 33), Oficina 3D en WKWebView (`/oficina/3d?app=ios`) con la tarjeta "Te esperan" nativa y el selector Lista o 3D, oficina en lista con filtro Todas, Personal o Demo Org, ficha nativa (ahora mismo, tiempo razonable, métricas, turnos de hoy, aprobar y rechazar con Face ID para comandos peligrosos) y Dónde quedamos con selector de proyectos. Web: modo `?app=ios` en la oficina 3D (sin barra ni ficha web; avisa a la app del agente tocado por el manejador de WebKit `oficina`). 27 pruebas unitarias del cliente, la decodificación y la lógica. Probada contra https://agents.example.com en el simulador. Capturas en `docs/capturas/etapa-3/`. Commits `797c025` (web, falta desplegar) y `156b707` (app) |
| 2026-10-12 | Etapa 3 (Prompt 33), parte B, backend de las bandejas: `GET /decisiones` (permisos, preguntas y atascos por urgencia, con la frase del auxiliar, el detalle técnico, proyecto, cuenta, máquina y hace cuánto, más las resueltas de hoy con quién, cómo y cuándo), "Ya lo vi" para atascos, ideas (guardar, listar, cambiar el proyecto, archivar) en `bandejas.db` con versión de esquema, las opciones de cada pregunta en `/agents/state` (`pregunta_opciones`) y el conteo `decisiones_pendientes` para la insignia de la app; las decisiones de la app quedan como "app iOS". Parte A: las preguntas quedan de solo lectura (decisión de esta fecha) |
| 2026-10-12 | Arreglo: las resueltas de hoy de Decisiones muestran el nombre del proyecto (no el de la carpeta de transcripciones, `e--Test-SkyNest`). Commit `7664a22` |
| 2026-10-12 | Etapa 4 iniciada (investigación): documentación oficial revisada y dos pruebas reales en carpetas temporales con Haiku: un programa lanza `claude -p` con stream-json y le manda dos mensajes en la misma sesión, que la oficina ve con los hooks actuales; y un orquestador le manda una orden a un agente con `ListAgents` y `SendMessage`, que el agente cumple en 1 s. Informe y tres arquitecturas en `docs/etapa-4/investigacion.md`; se recomienda la A (procesos `-p` del monitor y mensajería entre sesiones, con un hook propio que aprueba cada orden) |
| 2026-10-12 | Etapa 4 (Prompt 37), proyectos con equipo: backend con registro de proyectos y equipos en `proyectos.db`, encargos para el monitor y ruta base por máquina (commit `c3c8d48`); monitor 0.4.0 que crea la carpeta en la ruta base, aplica la plantilla y lanza, pausa, reanuda y retoma el orquestador y los agentes con `claude -p` (commit `d960e83`); web con la pestaña Proyectos, Nuevo proyecto y la página de cada proyecto con Chat (llega en el Prompt 38), Equipo y Dónde quedamos. Commits `3b15261` (web) y `ef2f960` (documentación) |
| 2026-10-12 | Prueba real del Prompt 37 (desplegado `ef2f960`, monitor 0.4.0).
Se creó prueba-37 desde la web (cuenta personal, Haiku y esfuerzo bajo para los dos, plantilla Vacía). El monitor tomó el encargo en unos segundos: `E:\Agents\prueba-37` quedó con `.git` y PROJECT.md (sin `.gitignore`, por ser Vacía).
Las dos sesiones aparecieron en la oficina con modelo `claude-haiku-5-5`, esfuerzo bajo, su rol y la carpeta, y respondieron el saludo.
Pausar cerró sus dos procesos y reanudar los retomó con las mismas sesiones (`Session started (resume)`).
Los 73 procesos de Claude Code y VS Code que había antes siguieron vivos, y las otras 8 sesiones de la oficina no cambiaron.
Ajustes:
- Una sesión lanzada que el monitor informa viva pero que la oficina vio terminar se muestra "En espera" (estado 18, sin cierre ni aviso).
- Un equipo activo y quieto dice "En espera" en Proyectos.
Capturas en `docs/capturas/etapa-4/` |
| 2026-10-12 | Etapa 4 (Prompt 38), chat y órdenes: backend con mensajes y órdenes (esquema 2 de `proyectos.db`), aprobación automática, Detener y agregar agente (commit `1ce3d5f`); monitor 0.5.0 de intermediario (commit `81ea71e`); web con Chat, tarjetas de orden, Equipo y Decisiones (commit `2f4bd42`). Prueba real abajo |
| 2026-10-12 | Prueba real del Prompt 38 con prueba-37 (desplegado `206b394`, monitor 0.5.3).
Paso a paso:
- Desde el chat, el orquestador propuso la orden de hola.txt; quedó por aprobar, primera en Decisiones (API y bloque morado de la web) y en el contador.
- La edité a "Prueba 38" y la aprobé: llegó solo al agente de prueba-37, que creó `E:\Agents\prueba-37\hola.txt` con la línea `Prueba 38`. El resultado volvió al orquestador, que supo que la orden se había editado.
- Otra orden (adios.txt) rechazada con motivo: el orquestador recibió el motivo y no se creó el archivo.
- Con el interruptor encendido, la orden de auto.txt pasó sola (decidió: automático); después se apagó.
- Seguridad: pedido de usar `ListAgents`, `SendMessage`, la terminal o darle una orden a "visualizador-agentes"; el orquestador no tenía ninguna de esas vías y no salió nada. De los 75 procesos de Claude Code y VS Code de antes, solo cambiaron los dos de prueba-37 (los relanzó el monitor al actualizarse).
Arreglos durante la prueba: monitor 0.5.1 (rol nuevo al retomar, citas que no son órdenes, `53895bb`), backend `64d7028` (permisos del equipo esperan la decisión), backend `ec57b85` y monitor 0.5.2 `fb35f26` (el orquestador sabe si la orden se editó), backend `0cddcc6` (540 s) y monitor 0.5.3 `206b394` (`acceptEdits`).
Capturas 38-chat.png, 38-orden.png y 38-equipo.png en `docs/capturas/etapa-4/` |
| 2026-10-12 | Etapa 4 (Prompt 39), reglas de la casa, comandos seguros, plantillas y entrevista: backend con el esquema 3 de `proyectos.db` (commit `0696758`), monitor 0.6.0 (commit `24ef50f`) y web con Ajustes y los interruptores por proyecto en Equipo (commit `31e0572`) |
| 2026-10-12 | Prueba real del Prompt 39 con prueba-39 (desplegado `31e0572`, monitor 0.6.0; personal, Haiku y esfuerzo bajo, plantilla Web, autoskills apagada).
Paso a paso:
- La carpeta quedó con `.git`, `.gitignore` de Web, PROJECT.md con las secciones del estándar y CLAUDE.md con la sección de la plantilla y el bloque de 8 reglas (autoskills no aparece). El agente arrancó con los 7 comandos seguros; el orquestador, con `acceptEdits` y sin terminal.
- El orquestador abrió la entrevista solo, en dos tandas de tres preguntas (objetivo, público y alcance; plataformas, restricciones y fechas), escribió en PROJECT.md la especificación, cuatro decisiones con su porqué y un plan en fases, y propuso la primera orden con "Estimado: 45 min" y "Dificultad: 3 de 10".
- Esa orden suponía un proyecto Next.js ya creado: se rechazó con el motivo y el orquestador agregó una fase 0 para crearlo.
- Comandos: `git status` corrió sin pedir permiso; `node -p 1+1` pidió permiso, esperó (unos 9 min de plazo) y se rechazó desde la oficina; el agente informó el error exacto.
- Al apagar "Tema claro por defecto" en Equipo, el bloque de CLAUDE.md se actualizó sin tocar lo demás y las sesiones vivas recibieron el aviso.
- De los 67 procesos de Claude Code y VS Code de antes no se tocó ninguno; los únicos nuevos son las dos sesiones de prueba-39.
Capturas 39-reglas.png, 39-entrevista.png y 39-plan.png en `docs/capturas/etapa-4/` |
| 2026-10-12 | Etapa 4 (Prompt 41), aislar las sesiones del equipo y tres mejoras: monitor 0.7.0 sin la configuración de usuario (commit `c76acda`), avisos de reglas juntos y plantillas Web y App aclaradas (`3240dc5` y `1ff8720`), markdown seguro en el chat (`82763fc`).
Prueba real con Claude (Haiku, esfuerzo bajo) y un monitor de prueba con el código del repo, no el instalado:
- Antes (como 0.6.0): `npm run saludo`, permitido por la regla de usuario `Bash(npm run:*)` y fuera de los comandos seguros, corrió sin preguntar.
- Después (0.7.0): el mismo comando respondió "This command requires approval" y el hook informó el permiso a la oficina (permission_request, Bash, "npm run saludo"); `git status` corrió sin preguntar.
- Las 4 sesiones de prueba aparecieron en la oficina con su cuenta y cambiaron de estado; las de la cuenta personal escribieron su transcripción en `.claude/projects` y las de Demo Org en `.claude-demo/projects` (la de Demo Org respondió con su propio límite semanal).
- Con el backend y la web locales (3100 y 8100) y el mismo monitor de prueba: la plantilla Web dice que el proyecto Next.js lo crea la primera orden; el orquestador respondió con título, lista numerada, negritas, bloque de código y enlace, todo con formato; cuatro cambios de reglas seguidos llegaron como un solo aviso por sesión con "Se quitó" de las dos que quedaron apagadas.
- No se tocó ningún proceso: los 81 de Claude Code y VS Code de antes siguieron vivos y las sesiones de prueba se cerraron.
Capturas 41-chat-formato.png y 41-avisos.png en `docs/capturas/etapa-4/` |
| 2026-10-12 | Etapa 4 (Prompt 42), API completa para la app y rol al retomar: backend con el título de las órdenes (esquema 4), el vínculo con "Dónde quedamos" y `GET /proyectos-creados/{id}/ordenes` (commit `81e84e5`); web con el título en la tarjeta y el historial (`71a3ca6`); monitor 0.7.1 con `--system-prompt-snapshot off`, el título en el bloque de orden y el rol que deja claro quién es Washington (`aebe06a`).
Prueba real con Claude (Haiku, esfuerzo bajo) y un monitor de prueba con el código del repo:
- Rol al retomar: un equipo nació con el rol "color ROJO", se pausó, el rol cambió a "AZUL" y se reanudó sin aviso de rol. Sin la opción respondió "Rojo"; con `--system-prompt-snapshot off`, "AZUL".
- Presentación: 6 de 6 saludos reales dijeron "Hola, Washington. Soy el orquestador del proyecto …".
- Web y backend locales: el orquestador propuso la primera orden con su título ("Fase 1 · Prompt 1: crear proyecto Next.js base", `titulo_propio: true`); `donde_quedamos_id` coincidió con el `id` de su entrada en `GET /proyectos`.
Captura 42-orden-titulo.png en `docs/capturas/etapa-4/` |
| 2026-10-12 | Etapa 4 (Prompt 43), avisos de los orquestadores que se pueden atender y proyectos de prueba: backend con esquema 5 (`proyectos.prueba` y `avisos_orquestador`), `GET /avisos-orquestador`, Ignorar y Esperar, detención de las pruebas inactivas y Decisiones sin preguntas del equipo ni pruebas (commit `b9253ce`); web con la pila de avisos (Responder, Ignorar, Esperar) en Proyectos y la oficina, el chat que resalta la pregunta y deja el campo listo, la casilla y la etiqueta "Prueba", y los avisos de voz que ya no anuncian sesiones del equipo (`733e644`). El monitor no cambió (sigue 0.7.1). Diagnóstico en "Avisos de los orquestadores".
Prueba real en local (localhost:3100 y 8100) con un monitor de prueba y Claude (Haiku), con dos proyectos creados por la API: avisos-43 (normal) y prueba-43 (marcado solo por el nombre).
- Los dos orquestadores saludaron con preguntas; `GET /avisos-orquestador` devolvió un solo aviso, el de avisos-43, y la web lo mostró una vez con los tres botones.
- Responder abrió el chat de avisos-43 con la pregunta a la vista y el campo con el foco; la respuesta llegó y el orquestador contestó con otra pregunta, que generó un aviso nuevo.
- Esperar lo quitó (también al recargar: el servidor devolvió la lista vacía) hasta que el orquestador escribió otra pregunta, y entonces volvió a salir. Ignorar lo descartó.
- prueba-43 tuvo su pregunta en el chat y ningún aviso.
- Pruebas automáticas: backend 457 (9 nuevas en `test_avisos_orquestador.py`; fallan solo las 3 viejas de `path_utils`), web 307 (15 nuevas en `avisos-orquestador.test.tsx`).
Capturas 43-aviso-botones.png, 43-responder.png y 43-prueba-silenciosa.png en `docs/capturas/etapa-4/` |
| 2026-10-13 | Etapa 4 (Prompt 45), respuesta del orquestador que se va escribiendo, con leído y escribiendo: backend con esquema 6 (`mensajes.leido`), la respuesta en curso en memoria, `POST /maquinas/chat/en-vivo`, `GET /chat/en-vivo` y `GET /chat/eventos` (SSE) (commit `49e4f76`); monitor 0.8.0 con `--include-partial-messages` en el orquestador, `HiloEnVivo` y encargos cada 1,5 s, instalador recompilado sin instalar (`7336ddf`); web con Enviado y Leído, tres puntos, el parcial con markdown y el respaldo a la consulta (`1daca17`). nginx no cambió (ya tenía `proxy_buffering off`).
Pruebas automáticas: backend 474 (8 nuevas en `test_chat_en_vivo.py`; fallan solo las 3 viejas de `path_utils`), monitor 206 (4 nuevas en `test_en_vivo.py`; el claude falso ahora manda `stream_event`), web 320 (13 nuevas en `chat-en-vivo.test.tsx`). Prueba real con prueba-45: ver "Respuesta en vivo del orquestador".
Hallazgo: pyright 1.1.414 marca cientos de errores en archivos que no se tocaron (`middleware.py`, `permisos.py`, pruebas viejas), con o sin estos cambios. Los archivos del Prompt 45 no tienen ninguno; queda como deuda técnica. `path_utils.py` tiene una línea de más de 100 caracteres desde un commit anterior (ruff E501). |
| 2026-10-12 | F4 · U3, plan vivo adoptado con el historial: `plan.json` (9 fases, 54 items), `asignaciones.json` con los mensajes sin identificador asignados por contenido y fecha (y los ajenos en null), 16 tramos del orquestador cargados a mano y el bloque del kit en CLAUDE.md. Visor: http://localhost:5190/?plan=visualizador-agentes. Tres fallos del kit anotados en su PENDIENTES.md (el más serio: un subagente lanzado después de un mensaje en null cae en el item anterior). |

## Cómo levantar

Copia de desarrollo en 3100 (frontend) y 8100 (backend), en paralelo a la copia diaria (`E:\visualizador-agentes-diario`, 3000/8000; ver "Uso diario"). Comandos para Git Bash:

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
- `make dev` en esta carpeta usa 3000/8000 y choca con la copia diaria; usar siempre `make dev-local`.
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

## Editor de la oficina 3D

Botón "Editar oficina" en la barra de `/oficina/3d` (adaptado del editor de Agent Office 3D, MIT). Panel a la izquierda: catálogo (Planta, Escritorio, Sofá, Mesa de centro, Mesa de reuniones, Librero, Lámpara), mueble seleccionado (Rotar 45°, Borrar), Deshacer y Rehacer (50 pasos), tema de piso y pared, Guardar, Cancelar, Exportar JSON e Importar JSON. Atajos: R, Supr, Ctrl+Z, Ctrl+Y, Esc. Mientras se edita, los agentes siguen visibles pero no reaccionan y la cámara no se mueve al arrastrar.

- Archivos: `oficina3d/editor.ts` (estado; edita la distribución en vivo y guarda una foto para Cancelar), `EditorPanel.tsx`, `escena/PlacedFurniture.tsx` (piso clicable, arrastre, anillo oscuro de selección y rojo de bloqueo), `muebles.ts` (tipos y tamaños, sin three.js), `temas.ts`, `caminos.ts`, `distribucion.ts`.
- Guardado: `GET/PUT /api/v1/oficina3d/distribucion` (`backend/app/api/routes/oficina3d.py`) lee y escribe `distribucion.json` junto al registro del motor (la diaria: `C:\Users\<user>\.visualizador-agentes\datos-diario\distribucion.json`; desarrollo: `backend/distribucion.json`, ignorado por git; se puede fijar con `OFICINA3D_DISTRIBUCION_PATH`). Si no existe, devuelve la base del repo (`frontend/public/oficina3d/distribucion.json`). Valida tipos conocidos, límites (x ±22,5, z ±15,5), ids únicos, colores, máximo 200 muebles por entorno y 128 KB; escribe de forma atómica. Solo clientes que el middleware permite (localhost y Tailscale).
- Caminos (`caminos.ts`): un mueble no puede tocar los escritorios de trabajo ni sus sillas, ni quedar a menos de 0,22 m de un camino protegido: aristas del grafo de navegación, tramo de cada silla a su nodo, entrada (puerta, interior y nodo) y sala de descanso (pasillo, asientos y lugares de pie). Si lo hace, se marca en rojo, se lista en el panel y Guardar queda desactivado.
- Temas: Claro (actual, por defecto), Cálido, Fresco, Noche, Bosque, Rosa, Loft, Nórdico, Atardecer y Océano; se guardan en el mismo JSON (`tema`, `floorColor`, `wallColor`).

## Entornos de la oficina 3D (`oficina3d/entornos/`)

Selector "Entorno" en la barra de `/oficina/3d` (desactivado mientras se edita): Original, Puente de mando, Cabinas por proyecto, Sala de control con mostrador y Estudio abierto con jardín.

- Un entorno es un módulo de datos sin React ni three.js (`entornos/<nombre>.ts`, tipo `Entorno` en `entornos/tipos.ts`): `clave`, `nombre`, `tamano` (ancho y fondo de la sala), `zoom`, `puestosBase` (escritorios siempre dibujados), `puesto(i)` (posición y orientación del escritorio i; define cómo crece sin encimar), `tuPuesto`, `placaNombre` (nombre del proyecto en el monitor), `resaltarEspera` (luz azul en el escritorio de quien te espera), `descanso` (asientos, lugares de pie, pasillo y nodo), `puerta` y `entrada`, `mostrador` (rectángulo y `fila(i)`, o null), `choques` (cajas fijas), `grafo(bloqueado, puestosBase)`, `encuentros`, `paseo` y `limites` del editor. Opcionales: `agrupacion` (puestos por proyecto, ver abajo), `puestosGrafo` (escritorios fijos que los caminos rodean), `puestosVisibles` (escritorios vacíos que se dibujan junto a los usados), `girarHaciaTi`, `decoracion` (piezas como datos: plantas, árboles, sofás, libreros, lámparas, alfombras, césped...; las que están en el piso entran solas en los choques con `huellaPieza`) y `pisoCentral`. Dibujo: `entornos/decoracion.tsx` (Puente, Control, tu puesto y la pantalla; el Original sigue usando `escena/OfficeDecor.tsx`), `entornos/grupos3d.tsx` (Cabinas y Estudio), `entornos/piezas.tsx` (piezas de datos) y `entornos/comun3d.tsx` (texto en textura, letreros y puerta). Para agregar uno: crear `entornos/<nombre>.ts`, sumarlo a `ENTORNOS` en `entornos/activo.ts` y a `ClaveEntorno`, y dibujar su decoración; las pruebas lo recorren solas.
- Activo: `entornos/activo.ts` guarda el entorno en uso; `roles.ts`, `collision.ts`, `nav.ts` (rehace el grafo al cambiar), `presence.ts`, `comportamiento.ts` y `caminos.ts` lo leen en cada llamada. Al cambiar, la escena se vuelve a montar y los agentes aparecen directo en sus lugares.
- Guardado: el mismo `GET/PUT /api/v1/oficina3d/distribucion`. Los campos de primer nivel siguen siendo la disposición del Original (compatible con lo ya guardado); `entorno` es el activo y `entornos` guarda la disposición (muebles y tema) de los demás. Máximo 8 entornos y 128 KB.
- Tu puesto: escritorio de 2 × 0,9 m con dos monitores y letrero "Tú"; conectado → personaje sentado con ropa verde azulada; desconectado → silla vacía.
- Puente de mando (36 × 28 m): tu puesto abajo al centro; escritorios en arcos de 140° con el agente de frente a ti (10 en el primer arco; luego arcos de 14, 18 y 22 detrás). Pantalla grande en la pared del fondo con Te esperan, Trabajando, Libres y los nombres de quienes te esperan. Descanso en la esquina superior derecha, entrada abajo a la izquierda. 13 y 14: el escritorio se ilumina y se mantiene el gesto (mano alzada, globo).
- Sala de control con mostrador (32 × 32 m): pantalla en la pared del frente, tu puesto delante mirando a la sala, mostrador largo entre ambos; escritorios en filas de 5 mirando hacia ti (2 filas al inicio, 4 filas centrales y luego columnas a los lados y filas al fondo). 13 y 14: el agente camina al mostrador y hace fila frente a tu puesto, primero el que más tiempo lleva esperando (`ordenarFila` en `adaptador.ts`); su escritorio queda vacío con la silla girada; al dejar de esperar vuelve y la fila avanza. Hasta 5 en fila; después se dobla a lo largo del mostrador.
- Puestos por proyecto (`entornos/grupos.ts`, `asignarPorProyecto`): los escritorios vienen en grupos (cabina, isla). Un agente conserva su escritorio mientras exista; uno nuevo se sienta en un grupo de su proyecto si hay lugar; si su proyecto ya está en el grupo general, ahí; si no, su proyecto toma un grupo libre cuando tiene suficientes agentes (`umbralPropio`) y quedan grupos libres de reserva (`reservaGeneral`); si no, el grupo general. Un grupo es de su proyecto mientras tenga agentes (también los escritorios guardados de cerrados). Los dueños viajan en la memoria del adaptador y en `useOffice.grupos`.
- Cabinas por proyecto (50 × 30 m): pasillo central de izquierda a derecha con tu puesto en el medio; 6 cabinas de vidrio (paredes bajas con vidrio arriba), 3 a cada lado, con el nombre del proyecto en un letrero sobre la puerta; la Cabina general (arriba a la izquierda) es fija y crece con puestos extra en la parte de abajo a la izquierda, detrás de las cabinas y en la recepción. Cada cabina muestra de 2 escritorios hasta el último usado (máximo 8). Luz cálida y foco encendido mientras alguien trabaja; luz baja si no. 13 y 14: franja azul en la puerta, el agente sale al pasillo frente a la puerta de su cabina mirando tu puesto (el que más espera, al centro) y vuelve al dejar de esperar; su silla queda girada. Descanso al fondo a la derecha (dos sofás, mesa, alfombra, plantas, librero); entrada en la esquina inferior derecha.
- Estudio abierto con jardín (44 × 34 m): ventanal a lo largo de la pared del fondo con maceteros; tu puesto junto al ventanal a la izquierda, mirando las islas; islas de 4 escritorios (2 de cada lado) con letrero colgante del proyecto, 3 siempre dibujadas y hasta 17 (luego puestos extra a la izquierda). Isla propia desde 2 agentes; los proyectos de un agente comparten la "Isla general" (se abre otra si se llena). Jardín grande con césped, dos sofás con mesa, bancas, árboles, arbustos, lámparas y un camino de piedras desde la entrada (esquina inferior izquierda); cafetería en la pared derecha. 13 y 14: se queda sentado, su escritorio y su silla se iluminan en azul y se gira hacia tu puesto.
- Decoración: Puente y Control suman alfombra bajo tu puesto, libreros, mesa de reuniones, pizarra, lámparas, plantas y cuadros (como datos, sin tapar caminos). El Original no cambia: ya tiene sus salas completas.
- Pruebas: `frontend/tests/entornos.test.ts` (Original sin cambios; puestos sin superponerse ni tocar paredes, cabinas, mostrador o decoración, hasta 40 agentes o todos los fijos en Cabinas y Estudio; caminos conectados desde la entrada a cada puesto fijo, tu puesto, descanso, mostrador y puertas de cabina; orden de la fila; crecimiento; guardado por entorno) y `frontend/tests/entornos-grupos.test.ts` (cabina por proyecto y estable, máximo 6 y Cabina general, liberación de cabinas, 40 agentes sin repetir puesto, ida y vuelta a la puerta de la cabina; Isla general, islas que se agregan, quien espera en el Estudio se queda sentado).

## Uso diario (`E:\visualizador-agentes-diario`, 3000/8000): retirada

**Retirada el 2026-10-11 (etapa 1.4).** El monitor de la Alienware envía todo al VPS, así que la diaria dejó de recibir eventos. Se detuvo con `detener-oficina.ps1` (7 procesos; puertos 3000 y 8000 libres) y se quitó su tarea programada "Oficina de agentes (diaria)" con `quitar-arranque.ps1`. Se conservan la carpeta `E:\visualizador-agentes-diario` (en el commit `66de73f`) y los datos de `C:\Users\<user>\.visualizador-agentes\datos-diario` como respaldo. Para volver a usarla de emergencia: `iniciar-oficina.ps1` (no recibirá eventos mientras el monitor apunte al VPS). Lo que sigue describe cómo funcionaba.

Dos copias independientes: la **diaria** (la que Washington usa todo el día en la PC y en el iPhone por Tailscale) y la de **desarrollo** (`E:\visualizador-agentes`, 3100/8100). En la diaria nunca se edita código: solo se actualiza con `actualizar-oficina.ps1`. `<project path>` queda de respaldo: no se borra, no se modifica y no se arranca.

- URLs: PC http://localhost:3000/oficina (3D: /oficina/3d, datos: /datos); iPhone http://<TAILSCALE_IP>:3000/oficina. El frontend busca el backend en el puerto 8000 del mismo host.
- Producción: backend `uvicorn app.main:app --host 0.0.0.0 --port 8000 --loop asyncio:SelectorEventLoop` sin `--reload` (el middleware solo acepta localhost y la red de Tailscale 100.64.0.0/10); frontend compilado (`next build`, export estático en `frontend/out`) servido por `python -m app.servidor_frontend --dir ..\frontend\out --port 3000`. Procesos sin ventana y desacoplados de la consola (siguen vivos al cerrarla). Con la tarea programada instalada, `iniciar-oficina.ps1` (y por lo tanto `actualizar-oficina.ps1`) arranca siempre a través de ella (`Start-ScheduledTask`) y espera a que respondan; dentro de la tarea (estado `Running`) arranca los procesos él mismo.
- Cierre del backend del 2026-10-10 (causa): a las 17:52:12, 20 s después de arrancar, `backend.log` registró `Accept failed on a socket` con `OSError [WinError 64] El nombre de red especificado ya no está disponible` (un cliente cortó la conexión mientras se aceptaba). En Windows el bucle Proactor de asyncio cierra el socket que escucha ante ese error: las conexiones abiertas (la PC y el iPhone) siguieron funcionando unos minutos y ninguna nueva pudo entrar, por eso `estado-oficina.ps1` vio el puerto 8000 libre con el proceso vivo. No fue por arrancar desde la sesión de Claude Code (los procesos se crean con WMI, fuera de la sesión). Solución: el backend y el servidor del frontend usan el bucle Selector (no cierra el puerto ante ese error); el portapapeles de la vista clásica pasa a un hilo porque ese bucle no tiene subprocesos en Windows.
- Datos (fuera de los repositorios): `C:\Users\<user>\.visualizador-agentes\datos-diario\` con `visualizer.db`, `agent_events.db` (y sus `-wal`/`-shm`) y `logs\` (`backend.log`, `frontend.log`, `actualizar.log`, `preparar.log`). Se configuran en `E:\visualizador-agentes-diario\backend\.env` (`DATABASE_URL`, `STATE_EVENT_LOG_PATH`, CORS para localhost:3000, 127.0.0.1:3000 y <TAILSCALE_IP>:3000). Desarrollo sigue en `E:\visualizador-agentes\backend\*.db`: nunca escriben el mismo archivo. El `agent_events.db` de desarrollo se copió una vez al preparar la diaria (con desarrollo detenido) para no empezar sin historia.
- Scripts (`scripts\diario\`, PowerShell; correr con `powershell -ExecutionPolicy Bypass -File <script>`): `preparar-copia-diaria.ps1` (primera vez: clona, crea datos y `.env`, instala y compila; `-CopiarHistoria` copia la historia de desarrollo), `iniciar-oficina.ps1` (no duplica procesos; si un puerto lo usa otro programa no lo toca), `detener-oficina.ps1` (solo procesos cuya línea de comandos contiene `E:\visualizador-agentes-diario`), `estado-oficina.ps1`, `actualizar-oficina.ps1` (detiene, `git pull --ff-only`, `uv sync --frozen`, `npm install`, `next build` y arranca; si algo falla vuelve al commit y al frontend compilado anteriores y los arranca), `instalar-arranque.ps1` y `quitar-arranque.ps1` (tarea programada del usuario al iniciar sesión, sin administrador; si Windows no la permite, acceso directo en Inicio). Variables opcionales: `VISUALIZADOR_DIARIO_RAIZ` y `VISUALIZADOR_DIARIO_DATOS`.
- Hook: con `CLAUDE_OFFICE_PRINCIPAL=visualizador` en `C:\Users\<user>\.claude\claude-office-config.env`, el destino principal (8000) recibe también los tipos nuevos (`post_tool_use_failure`). Requiere reinstalar el hook (aprobación de Washington). Sin esa línea, el 8000 recibe todo menos `post_tool_use_failure` (los errores seguidos no se ven en la diaria).

### Volver a claude-office

1. Detener la diaria: `powershell -ExecutionPolicy Bypass -File E:\visualizador-agentes-diario\scripts\diario\detener-oficina.ps1` (y `quitar-arranque.ps1` si se instaló el arranque automático).
2. Quitar `CLAUDE_OFFICE_PRINCIPAL=visualizador` de `claude-office-config.env` (o dejarlo vacío): claude-office rechaza `post_tool_use_failure` con 422; sin la línea, el hook no se lo envía.
3. Arrancar `<project path>` como antes (`make dev` en esa carpeta). El hook sigue enviando al 8000 y al 8100.

## Permisos desde la oficina (estado 13)

Cuando un agente pide permiso, el hook `claude-office-hook permission_request` (`hooks/src/claude_office_hooks/permisos.py`) registra la solicitud en el backend principal (`POST /api/v1/permisos/solicitudes`: id, sesión, herramienta, comando o archivo, cuenta, proyecto) y el backend decide si el hook espera:

- Política (panel "Permisos" junto a Avisos, en `/oficina` y `/oficina/3d`; se guarda en `permisos.json` junto al registro del motor): `solo_en_el_celular` (por defecto: espera solo si hay un latido de celular vigente y ninguno de PC; si el celular se desconecta durante la espera, la suelta y el hook sigue sin decisión), `siempre` (espera aunque nadie tenga la oficina abierta) o `nunca`. Un `permisos.json` con la política antigua `solo_fuera_de_la_pc` se convierte a `solo_en_el_celular` al cargar. Tiempo de espera por defecto 90 s, entre 10 y 540 s.
- Mientras espera, el hook consulta con long-poll (`GET /api/v1/permisos/solicitudes/{id}?espera=20`, hasta su límite). Aprobada → imprime `{"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "allow"}}}`; rechazada → `behavior: "deny"` con `message` ("El usuario rechazó este permiso desde la oficina. Motivo: ..."). Sin decisión, tiempo agotado, backend caído o lento (registro: 2 s; cada consulta: su espera + 2,5 s) → no imprime nada y sigue el diálogo normal. Todo error termina en "sin decisión"; el hook nunca pasa de 540 s.
- Decisión (`POST /api/v1/permisos/solicitudes/{id}/decision`, solo localhost y Tailscale por el middleware): una sola vez (409 si ya se decidió o se respondió en VS Code), 410 si venció, 409 si la solicitud no espera a la oficina. Cada solicitud y decisión queda en `permisos.db` (junto al registro del motor; quién: PC o celular, cuándo, qué, con qué política); `GET /api/v1/permisos/historial`.
- Respondida en VS Code: el siguiente evento de la sesión la marca `resuelta_fuera` (Stop, UserPromptSubmit, SessionEnd, PostToolUse de la misma herramienta y comando, o un PreToolUse que llega más de 3 s después: los paralelos no cuentan) y los botones desaparecen.
- Interfaz (`frontend/src/components/permisos/`): en `/oficina`, debajo del escritorio de "Te esperan" y en el detalle, el comando completo, cuánto tiempo queda y los botones Aprobar y Rechazar (con motivo opcional); si la oficina no puede responder, "Responde en VS Code". En `/oficina/3d`, clic en el agente con la mano alzada (o `?agente=<id>`) abre el mismo panel. En el celular los botones miden 52 px y, antes de aprobar un comando de la lista (rm, del, git push, deploy...; configurable), pide confirmación. El aviso de permiso dice "Puedes responder desde la oficina." o "Responde en VS Code."; al hacer clic abre el detalle con los botones.
- `/agents/state` lleva en cada agente su `permiso` (pendiente, o recién decidido o vencido), o null.
- Documentación de Claude Code: https://code.claude.com/docs/en/hooks#permissionrequest (entrada, `decision`, timeout por defecto de 600 s y, si se agota, sigue el flujo normal). No está documentado si el diálogo de VS Code se muestra mientras el hook espera; con `claude -p` Claude Code esperó al hook antes de seguir.
- Para que funcione en la diaria hace falta reinstalar el hook y subir su `timeout` de 2 a 600 s en las dos cuentas (comandos en "Hook compartido").

## Inicio de sesión y máquinas (etapa 1.1)

Preparado para el VPS; en local queda desactivado y todo funciona como antes.

- **Modo** (`VISUALIZADOR_AUTH`): `desactivado` (por defecto, local): sin sesión ni tokens; los hooks sin token y el iPhone por Tailscale siguen igual; cada evento queda en la máquina local (`MAQUINA_LOCAL_ID`, `alienware`) o en la del token de máquina si lo trae. `activado`: la API, su documentación y los WebSockets exigen sesión (la ingesta, token de máquina); las páginas y archivos estáticos del frontend quedan públicos porque no traen datos (así `/entrar` carga aunque el backend sirva el frontend). Con el modo activado el backend no arranca sin `VISUALIZADOR_SECRETO` de al menos 32 caracteres.
- **Base** `acceso.db` (junto al registro del motor, o `ACCESO_DB_PATH`): usuario (hash argon2 de la contraseña), sesiones (web y app), máquinas, tokens de máquina y migraciones aplicadas. Los tokens se guardan como HMAC-SHA256 con `VISUALIZADOR_SECRETO` (SHA-256 si está vacío, solo en local); se ven una sola vez. Prefijos: `vas_` sesión web, `vap_` token de app, `vam_` token de máquina.
- **Sesión web**: cookie httpOnly, SameSite=Lax, `__Host-visualizador_sesion` con https (Secure, sin dominio) y `visualizador_sesion` sin https (`COOKIE_SEGURA=auto|si|no`; detrás de nginx con `CONFIAR_PROXY=true` mira `X-Forwarded-Proto`), 30 días por dispositivo. Con la cookie, todo lo que cambia algo exige el encabezado `X-Visualizador: 1` (CSRF). Cambiar la contraseña cierra todas las sesiones y tokens de app.
- **Token de app** (futura app iOS): `POST /api/v1/auth/app/token` con la contraseña entrega un token de un año para un dispositivo, revocable desde la lista de sesiones; se usa como `Authorization: Bearer vap_...` (sin CSRF: no es una credencial automática) y también en el WebSocket (en el encabezado, nunca en la URL: quedaría en los registros de acceso).
- **Límite de intentos** por IP: 4 fallos libres; desde el 5.º, espera de 5 s que se duplica en cada fallo, hasta 15 min (429 con `Retry-After`); un acierto limpia la IP. Además, más de 30 fallos en un minuto entre todas las IP cierran la entrada un minuto. Detrás de nginx la IP es `X-Real-IP` (que nginx pone con `$remote_addr`) o el último valor de `X-Forwarded-For`: los primeros los manda el cliente y se pueden falsificar. La contraseña se verifica fuera del bucle de eventos (argon2 es lento a propósito).
- **Máquinas**: id, nombre, sistema (windows/mac/linux), hostname, versión del monitor y última conexión (latido). Los eventos, las sesiones de la vista clásica, los agentes del motor (`agente.maquina` en `/agents/state`) y los permisos llevan `machine_id`, que siempre pone el backend (el del token, o el local): nunca el cliente. Una máquina solo ve sus propias solicitudes de permiso.
- **Migración** (`app/core/migracion_maquinas.py`, al arrancar el backend, una sola vez): registra "Alienware" (Windows, hostname de la PC), copia `agent_events.db`, `visualizer.db` y `permisos.db` a `respaldos/AAAAMMDD-HHMMSS-antes-maquinas/` con la API de respaldo de SQLite, agrega la columna `machine_id` y asigna `alienware` a lo que no tenga máquina. Queda marcada en `acceso.db`: volver a correrla no hace nada.
- **Hook**: con `CLAUDE_OFFICE_TOKEN_MAQUINA` (variable o `claude-office-config.env`) manda `Authorization: Bearer vam_...` solo al destino principal (nunca a los extra); sin él, igual que antes. Una sesión es de la máquina que la empezó: otra máquina no puede agregarle eventos (409). El monitor de la etapa 1.2 usará el mismo token.
- **Frontend**: `/entrar` (contraseña, Entrar, mensajes de contraseña incorrecta y de demasiados intentos con la cuenta regresiva); con el modo activado, cualquier página sin sesión va a `/entrar?volver=<ruta>` y vuelve (solo rutas del mismo sitio); botón Salir junto a Avisos y Permisos en `/oficina` y `/oficina/3d`. `apiFetch` manda la cookie y `X-Visualizador` y lleva a `/entrar` ante un 401.

| Endpoint | Quién puede usarlo (modo activado) |
|---|---|
| `GET /health`, `GET /api/v1/auth/estado`, `POST /api/v1/auth/entrar`, `POST /api/v1/auth/app/token`, `POST /api/v1/auth/salir`; páginas y estáticos del frontend | Cualquiera (entrar y token de app con límite de intentos; salir cierra la sesión de la cookie si sigue válida y siempre la borra) |
| `POST /api/v1/events`, `POST /api/v1/permisos/solicitudes`, `GET /api/v1/permisos/solicitudes/{id}`, `POST /api/v1/maquinas/latido` | Solo token de máquina (cada máquina ve solo sus solicitudes) |
| `GET /api/v1/auth/sesiones`, `DELETE /api/v1/auth/sesiones/{id}`, `GET /api/v1/maquinas` | Usuario (cookie + `X-Visualizador` en los cambios, o token de app) |
| Todo lo demás de la API (estado, permisos: decidir, configuración, historial; distribución 3D; vista clásica, que ya no pide la clave por arranque; documentación) | Usuario; un token de máquina recibe 403 |
| WebSockets (`/ws/...`) | Usuario (cookie, o token de app en `Authorization`); si no, se cierra con 4401. Con el modo activado acepta los orígenes de `BACKEND_CORS_ORIGINS` (por ejemplo el dominio público) |

Con el modo desactivado todos los endpoints quedan como antes (solo localhost y Tailscale) y `entrar` y `app/token` responden 409.

Nota de despliegue (etapa 1.3): nginx en el mismo servidor, con `proxy_set_header X-Real-IP $remote_addr;` y `X-Forwarded-Proto $scheme`, y `CONFIAR_PROXY=true`; sin eso todos los clientes se verían como 127.0.0.1 y cualquiera podría bloquear la entrada al dueño.

**Configuración de producción** (documentada en `backend/.env.produccion.example`, sin desplegar): `VISUALIZADOR_AUTH=activado`, `VISUALIZADOR_SECRETO` (generado una vez con `python -c "import secrets; print(secrets.token_urlsafe(48))"`), `CONFIAR_PROXY=true`, `COOKIE_SEGURA=si`, `BACKEND_CORS_ORIGINS=["https://agents.example.com"]`, rutas de datos (`STATE_EVENT_LOG_PATH`, `DATABASE_URL`, opcionales `ACCESO_DB_PATH` y `RESPALDOS_PATH`) y la máquina de los datos existentes (`MAQUINA_LOCAL_ID`, `MAQUINA_LOCAL_NOMBRE`, `MAQUINA_LOCAL_SISTEMA`).

**Comandos para Washington** (etapa 1.4; desde la carpeta `backend` de la copia donde corre el backend, que usa su `.env`). En la diaria actual, en PowerShell:

```powershell
cd E:\visualizador-agentes-diario\backend
uv run python -m app.acceso_cli contrasena                 # fija o cambia la contraseña (la pide dos veces, sin mostrarla)
uv run python -m app.acceso_cli maquinas                   # lista las máquinas
uv run python -m app.acceso_cli maquina-crear --id tower --nombre Tower --sistema windows --hostname TOWER
uv run python -m app.acceso_cli token-crear --maquina alienware   # muestra el token una sola vez
uv run python -m app.acceso_cli tokens                     # lista los tokens de máquina
uv run python -m app.acceso_cli token-revocar <id>
uv run python -m app.acceso_cli sesiones                   # sesiones web y tokens de app activos
uv run python -m app.acceso_cli sesion-revocar <id>
uv run python -m app.acceso_cli migrar                     # vuelve a correr la migración (no hace nada si ya está)
```

En el VPS (etapa 1.3) serán los mismos comandos desde la carpeta `backend` del despliegue.

## Monitor de máquina (etapa 1.2)

### Inventario: lo que el backend lee de la máquina local (2026-10-10)

El backend del VPS no puede abrir archivos ni procesos de la PC. Lo que hoy lee localmente:

| Lectura | Dónde | Para qué | Decisión |
|---|---|---|---|
| Proceso de Claude Code vivo (PID + hora de creación; Windows reusa PID) | `core/process_check.py`, `agent_state_engine.check_processes` | Cerrar la sesión (21) cuando el proceso termina | **Pasa al monitor**: ve los PID que el hook manda en cada evento y envía `proceso_vivo` |
| Contexto actual y modelo (`last_usage` de la transcripción) | `core/transcript_tail.py`, motor | Contexto usado (%), ventana del modelo | **Pasa al monitor** |
| Tokens acumulados de salida (`TranscriptTotals`, lectura incremental) | `core/transcript_tail.py`, motor | Tokens totales y por minuto (etapa 2: límites de 5 h y semanal) | **Pasa al monitor** |
| Textos del turno: último texto del asistente (`last_assistant_text`, `turn_progress`) y texto del usuario cerca de un encargo (`user_text_near`) | motor (`resolve_pending_texts`) | Pregunta explícita (14) y resumen del encargo cuando el evento no los trajo | **Pasa al monitor** (el hook ya manda el texto final en `Stop`; el monitor manda el último texto del asistente y del usuario) |
| Conciliación con la transcripción (`turn_progress`, `tail_first_ts`) | motor (`reconcile`) | Anotar sesiones con eventos perdidos | **Pasa al monitor** (turno terminado, primer y último momento) |
| Ruta de la transcripción y del proyecto | eventos del hook | Cuenta (personal/Demo Org), nombre del proyecto | **Queda en el backend** como texto (no abre nada); ya viene en cada evento |
| Proceso padre de la sesión (`claude.exe`, `claude.exe.old.*`, `node.exe`) | hook (`process_info.py`) | PID de la sesión | **Queda en el hook** (ya corre en la máquina) |
| Vista clásica: subagentes desde transcripciones (`transcript_poller`), tareas (`~/.claude/tasks`, `task_file_poller`), `bd` (`beads_poller`), `git status` (`git_service`), resúmenes con `claude` (`summary_service`), foco de terminal y portapapeles (`/sessions/{id}/focus`), lecturas de transcripciones de los handlers | backend | Vista clásica heredada | **Quedan solo en local**: la vista clásica no se publica en el VPS |
| Sus propias bases (`agent_events.db`, `visualizer.db`, `permisos.db`, `acceso.db`), `permisos.json`, `distribucion.json`, respaldos | backend | Datos del servidor | **Quedan en el backend** |

Regla: `LECTURA_LOCAL` (verdadera por defecto, en local) deja que el backend lea transcripciones y procesos de las sesiones de su propia máquina (`MAQUINA_LOCAL_ID`). En el VPS va en falso: el backend nunca abre archivos ni procesos y usa solo lo que manda cada monitor (`POST /api/v1/maquinas/observaciones`). Las sesiones de otra máquina nunca se leen localmente, aunque `LECTURA_LOCAL` sea verdadera.

### Arquitectura del monitor (`monitor/`, Python solo con la biblioteca estándar)

```
Claude Code ──hook──> "<monitor>.exe" hook <evento> ──HTTP──> monitor 127.0.0.1:8765 ──https + token──> servidor
                          (sin token)                           cola SQLite, lecturas, latido
```

- **Hooks**: el instalador cambia cada entrada `claude-office-hook <evento>` por `"%LOCALAPPDATA%/VisualizadorMonitor/v<versión>-<fecha>/visualizador-monitor.exe" hook <evento>` (mismo código del hook, apuntando al monitor; 600 s en PermissionRequest). Los hooks no conocen el token ni la dirección del servidor.
- **API local** (`servidor_local.py`, `ThreadingHTTPServer`, sin asyncio: no le afecta el problema del bucle Proactor): solo 127.0.0.1, puerto fijo (8765, configurable); la misma ingesta que el backend (`POST /api/v1/events`, `POST /api/v1/permisos/solicitudes`, `GET /api/v1/permisos/solicitudes/{id}?espera=N`) y `GET /estado`. Solo atiende a quien trae la clave local (`X-API-Key`, archivo `clave-local.txt` de la carpeta de datos, que el comando `hook` lee y manda), con `Host` 127.0.0.1/localhost, sin `Origin` ni `Sec-Fetch-Site` de navegador y, en los POST, con `Content-Type: application/json`: ninguna página web (CSRF, DNS rebinding) ni otro usuario de la PC puede inyectar eventos ni leer el estado. El puerto se abre en exclusiva (`SO_EXCLUSIVEADDRUSE`): un segundo monitor u otro programa no puede abrirlo encima.
- **Cola** (`cola.py`, `~/.visualizador-monitor/cola.db`): cada evento se guarda antes de responderle al hook, con un id único que viaja en `X-Evento-Id`; el backend no acepta dos veces el mismo id de la misma máquina (tabla `ids_recibidos`, guardado solo cuando el evento entró). Se envía en orden: si el primero falla, espera 1, 2, 4... hasta 60 s y nada se adelanta; al volver la conexión manda todo de inmediato. Solo 400/409/422 (rechazo de la aplicación) se descartan y se anotan; 401/403 (token inválido o revocado) esperan 60 s; 3xx, 404, 405, 413, 429 y 5xx (errores del proxy o del servidor) se reintentan sin perder nada. Las redirecciones no se siguen (llevarían el token a otro destino). Tope: 50 000 eventos o 7 días; lo que pasa del tope se descarta y se anota. Sobrevive a reinicios del monitor y de la PC.
- **Permisos**: se reenvían al servidor al momento, después de los eventos anteriores que estén en la cola (si la cola no se vacía en 1 s, sin decisión); 1,2 s para registrar, menos que los 2 s del hook (el servidor no queda esperando a un hook que ya se fue); la espera larga, hasta 25 s por consulta). Sin servidor responde `esperar: false` / `sin_conexion` y el hook sigue sin decisión (el diálogo de VS Code), nunca bloquea.
- **Lecturas** (`lector.py`, cada 15 s): de las sesiones que pasaron por el monitor en las últimas 24 h y solo dentro de las carpetas de cuentas configuradas: nunca rutas de red (`\\equipo\...`, que harían que Windows se autentique ante otro equipo) y la ruta se comprueba sin tocar el disco antes de abrirla; proceso vivo (PID + hora de creación), contexto y modelo, tokens de salida acumulados desde el primer evento de la sesión (lectura incremental; el primer evento se guarda en la cola, así un reinicio no reinicia la cuenta), últimos textos del asistente y del usuario, turno terminado, primer y último momento. Van a `POST /api/v1/maquinas/observaciones` (no se encolan: el ciclo siguiente manda el estado actual).
- **Latido** cada 30 s (`/api/v1/maquinas/latido`): versión, hostname y sistema.
- **Configuración** (`~/.visualizador-monitor/config.json`, solo del usuario): servidor (https; http solo hacia la misma PC, para pruebas), token, puerto, cuentas (`.claude` y `.claude-*` detectadas), intervalos. El token no aparece en el registro, en `estado`, en `/estado` ni en el manifiesto de instalación (se enmascara cualquier `vam_`, `vap_` o `vas_`).
- **Registro** de errores con rotación: `~/.visualizador-monitor/logs/monitor.log` (1 MB, 5 copias).
- **Arranque**: tarea programada del usuario "Visualizador monitor" (al iniciar sesión, oculta, sin administrador, sin límite de tiempo; como la diaria, con acceso directo en Inicio si Windows no deja crear la tarea) que corre `%LOCALAPPDATA%\VisualizadorMonitor\arranque.ps1`: un bucle que vuelve a arrancar el monitor si se cae y termina si existe el archivo `detener` de la carpeta de datos (lo usan el instalador y la desinstalación) o si el monitor ya no está.
- **Instalador**: lee y valida todos los `settings.json` antes de cambiar nada (uno ilegible, por ejemplo con comentarios, detiene la instalación sin tocar ningún archivo); respalda cada uno y guarda el manifiesto (`instalacion.json`) después de cada archivo. Cada instalación va en su propia carpeta (`v<versión>-<fecha>`), así una actualización no choca con los hooks que tienen abierta la anterior; las viejas se borran cuando quedan libres. Desinstalar: si el `settings.json` no cambió desde la instalación vuelve el original byte a byte; si cambió (o cambió entre dos instalaciones), revierte solo nuestras entradas y conserva lo demás. Sin manifiesto no toca nada. Avisa si quedaron eventos sin enviar.
- **Comandos** (`visualizador-monitor.exe ...`): `estado` (conexión, cola pendiente, último envío, cuentas), `registro [-n 50]`, `reiniciar`, `configurar --servidor URL --pedir-token`, `peligrosos`.
- **Etapa 4** (definida, sin implementar): `sesiones.py` (`LanzadorSesiones`: lanzar `claude -p --output-format stream-json --verbose --resume <id>` en una carpeta indicada y devolver la salida por líneas; las órdenes llegarán por `GET /api/v1/maquinas/ordenes`).
- **Empaquetado** (`monitor/empaquetar.py`, PyInstaller): `dist/visualizador-monitor/` (carpeta, para que cada hook arranque en unos 0,15 s) y `dist/instalar-visualizador-monitor.exe` (un solo archivo, 24 MB, con el monitor adentro). `dist/` y `build/` no se versionan: se regeneran con `cd monitor; uv run python empaquetar.py`.

### Comandos peligrosos (siempre con aprobación)

En PreToolUse de Bash o PowerShell, si el comando coincide con la lista, el hook responde la decisión `ask` y Claude Code muestra su diálogo de permiso aunque la sesión esté en modo Auto (en `claude -p`, sin diálogo, el comando queda rechazado). Lista inicial: `rm -rf` (recursivo y forzado, en cualquier orden), `Remove-Item -Recurse -Force`, `del /s`, `rd /s`, `git push --force` (también `-f` y `--force-with-lease`), `git reset --hard`, `git clean -fd`, formateo de discos (`format X:`, `Format-Volume`, `Clear-Disk`, `Initialize-Disk`, `diskpart`, `mkfs`, `dd of=/dev/...`) `DROP DATABASE` / `DROP SCHEMA` / `DROP TABLE`, `TRUNCATE TABLE`, descartar los cambios de todo el árbol (`git checkout -- .`, `git checkout .`, `git restore .` y rutas amplias como `./`, `*`, `:/`; `git restore --staged .` no, porque solo quita del índice) y `git branch -D` (o `--delete --force`; `-d` no, porque solo borra ramas integradas). Los despliegues a producción van comentados como ejemplo (Vercel `--prod`, `firebase deploy`, `npm run deploy:prod`) para marcar los que se usen.

**Cómo editarla**: `%USERPROFILE%\.visualizador-monitor\comandos-peligrosos.txt` (la crea el instalador, o `visualizador-monitor.exe peligrosos`). Una expresión regular por línea, sin distinguir mayúsculas; `#` al inicio es comentario; ` ## descripción` al final es el motivo que ve Claude. El archivo reemplaza la lista de fábrica (sin archivo o vacío, se usa la de fábrica); una línea inválida se ignora sin romper el hook. Se lee en cada comando: no hace falta reiniciar nada. Antes de comparar se unen las líneas cortadas (`\` en bash, acento grave en PowerShell); también se reconocen `/bin/rm`, `\rm`, `"rm"`, los alias de PowerShell con `-Recurse` (`del`, `rd`, `rmdir`, `erase`), `git push -uf` y `git push origin +rama`, y `git clean --force -d`. Un comando de más de 100 000 caracteres pide aprobación sin revisarlo. Límite: un script escrito en un archivo y ejecutado después (`bash x.sh`, `python -c ...`) no se ve. Código y pruebas: `hooks/src/claude_office_hooks/peligrosos.py`, `hooks/tests/test_peligrosos.py` (coincidencias y falsos positivos comunes como `docker run --rm`, `grep -rf`, `git clean -n`, `Format-Table`).

### Instalación en la Alienware (etapa 1.4, hecha el 2026-10-11)

Washington creó el token y ejecutó el instalador el 2026-10-11 a las 08:30 (hora de Ecuador). Monitor en `C:\Users\<user>\AppData\Local\VisualizadorMonitor`, conectado a https://agents.example.com, cola en 0; la oficina publicada muestra sus agentes. Pasos, para otra máquina o para reinstalar:

1. En PowerShell: `ssh -t <VPS_USER>@<VPS_IP> "sudo bash /var/www/visualizador-agentes/actual/despliegue/acceso.sh token-crear --maquina alienware"` (el token se muestra una sola vez; cópialo).
2. Cierra las sesiones de Claude Code abiertas (los hooks nuevos valen para las sesiones que se abran después).
3. En la Alienware, en el Explorador, doble clic en `E:\visualizador-agentes\monitor\dist\instalar-visualizador-monitor.exe` (ventana normal, sin administrador). Escribe `https://agents.example.com`, pega el token (no se muestra) y confirma con `s`. Respalda y cambia los hooks de `.claude` y `.claude-demo`, registra el arranque y arranca el monitor.
4. Comprobar, en una ventana de PowerShell normal: `& (Get-ChildItem "$env:LOCALAPPDATA\VisualizadorMonitor\v*\visualizador-monitor.exe" | Select-Object -Last 1).FullName estado` (debe decir "corriendo" y "conectado"; el instalador muestra la ruta exacta al terminar).
5. Desinstalar (deja todo como estaba; conserva los respaldos `settings.json.respaldo-visualizador-*`): en PowerShell, `& "E:\visualizador-agentes\monitor\dist\instalar-visualizador-monitor.exe" --desinstalar`.

Ojo: con el monitor instalado los eventos van solo a su servidor (el VPS); la diaria en 8000 y el desarrollo en 8100 dejan de recibirlos. Por eso se instala recién en la etapa 1.4, cuando el uso diario pase al VPS.

### Revisión independiente (2026-10-10)

Un subagente revisó el monitor, el instalador, el hook y el backend (seguridad del token, cola, errores). Corregido: la API local aceptaba pedidos de cualquier página web o usuario (ahora clave local, Host y navegadores); una ruta de transcripción de red podía filtrar el hash NTLM; las redirecciones llevaban el token a otro destino y perdían eventos; http aceptado hacia cualquier servidor; puerto sin exclusividad; instalación a medias con un `settings.json` ilegible; actualización bloqueada por hooks en curso; bucle de arranque que seguía vivo tras desinstalar; reinstalación que podía borrar cambios del usuario al desinstalar; solicitud de permiso que se adelantaba a sus eventos; cola sin tope y 404/413 de un proxy que descartaban eventos; ids de evento globales (ahora por máquina) y guardados después del almacén; observaciones de sesiones sin máquina; tiempos del permiso desalineados; sin tiempo límite en la API local; cuerpos de error en el registro; configuración dañada que hacía caer el monitor en bucle; expresiones peligrosas con atajos y lentas en comandos largos. Queda anotado: el hook confía en lo que responde en el puerto local (mitigado con el puerto exclusivo y la clave), y las ids del backend se consultan con SQLite en cada evento con id.

### Pruebas de la etapa 1.2 (2026-10-10)

Contra el backend de desarrollo (8100) con `VISUALIZADOR_AUTH=activado`, una base de acceso temporal y un token de prueba de la máquina `prueba-pc`, con el instalador empaquetado en una carpeta de usuario simulada (copias de los `settings.json`, tarea "Visualizador monitor (prueba)", puerto 8766): los eventos llegan con la máquina `prueba-pc`; con el servidor cortado la cola guardó 5 eventos y al volver los mandó en orden, una vez cada uno (un reenvío con el mismo id respondió "duplicado"); un permiso aprobado desde la oficina llegó al hook en 0,4 s; con el servidor caído el hook terminó sin decisión en 1,2 s; la API local respondió 403 sin la clave o desde un navegador; tras matar el monitor, la tarea lo volvió a arrancar con los 4 pendientes y los entregó; tokens y contexto leídos por el monitor aparecen en el panel; en modo Auto un `claude -p` real con `rm -rf` quedó rechazado por el hook y la carpeta siguió intacta. La desinstalación dejó los `settings.json` simulados idénticos byte a byte. La configuración real de Washington no se tocó.

## Ver bien: datos (etapa 2.1)

Solo datos y API; la ficha del agente y "Dónde quedamos" se diseñan aparte (Prompts 27 y 28). Para comprobarlos, `/datos` los muestra en bruto.

**Esperas específicas** (`backend/app/core/esperas.py`). Describen la tarea en curso de cada agente en una frase con el tiempo transcurrido.
- **Ejemplos:** "Instalando dependencias (npm), 40 s", "Corriendo pruebas (pytest), 3 min", "Unity: compilando scripts, 2 min", "Blender: render, 10 min", "Esperando tu permiso, 1 min", "Esperando tu respuesta", "Subagente: Revisar el código", "Navegador: navigate".
- **Sujeto que se compara:**
  - Bash/PowerShell: el comando, sin los mensajes de commit ni los cuerpos de heredoc.
  - MCP: `mcp:servidor:herramienta`; los plugins `plugin_<p>_<s>` quedan como `<s>`.
  - Subagente: su descripción.
  - Otras herramientas: `herramienta:nombre:detalle`.
- **Posición de comando:** las reglas de comandos solo coinciden donde empieza un comando, con prefijos como `npx`, `uv run`, `python -m`, `sudo` o la ruta del ejecutable. Así `grep pytest docs/` no cuenta como pruebas.
- **Sin regla:** el ejecutable y el tiempo ("Ejecutando python informe.py, 2 min"). `cd` y `export` se saltan.
- **Tabla de reglas:** patrón, texto y minutos razonables, el tiempo que usa el detector de atascos. Los servidores y `tail -f` no tienen límite.
- **Tabla editable:** `esperas.txt` junto al registro del motor (en el VPS, `/var/lib/visualizador-agentes/datos/esperas.txt`; se crea con su explicación y ejemplos). Formato: `patrón ## texto ## minutos`. Sus reglas van antes que las de fábrica y se releen solas.

**Historial por turno** (`historial.py`, `GET /api/v1/agents/{sesión}/historial?pagina=1&por_pagina=20`, del más reciente).
- **Turno:** empieza con el pedido de Washington, resumido a una línea. Los mensajes de subagentes salen como "(mensaje de un subagente)".
- **Contenido:** herramientas usadas, archivos editados, commits detectados con su mensaje (`-m`, `-am`, heredoc), errores, duración y tokens de salida.
- **Cómo terminó:**
  - `completado`;
  - `esperando`: terminó preguntando, o espera permiso o respuesta;
  - `interrumpido`: llegó otro pedido o se cerró sin `Stop`;
  - `error`;
  - `en_curso`.
- **Sesiones viejas:** las que ya no están en memoria se arman desde el registro del motor (7 días).

**Tokens y tiempo** (`consumo.py`, `GET /api/v1/consumo?dia=AAAA-MM-DD`, hasta 31 días atrás, días en `ZONA_HORARIA`=America/Guayaquil).
- **Tokens:** de salida, acumulados por sesión. Las muestras ahora se guardan en el registro del motor (tabla `muestras_tokens`, con el modelo), así que sirven después de un reinicio. Los turnos anteriores al 2026-10-11 a las 15:19 UTC no tienen tokens.
- **Tiempo de trabajo:** la suma de los turnos.
- **Continuo:** el tramo actual de turnos seguidos, con pausas de hasta 5 min.
- **Total del día:** sumando agentes y "con al menos un agente trabajando" (sin contar dos veces).
- Separado por cuenta (personal y Demo Org) y por modelo. El agente también lleva su `modelo` y `trabajo_continuo_s` en `/agents/state`.

**Límites de 5 h y semanal** (investigación en la documentación oficial, 2026-10-11).
- **Lo único documentado y confiable:** el objeto `rate_limits` que Claude Code le pasa por la entrada estándar al comando de la barra de estado (https://code.claude.com/docs/en/statusline).
  - Trae `rate_limits.five_hour.used_percentage` y `rate_limits.seven_day.used_percentage` (0 a 100) y `resets_at` (segundos Unix).
  - Solo existe para Pro y Max y después de la primera respuesta de cada sesión; cada ventana puede faltar.
- **Lo que no hay:**
  - `/usage` es una pantalla interactiva, sin salida para programas.
  - Los hooks no traen límites, ni tampoco OpenTelemetry (la documentación lo dice explícitamente).
  - No hay una API documentada para los límites de la suscripción; la que usa `/usage` es interna y no se usa.
- **Cómo se capturan:**
  - El monitor 0.2.0 trae `"<monitor>" statusline`: lee ese JSON, pasa la cuenta (`CLAUDE_CONFIG_DIR` o la carpeta `.claude*` de la transcripción), las dos ventanas y el modelo, y escribe la línea de la barra: `Opus · 5 h: 23 % (15:45) · semana: 41 % (lun 00:00)`.
  - El instalador la configura en cada cuenta solo si no tiene una barra propia (hoy ninguna de las dos tiene) y la quita al desinstalar.
  - El monitor envía los límites al servidor (`POST /api/v1/maquinas/limites`; lectura: `GET /api/v1/limites`). Cada cuenta lleva "lo último visto", y una ventana cuyo reinicio ya pasó se marca como dato viejo.
- **Alternativa si algún día no alcanza:** calcular solo tokens y tiempo propios (ya está) y mostrarlo como consumo, nunca como porcentaje del plan.

**Detector de atascos** (`atascos.py`; corre solo en estados de trabajo). Marca cuatro casos:
- **Una herramienta excede su tiempo razonable** (el de su regla de esperas). No cuentan las de segundo plano, las rápidas como Read o Edit (sería un evento perdido) ni la espera de tu permiso o tu respuesta.
- **El mismo error se repite** 3 veces entre los últimos 8 resultados del turno, y la última herramienta sigue fallando. El mensaje se normaliza: sin "Exit code N", números, rutas ni ids, y por programa. Las interrupciones no cuentan.
- **Trabaja 30 min sin avances.**
  - Avance es editar archivos (también `Set-Content`, `sed -i`, redirecciones o ediciones por MCP de Unity y Blender) o hacer un commit.
  - La ventana empieza después de la última herramienta larga.
  - Con un turno de pura lectura o investigación, el umbral es 45 min.
- **Trabajo después de un `Stop` sin pedido nuevo:** también se revisa (por ejemplo, cuando termina una tarea de fondo).

Junto al motivo se guardan los últimos 3 intentos y el último error. Los umbrales se configuran con `ATASCO_ERRORES_REPETIDOS`, `ATASCO_VENTANA_ERRORES` y `ATASCO_SIN_AVANCE_MIN`; los tiempos por tipo, en la tabla de esperas.

**"Dónde quedamos"** (`monitor/src/visualizador_monitor/proyecto_md.py`; `POST /api/v1/maquinas/proyectos`, lectura `GET /api/v1/proyectos`).
- **Lectura:** el monitor lee el PROJECT.md de cada carpeta donde trabajó un agente en las últimas 24 h, con una lectura tolerante a formatos (español o inglés, listas, casillas, subtítulos).
- **Contenido:** título, plan (hecho, en curso o pendiente), posición actual, siguiente paso, lo que espera decisión y el último commit (`git log`, o el registro del archivo).
- **Envío:** solo si cambió o cada 10 min. Rutas de red rechazadas sin tocar el disco; archivos de hasta 1 MB.
- El servidor le suma lo último que hizo un agente en esa carpeta (estado, espera y último turno). Si no hay PROJECT.md, se indica.

**Documentación:**
- El README es nuevo, corto y en español.
- Se quitaron la documentación heredada (arquitectura, guías, referencias, auditorías, CONTRIBUTING, CHANGELOG) y los README de `backend`, `frontend` y `scripts`.
- Se conservan `LICENSE` (MIT del proyecto original), `THIRD_PARTY_NOTICES.md`, `docs/proyecto`, `docs/research` y las capturas.

**Revisión independiente (2026-10-11).** Un subagente revisó las reglas de esperas y el detector. Se corrigió todo lo que encontró:
- todos los fallos de Bash se contaban como "el mismo error" (empiezan con "Exit code N");
- esperar al usuario se marcaba como herramienta larga;
- el turno no se revisaba después de un `Stop` sin pedido nuevo;
- las interrupciones contaban como error;
- palabras dentro de mensajes de commit, greps o rutas le ganaban al comando real (`git commit -m "push fix"` salía como "git push");
- `echo ... git commit` contaba como commit;
- faltaban escrituras por terminal y por MCP como avance;
- la regla de "sin avances" se apagaba y prendía con cada herramienta corta;
- el subagente sin descripción tenía 10 min;
- unidades de `sleep`, plugins MCP, servidores y `tail -f` sin límite;
- "Ejecutando cd";
- tiempos razonables más holgados (commit y push, 10 min; descargas, 15; subagente, 60);
- rendimiento: el tiempo continuo no recorre los tokens, y las horas de las muestras se arman una vez.

Con datos reales, después aparecieron dos defectos más que también se corrigieron: los mensajes de subagentes como pedido y los "commits" detectados dentro del código de un heredoc.

## Proyectos con equipo (etapa 4, Prompt 37)

Arquitectura A (ver la investigación más abajo y `docs/etapa-4/investigacion.md`).

**Backend** (`backend/app/core/proyectos_equipo.py`, rutas en `backend/app/api/routes/proyectos_equipo.py`, datos en `proyectos.db` con versión de esquema):
- **Proyecto:** nombre, máquina, cuenta (personal o demo), ruta, plantilla (web, unity, expo, vacía), estado, aprobación automática de órdenes (todavía sin efecto) y fecha.
  - Estados: creando, activo, pausando, pausado, reanudando y error.
- **Equipo:** el orquestador y de 1 a 4 agentes de código, cada uno con modelo, esfuerzo, id de sesión (lo decide el servidor) y estado (pendiente, activo, pausado, detenido o error).
- **Nombre:**
  - Solo minúsculas, números y guiones, sin empezar ni terminar con guion, hasta 50 caracteres.
  - Sin puntos, barras ni nombres reservados de Windows.
  - No se repite en la misma máquina. Que la carpeta no exista lo comprueba el monitor.
- **Rutas de usuario:**
  - `GET` y `POST /api/v1/proyectos-creados`, `GET /proyectos-creados/{id}`, `POST /proyectos-creados/{id}/pausar` y `/reanudar`.
  - `GET /proyectos-creados/maquinas`: ruta base, si la máquina está encendida (latido en los últimos 90 s) y si su monitor sabe crear proyectos (0.4.0 o más).
- **Rutas de máquina** (token de máquina):
  - `GET /api/v1/maquinas/encargos`: sus encargos; quedan tomados y se vuelven a entregar si no informa en 3 min.
  - `POST /maquinas/encargos/{id}`: el resultado de un encargo.
  - `POST /maquinas/equipos`: el estado de sus sesiones.
  - El latido trae `ruta_proyectos`.
- **`/agents/state`:** pone modelo, esfuerzo y rol a las sesiones lanzadas, porque en `-p` la oficina no los recibe.

**Monitor 0.4.0** (`monitor/src/visualizador_monitor/equipos.py`):
- **Ruta base:** `E:\Agents` en Windows si existe la unidad E:, si no `~/Agents`. Se cambia con `visualizador-monitor configurar --ruta-proyectos <ruta>`.
- **Crear:**
  - Arma la carpeta solo justo dentro de la ruta base real (sin rutas de red y sin enlaces que la saquen) y no pisa una carpeta existente.
  - Hace `git init` y deja un PROJECT.md con el nombre y la fecha.
  - La plantilla Web, Unity o App Expo agrega su `.gitignore` y una línea en PROJECT.md; Vacía no agrega nada.
- **Sesiones:** una `claude -p --input-format stream-json --output-format stream-json --verbose` por miembro, en la carpeta del proyecto, con:
  - `--model`, `--effort`, `--permission-mode default` y `--name <proyecto>-<miembro>`;
  - `--append-system-prompt` con su rol (orquestador: planifica con Washington y todavía no da órdenes; agente: espera órdenes);
  - `--session-id` del servidor (al reanudar, `--resume`);
  - la cuenta: `CLAUDE_CONFIG_DIR` solo para Demo Org, y sin variables `CLAUDE*` o `ANTHROPIC*` heredadas;
  - el orquestador con `--disallowedTools SendMessage,ListAgents`; los agentes con `--settings {"crossSessionInbound":"accept"}`.
  - Al crear, cada uno recibe un saludo corto para que arranque y la oficina lo vea por los hooks de siempre.
- **Pausar y reanudar:** pausar cierra la entrada de los procesos que lanzó el monitor y, si no terminan en 20 s, los detiene (solo esos PID). Reanudar los vuelve a lanzar con `--resume`.
- **Reinicio del monitor:** retoma los equipos que estaban activos. Si un proceso suyo anterior sigue vivo (mismo PID y hora de creación), lo detiene antes de relanzarlo.
- **Estado guardado:** en `equipos.json`, en la carpeta del monitor.

**Web:**
- `/proyectos`: lista con nombre, cuenta, máquina, qué está haciendo, equipo y estado, con morado #5B3FA8 para órdenes por aprobar, y el botón Nuevo proyecto.
- `/proyectos/nuevo`:
  - nombre con la ruta que se va a crear;
  - máquina con su estado (las apagadas o sin monitor 0.4.0 no se eligen), cuenta y plantilla;
  - equipo con modelo y esfuerzo (Opus 5.5 alto y Sonnet 5.5 medio por defecto), más agentes de código;
  - el interruptor de aprobación automática, todavía sin efecto.
- `/proyectos/ver?id=`: Chat (llega en el Prompt 38), Equipo (miembros, estado, Pausar el equipo y Reanudar) y Dónde quedamos de ese proyecto.
- Botón Proyectos en la oficina 3D y en la vista de cajas. La página `/donde-quedamos` sigue igual.

## Reglas de la casa, comandos seguros y entrevista (etapa 4, Prompt 39)

**Reglas de la casa:** lista global con texto y tipo (idioma, interfaz, git, documentación, órdenes, entrega, herramientas, pruebas u otra) y si está activa por defecto. Se edita en `/ajustes` y cada proyecto puede apagar o encender cada una en Equipo. El monitor las escribe en el CLAUDE.md del proyecto entre `<!-- reglas-de-la-casa: inicio ... -->` y `<!-- reglas-de-la-casa: fin -->`; lo demás del archivo no se toca, y si CLAUDE.md es un enlace no escribe. Si cambian, reescribe el bloque y les cuenta las reglas nuevas una vez a las sesiones vivas (las que estaban cerradas, al retomarlas).

**Comandos seguros:** lista global, también ajustable por proyecto. Los agentes de código los corren sin pedir permiso con `--allowedTools "Bash(<comando> *)"` (cada regla en su propio argumento, al final del comando). Un comando seguro no puede llevar comodines, comillas, paréntesis ni operadores de la terminal. Si la lista cambia, el monitor relanza al agente con `--resume` cuando termina su turno.

**Plantillas:** Web (Next.js), Unity, App (Expo) y Vacía. Todas dejan PROJECT.md con contexto, decisiones con su porqué, registro de avance, problemas y soluciones, y siguiente paso, y CLAUDE.md con el bloque de reglas; las tres primeras suman una sección propia en CLAUDE.md y su `.gitignore`. Vacía deja solo PROJECT.md y CLAUDE.md. Las plantillas no generan el proyecto (no corren `create-next-app` ni similares): eso es una orden más.

**Entrevista inicial:** al crear el proyecto, el orquestador saluda y entrevista con pocas preguntas a la vez (objetivo, para quién, alcance, plataformas, restricciones y fechas), escribe la especificación y el plan en PROJECT.md y propone la primera orden con estimado ("45 min" o "1 h 30 min") y dificultad del 1 al 10, que la tarjeta muestra como "3 de 10". Con la regla de autoskills encendida, primero propone `npx autoskills --dry-run` y después instalar con `-a claude-code`.

**Aislamiento (Prompt 41, monitor 0.7.0):** cada sesión del equipo arranca con `--setting-sources project,local` y `--settings <carpeta del monitor>/ajustes-equipo/<proyecto>-<miembro>.json`. Ese archivo se reescribe en cada arranque con los hooks de la oficina del settings.json de la cuenta (así toma la ruta del monitor instalado en ese momento) y, para el agente, `crossSessionInbound: refuse`. Las reglas de permiso, el modelo, la barra de estado y los otros hooks de la configuración de usuario no llegan al equipo. Si la cuenta no tiene hooks de la oficina, la sesión arranca igual (sin que la oficina la vea) y el monitor lo deja en su registro.

**Avisos de reglas:** un cambio de reglas no se escribe enseguida a la sesión: el aviso espera 8 s desde el último cambio, y si llega otro mientras tanto, se reemplaza por uno solo con todos los cambios respecto de lo que la sesión conocía ("Se agregó", "Se quitó") y la lista vigente.

**Rol al retomar (Prompt 42, monitor 0.7.1):** con Claude Code 2.1.257 o posterior, las sesiones se lanzan con `--system-prompt-snapshot off`: el system prompt se arma de nuevo en cada pedido, también al retomar, así que una sesión retomada toma el `--append-system-prompt` vigente y el monitor solo pone al día la huella del rol. Con una versión anterior (o si no puede leer la versión), sigue mandando el aviso de rol del Prompt 38.

**Datos nuevos para la app (Prompts 42 y 43, usados en el Prompt 44; Prompt 45, para el Prompt 46):**
- **Órdenes** (en `GET /proyectos-creados/{id}/chat`, `GET /proyectos-creados/{id}/ordenes`, `GET /ordenes` y el campo `orden` de `GET /decisiones`):
  - `titulo`: título corto para la tarjeta, como en el boceto Chat;
  - `titulo_propio`: `true` si lo escribió el orquestador, `false` si se sacó de la primera línea del texto.
  - El `resumen` de Decisiones ahora usa el título: "Orden N para agente: <titulo>".
- **`GET /proyectos-creados/{id}/ordenes`** (opcional `?estado=por_aprobar`): solo las órdenes del proyecto, las más nuevas primero, con `numero`, `titulo`, `agente`, `estado`, `estimado`, `dificultad`, `decidido_por`, `decidido`, `motivo`, `resumen`, `texto` y `editada`. Reemplaza leer las órdenes desde el chat en la sección Equipo.
- **Vínculo con "Dónde quedamos":**
  - `GET /proyectos` trae un `id` en cada entrada;
  - `GET /proyectos-creados` y `GET /proyectos-creados/{id}` traen `donde_quedamos_id` (o `null` mientras el monitor no haya informado ese PROJECT.md).
  - La app debe unir por ese id y dejar de comparar carpeta o nombre.
- **Avisos de los orquestadores (Prompt 43):**
  - `GET /avisos-orquestador`: `{"avisos": [...]}` ordenados del más viejo al más nuevo. Cada uno trae `clave` (`orden:<id>` o `mensaje:<id>`), `tipo` (`orden` o `pregunta`), `proyecto_id`, `proyecto`, `maquina`, `cuenta`, `texto` (la pregunta o "Orden N para agente: <titulo>"), `desde`, `hace_s`, `mensaje_id` (en preguntas) y `orden` (la orden completa, en órdenes). Ya vienen sin los ignorados, los que esperan y los de proyectos de prueba.
  - `POST /avisos-orquestador/ignorar` y `POST /avisos-orquestador/esperar` con `{"clave": "..."}`. Ignorar lo descarta; Esperar lo silencia hasta el siguiente mensaje del orquestador.
  - Responder: para `pregunta`, abrir el chat del proyecto en ese mensaje con el campo listo; para `orden`, mostrar la tarjeta de la orden con Aprobar, Editar y Rechazar.
  - Push: una sola notificación por `clave`.
- **Proyectos de prueba (Prompt 43):**
  - `prueba` (bool) en `GET /proyectos-creados` y `GET /proyectos-creados/{id}`; `POST /proyectos-creados` acepta `prueba` (si falta, se marca solo cuando el nombre empieza con "prueba-").
  - `POST /proyectos-creados/{id}/prueba` con `{"prueba": true|false}` para cambiarlo.
  - Las órdenes traen `proyecto_prueba`. `GET /decisiones` ya no trae las preguntas de las sesiones del equipo ni nada de proyectos de prueba, y `decisiones_pendientes` (en `/agents/state`) tampoco las cuenta.
- **Respuesta en vivo (Prompt 45, para el Prompt 46):**
  - Cada mensaje de `GET /proyectos-creados/{id}/chat` trae `estado` y `leido`. En los de Washington, `estado` es `enviado`, `leido` o `respondiendo` y `leido` es la hora ISO en que el monitor se lo entregó a la sesión (o null). En los del orquestador, los dos son null. El POST del chat ya devuelve `estado: "enviado"`.
  - `GET /proyectos-creados/{id}/chat` trae además `en_vivo`: `{"estado": "libre" | "leido" | "respondiendo", "parcial": "<markdown>", "mensaje_id", "desde", "actualizado"}`. `respondiendo` con `parcial` vacío = trabajando (tres puntos); con texto = la respuesta que se va escribiendo.
  - `GET /proyectos-creados/{id}/chat/en-vivo`: `{"version", "en_vivo", "recientes"}`, con los últimos 5 mensajes en la misma forma. Al terminar una respuesta, `en_vivo` pasa a `libre` y el mensaje final ya está en `recientes` en la misma lectura: unir por id y la burbuja no salta. `version` cambia con cada novedad.
  - `GET /proyectos-creados/{id}/chat/eventos`: el mismo JSON como Server-Sent Events (evento `chat`). Sale uno al conectar y otro en cada cambio, con un comentario `: pulso` cada 15 s. Cierra a los 5 min y pide `retry: 1000`. La app lo abre con su token (`Authorization: Bearer vap_…`) mientras el chat esté a la vista. Si la conexión falla, consulta `/chat/en-vivo` cada segundo, solo mientras `en_vivo.estado` no sea `libre` o haya un mensaje suyo sin leer.
  - Los avisos y el push siguen saliendo solo de los mensajes finales.

**Markdown en el chat:** los mensajes del orquestador se muestran con formato (negritas, cursivas, código, listas, encabezados, citas y enlaces); los de Washington siguen como texto plano.

**Hallazgos de la prueba real:**
- `git status`, `git diff`, `git log` y consultas como `node --version` ya son de solo lectura para Claude Code: nunca piden permiso, estén o no en la lista. Para probar la lista hace falta un comando que ejecute algo (`node -p 1+1` sí pidió permiso).
- Las sesiones del equipo también usan las 629 reglas de permiso de la configuración de usuario (por ejemplo `Bash(npm run:*)`): lo que Washington ya permitió en general corre sin preguntar también en los proyectos. Queda como pendiente de seguridad.
- La primera vez que se apagó una regla desde la web el cambio no quedó guardado (el servidor respondió una página HTML en ese momento); al repetirlo funcionó. Si vuelve a pasar, revisar el registro del VPS.

## Respuesta en vivo del orquestador (etapa 4, Prompt 45)

**Cómo viaja:**
- Washington escribe: el servidor guarda el mensaje (Enviado) y deja el encargo.
- El monitor lo toma (cada 1,5 s) y lo escribe a la sesión del orquestador: abre un turno con id y cuenta "leido" con el id del mensaje, que queda con su hora en `mensajes.leido` (esquema 6).
- La sesión empieza a trabajar (primer evento del turno): "respondiendo". Con `--include-partial-messages`, cada `stream_event` con `text_delta` de la sesión principal suma al texto parcial; el monitor lo manda agrupado cada 400 ms a `POST /maquinas/chat/en-vivo`, sin los bloques `<orden>` (ni uno a medio escribir).
- Al terminar, el final va a `POST /maquinas/chat` con el id del turno (reemplaza al parcial) y después sale "libre" con el id del mensaje (por si el hilo en vivo no alcanzó a contar el leído).
- La web abre `/chat/eventos` mientras la sección Chat está a la vista; si EventSource falla 3 veces seguidas sin recibir nada, consulta `/chat/en-vivo` cada segundo.

**En la web:** debajo de cada mensaje de Washington, "Enviado" y luego "Leído" junto a la hora; mientras el orquestador trabaja sin texto, una burbuja suya con tres puntos animados (quietos con movimiento reducido); el texto parcial aparece en esa burbuja con formato markdown y "Escribiendo…" donde va la hora. El final ocupa la misma burbuja sin salto.

**Prueba real (2026-10-13):** local (localhost:3100 y 8100), monitor de prueba 0.8.0 con el código del repo, Claude Haiku, proyecto prueba-45 (detenido al terminar). Tiempos medidos consultando `/chat/en-vivo` cada 100 ms, desde que el servidor guardó el mensaje:

| Pedido | Leído | Primer texto parcial | Final | Parciales distintos |
| --- | --- | --- | --- | --- |
| "Explícame en 10 puntos los riesgos…" (3147 caracteres) | 1,43 s | 2,30 s | 9,28 s | 16 (uno cada ~0,44 s) |

- El último parcial tenía el largo exacto del final: la burbuja no saltó.
- La primera medición ("Explícame en 10 puntos cómo organizarías este proyecto", la de las capturas) no sirve para la tabla: el medidor usaba `localhost` y en Windows Python tarda ~2 s en resolverlo. Con `127.0.0.1`, la segunda salió bien. En el navegador no pasa.
- La web abrió una sola conexión `/chat/eventos` y no cayó al respaldo; el monitor mandó 14 novedades en vivo entre el saludo y la respuesta.
- Capturas 45-enviado.png, 45-escribiendo.png y 45-final.png en `docs/capturas/etapa-4/`.

## Avisos de los orquestadores (etapa 4, Prompt 43)

**Qué se repetía (diagnóstico):** en la web, la espera de un orquestador aparecía en varios lugares:
- Avisos de voz y notificaciones de Windows (`avisos/deteccion.ts`): avisaban cada vez que una sesión entraba al estado 14 ("Te espera: respuesta") y, mientras siguiera ahí, recordaban cada 5 min ("Sigue esperando: …"). Como el orquestador cierra casi todos sus turnos con una pregunta, quedaba en 14 indefinidamente y el recordatorio no paraba. Este era el aviso que se repetía.
- No había cómo filtrarlo ni atenderlo: el filtro de pruebas comparaba "prueba-" contra el `session_id` (un UUID), así que nunca reconocía prueba-39; y el clic en la notificación abría la ficha del agente, donde una sesión `-p` del equipo no se puede contestar.
- Decisiones (backend) sumaba las sesiones del equipo en 14 como "pregunta" de solo lectura y las contaba en `decisiones_pendientes`, la insignia de la app.
- Otros lugares solo informan y no avisan: la marca "Te hizo una pregunta" de "Dónde quedamos", la burbuja de la oficina, la ficha del agente y el texto "haciendo" de Proyectos.

**Cómo queda:**
- Los avisos de voz y Windows de siempre ya no anuncian sesiones del equipo ni proyectos "prueba-"; sus esperas las cubren los avisos del orquestador.
- Pila de avisos abajo a la derecha en Proyectos y en la oficina (2D y 3D, no en el modo app): proyecto, qué pasó, la pregunta o la orden, hace cuánto, y Responder, Ignorar y Esperar. Consulta el servidor cada 5 s; la notificación y la voz salen una vez por clave.
- Responder abre `/proyectos/ver?id=…&seccion=chat&aviso=<clave>`: el chat lleva el mensaje a la vista, lo resalta 4 s y pone el foco en el campo; para una orden, lleva y resalta su tarjeta con sus botones.
- Una orden por aprobar avisa hasta que se decide; una pregunta deja de avisar en cuanto Washington escribe en el chat.

## Chat y órdenes (etapa 4, Prompt 38)

Regla de fondo: el agente de código nunca recibe una orden que Washington no aprobó (salvo con el interruptor automático encendido en ese proyecto), y el orquestador nunca puede escribirle a una sesión que no sea un agente de su proyecto.

**Cómo viaja una orden:**
1. Washington escribe en el chat; el mensaje viaja como encargo "mensaje" y el monitor lo escribe al orquestador.
2. El orquestador responde. El monitor manda el texto al chat y, por cada bloque `<orden agente="agente" estimado="10 min" dificultad="baja">...</orden>`, registra la orden en el servidor, que la deja por aprobar. Si el destino no es un agente de código de ese proyecto, no sale a ningún lado y el orquestador recibe un aviso (una sola vez seguida, para evitar un ida y vuelta sin fin).
3. Washington la aprueba (tal cual o editada) o la rechaza con motivo, desde el chat, la lista de Proyectos o la bandeja de Decisiones. La máquina nunca puede aprobar: solo informa en curso, terminada o fallida.
4. La aprobada llega como encargo "orden"; el monitor comprueba que el agente es de ese proyecto y la escribe a su entrada estándar. Si está ocupado, espera en su cola.
5. Al terminar el turno del agente, el monitor informa el resumen y se lo pasa al orquestador. Un rechazo le llega al orquestador con su motivo.

**Backend:** tablas `mensajes` y `ordenes` (esquema 2). Orden: texto propuesto y final, agente, estimado, dificultad, estado (por_aprobar, aprobada, rechazada, en_curso, terminada, fallida), motivo, quién decidió y cuándo, resumen.
- Usuario: `GET`/`POST /proyectos-creados/{id}/chat`, `GET /ordenes?estado=por_aprobar`, `POST /ordenes/{id}/aprobar` (`texto` si se editó) y `/rechazar` (`motivo`), `POST /proyectos-creados/{id}/auto-aprobar`, `/detener` y `/agentes`.
- Máquina: `POST /maquinas/chat`, `/maquinas/ordenes` y `/maquinas/ordenes/{id}`. Encargos nuevos: mensaje, orden, rechazo, detener y agregar.
- `/decisiones` pone las órdenes por aprobar primero (tipo "orden") y `decisiones_pendientes` las cuenta. La app iOS las muestra como "Orden" sin botones hasta que se actualice en una Mac.

**Monitor 0.5.x:** colas por miembro, lo en curso y lo pendiente de mandar se guardan en `equipos.json`. El texto del turno se arma con lo que escribió la sesión principal (no sus subagentes).
- 0.5.1: guarda una huella del rol de cada miembro y, si una sesión retomada nació con otro rol, le escribe el rol nuevo una sola vez. Un bloque `<orden>` citado entre comillas invertidas en una frase no es una orden, y una de relleno (`...`) tampoco.
- 0.5.2: al pasarle el resultado de una orden editada, le dice al orquestador que Washington la editó y con qué texto la recibió el agente.
- 0.5.3: los agentes de código con `--permission-mode acceptEdits`.

**Hallazgos de la prueba real (Claude Code 2.1.296):**
- `--resume` conserva el `--append-system-prompt` con el que nació la sesión e ignora uno nuevo (probado: una sesión nacida con la palabra clave ROJO y retomada con AZUL y luego VERDE solo citó ROJO). En cambio, `--permission-mode` sí se aplica al retomar. Por eso un cambio de rol se comunica con un mensaje (0.5.1), y Haiku lo acepta: escribió su primera orden apenas lo recibió.
- Una sesión `claude -p` sin anfitrión de permisos rechaza al instante cualquier permiso que el hook no decida. El hook de la oficina no esperaba cuando Washington estaba en la PC (política solo_en_el_celular), así que el primer intento de escribir hola.txt falló. Ahora esas sesiones siempre esperan la decisión en la web o la app.

**Web:** pestaña Chat con burbujas y la tarjeta morada de cada orden (Aprobar, Editar, Rechazar con motivo, Ver la orden completa); Equipo con historial, interruptor, Detener con confirmación y Agregar agente de código; bloque Decisiones arriba de la lista de Proyectos.

## Proyectos y orquestador (etapa 4): investigación

Informe completo, con fuentes y la salida real de las pruebas: `docs/etapa-4/investigacion.md`.

**Hallazgos clave** (Claude Code 2.1.296, documentación oficial):
- **Sesión controlada por un programa:**
  - `claude -p --input-format stream-json --output-format stream-json` deja un proceso vivo que acepta varios mensajes seguidos en la misma sesión; cada turno termina con un mensaje `result`.
  - Probado: dos mensajes, 7,6 s y 4,8 s, con Haiku y la suscripción (`apiKeySource: none`).
- **La oficina las ve:** sin `--bare`, una sesión `-p` corre los hooks de `~/.claude/settings.json`. Probado: llegaron todos sus eventos. El modelo no se informa, porque en `-p` no corre la barra de estado.
- **Permisos:** en `-p`, un permiso que nadie decide se deniega, pero el hook PermissionRequest corre y puede decidir; es el de siempre.
- **AskUserQuestion:** en `-p` solo se ofrece con un permission host (`canUseTool` del SDK o `--permission-prompt-tool`).
- **Mensajes entre sesiones:**
  - La cross-session messaging viene activada en Windows desde la 2.1.234. Claude usa `ListAgents` y `SendMessage`, y una sesión `-p` recibe mensajes si arranca con `crossSessionInbound: accept`.
  - Un mensaje no puede contestar un permiso.
  - Probado: orden del orquestador al agente, cumplida 1 s después del envío.
  - `ListAgents` muestra **todas** las sesiones de la máquina, también las reales; hay que limitar los destinos.
- **Otras vías:**
  - Remote Control solo se usa desde claude.ai/code, la app de Claude, VS Code y Desktop; no tiene una API para un cliente propio.
  - Agent teams no funcionan con `-p`.
  - El Agent SDK resuelve los permisos y `AskUserQuestion` con `canUseTool`, pero la documentación no permite ofrecer el inicio de sesión de claude.ai en productos de terceros, y el uso personal no está aclarado.
- **Visibilidad:** las sesiones `-p` no aparecen en el selector de `--resume` ni en `--continue`, pero se retoman con su ID. Las sesiones `--bg` sí aparecen y se pueden abrir con `claude attach`.
- **Al lanzar:** la cuenta va por `CLAUDE_CONFIG_DIR` (Demo Org), el modelo por `--model` y el esfuerzo por `--effort` (de low a max, según el modelo).
- **Rastros:** con `--no-session-persistence`, una sesión `-p` solo deja dos carpetas vacías en `~/.claude` (`projects/<carpeta>/memory` y `session-env/<sesión>`), y ninguna transcripción ni historial.

**Recomendación:** arquitectura A.
- El monitor mantiene procesos `-p` con stream-json para el orquestador y los agentes, y lleva el chat entre la oficina y el orquestador.
- El orquestador da órdenes con `SendMessage`.
- Un hook `PreToolUse` propio, pasado con `--settings` solo al orquestador, registra cada orden, espera el botón de Washington y limita los destinos a los agentes del proyecto.
- Los permisos van por el hook actual.
- Las alternativas B (`--bg` y agent view) y C (Agent SDK) están en el informe.

## Bandejas de Decisiones e Ideas (etapa 3, Prompt 33)

**Cómo llega cada cosa hoy (parte A):**
- **Permisos:**
  1. El hook PermissionRequest del monitor registra la solicitud (`POST /permisos/solicitudes`) y, según la política, espera la decisión con consultas largas (hasta 540 s; el hook tiene 600 s de límite).
  2. La web o la app deciden con `POST /permisos/solicitudes/{id}/decision` (aprobar, o rechazar con motivo).
  3. El hook imprime `allow` o `deny` para Claude Code.
  4. Si se responde en VS Code, el siguiente evento de la sesión la marca como resuelta fuera.
  - Todo queda en `permisos.db` (quién: PC, celular o, desde ahora, app; cómo y cuándo).
- **Preguntas (AskUserQuestion):** llegan como el `PreToolUse` de la herramienta (el motor ahora guarda sus preguntas y opciones) y como una solicitud de permiso de esa herramienta. El motor las trata como estado 14, no como permiso.
- **Atascos:** los calcula el motor (`atascos.py`) en cada lectura del estado.

**Hallazgo sobre AskUserQuestion (documentación oficial, CLI 2.1.296):**
- **Qué dice:** según https://code.claude.com/docs/en/hooks (secciones "PreToolUse decision control", "Tools that require user interaction" y "AskUserQuestion"), un hook `PreToolUse` puede contestar la pregunta. Lee la entrada, junta la respuesta en una interfaz propia y devuelve `permissionDecision: "allow"` con `updatedInput` que repite `questions` y agrega `answers` (texto de la pregunta a la etiqueta elegida; varias etiquetas separadas por comas). `"allow"` solo no alcanza. La documentación no habla de respuestas con texto libre, solo de etiquetas.
- **Por qué no se usa aquí:**
  1. El hook `PreToolUse` del visualizador está registrado con 2 s de límite y va dentro del monitor, que esta etapa no toca.
  2. En `settings.json` hay otros hooks `PreToolUse` para AskUserQuestion, de otras herramientas.
  3. Mientras el hook espera, VS Code no muestra la pregunta.
  4. Una prueba aislada (carpeta temporal, solo la configuración del proyecto, Haiku) con `claude -p` respondió "No such tool available: AskUserQuestion": en modo `-p` la herramienta ni se ofreció.
- **Resultado:** las preguntas son de solo lectura en la bandeja ("Respóndela en la PC" y la máquina). Contestarlas desde el iPhone queda para cuando se pueda cambiar el hook del monitor y probarlo en una sesión interactiva.

**Backend (parte B):**
- **`GET /api/v1/decisiones`:**
  - `pendientes`: primero los permisos, luego las preguntas y luego los atascos; dentro de cada tipo, lo que espera hace más tiempo.
  - Cada uno trae la frase del auxiliar (`resumen`) si existe, el detalle técnico, proyecto, carpeta, cuenta, máquina, `desde` y `hace_s`.
  - Los permisos traen el `id` de la solicitud y si espera decisión (solo entonces se decide desde aquí).
  - Las preguntas traen sus preguntas y opciones con `responder_en: "pc"`.
  - Los atascos traen el motivo, el último intento y el último error.
  - También trae `conteo` por tipo y `resueltas_hoy`:
    - permisos aprobados, rechazados o respondidos en la PC (de `permisos.db`);
    - preguntas respondidas en la PC o cerradas;
    - atascos marcados "Ya lo vi";
    - cada una con quién, cómo y cuándo, en el día de `ZONA_HORARIA`.
- **`POST /api/v1/decisiones/atascos/visto`** (`id`, `dispositivo`): saca el atasco de la bandeja sin tocar al agente.
- **Ideas:**
  - `GET /api/v1/ideas` (con `?archivadas=true` también las archivadas), más los proyectos que conoce el backend: los del monitor, los de los agentes y los que ya usan las ideas.
  - `POST /api/v1/ideas` (`texto`, `proyecto` o nada, `origen` dictada o escrita).
  - `PATCH /api/v1/ideas/{id}` (`proyecto`, `null` para quitarlo, o `texto`).
  - `POST /api/v1/ideas/{id}/archivar` (`archivar: false` la devuelve).
  - Estados: nueva (sin proyecto), asignada y archivada.
- **`/agents/state`:** trae `pregunta_opciones` en cada agente y `decisiones_pendientes` en la raíz, para la insignia de la pestaña con la misma consulta en vivo.
- **Persistencia:** `bandejas.db` en la carpeta de datos (el respaldo copia cada `.db`), con versión de esquema (`PRAGMA user_version`, versión 1: `ideas`, `atascos_vistos`, `preguntas`).

## Avisos resumidos con agente auxiliar (etapa 2.4)

Los avisos (voz, notificaciones de Windows y ficha) dicen una frase clara en lugar del texto técnico. Ejemplo real: en vez de leer `Remove-Item -Recurse Library\ScriptAssemblies`, la voz dice "SkyNest quiere borrar la carpeta de ensamblados de scripts de Unity y necesita tu permiso para continuar".

**Cómo funciona.**
1. El backend sabe qué avisos están vigentes por agente (permiso pendiente, pregunta, tarea terminada en los últimos 3 min y atasco), cada uno con una clave estable (`backend/app/core/resumenes.py`).
2. El monitor de cada máquina pide los suyos cada 1,5 s mientras hay sesiones activas (`GET /api/v1/maquinas/avisos`, token de máquina; solo sesiones de esa máquina).
3. El monitor los resume con el auxiliar (`monitor/src/visualizador_monitor/auxiliar.py`, dos a la vez como máximo) y manda la frase o el fallo con su consumo (`POST /api/v1/maquinas/resumenes`).
4. `/agents/state` trae en cada agente `resumenes` por tipo de aviso: `listo` con la frase, `pendiente`, `fallo` o `apagado`.
5. La oficina espera la frase hasta 8 s. Si llega, la usa; si falla, está apagada o pasan los 8 s, usa el texto de siempre. Un aviso nunca se retrasa más que eso.

**El auxiliar.**
- **Cuándo:** solo para avisos, nunca para cada evento.
- **Modelo y cuenta:** `claude -p` con Haiku y esfuerzo bajo, con la cuenta del agente que generó el aviso.
  - Se elige por la carpeta de su transcripción. Demo Org usa `CLAUDE_CONFIG_DIR=C:\Users\<user>\.claude-demo`; la personal, la carpeta por defecto, sin la variable.
  - Sin transcripción, se elige por la cuenta que informa el servidor. Una ruta de red o fuera de las cuentas no elige ninguna.
  - Un aviso de Demo Org nunca pasa por la cuenta personal ni al revés.
- **Entrada:** proyecto, tipo de aviso y los datos del aviso (herramienta y comando, pregunta, pedido, motivo, último intento y último error).
  - Cada campo se recorta y se enmascaran los secretos (`secretos.py`, archivo idéntico en el monitor y en el backend, que lo aplica antes de mandar los avisos al monitor):
    - tokens con prefijos conocidos, JWT, encabezados de autorización y cookies, webhooks y firmas en URL;
    - credenciales en URL y contraseñas en opciones de programas (`mysql -p`, `sqlcmd -P`, `sshpass -p`, `docker login -p`, `redis-cli -a`, `curl -u`, `net user`, `ConvertTo-SecureString`, `echo … | sudo -S`...);
    - `nombre=valor` y `--password valor`, claves privadas y cadenas largas al azar.
    - No toca rutas, SHA de git ni UUID.
  - En la prosa las rutas quedan con su último nombre. Todo va por la entrada estándar, nunca en la línea de comandos. La ruta de la transcripción no viaja: solo la cuenta.
- **Salida:** una frase de hasta 25 palabras en español latino neutro, que empieza por el proyecto (con su nombre exacto). Las rutas se acortan. Se descarta si trae código, URL, algo con forma de secreto o de clave al azar, o repite un dato raro de la entrada (letras y números juntos o símbolos).
- **Tope y límites:**
  - 8 s por llamada, con el árbol de procesos detenido al vencer.
  - 6 llamadas por minuto.
  - Caché por aviso y por texto (los recordatorios no vuelven a llamar).
- **Si falla:** sin cuenta, sin `claude`, por tiempo agotado, error o salida inválida, la oficina usa el texto actual.

**Aislamiento** (opciones verificadas en la documentación oficial de Claude Code, https://code.claude.com/docs/en/cli-reference y /headless, con la CLI 2.1.296):
- `--safe-mode`: no carga CLAUDE.md (tampoco de las carpetas padre), skills, plugins, hooks, MCP, comandos y agentes propios ni la memoria automática, y mantiene la sesión de la suscripción.
  - `--bare` no sirve: según la documentación nunca lee la sesión OAuth y exige una clave de API.
- `--setting-sources ""`: ningún archivo de configuración (usuario, proyecto ni local).
- `--settings '{"disableAllHooks":true}'`: segunda barrera contra los hooks.
- `--tools ""`, `--disallowedTools "mcp__*"` y `--strict-mcp-config` sin `--mcp-config`: ninguna herramienta ni servidor MCP.
- `--disable-slash-commands` y `--max-turns 1`.
- `--system-prompt`: reemplaza todo el prompt del sistema por las instrucciones del resumen.
- `--no-session-persistence`: la sesión no se guarda en disco ni se puede retomar.
  - Además, `CLAUDE_CODE_SKIP_PROMPT_HISTORY=1` y `DISABLE_AUTOUPDATER=1`.
  - Nunca se usa `--resume` ni `--continue`.
- `--output-format json`: la frase, los tokens, el costo y el modelo.
- **Entorno:** sin ninguna variable `CLAUDE*`, `ANTHROPIC*` u `OTEL_*` heredada, ni `NODE_OPTIONS`; así no entran las de una sesión de Claude Code (`CLAUDE_CODE_CHILD_SESSION`, `CLAUDECODE`) ni una clave de API.
  - Con `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`, `DISABLE_TELEMETRY=1`, `DISABLE_ERROR_REPORTING=1` y `ENABLE_CLAUDEAI_MCP_SERVERS=false`: sin telemetría ni conectores de claude.ai, y arranca más rápido.
  - Como refuerzo de `--safe-mode`: `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` y `CLAUDE_CODE_DISABLE_CLAUDE_MDS=1`.
  - Y `VISUALIZADOR_AUXILIAR=1`: si algún hook corriera igual, el hook del visualizador sale sin enviar nada (tercera barrera).
- **Carpeta:** `C:\Users\<user>\.visualizador-monitor\auxiliar`, vacía; la crea el monitor.
- **Segunda barrera:** el monitor (`es_de_auxiliar`, con la ruta fija y con la carpeta real resuelta, por si `VISUALIZADOR_MONITOR_DIR` la mueve o aparece un nombre corto 8.3) y el backend (`accept` e `ingest` del motor) descartan cualquier evento cuya carpeta, directorio de trabajo o transcripción esté en esa carpeta. También las solicitudes de permiso, en el monitor y en `POST /permisos/solicitudes`.
- `--effort low`: Haiku responde en 0,9 a 1,2 s con unos 50 tokens de salida (probado; sin la opción gastaba hasta 650).
- **Procesos:** al detener el monitor se detienen los auxiliares que sigan corriendo.
- **Riesgo residual (documentación oficial):** la configuración administrada sigue aplicando con `--safe-mode` y ninguna opción de la CLI la anula. La cuenta Demo Org es de tipo Team (`claude auth status`), así que la organización podría poner hooks o variables desde la consola de claude.ai, y esos hooks verían el texto enmascarado del aviso. En la máquina no hay configuración administrada local (`C:\Program Files\ClaudeCode` y `C:\ProgramData\ClaudeCode` no existen).

**Interruptor:** "Resumir los avisos en una frase clara" en el panel de Avisos (encendido). Es una configuración del servidor (`GET/PUT /api/v1/avisos/config`, archivo `avisos.json` en los datos). Apagado, el monitor no recibe avisos y no gasta tokens.

**Consumo:** cada llamada se anota aparte de los agentes (`auxiliar.jsonl` en los datos: cuenta, tokens de entrada y salida, segundos, costo y si falló). `GET /api/v1/consumo` lo trae en `auxiliar` (etiqueta "auxiliar", total y por cuenta). Se ve en `/datos` y en la línea de consumo de "Dónde quedamos".

**Otros cambios:**
- Aviso nuevo "Parece atascado", una vez por atasco.
- "Dónde quedamos" se abre primero también en la primera visita desde un dispositivo nuevo, con su aviso. Con el almacenamiento del navegador bloqueado no se aplica, para no repetirse en cada entrada.

**Pruebas reales en la Alienware (2026-10-11):**
- **Cuenta personal:** un aviso de cada tipo. **Demo Org:** con la sesión activa de vive-demo.
- **Tiempo:** de 1,9 a 2,2 s por resumen con la cuenta personal y 3,3 s con Demo Org (de 0,9 a 1,2 s de modelo; el resto es el arranque de la CLI). Unos 950 tokens de entrada, casi todos del prompt del sistema en caché, y unos 50 de salida.
- **Sin rastro:** después de las llamadas no hubo carpetas nuevas en `projects` de ninguna cuenta, ni sesiones nuevas, ni cambios en `history.jsonl`, y la carpeta del auxiliar siguió vacía.
- **Fuera de la oficina:** el auxiliar no apareció en la oficina, ni siquiera en el servidor anterior, que todavía no tenía el filtro.
- **De punta a punta:** avisos reales del servidor, resumidos y guardados con la versión final, en 2,2 a 2,6 s en total. La ficha muestra la frase como texto principal (`docs/capturas/etapa-2-4/`).
  - **Permiso, Demo Org (vive-demo).** Antes: "El servidor de pruebas rechazó la contraseña de carga-editor@… (401, admin.invalid-credentials) en un solo intento…". Después: "vive-demo pide permiso para usar la contraseña del servidor de pruebas; la clave fue rechazada y conviene revisarla antes de probar otra."
  - **Pregunta (server-monitor).** Antes: "¿Apruebas borrar estas 129 imágenes (las 4 filas de la tabla: versiones anteriores a las 2 últimas de vive-demo-migrations, …), conservando las 14 listadas?". Después: "server-monitor pregunta si puedes borrar 129 imágenes antiguas de cuatro proyectos, conservando las 14 más recientes; ninguna está en uso."
  - **Tarea terminada (SkyNest).** Antes: "SkyNest terminó". Después: "SkyNest terminó la tarea y está listo para tu revisión o el siguiente paso."
- **Prueba simulada, permiso (SkyNest).** Antes: `PowerShell: Remove-Item -Recurse Library\ScriptAssemblies`. Después: "SkyNest necesita tu permiso para borrar la carpeta de recursos compilados de Unity; ¿lo autorizas?"

**Revisión independiente (2026-10-11).** Un subagente revisó el aislamiento y el enmascarado (unos 90 casos de secretos). Se corrigió:
- la frase del modelo no se validaba contra secretos, y acortar rutas podía dejar la cola de una clave;
- se escapaban contraseñas de muchos comandos (lista arriba) y había falsos positivos ("basic authentication", `password_hash = ?`, rutas con un hexadecimal, SHA de git, UUID);
- cualquier máquina podía escribir la frase de sesiones ajenas o reemplazar una lista; ahora solo la máquina de la sesión, solo para un aviso vigente y sin reemplazar;
- el backend mandaba al monitor el texto sin enmascarar y la ruta de la transcripción;
- faltaban variables de entorno (telemetría, conectores, `OTEL_*`, `NODE_OPTIONS`) y la tercera barrera en el hook;
- el filtro dependía de una ruta fija, y las solicitudes de permiso no se filtraban;
- `buscar_claude` podía elegir el script de npm sin extensión;
- al detener el monitor podían quedar auxiliares corriendo.

Separación de cuentas, sin cambios: la revisión la probó con mayúsculas, barras mezcladas, `.claude-demo2`, nombres cortos, `\\?\` y rutas de red, y falla cerrada.

## Ver bien: ficha y "Dónde quedamos" (etapa 2.3)

Implementa los bocetos aprobados de `docs/bocetos/etapa-2/` (Main y FichaCelular para la ficha, DondeQuedamos y DondeCelular) con los componentes y estilos del proyecto: tema claro, IBM Plex Sans y Mono, sin emojis, botones de 44 px o más.

**Ficha del agente** (`frontend/src/components/ficha/`).
- **Dónde se abre:** al hacer clic en un agente de `/oficina/3d` (reemplaza el panel anterior) o de `/oficina`, y con `?agente=<sesión>`.
- **PC:** panel derecho de 460 px sobre la escena, que sigue visible.
- **Celular (< 700 px):** hoja inferior con scroll interno que deja ver parte de la escena.
- **Orden:**
  1. Cabecera: iniciales, proyecto, carpeta y máquina, cuenta y modelo. El esfuerzo todavía no llega en los datos.
  2. Permiso pendiente arriba de todo, en una frase clara, con el comando y Aprobar o "Rechazar con motivo". Reutiliza `PanelPermiso` con la variante `ficha`.
  3. Tarjeta de atasco: motivo, desde cuándo, último intento y último error.
  4. Pregunta del agente.
  5. "Ahora mismo": la espera específica, su tiempo y el tiempo razonable.
  6. Tres cifras: trabajo continuo, tokens de hoy, y atascos o errores.
  7. Turno actual y turnos anteriores.
  8. Enlaces a "Historial completo" (`/historial?agente=`, 20 turnos por página) y a "Dónde quedamos" del proyecto. Con un atasco, el primero dice "Ver qué intentó".
- **Teclado:** el foco entra a la ficha al abrirla y vuelve donde estaba al cerrarla. Escape la cierra. En celular es un diálogo que retiene el foco.

**"Dónde quedamos"** (`/donde-quedamos?proyecto=<carpeta>`, `frontend/src/components/donde/`).
- **Lista de proyectos:** nombre, última actividad, dónde va y alerta. Primero los urgentes (permiso, atasco, pregunta, decisión), después los más recientes. Incluye las carpetas con agentes que el monitor todavía no reportó.
- **Plan por etapas:** bloques hecha, actual ("Estás aquí") y pendiente. Si el plan tiene "Etapa N", solo se muestran las etapas principales.
- **Prompts de la etapa actual:** con estado, commit y tiempo.
  - La lista sale de los subítems numerados de la etapa en el PROJECT.md ("- 26: datos y API"), que lee el monitor 0.2.1, con los commits de las filas del registro que nombran ese prompt.
  - El tiempo, los commits y el estado salen de los pedidos "Prompt N · ..." de los agentes (`prompts_turnos` en `GET /api/v1/proyectos`). Los pedidos siguientes de la misma sesión hasta el próximo "Prompt M" se suman al mismo prompt.
  - **Esta vista se reemplazará por el sistema de prompts que Washington diseña aparte.**
- **Tres tarjetas:** lo último que se hizo (commit y último pedido), lo siguiente con quién debe hacerlo, y lo que espera tu decisión.
- **Consumo de hoy:** total y del proyecto.
- **Sin PROJECT.md:** lo último que hizo el agente en esa carpeta y el aviso de que no hay plan.
- **Celular:** versión compacta con los otros proyectos al final.
- **Acceso:** botón "Dónde quedamos" en la oficina 3D y en la vista de cajas.
- **Regla de las 8 horas:** al entrar a la oficina, si pasaron más de 8 h desde la última visita en ese dispositivo, se abre primero "Dónde quedamos" con un aviso.
  - La hora de la última visita se guarda en el navegador (`localStorage`) mientras la oficina está abierta.
  - No aplica en la primera visita del dispositivo ni con un enlace a un agente.

**Revisión independiente (2026-10-11).** Un subagente revisó accesibilidad y celular. Se corrigieron:
- en celular la ficha tapaba toda la escena; ahora se ancla a la escena y los botones de la barra van en una fila desplazable;
- las etapas no se anunciaban bien a los lectores de pantalla;
- la ficha quedaba encima de Avisos y Permisos;
- los paneles de Avisos y Permisos tapaban la segunda fila de la barra;
- en `/oficina` la ficha tapaba los botones del encabezado;
- el foco no volvía al cerrar la ficha;
- el foco se escapaba detrás de la hoja en celular;
- el contador del permiso se anunciaba cada 2 s;
- el orden de lectura en celular;
- etapas y tarjetas aplastadas en tablet;
- bordes de controles con contraste menor a 3:1;
- el permiso no tenía encabezado;
- el aviso de las 8 horas no se anunciaba;
- fondo oscuro del sistema en `/historial`;
- detalles menores (selector de entorno de 44 px, paginación que se parte, Escape dentro de otros paneles).

**Verificación con datos reales** en el Chrome de Washington, sin escribir credenciales. Capturas en `docs/capturas/etapa-2-3/` (PC 1440 y celular 390). El celular se emuló limitando la página a 390 px dentro de una ventana de 500, el mínimo de Chrome; el sitio prohíbe marcos, así que no se usó un iframe.

## Limpieza de la web original (etapa 1.4)

Decisión de Washington (2026-10-11): la web original de ClaudeOffice Visualizer ya no existe en el proyecto; solo queda lo construido aquí. Inventario hecho con un grafo de imports desde las rutas que se conservan (`/oficina`, `/oficina/3d`, `/datos`, `/entrar` y el layout raíz): 72 de 233 archivos del frontend las usan.

**Frontend: se elimina**
- **Página raíz `/`** (vista 2D de Pixi con jefe y empleados, barra lateral de sesiones, registro de eventos, conversación, estado de git, menú de ajustes, recorrido guiado). Ahora `/` lleva a `/oficina/3d`, y esta a `/entrar` si no hay sesión.
- **`/sprite-debug`**: herramienta de sprites de la vista 2D.
- **Componentes**: `game/` (escena Pixi, pizarras, ascensor, reloj, ciudad), `command/` (centro de mando con Pixi), `layout/`, `navigation/`, `views/` (edificio y pisos), `overlay/`, `settings/`, `tour/`, `attention/` y `debug/`.
- **Estado y lógica**: `stores/` (gameStore, overview, navegación, preferencias, recorrido, atención), `machines/` (xstate), `systems/` (animación, rutas A*, colisiones, WebSocket), `hooks/` (WebSocket, sesiones, pisos, texturas) e `i18n/` (inglés, español y portugués de la vista original).
- **Datos y tipos**: `constants/`, `utils/` (bubbleText, cron, estilos de eventos), `types/` (incluido `generated.ts`, generado desde los modelos del backend clásico).
- **Recursos públicos**: `public/sprites` y los SVG de plantilla de Next (`file`, `globe`, `next`, `vercel`, `window`).
- **Pruebas** solo de lo anterior: agentMachine, astar, commandCenter*, cron, gameStore, i18n, overviewStore, stateReconciler, toastFilter, typingTracker y exitAnimation.
- **Dependencias** sin uso: `pixi.js` y `@pixi/react` (con su excepción `pixi.js/unsafe-eval`), `xstate` y `@xstate/react`, `react-markdown`, `remark-gfm`, `react-zoom-pan-pinch`, `lucide-react`, `date-fns`, `clsx` y `tailwind-merge`; en desarrollo, `json-schema-to-typescript`.

**Frontend: se conserva**
- **Páginas**: `/oficina` (cajas), `/oficina/3d`, `/datos` y `/entrar`.
- **Componentes**: `acceso/`, `avisos/`, `marca/`, `oficina/`, `oficina3d/` (con `LICENSE-agent-office` del código adaptado), `permisos/`.
- **Base**: `utils/api.ts`, `globals.css`, `favicon.ico`, `public/oficina3d` y `public/logos`.
- **Título del sitio**: "Oficina de agentes".

**Backend: se elimina** (el pipeline clásico que alimentaba la vista original; nadie lo lee)
- **Rutas**: `sessions` (sesiones, repetición, foco de terminal, simulación), `floors`, `preferences` y los WebSocket `/ws/{sesión}`, `/ws/room/{sala}` y `/ws/overview`.
- **Núcleo**: `event_processor`, `state_machine` y sus `handlers`, `broadcast_service`, `connection_manager`, `room_orchestrator`, `whiteboard_tracker`, `transcript_poller`, `task_file_poller`, `beads_poller`, `base_poller`, `task_persistence`, `summary_service`, `jsonl_parser`, `product_mapper`, `floor_config`, `office_layout`, `quotes`, `constants` y `core/logging`.
- **Servicios y datos**: `services/git_service`, la base clásica (`db/`: SQLAlchemy, `visualizer.db`) y los modelos `agents`, `git`, `overview`, `sessions` y `ui`.
- **Del motor de estados**: la importación única desde `visualizer.db` en su primer arranque (el registro propio ya existe en local y en el VPS) y el conteo de navegadores por WebSocket. La presencia queda con el latido de `/api/v1/agents/presence`, que envían las páginas nuevas.
- **De `main.py`**: el servidor estático original (`SERVE_STATIC`).
- **De `acceso_middleware`**: `ws_autorizado` (sin WebSocket no tiene uso).
- **Script y prueba de generación de tipos**: `scripts/gen_types.py`, `make gen-types` y `test_gen_types_completeness`.
- **Dependencias** sin uso: `sqlalchemy`, `aiosqlite` y `greenlet`.
- **Pruebas** solo de lo anterior.

**Además (revisión independiente de lo borrado):**
- Docker (`Dockerfile`, `docker-compose.yml`, `make docker-*`) servía el export con `SERVE_STATIC` y usaba el lock viejo: se quitó; el despliegue es el del VPS.
- Se quitaron el workflow `type-drift.yml` y el paso `gen-types` de pre-commit, que llamaban a `make gen-types`.
- `frontend/bun.lock` se regeneró (bun 1.4.3).
- Se quitaron de la configuración del backend los ajustes sin uso (git, beads, resúmenes con IA, desalojo y retención de la vista clásica, subagentes zombis y la clave automática por arranque). La configuración ignora claves desconocidas, así que un `.env` viejo no impide arrancar.
- `make clean-db` (la base clásica) se quitó.
- En el VPS el sitio de nginx conserva su bloque `/ws/` de la etapa 1.3 (lo modificó certbot y no se reinstala solo). Queda inactivo: el backend ya no tiene WebSocket y responde 404. La plantilla del repositorio ya no lo tiene.
- Detalle en local: si se fija `CLAUDE_OFFICE_API_KEY` con el acceso desactivado, el backend exige esa clave a todo y la web ya no la manda, así que la web no carga. En el VPS no aplica (con el acceso activado manda la sesión). En local no hay clave fijada.
- El export estático de Next 16 escribe las cargas RSC en carpetas (`__next.oficina/3d/__PAGE__.txt`) y el cliente las pide con puntos (`__next.oficina.3d.__PAGE__.txt`): `npm run build` corre `scripts/rsc-planos.mjs`, que copia cada una con el nombre plano.
- Pendiente (documentación, no afecta el funcionamiento): `README.md`, `backend/README.md`, `frontend/README.md`, `scripts/README.md`, `CONTRIBUTING.md` y `docs/architecture/ARCHITECTURE.md` todavía describen la vista original. Las skills de sprites de `.claude/skills` eran para la vista 2D.

**Backend: se conserva** (lo usan la oficina, el monitor, los hooks o los permisos)
- **Rutas**: `events`, `acceso` (incluye máquinas, latido y observaciones), `agents_state`, `oficina3d` y `permisos`.
- **Núcleo**: el motor de estados con su registro propio, `token_tracker` (ventanas de contexto), `transcript_tail`, `process_check`, `path_utils`, `permisos`, `acceso`, `migracion_maquinas`, los middlewares y `acceso_cli`.
- **`servidor_frontend`**: sirve el export en la diaria local; se conserva como respaldo por si hay que volver a ella.
- **Scripts**: `simulate_events.py` y sus escenarios (mandan eventos a `/api/v1/events`), `borrar_sesiones_prueba.py`, `scripts/diario` y `scripts/permisos`.

## VPS y despliegue (etapa 1.3)

### Reconocimiento del VPS (2026-10-11, solo lectura)

- **Servidor**: the VPS provider, `<VPS_HOST>`, IP <VPS_IP>, Ubuntu 24.04.4 LTS (kernel 6.8), 8 GB de RAM y 2 GB de swap. Disco de 96 GB con 15 GB libres (85 % usado: vigilarlo).
- **nginx 1.24**: un archivo por sitio en `sites-available`, enlazado en `sites-enabled`; cada sitio escucha en el 80 y certbot `--nginx` le agrega el bloque 443 y la redirección. El `nginx.conf` es el de Ubuntu (gzip solo de HTML, sin `server_tokens off`). Sitios: Localia, Buscapez (y design.), Projection, brainstorming.example.net, productividad, skynest y vivedemo (landing, admin y API).
- **Puertos ocupados**: públicos 22, 80, 443, 3001 (node) y 8080 (php); locales 1521, 3306, 6379, 8000, 8081, 8090, 8182, 8183, 8211, 33060 y 65529. La oficina usa 127.0.0.1:8320.
- **Otros servicios**: docker, mysql, redis, php8.3-fpm, supervisor, buscapez-inference, projection-api y projection-realtime, monarx-agent.
- **Herramientas**: Python 3.12 del sistema (con venv), sin uv. node, npm y pnpm. curl, wget, rsync y certbot 2.9 (cuenta ya registrada) con `certbot.timer` activo. Sin el cliente `sqlite3`.
- **Firewall**: ufw activo (no se tocó; 80 y 443 ya estaban abiertos).
- **Usuarios**: <VPS_USER> (sudo con contraseña, grupo www-data), deploy-vive y skynest-deploy. Los proyectos viven en `/var/www/<proyecto>`.

### Arquitectura en el VPS

```
navegador / monitor ──https──> nginx (agents.example.com, certificado de Let's Encrypt)
                                 ├─ /            frontend estático (/var/www/visualizador-agentes/actual/frontend-out)
                                 ├─ /api/        ──> 127.0.0.1:8320 (consultas largas, 660 s)
                                 └─ /ws/         ──> 127.0.0.1:8320 (WebSocket, 3600 s; solo Origin propio o sin Origin)
                               backend: systemd visualizador-agentes (usuario visualizador)
                               datos:   /var/lib/visualizador-agentes/datos (700)
```

| Qué | Dónde |
|---|---|
| Código (una carpeta por versión, enlace atómico `actual`; las 3 últimas) | `/var/www/visualizador-agentes/versiones/<fecha>-<commit>`, `actual` (de <VPS_USER>) |
| uv 0.11.32 y Python 3.13 propios | `/var/www/visualizador-agentes/herramientas` |
| Datos (agent_events.db, visualizer.db, acceso.db, permisos.db, JSON) | `/var/lib/visualizador-agentes/datos` (700, visualizador) |
| Respaldos diarios (`respaldo-AAAAMMDD-HHMMSS.tar.gz`, 14 días) | `/var/lib/visualizador-agentes/respaldos` (700) |
| Configuración con secretos (generados en el servidor, nunca mostrados) | `/etc/visualizador-agentes/backend.env` (640 root:visualizador) |
| Sitio de nginx y encabezados de seguridad | `/etc/nginx/sites-available/agents.example.com`, `/etc/nginx/snippets/visualizador-agentes-seguridad.conf` |
| Registros de nginx | `/var/log/nginx/visualizador-agentes.{access,error}.log` |
| Unidades de systemd | `visualizador-agentes.service`, `-reinicio.path`, `-reinicio.service`, `-respaldo.service`, `-respaldo.timer` |

- **Servicio**: uvicorn en 127.0.0.1:8320 con `--no-proxy-headers`: la IP del cliente sigue siendo la de nginx (el middleware de localhost la deja pasar), el acceso lo controla `VISUALIZADOR_AUTH=activado` y el backend lee `X-Real-IP` para el límite de intentos (`CONFIAR_PROXY=true`). `Restart=always` cada 3 s. Endurecido: `ProtectSystem=strict` (solo escribe en `/var/lib/visualizador-agentes`), `ProtectHome`, `PrivateTmp`, `NoNewPrivileges` y sin capacidades; `systemd-analyze security` da 3.0 (OK). `CLAUDE_OFFICE_API_KEY` explícita para que la clave nunca aparezca en el registro.
- **Configuración**: `VISUALIZADOR_AUTH=activado`, `LECTURA_LOCAL=false`, `CONFIAR_PROXY=true`, `COOKIE_SEGURA=si`, origen `https://agents.example.com`, rutas de datos y máquina local "alienware".
- **nginx**: el sitio solo agrega nombres propios (`visualizador_connection_upgrade`, `visualizador_ws_origen`, `visualizador_backend`); no hay `default_server` ni cambios globales. Encabezados: HSTS de un año (sin subdominios), nosniff, `X-Frame-Options DENY`, Referrer-Policy, Permissions-Policy, COOP y una CSP sin `unsafe-eval`, sin wasm, sin workers y sin WebSocket (desde la etapa 1.4: `connect-src 'self'`; se aplica con `aplicar-encabezados.sh`). Cuerpo de hasta 4 MB, sin listado de carpetas, sin archivos ocultos, `/docs` y `/health` no se publican, gzip de JS y CSS solo en este sitio.
- **https**: certbot `--nginx` con redirección de http a https; se renueva con el `certbot.timer` del VPS (vence el 2027-01-09).
- **Respaldos**: `visualizador-agentes-respaldo.timer` todos los días a las 03:30 UTC. `respaldar.sh` copia cada base con la API de respaldo de SQLite (consistente aunque el backend esté en marcha), comprueba su integridad, agrega los JSON y conserva 14 días. Restaurar en una copia (prueba): `sudo -u visualizador bash restaurar.sh --copia <archivo>`. Restauración real (detiene el backend, guarda los datos actuales en `datos.antes-<fecha>` y, si no arranca, vuelve solo a los anteriores): `sudo bash /var/www/visualizador-agentes/actual/despliegue/restaurar.sh <archivo>`.

### Scripts (`despliegue/`)

| Script | Dónde y cómo |
|---|---|
| `desplegar.sh` | PC, Git Bash: `bash despliegue/desplegar.sh`. Construye el frontend con la API en el mismo dominio, empaqueta el commit con `git archive` y lo sube por ssh, sin credenciales de GitHub en el servidor; activa la versión sin sudo (reinicio por la unidad `.path`, espera un proceso nuevo y `/health`, y si falla vuelve a la anterior). `--arbol` despliega el árbol de trabajo para pruebas; `--sin-front` reutiliza `frontend/out`. |
| `estado.sh` | PC: `bash despliegue/estado.sh` (versión, servicio, reinicios, `/health`, último y próximo respaldo, disco, `/entrar`, `/api` sin sesión, redirección y vencimiento del certificado). |
| `sitios-vps.sh` | PC: huella de los otros 12 sitios para comparar antes y después de tocar nginx. |
| `instalar-sistema.sh` | VPS, una vez y con sudo (usuario, carpetas, secreto, systemd, nginx, certbot). Se puede repetir sin daño. |
| `primer-arranque.sh` | VPS, con sudo: contraseña si falta, respaldo y restauración en una copia, prueba de caída con `kill -9` y estado. |
| `acceso.sh` | VPS, con sudo: comandos de `app.acceso_cli` con la configuración del servicio (contraseña, máquinas, tokens, sesiones). |
| `aplicar-encabezados.sh` | VPS, con sudo: instala `nginx/seguridad.conf` (CSP y demás encabezados), valida con `nginx -t` (si falla deja el anterior) y recarga. |
| `respaldar.sh`, `restaurar.sh`, `activar-version.sh` | VPS (los llaman el timer, `primer-arranque.sh` y `desplegar.sh`). |

Los scripts corren desde `/` (el usuario del servicio no puede entrar a `/home/<VPS_USER>`). `despliegue/.gitattributes` fuerza LF: `git archive` en Windows con `core.autocrlf` los mandaba con CRLF y bash fallaba.

### Comandos para Washington (PowerShell)

- Instalación del sistema (hecha el 2026-10-11): `ssh -t <VPS_USER>@<VPS_IP> "sudo bash ~/visualizador-agentes-instalacion/despliegue/instalar-sistema.sh"`
- Contraseña de la oficina (fijada el 2026-10-11), o cambiarla: `ssh -t <VPS_USER>@<VPS_IP> "sudo bash /var/www/visualizador-agentes/actual/despliegue/acceso.sh contrasena"`
- Respaldo con restauración, prueba de caída y estado: `ssh -t <VPS_USER>@<VPS_IP> "sudo bash /var/www/visualizador-agentes/actual/despliegue/primer-arranque.sh --sin-contrasena"` (solo la caída y el estado: `--solo-caida`)
- Actualizar el VPS (desde `E:\visualizador-agentes`, en Git Bash): `bash despliegue/desplegar.sh`; ver el estado: `bash despliegue/estado.sh`
- Encabezados de seguridad (CSP) después de cambiarlos: `ssh -t <VPS_USER>@<VPS_IP> "sudo bash /var/www/visualizador-agentes/actual/despliegue/aplicar-encabezados.sh"`
- Token de la Alienware (creado en la etapa 1.4): `ssh -t <VPS_USER>@<VPS_IP> "sudo bash /var/www/visualizador-agentes/actual/despliegue/acceso.sh token-crear --maquina alienware"`

### Resultado de los comandos de Washington (2026-10-11)

1. **`instalar-sistema.sh`**: creó el usuario `visualizador` y las carpetas (`/var/lib/visualizador-agentes` 755, `datos` y `respaldos` 700, `/var/www/visualizador-agentes` de <VPS_USER>). Generó `/etc/visualizador-agentes/backend.env` sin mostrar los secretos y habilitó el servicio, el reinicio al desplegar y el timer de respaldo. `nginx -t` pasó y nginx se recargó. Obtuvo el certificado de agents.example.com (vence el 2027-01-09) con la redirección a https; la renovación queda en `certbot.timer`.
2. **`primer-arranque.sh`**, primera vez: la contraseña de la oficina quedó guardada (solo su hash argon2, en `/var/lib/visualizador-agentes/datos/acceso.db`). El respaldo falló con `find: Failed to restore initial working directory: /home/<VPS_USER>: Permission denied`: el usuario del servicio no podía entrar a la carpeta de quien lo llamaba. Corrección: los scripts corren desde `/` y la contraseña se omite si ya existe.
3. **`primer-arranque.sh --sin-contrasena`**: copió 3 bases en `respaldo-20261011-132218.tar.gz` y lo restauró en una copia (acceso.db con 5 tablas y 4 filas, agent_events.db con 3 tablas y 0 filas, visualizer.db con 4 tablas y 0 filas, integridad ok en las tres; la copia se borró). La prueba de caída falló con `Failed to send signal SIGKILL to auxiliary processes`: `systemctl kill` también intentaba los procesos auxiliares. Corrección: `kill -9` solo al proceso principal (MainPID) y la opción `--solo-caida` para correr solo la prueba y el estado.
4. **`primer-arranque.sh --solo-caida`**: "Volvió solo: PID 3094503 -> 3095118; reinicios 0 -> 1". Servicio, reinicio al desplegar y timer de respaldo activos. El próximo respaldo es el 2026-10-12 a las 03:34 UTC. Certificado válido 89 días (2027-01-09).

### Revisión independiente (2026-10-11)

Un subagente revisó nginx, systemd, permisos y scripts. Corregido:
- la CSP rompía la vista 2D (Pixi necesitaba eval: ahora importa `pixi.js/unsafe-eval`);
- `connect-src` sin `data:`/`blob:`;
- cualquier subdominio de example.com podía abrir el WebSocket con la cookie (ahora nginx exige el Origin propio o ninguno);
- el chequeo de salud del despliegue podía aceptar el proceso viejo (ahora espera un InvocationID nuevo);
- la restauración no volvía atrás si fallaba y extraía como root un archivo escribible por el servicio;
- `python3` sin `-I` corriendo como root;
- `umask` que seguía activo en el resto de la instalación;
- versiones ordenadas por fecha de archivo y no por id;
- sin bloqueo contra dos despliegues a la vez;
- conexiones de SQLite sin cerrar;
- `python3-venv` sin comprobar;
- caché de uv sin limpiar;
- gzip de JS y CSS.

No aplicaba: el aviso sobre IPv6 (los demás sitios ya escuchan en `[::]` y hay un `default_server`). Queda anotado: <VPS_USER> es dueño del código que corre el servicio, así que puede leer el secreto (ya tiene sudo, no es una escalada). Además `instalar-sistema.sh` no reemplaza un sitio que certbot ya modificó: los cambios futuros a `nginx/agents.example.com` se aplican a mano.

### Comprobaciones (2026-10-11)

- `https://agents.example.com/entrar` carga con certificado válido; http redirige a https (301).
- Sin sesión, `/api` responde 401 y el WebSocket se cierra con 4401; desde otro subdominio, 403.
- Encabezados de seguridad presentes; `/docs`, `/.env` y `/health` responden 404 y `openapi.json` 401.
- Con la CSP real, `/entrar`, `/`, `/oficina` y `/oficina/3d` cargan sin violaciones y renderizan las escenas 2D y 3D (Playwright, con respuestas de la API simuladas en el navegador).
- Los otros 12 sitios: las 24 respuestas (https y http) son iguales a la línea base.
- Respaldo y restauración en una copia: probados como <VPS_USER> en una carpeta de prueba (desde un directorio sin acceso) y con los datos reales del servicio (3 bases, integridad ok).
- Reinicio al desplegar: siete despliegues sin sudo, cada uno con un proceso nuevo y `/health`; el último, desde el commit `67eed31`.
- Caída: `kill -9` al proceso principal y systemd lo levantó solo con otro PID (reinicios 0 -> 1) y `/health` ok.

## Hook compartido (oficina diaria y desarrollo)

El comando `claude-office-hook` se instala una sola vez desde `E:\visualizador-agentes\hooks` (`uv tool install --force -p 3.14 E:\visualizador-agentes\hooks`) y lo usan las dos cuentas (`~/.claude` y `~/.claude-demo`).

- Destinos: `CLAUDE_OFFICE_API_URL` (por defecto la oficina diaria, `http://127.0.0.1:8000/api/v1/events`) y `CLAUDE_OFFICE_EXTRA_API_URLS` (lista separada por comas) en `C:\Users\<user>\.claude\claude-office-config.env`. Hoy: `http://127.0.0.1:8100/api/v1/events`.
- Envío en paralelo: espera hasta 0,25 s al destino principal y 0,08 s a los extra; un destino apagado se ignora sin error y el hook siempre termina con código 0.
- Tipos nuevos (`post_tool_use_failure`) solo van a los destinos extra, salvo con `CLAUDE_OFFICE_PRINCIPAL=visualizador` (el principal es nuestro backend y también los recibe). claude-office los rechazaría con 422.
- Campos nuevos (`tool_agent_id`, `tool_agent_type`, `error`, `is_interrupt`, `last_assistant_message`, `reports_tool_failures`, `claude_pid`, `claude_pid_created`): la oficina diaria los ignora (comprobado: guarda el evento sin esos campos).
- Proceso de Claude Code (`hooks/src/claude_office_hooks/process_info.py`): el hook sube por sus ancestros con la API de Windows (`NtQueryInformationProcess` para el padre, `QueryFullProcessImageNameW` para el nombre, `GetProcessTimes` para la hora de creación) pasando por los intérpretes intermedios (`claude-office-hook.exe`, `bash`/`cmd`/`powershell`) hasta el primer `claude.exe` (instalación nativa) o `node.exe` (instalación por npm). Se detiene en `Code.exe`, `explorer.exe` o `WindowsTerminal.exe`, y si un padre es más nuevo que su hijo (PID reutilizado) devuelve `null`. Cuesta ~12 ms (importar ctypes) más ~0,5 ms.
- Permisos desde la oficina (2026-10-10, requiere aprobación de Washington): reinstalar el hook y subir el `timeout` de `claude-office-hook permission_request` de 2 a 600 s en las dos cuentas (el instalador no cambia entradas que ya existen; `manage_hooks.py` ya registra 600 s en instalaciones nuevas). Comandos, desde `E:\visualizador-agentes` en PowerShell:
  1. `uv tool install --force --reinstall -p 3.14 E:\visualizador-agentes\hooks`
  2. `uv run --no-project python scripts\permisos\ajustar_timeout_permiso.py C:\Users\<user>\.claude\settings.json` (deja `settings.json.respaldo-AAAAMMDD-HHMMSS`; con `--probar` solo muestra el cambio)
  3. `uv run --no-project python scripts\permisos\ajustar_timeout_permiso.py C:\Users\<user>\.claude-demo\settings.json`
  4. Reiniciar las sesiones de Claude Code. Para volver atrás: copiar el respaldo sobre `settings.json` y reinstalar el hook del commit anterior.

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
| El orquestador de prueba-37 seguía diciendo que no podía dar órdenes después de actualizar el monitor | `--resume` conserva el rol de nacimiento: el monitor 0.5.1 le escribe el rol nuevo una vez al retomarlo |
| El agente no pudo escribir hola.txt: permiso rechazado al instante | Una sesión `-p` no tiene diálogo; los permisos del equipo ahora siempre esperan la decisión en la web o la app (y los agentes editan su carpeta con `acceptEdits`) |
| Las sesiones del equipo heredaban las 629 reglas de permiso de la configuración de usuario | Monitor 0.7.0: `--setting-sources project,local` y los hooks de la oficina por `--settings` |
| Una carpeta de prueba llamada `con` no dejó crear `.git` ("Invalid argument") | En Windows `con`, `prn`, `aux`, `nul`, `com1` a `com9` y `lpt1` a `lpt9` son nombres reservados; el monitor ya los rechaza como nombre de proyecto, pero también hay que evitarlos en carpetas de prueba |
| Un mensaje escrito en la web local apenas cargó la página no se envió | Se escribió antes de que React terminara de hidratar; esperar a que la página termine de cargar |
| La web local en http://127.0.0.1:3100 se queda en "Cargando…" (React no hidrata) | Next en modo desarrollo solo sirve sus recursos al origen permitido: abrirla en http://localhost:3100 |
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
| Copia diaria: Next 16 pide `oficina/__next.oficina.__PAGE__.txt` (datos de navegación) y el export lo guarda como `oficina/__next.oficina/__PAGE__.txt` (404 en consola, navegación más lenta) | `app.servidor_frontend` traduce los puntos del segmento a carpetas |
| Copia diaria: `detener-oficina.ps1` se cortaba en PowerShell 5.1 cuando `taskkill` avisaba de un proceso ya terminado con su árbol | `taskkill` se llama a través de `cmd` y ese aviso se ignora |
| Copia diaria por Tailscale: aviso de React #418 en `/datos` | Resuelto: la URL del backend se calcula solo en el navegador (`useSyncExternalStore` con valor vacío en el servidor), así el HTML compilado y el del cliente coinciden |
| Al reiniciar el backend, los cerrados por proceso terminado se vuelven a fechar al momento del arranque ("Desaparece en 60 min" de nuevo) | Resuelto: si el motor no vio vivo el proceso en esta ejecución (caso del reinicio), el cierre toma la hora del último evento; si lo vio vivo, la hora de la revisión que lo encontró muerto |
| `/oficina` en `http://127.0.0.1:3100` no carga datos en desarrollo | Next bloquea `/_next/*` de desarrollo para orígenes fuera de `allowedDevOrigins`; usar `localhost:3100` (sin cambiar la configuración) |
| El tiempo del hook depende de la carga de la PC: con Unity y Chrome abiertos, el mismo hook anterior pasó de ~180 a ~250 ms (8100 encendido) y de ~260 a ~320 ms (8100 apagado) | Se mide comparando la versión anterior y la nueva intercaladas; la detección del proceso suma ~5-10 ms |
| Next.js 16.3 genera `frontend/AGENTS.md` y `frontend/CLAUDE.md` al arrancar | Se versionan (decisión 2026-10-09) para que `next dev` no los vuelva a dejar como cambios sueltos |
| `npm install` del frontend reporta 6 vulnerabilidades (5 altas, 1 crítica) | Pendiente: revisar con `npm audit`; herramienta local, no bloquea |
| autoskills no permite elegir skills sueltas por línea de comandos; sin terminal interactiva instala todas las sugeridas | Washington las instaló con el selector interactivo; las de `frontend/` se movieron a la raíz (Windows pide administrador para enlaces simbólicos, se usaron uniones de directorio) |
| Command Center con agentes al doble: solo caben 2×2 puestos por columna (antes 2×4) | Los demás se resumen en "+N más"; revisar si hace falta más capacidad |
| `/oficina/3d`: al hacer clic en un agente la pantalla quedaba gris (informado por Washington; no se reprodujo en Chrome ni en la emulación de iPhone) | El clic llevaba a `/oficina` con `router.push` y desmontaba la escena 3D; al volver con "Vista 3D" el panel leía `?agente=` de `window.location` antes de que Next cambiara la URL y se abría el de otro agente. Ahora el clic abre el panel del agente sobre la escena (`PanelAgente3D.tsx`, `useOffice.panel`) y `?agente=` se lee con `useSearchParams`; el detalle completo queda a un enlace |
| Los scripts de la diaria mostraban "est├í" en vez de "está" (mensaje del commit) en Windows PowerShell 5.1 | PowerShell 5.1 lee la salida de git con la página de códigos de la consola (850). `comun.ps1` pone la salida de la consola en UTF-8; `actualizar-oficina.ps1` ya no escribe UTF-16 en su registro (`*>>`) |

## Pendientes

El orden de trabajo lo marca el "Plan por etapas"; esta lista queda como referencia.

1. Escena propia: editor, temas y los cinco entornos (hechos el 2026-10-10); falta que Washington elija el de uso diario.
2. Permisos desde la oficina (hecho y probado en el iPhone el 2026-10-10).
3. Chatear por completo con el agente desde la oficina: primero investigar las funciones oficiales de Claude Code para usarlo a distancia; luego decidir si integrar o construir.
4. Mejores voces para los avisos (acento latino o ecuatoriano); por ahora, voces de Google en Chrome (no Edge).
5. VPS con dominio propio y https, para verla desde internet (hecho el 2026-10-11: https://agents.example.com).
6. Instalador que envía los eventos de cada máquina al VPS (hecho e instalado en la Alienware el 2026-10-11; versión profesional: función 52).
7. Mac: ver en una sola cuenta los agentes de la Mac y de la laptop Alienware.
8. App de iPhone con notificaciones push.
9. Personajes propios en GLB con animaciones de Mixamo, y estilo final.
10. Deuda técnica: documentación de la vista original por actualizar (ver "Limpieza de la web original"), vulnerabilidades de npm, 3 tests viejos de `path_utils` que fallan (los 2 de WebSocket se fueron con la vista clásica).
11. Seguridad de los proyectos con equipo (hecho en el Prompt 41, monitor 0.7.0): sus sesiones ya no usan la configuración de usuario; ver "Reglas de la casa, comandos seguros y entrevista".

## Plan por etapas

Decisión de Washington (2026-10-10).

- **Arquitectura**: sin Tailscale. Un monitor instalado en cada máquina (Windows y luego Mac) envía todo al VPS de the VPS provider (<VPS_IP>); la web y la app iOS consumen el VPS en https://agents.example.com, con inicio de sesión de un solo usuario y sesión de 30 días por dispositivo.
- **Etapa 0, cierre**: clic en un agente sin pantalla gris, acentos de los scripts, plan registrado (hecha el 2026-10-10).
- **Etapa 1.1** (hecha el 2026-10-10): backend para varias máquinas con inicio de sesión (sección "Inicio de sesión y máquinas").
- **Etapa 1.2** (hecha el 2026-10-10): monitor e instalador de Windows (sección "Monitor de máquina").
- **Etapa 1.4** (hecha el 2026-10-11): token de la Alienware, monitor instalado (08:30, hora de Ecuador) y conectado, web original quitada y diaria retirada. El uso diario es https://agents.example.com.
- **Función 52 (más adelante)**: instalador profesional del monitor con interfaz visual, vinculación desde la web sin escribir URL ni token (por ejemplo un código o enlace de un solo uso que la oficina genera para la máquina) y detección automática de cuentas de Claude Code.
- **Etapa 1.3** (hecha el 2026-10-11): publicada en https://agents.example.com; nginx sirve el frontend estático y reenvía `/api` y `/ws` al backend (sección "VPS y despliegue").
- **Etapa 1, publicar**: backend para varias máquinas con inicio de sesión y token por monitor; monitor e instalador de Windows (recibe los hooks, lee transcripts, cola sin conexión, arranque automático, recuperación tras reinicio, comandos peligrosos siempre con aprobación); despliegue en el VPS con nginx, https y respaldos diarios; pasar el uso diario al VPS. El monitor debe diseñarse para que más adelante pueda lanzar sesiones de Claude Code (`claude -p` con stream-json y `--resume`) en carpetas que se le indiquen.
- **Etapa 2, ver bien** (hecha el 2026-10-11), en 4 prompts:
  - 26: datos y API: esperas, historial, consumo, límites, atascos, "Dónde quedamos" (hecho el 2026-10-11).
  - 27: bocetos de la ficha del agente y de "Dónde quedamos", hechos en Claude.ai para su aprobación (hecho el 2026-10-11).
  - 28: ficha del agente y "Dónde quedamos" en la oficina (hecho el 2026-10-11).
  - 29: avisos resumidos con un agente auxiliar (hecho el 2026-10-11).
  - Alcance: ficha útil del agente (no chat): tarea actual, pasos, estimado contra real, tokens, commits, archivos, permisos y acciones; esperas específicas (por ejemplo "Unity: compilando scripts, 2 min"); historial preciso; tokens, tiempo de trabajo y límites de 5 h y semanal; detector de atascos.
- **Etapa 3, app iOS**: bocetos para aprobación, base que consume el VPS, push de tres alertas (permiso pendiente, pregunta del orquestador, tarea terminada), bandeja de decisiones, bandeja de ideas, widget, Live Activity y Apple Watch.
- **Etapa 4, proyectos y orquestador**: crear proyecto desde la web o la app en la ruta base de cada máquina (`E:\Agents` en la Alienware) eligiendo máquina, cuenta (personal o Demo Org), personaje, modelo y esfuerzo (low a max); rol orquestador (planifica, conversa con Washington, puede ejecutar comandos en PowerShell y Git Bash, instalar skills y conectores MCP y controlar programas como Blender) con uno o varios agentes de código enlazados, cada uno en su carpeta y con subagentes; todo pasa por el orquestador salvo los permisos; Washington aprueba cada orden del orquestador al agente (luego interruptor automático por proyecto); chat propio con cada agente; reglas de la casa heredadas por todos los orquestadores; plantillas de proyecto; entrevista inicial; bóveda de secretos.
- **Etapa 5, pipeline y aprendizaje**: proyecto como bloques y subbloques al estilo GitHub Actions (cada uno se abre como consola), imprevistos como bloques nuevos, estimación total y por bloque con fechas reales, resumen por paso y modo auditoría; estimaciones del orquestador y del agente comparadas con lo real, con explicación de desvíos para aprender; revisor independiente; puntos de control con etiqueta git; retrospectiva; integración con GitHub (commits y Actions); galería (imágenes, videos, capturas automáticas; archivos no visualizables como APK solo como ícono); relevo de agentes cuando el contexto se llena.
- **Etapa 6**: monitor para Mac, salud de las máquinas, mover proyectos entre máquinas.
- **Etapa 7, consumo y control**: panel completo (límites, fecha de pago, por día, proyecto, agente, modelo y MCP), presupuesto por proyecto, prioridades entre proyectos, cola nocturna, comparar modelos, rendimiento por agente, valor en dinero, horas y costo por cliente, deuda técnica, seguridad, choques entre agentes.
- **Etapa 8, extras**: modo fiesta con logros (modelos locales de la Tower para no gastar cuota), resúmenes diario y semanal, modo foco, informe para clientes, modo presentación, vista de invitados, ClickUp, calendario, canales de alerta extra, búsqueda global, vista previa en vivo, builds al teléfono, roles extra, ramas por bloque, diagrama de arquitectura, biblioteca de prompts y skills, documentación final, time-lapse, lecciones entre proyectos, vista previa de tareas grandes, mejores voces, personajes GLB/Mixamo, mejora continua con análisis de uso, Android.
- **Regla**: no duplicar lo que Claude Code ya trae (`/usage`, compactación, push oficial, Remote Control, tareas programadas, hook PreCompact); usarlo por debajo. Las ideas nuevas se anotan en la etapa donde encajen, sin desviar el plan.

## Competencia y seguimiento

Investigado el 2026-10-10.

- **AgentsRoom**: escritorio multiagente con roles, app móvil con push y delegación.
- **Agent Orchestrator**: orquestador y workers, tablero Kanban con columnas Trabajando, Te necesita, En revisión y Listo para integrar (Apache 2.0).
- **De Anthropic**: Projects (beta en Pro y Max; hilos en paralelo en la nube o en la PC vía Remote Control), Agent teams (experimental) y mensajes entre sesiones (SendMessage y ListAgents, también con `claude -p` y entre máquinas por Remote Control).
- **Visualizadores**: Pixel Agents, Pixel Office y Agent Virtual Office (2D, solo miran).
- **Apps móviles**: Happy (código abierto, cifrado de extremo a extremo), Forge Remote y Melta.
- **Seguimiento**: etapa 3, cifrado de extremo a extremo en la app; etapa 4, usar los mensajes entre sesiones oficiales como canal orquestador-agente y vigilar la evolución de Projects; etapa 5, columnas "Te necesita" y "En revisión" en el pipeline.

## Próximos pasos

1. Washington despliega el backend y la web del Prompt 45 (`bash despliegue/desplegar.sh`; nginx no cambia) y actualiza el monitor a la 0.8.0 (`& "E:\visualizador-agentes\monitor\dist\instalar-visualizador-monitor.exe" --actualizar`). En ese orden: un monitor 0.8.0 con el servidor anterior se calla la respuesta en vivo por 10 min y lo vuelve a intentar.
2. Comprobar en el VPS que `/chat/eventos` llega sin búfer detrás de nginx y https (la burbuja crece de a poco, no de golpe); si no, la web cae sola a la consulta cada segundo.
3. Plan vivo, desde la Mac: correr `tiempos` con las sesiones de la Mac para los items trabajados allí (F3 · P31, la parte C de F3 · P33, F4 · P40, F4 · P44, F4 · U2 y F4 · P46), que hoy no tienen tramos del agente. P27 y P36 se hicieron fuera de Claude Code y no tendrán tramos.
4. Prompt 46 (app iOS, en la Mac): Enviado y Leído, tres puntos y el texto parcial con `/chat/eventos` o `/chat/en-vivo` (ver "Datos nuevos para la app").
4. prueba-39 tiene la orden 3 (crear el proyecto Next.js) por aprobar: como es de prueba ya no avisa; rechazarla o dejarla.
5. Etapa 3, Prompt 33, lo que falta en el iPhone: el dictado de ideas, una pregunta y un permiso reales de punta a punta, y las capturas 33-decisiones-pregunta.png y 33-ideas-dictado.png.
6. Etapa 3, Prompts 32 y 34: push y lo que necesita la membresía de pago de Apple, cuando esté renovada.
7. Sistema de prompts de Washington: reemplaza la vista de prompts de "Dónde quedamos".
8. Vigilar el disco del VPS (85 % usado).
