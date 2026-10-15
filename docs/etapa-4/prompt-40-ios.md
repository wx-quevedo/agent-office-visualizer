# Prompt 40: proyectos, chat y órdenes en la app iOS

Fecha: 2026-10-12. App en `ios/VisualizadorAgentes` (SwiftUI, iOS 26, XcodeGen). Bocetos aprobados: `docs/bocetos/etapa-4/` (Main, Nuevo, Chat, Equipo y Reglas; Escritorio es la web y solo sirvió de referencia).

## Qué se hizo

- **Pestañas:** Oficina, Proyectos, Decisiones e Ideas (TabView nativa con Liquid Glass). "Dónde quedamos" dejó de ser pestaña: es una sección de cada proyecto. El botón "Dónde quedamos" de la ficha abre el proyecto de esa carpeta en esa sección.
- **Proyectos** (boceto Main):
  - Lista unificada: primero los proyectos con orquestador (`GET /proyectos-creados`), luego los que solo tiene el monitor (`GET /proyectos`, los de "Dónde quedamos"). Un proyecto con equipo se une a su "Dónde quedamos" por la carpeta (`ruta` contra `carpeta`) o por el nombre y la máquina.
  - Resumen "N con orquestador · M sin orquestador".
  - Estado y color, lo más urgente primero: orden por aprobar (#5B3FA8), te pide permiso (#1D4FAF), atascado (#9B2C1E, también un equipo con error), en pausa o detenido (gris), trabajando (#2F5C45), y si no, "En espera", "Listo" o "Sin actividad" en gris.
  - Cada fila: nombre, cuenta y máquina, qué hace (`haciendo` del equipo o la posición del PROJECT.md con el prompt actual) y el equipo ("Orquestador + 1 agente", "Sin orquestador · 2 agentes").
  - Se lee cada 5 s; los proyectos del monitor y el consumo, cada 30 s.
- **Nuevo proyecto** (boceto Nuevo): nombre (misma validación que el backend y la web, con la carpeta que se va a crear), máquina (de `GET /proyectos-creados/maquinas`, con su motivo si no está disponible), cuenta, plantilla (Web, Unity, Expo, Vacía), orquestador y agentes de código con modelo y esfuerzo (hasta 4), y aprobación automática. `POST /proyectos-creados`, igual que la web. Al crear abre el chat del proyecto.
- **Proyecto** con selector Chat | Equipo | Dónde quedamos (bocetos Chat y Equipo). Sin orquestador solo hay Dónde quedamos.
  - **Chat:** burbujas con markdown ligero (`MarkdownLigero`: párrafos, títulos, viñetas, listas numeradas, bloques de código y, dentro de cada línea, negritas, cursivas, código y enlaces con `AttributedString`). El HTML nunca se muestra crudo: las etiquetas se quitan y las entidades comunes se traducen. Mensajes y órdenes mezclados por fecha (en un empate va primero el mensaje). Se lee cada 2 s. Botón de dictar con el reconocimiento de voz de iOS en español (la misma clase `Dictado` de Ideas: en el iPhone si el idioma lo permite).
  - **Tarjeta de orden:** agente, número, texto (con "Ver la orden completa" si es larga), estimado y dificultad ("Estimado: 5 min · dificultad 1 de 10"). Por aprobar: Aprobar, Editar y Rechazar. Rechazar pide el motivo (obligatorio, hasta 500). Editar abre el texto y aprueba la versión editada (solo se manda `texto` si cambió). Ya decidida: quién y cuándo, el motivo o el resumen. Todo con `dispositivo: "app"`.
  - **Equipo:** miembros con modelo, esfuerzo y lo que muestra la oficina (o "Espera que apruebes una orden"), enlace a la ficha si tiene sesión, Agregar agente de código (hasta 4), órdenes del orquestador con su estado, interruptor de aprobar órdenes automáticamente (pide confirmación al encenderlo), Pausar o Reanudar el equipo y Reglas de la casa.
- **Reglas de la casa** (boceto Reglas): `GET /proyectos-creados/{id}/reglas` con un interruptor por regla para ese proyecto (`POST /proyectos-creados/{id}/reglas/{regla}`). Agregar crea una regla para todos (`POST /reglas`: texto, tipo y si está encendida por defecto), porque la API lo permite.
- **Decisiones:** las órdenes por aprobar (tipo `orden` de `GET /decisiones`) van arriba, con la misma tarjeta y los mismos botones. La insignia sigue usando `decisiones_pendientes`, que ya cuenta las órdenes.
- **Pruebas unitarias:** 43 en total (8 nuevas en `ProyectosTests`: decodificación, lista unificada y colores, nombre y carpeta, chat mezclado, textos de la orden, markdown sin HTML y las rutas y cuerpos del cliente).

## Decisiones

| Decisión | Por qué |
| --- | --- |
| La lista mezcla proyectos con y sin orquestador | El boceto Main muestra "3 con orquestador · 4 sin orquestador" y "Dónde quedamos" pasa a cada proyecto: los proyectos sin equipo también necesitan su lugar. |
| Las órdenes se aprueban sin Face ID | El prompt no lo pide; Face ID sigue en los permisos peligrosos. Una orden aprobada pasa por los permisos del agente. |
| Encender la aprobación automática pide confirmación | Deja de pasar por ti cada orden; apagarla no pregunta. |
| Markdown propio por bloques en lugar de `AttributedString(markdown:)` completo | `Text` no dibuja listas ni bloques de código con el modo completo; por líneas se ven bien y se quita el HTML antes. |
| Xcode 26.6 para el simulador y Xcode 27 para el iPhone | El simulador de Xcode 27 falla; el iPhone tiene iOS 27.0.1 y solo Xcode 27 instala en él. |

## Prueba real (2026-10-12, servidor https://agents.example.com)

- **Entorno:** simulador iPhone 17 Pro Max con iOS 26.5 y Xcode 26.6. La sesión de la app seguía activa, así que no hizo falta iniciar sesión.
- **Proyectos:** la lista mostró "2 con orquestador · 17 sin orquestador" (prueba-39 y prueba-37 con equipo; SkyNest, vive-demo, mi-proyecto y otros sin él), cada uno con su estado y color. Nuevo mostró la Alienware encendida con su ruta base `E:\Agents`; se canceló sin crear nada.
- **Chat de prueba-39:**
  - Las respuestas del orquestador se vieron con negritas, lista numerada y código, sin HTML.
  - Desde la app se envió "Propón una orden pequeña: agregar una línea al README" (18:10).
  - A las 18:11 llegó la respuesta y la Orden 6 ("ORDEN PARA AGENTE", estimado 5 min, dificultad 1 de 10, por aprobar), también arriba en Decisiones.
- **Rechazo:**
  - Se rechazó desde Decisiones con el motivo "Prueba de la app" (el campo puso la primera letra en mayúscula).
  - La orden salió de la bandeja y en el chat quedó "Tú desde la app · Hoy 18:13 · Motivo: Prueba de la app". El orquestador contestó que la orden quedó rechazada.
  - En la web (`/proyectos/ver`) la Orden 6 aparece "Rechazada" y la API devuelve `estado: rechazada`, `decidido_por: app` y el motivo.
  - No se aprobó ninguna orden.
- **Regla "Usar subagentes para pruebas si es más rápido" en prueba-39:**
  - Se apagó desde la app: la app y la web la mostraron apagada y "ajustada en este proyecto".
  - Se volvió a encender: la web la mostró encendida.
- **Permisos de otras sesiones:** el permiso de visualizador-agentes que apareció en Decisiones durante la prueba no se tocó.
- **iPhone (Washington X., iPhone 16 Pro Max con iOS 27.0.1):** la app se compiló con Xcode 27 y el Personal Team (KVU83MD66W) y quedó instalada (`devicectl device install app`). No se abrió sola porque el teléfono estaba bloqueado.

Capturas no incluidas en el repositorio público.

## Problemas y soluciones

- **Tildes en el simulador:** el texto pegado por la herramienta del simulador llegó en Mac Roman ("Prop√≥n"). Se copió con `LANG=en_US.UTF-8 xcrun simctl pbcopy` y se pegó con Seleccionar todo y Pegar. Es un problema del portapapeles del simulador, no de la app.
- **Interruptores en el simulador:** el toque instantáneo de la herramienta del simulador no acciona los `UISwitch`; deslizar la perilla sí. En un iPhone real no pasa.
- **Motivo en mayúscula:** el campo de texto del aviso pone la primera letra en mayúscula ("Prueba de la app"). Se dejó así; es lo normal en iOS.
- **Dictado:** en el chat usa la misma clase que Ideas. En el simulador no se probó porque el audio de entrada del simulador se cuelga (ver Prompt 33); falta probarlo en el iPhone.

## Lo que falta en la API (anotado, sin cambiar el backend)

- **Título corto de la orden:** el boceto muestra "Fase 1 · Prompt 1: base del sitio", pero la orden solo trae `texto`; la app muestra "Orden N" y el texto debajo.
- **Unión de los dos tipos de proyecto:** `GET /proyectos-creados` no dice qué entrada de `GET /proyectos` (Dónde quedamos) le corresponde. La app los une por carpeta o por nombre y máquina; un `carpeta` normalizada o un id común en ambos lo haría exacto.
- **Órdenes y chat sin paginar:** Equipo lee las órdenes desde `GET /proyectos-creados/{id}/chat`, que trae hasta 200 mensajes; un `GET /proyectos-creados/{id}/ordenes` sería más liviano.
- **Pregunta del orquestador:** no hay una forma de marcar que un mensaje del orquestador espera respuesta (la app no puede destacarlo ni contarlo en Decisiones).

## Pendiente

- Probar el dictado del chat en el iPhone.
- Abrir la app en el iPhone y revisar Proyectos, el chat y Reglas con el dedo (incluidos los interruptores).
- El orden de los proyectos sin orquestador cambia según su última actividad; si molesta, fijarlo por nombre.
