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
| 2026-10-10 | Cuentas: la personal no lleva marca; la de Demo Org lleva el isotipo (`frontend/public/logos/isotipo-demo.png`, ~16 px) en la etiqueta 3D y en los escritorios de `/oficina`, y el logo completo (`logo-demo.png`) solo donde hay espacio (detalle). "Demo Org" como texto solo en tooltips y `alt` | Se distingue la cuenta sin texto extra |
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
| 2026-10-11 | Etapa 1.3 cerrada en el VPS: Washington ejecutó la instalación del sistema, fijó la contraseña de la oficina y corrió el respaldo con restauración en una copia y la prueba de caída (`kill -9`): todo correcto (detalle en "Resultado de los comandos de Washington") |

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

## Uso diario (`E:\visualizador-agentes-diario`, 3000/8000)

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

### Instalación en la Alienware (etapa 1.4, cuando el VPS esté listo)

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
- **nginx**: el sitio solo agrega nombres propios (`visualizador_connection_upgrade`, `visualizador_ws_origen`, `visualizador_backend`); no hay `default_server` ni cambios globales. Encabezados: HSTS de un año (sin subdominios), nosniff, `X-Frame-Options DENY`, Referrer-Policy, Permissions-Policy, COOP y una CSP sin `unsafe-eval` (Pixi usa `pixi.js/unsafe-eval`). Cuerpo de hasta 4 MB, sin listado de carpetas, sin archivos ocultos, `/docs` y `/health` no se publican, gzip de JS y CSS solo en este sitio.
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
| `respaldar.sh`, `restaurar.sh`, `activar-version.sh` | VPS (los llaman el timer, `primer-arranque.sh` y `desplegar.sh`). |

Los scripts corren desde `/` (el usuario del servicio no puede entrar a `/home/<VPS_USER>`). `despliegue/.gitattributes` fuerza LF: `git archive` en Windows con `core.autocrlf` los mandaba con CRLF y bash fallaba.

### Comandos para Washington (PowerShell)

- Instalación del sistema (hecha el 2026-10-11): `ssh -t <VPS_USER>@<VPS_IP> "sudo bash ~/visualizador-agentes-instalacion/despliegue/instalar-sistema.sh"`
- Contraseña de la oficina (fijada el 2026-10-11), o cambiarla: `ssh -t <VPS_USER>@<VPS_IP> "sudo bash /var/www/visualizador-agentes/actual/despliegue/acceso.sh contrasena"`
- Respaldo con restauración, prueba de caída y estado: `ssh -t <VPS_USER>@<VPS_IP> "sudo bash /var/www/visualizador-agentes/actual/despliegue/primer-arranque.sh --sin-contrasena"` (solo la caída y el estado: `--solo-caida`)
- Actualizar el VPS (desde `E:\visualizador-agentes`, en Git Bash): `bash despliegue/desplegar.sh`; ver el estado: `bash despliegue/estado.sh`
- Token de la Alienware (etapa 1.4): `ssh -t <VPS_USER>@<VPS_IP> "sudo bash /var/www/visualizador-agentes/actual/despliegue/acceso.sh token-crear --maquina alienware"`

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
6. Instalador que envía los eventos de cada máquina al VPS (monitor e instalador de Windows hechos el 2026-10-10; se instala en la etapa 1.4).
7. Mac: ver en una sola cuenta los agentes de la Mac y de la laptop Alienware.
8. App de iPhone con notificaciones push.
9. Personajes propios en GLB con animaciones de Mixamo, y estilo final.
10. Deuda técnica: `frontend/bun.lock` sin three, 6 vulnerabilidades de npm, 10 errores de lint de la vista clásica, 5 tests viejos que fallan.

## Plan por etapas

Decisión de Washington (2026-10-10).

- **Arquitectura**: sin Tailscale. Un monitor instalado en cada máquina (Windows y luego Mac) envía todo al VPS de the VPS provider (<VPS_IP>); la web y la app iOS consumen el VPS en https://agents.example.com, con inicio de sesión de un solo usuario y sesión de 30 días por dispositivo.
- **Etapa 0, cierre**: clic en un agente sin pantalla gris, acentos de los scripts, plan registrado (hecha el 2026-10-10).
- **Etapa 1.1** (hecha el 2026-10-10): backend para varias máquinas con inicio de sesión (sección "Inicio de sesión y máquinas").
- **Etapa 1.2** (hecha el 2026-10-10): monitor e instalador de Windows (sección "Monitor de máquina").
- **Etapa 1.3** (hecha el 2026-10-11): publicada en https://agents.example.com; nginx sirve el frontend estático y reenvía `/api` y `/ws` al backend (sección "VPS y despliegue").
- **Etapa 1, publicar**: backend para varias máquinas con inicio de sesión y token por monitor; monitor e instalador de Windows (recibe los hooks, lee transcripts, cola sin conexión, arranque automático, recuperación tras reinicio, comandos peligrosos siempre con aprobación); despliegue en el VPS con nginx, https y respaldos diarios; pasar el uso diario al VPS. El monitor debe diseñarse para que más adelante pueda lanzar sesiones de Claude Code (`claude -p` con stream-json y `--resume`) en carpetas que se le indiquen.
- **Etapa 2, ver bien**: ficha útil del agente (no chat): tarea actual, pasos, estimado contra real, tokens, commits, archivos, permisos y acciones; esperas específicas (por ejemplo "Unity: compilando scripts, 2 min"); historial preciso; tokens, tiempo de trabajo y límites de 5 h y semanal; detector de atascos.
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

1. Etapa 1.4: pasar el uso diario al VPS: crear el token de la Alienware, instalar el monitor (guía en "Instalación en la Alienware") y comprobar la oficina en https://agents.example.com desde la PC y el iPhone.
2. Vigilar el disco del VPS (85 % usado).
