# Catálogo de estados del avatar

Versión 2026-10-09. Documento vivo: https://claude.ai/code/artifact/0a5288ae-d07f-4175-9545-26ecfe769d07

El avatar tiene 21 estados en tres grupos, más indicadores de esfuerzo encima, cada uno ligado a un evento de Claude Code. Se definen por lo que pasa, no por el dibujo: el arte en pixel se reemplaza al final sin tocar la lógica.

## Ciclo de trabajo

Todos estos estados se detectan con seguridad: cada uno sale directo de un evento de los hooks.

| # | Estado | Cómo se ve | Dato que lo dispara |
| --- | --- | --- | --- |
| 1 | Llega | Entra a la oficina y se sienta en su escritorio | `SessionStart` |
| 2 | Recibe encargo | Suena el teléfono o lee una nota | `UserPromptSubmit` |
| 3 | Pensando | Globo de pensamiento, manos quietas | Después del encargo y antes de usar una herramienta |
| 4 | Leyendo | Lee papeles; monitor cian | Herramientas `Read`, `Grep`, `Glob` |
| 5 | Escribiendo código | Teclea rápido; monitor azul | `Edit`, `Write` |
| 6 | En la terminal | Teclea comandos; monitor naranja | `Bash` |
| 7 | Investigando en la web | Monitor con un globo terráqueo | `WebSearch`, `WebFetch` |
| 8 | Usando una app externa | Ícono de la app sobre el monitor (por ejemplo, ClickUp) | Herramientas de conectores (`mcp__*`) |
| 9 | Planificando | Escribe en su pizarra la lista de tareas | `TodoWrite` |
| 10 | Compactando memoria | Vacía o pisa su basurero | `PreCompact` |
| 11 | Terminó el turno | Se estira; pequeña celebración | `Stop` sin pregunta explícita; tras 5 min sin eventos pasa a 18 o 19 |
| 12 | Se va | Sale por el ascensor | `SessionEnd` |

## Esperando: a quién espera

Sobre la cabeza aparece un ícono de quién lo detiene, y parpadea más rápido cuanto más tiempo lleva esperando. Esperarte a ti se detecta con seguridad; esperar un programa o una subida se deduce del comando que corre.

| # | Estado | Cómo se ve | Dato que lo dispara | Detección |
| --- | --- | --- | --- | --- |
| 13 | Te espera: permiso | "?" rojo, mano levantada, brillo rojo | `PermissionRequest` | Segura |
| 14 | Te espera: respuesta | Mira hacia ti con un globo de diálogo | Pregunta explícita: `AskUserQuestion` o `ExitPlanMode` pendiente, o `Stop` cuyo último mensaje del asistente termina en "?" | Segura |
| 15 | Espera un programa | Reloj de arena sobre el monitor | `Bash` que lleva más de 30 s sin terminar (compilar, instalar, pruebas) | Deducida |
| 16 | Espera una subida o descarga | Barra de progreso con flecha | `Bash` con comandos de red: `git push`, `scp`, `rsync`, `docker push`, `eas submit` | Deducida por comando |
| 17 | Espera a otros agentes | Mira hacia sus subagentes; número de agentes trabajando | `SubagentStart` sin su `SubagentStop`; un subagente sin actividad por 30 min se da por terminado | Segura |

## Ausencia y regreso

Los hooks no saben si estás frente a la PC, así que tu presencia se deduce: estás conectado si tienes la oficina abierta (PC o celular) o si respondiste a algún agente hace poco.

| # | Estado | Cómo se ve | Dato que lo dispara |
| --- | --- | --- | --- |
| 18 | Inactivo contigo presente | Toma café junto a su escritorio | Sin eventos por 5 min y tú conectado |
| 19 | Descansando sin ti | Va a la sala: juega videojuegos, lee o duerme una siesta (rota entre actividades) | Sin eventos y tú desconectado por 10 min |
| 20 | Regresa al trabajo | Camina de vuelta, se sienta y se estira para empezar | Abres la oficina o le envías un encargo (`UserPromptSubmit`), o se reabre su sesión cerrada (si tenía una pregunta sin responder, luego pasa a 14) |
| 21 | Cerrado | Su escritorio queda vacío; la pregunta pendiente, si la hay, queda anotada | La sesión ya no existe: `SessionEnd` (después de 12 "Se va"), el proceso de Claude Code registrado ya no existe (revisión cada 30 s) o, si no se conoce el proceso, 24 h sin eventos |

Si un agente te estaba esperando cuando te desconectaste, no descansa: se queda en su estado de espera para que lo veas primero al volver. Si su sesión de Claude Code se cerró, pasa a 21 aunque tuviera una pregunta pendiente; la pregunta se guarda y vuelve a mostrarse (14) cuando se reabre la sesión.

## Indicadores de esfuerzo

No son estados: se dibujan encima de cualquier estado para mostrar cuánto y cómo trabaja.

| Indicador | Cómo se ve | Dato |
| --- | --- | --- |
| Ritmo | Teclea más rápido o se queda quieto | Herramientas usadas por minuto |
| Esfuerzo | Barra sobre la cabeza (verde, amarillo, rojo); sudor o vapor en rojo | Tokens por minuto |
| Trabajo acumulado | Pila de papeles que crece en el escritorio | Tokens totales de la sesión |
| Tiempo trabajado | Taza de café que se vacía; duración al pasar el mouse | Minutos con actividad desde que llegó |
| Cansancio | Ojeras y cabeceo | Contexto usado sobre 80 % |
| Problemas | Humo o señal roja | Herramientas que fallan seguidas (2 o más) |
| Subagentes | Un número sobre el agente | Subagentes activos |

## Decisiones confirmadas (2026-10-09)

| Tema | Decisión | Por qué |
| --- | --- | --- |
| Cuándo un comando cuenta como "espera un programa" | Más de 30 s sin terminar | Los comandos rápidos no deben cambiar el estado a cada rato |
| Cuándo estás "desconectado" | Sin la oficina abierta y 10 min sin responder a ningún agente | Es lo único que se puede medir sin instalar nada más |
| Cómo se muestran los subagentes | Un número sobre el agente | Casi no se usan; un número no quita protagonismo al agente |
| Actividades de descanso | Videojuego, lectura y siesta, rotando | Dan variedad sin distraer de los que esperan |
| Tamaño del agente | El doble del actual de claude-office | El agente es lo principal |

## Decisiones confirmadas (2026-10-10)

| Tema | Decisión | Por qué |
| --- | --- | --- |
| Cuándo un agente "te espera: respuesta" (14) | Solo con pregunta explícita: `AskUserQuestion` o `ExitPlanMode` pendiente, o el último mensaje del asistente termina en "?". Si no, `Stop` lleva a 11 y tras 5 min a 18 o 19 según la presencia | Un agente que solo terminó no debe quedar esperándote para siempre |
| Descanso | 10 min desde la última señal tuya (último navegador visto o último encargo); un reinicio del backend lo atrasa | Se puede medir sin instalar nada más |
| Subagentes colgados | Un subagente sin actividad por 30 min (configurable) se da por terminado | Sesiones cerradas a la fuerza no deben dejar subagentes eternos |
| Agente cuya sesión de Claude Code se cerró | No está activo: pasa a 21 "Cerrado" aunque tenga una pregunta pendiente; la pregunta se guarda como dato | Una sesión cerrada no puede esperar a nadie |
| Reabrir una sesión cerrada | Vuelve al trabajo (20) y, si su pregunta seguía sin respuesta, pasa a 14 | La pregunta sigue vigente cuando la sesión vuelve |
