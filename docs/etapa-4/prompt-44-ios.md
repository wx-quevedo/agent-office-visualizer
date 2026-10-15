# Prompt 44: la app con títulos de orden, avisos y proyectos de prueba

Fecha: 2026-10-12. App en `ios/VisualizadorAgentes`. Usa lo que ya estaba desplegado de los Prompts 42 y 43 (sección "Datos nuevos para la app" de PROJECT.md), sin cambiar el backend.

## Qué se hizo

- **Título de la orden:**
  - La tarjeta (chat, Equipo y Decisiones) muestra en negrita el título corto (`titulo`) debajo de la cabecera "ORDEN N PARA AGENTE", como en el boceto Chat.
  - Si el título no llega, la tarjeta muestra "Orden N".
  - La lista de órdenes de Equipo también usa el título.
- **Equipo** lee `GET /proyectos-creados/{id}/ordenes`, no el chat.
- **Dónde quedamos** se une por `donde_quedamos_id` contra el `id` de cada entrada de `GET /proyectos`. La unión por carpeta o por nombre queda solo como respaldo cuando el id viene null.
- **Avisos de los orquestadores** (`GET /avisos-orquestador`, con las reglas de la web):
  - Se leen cada 5 s, junto con la lectura en vivo.
  - En Decisiones, las preguntas van en una tarjeta propia con Responder, Ignorar y Esperar. Las órdenes ya estaban en Decisiones por `GET /decisiones`; si su aviso sigue vigente, los mismos tres botones van debajo de la tarjeta.
  - Ignorar y Esperar se guardan en el servidor (`POST /avisos-orquestador/ignorar` y `/esperar`).
  - Responder abre la pestaña Proyectos en el chat de ese proyecto, lleva la pregunta (o la orden) a la vista con un borde morado y deja el campo listo para escribir.
  - **Una sola vez por mensaje:** las claves ya anunciadas se guardan en el iPhone (las últimas 200). En la primera lectura solo se anotan, como hace la web al cargar. Cada clave nueva sale una vez como aviso arriba de cualquier pestaña, con Responder y cerrar.
  - **Proyectos de prueba:** no tienen avisos ni entran en Decisiones. Eso ya lo filtra el servidor, y la app no agrega nada propio.
  - **Insignia de Decisiones:** `decisiones_pendientes` (permisos, atascos y órdenes, sin proyectos de prueba) más las preguntas de los orquestadores. Las preguntas de las sesiones normales ya no cuentan si no tienen acción.
- **Proyectos de prueba:**
  - Casilla "Proyecto de prueba" en Nuevo, que se marca sola cuando el nombre empieza con "prueba-".
  - Interruptor equivalente en Equipo (`POST /proyectos-creados/{id}/prueba`).
  - Etiqueta "Prueba" en la lista.
  - Se agregó el botón "Detener el equipo" en Equipo, con confirmación, porque la prueba pedía detener desde la app.
- **Motivo al rechazar:** sin mayúscula automática ni corrección automática, en la tarjeta de orden y en el rechazo de permisos.
- **Pruebas unitarias:** 51 en total, todas pasan. Las 8 nuevas de `AvisosTests` cubren:
  - decodificación de los avisos y del título;
  - el título de respaldo;
  - una sola vez por clave (y el tope de 200);
  - la insignia;
  - a dónde lleva Responder;
  - el nombre "prueba-";
  - la unión por `donde_quedamos_id` con su respaldo;
  - las rutas y cuerpos nuevos del cliente.

## Prueba real (simulador iPhone 17 Pro Max, iOS 26.5, Xcode 26.6, servidor https://agents.example.com)

La sesión de la app seguía activa; no se pidió iniciar sesión.

1. **prueba-44** (Vacía, Haiku 5.5 con esfuerzo bajo para orquestador y agente):
   - Al escribir el nombre, la casilla Proyecto de prueba se marcó sola (captura 44-nuevo-prueba) y el servidor lo guardó con `prueba: true`.
   - La pregunta inicial del orquestador (20:48) no generó aviso: `GET /avisos-orquestador` no devolvió nada de prueba-44.
   - Desde la app se pidió "Propón una orden pequeña: agregar una línea al README".
   - Llegó la Orden 1 con título propio "Fase 0 · Prompt 0: crear README con una línea" (`titulo_propio: true`). La tarjeta lo mostró en negrita (captura 44-orden-titulo) y la insignia no la contó.
   - Se rechazó con "prueba de la app", que quedó en minúscula, con `decidido_por: app`.
2. **avisos-44** (mismos ajustes, sin marcar como prueba; el servidor lo guardó con `prueba: false`):
   - La pregunta inicial salió una vez como aviso arriba y apareció en Decisiones con los tres botones (captura 44-avisos). La insignia pasó a 2: esta pregunta y una de mi-proyecto, que es real y no se tocó.
   - **Responder:** abrió el chat con la pregunta resaltada y el campo listo (captura 44-responder). La respuesta enviada desde la app llegó al orquestador, que contestó a los 9 s.
   - **Esperar:** la nueva pregunta salió una vez como aviso y se puso en espera. `GET /avisos-orquestador` dejó de devolverla y la insignia bajó a 1. Con el siguiente mensaje del orquestador (después de otra respuesta desde la app) el aviso volvió, una sola vez.
   - **Ignorar:** sobre ese último aviso. El servidor dejó de devolverlo y la pila de avisos de la web no muestra nada de avisos-44, igual que la app.
3. **Detener:** los dos se detuvieron desde la app (Equipo, Detener el equipo). El servidor los muestra `detenido`. No se aprobó ninguna orden.
4. **iPhone (Washington X., iPhone 16 Pro Max con iOS 27.0.1):** compilada con Xcode 27 y el Personal Team (KVU83MD66W), instalada con `devicectl device install app`.

## Problemas y soluciones

- **Teclado del simulador:** la herramienta del simulador escribe un apóstrofo en lugar del guion, y el pegado sin UTF-8 rompe las tildes. Se usó `LANG=en_US.UTF-8 xcrun simctl pbcopy` y luego Pegar. La validación del nombre detectó el apóstrofo ("Usa solo letras minúsculas sin tildes, números y guiones").
- **Coordenadas:** varios toques fallaron por convertir mal de la captura a puntos. No es un problema de la app.

## Lo que falta en la API (anotado, sin cambiar el backend)

- **Estado del aviso:** `GET /avisos-orquestador` no devuelve los avisos ignorados ni los en espera. La app no puede mostrar "En espera" ni deshacer un Ignorar; solo desaparecen. Una ruta que liste los avisos con su estado (o un `?todos=true`) permitiría mostrarlos y deshacer.
- **Insignia en un solo número:** el servidor podría devolver en `/agents/state` un conteo que ya incluya las preguntas de los orquestadores. Hoy la app suma `decisiones_pendientes` más las preguntas de `GET /avisos-orquestador`, con dos lecturas que pueden desfasarse hasta 5 s.

## Pendiente

- El aviso de arriba también sale si ya se tiene abierto el chat de ese proyecto (la web lo oculta en la página del proyecto). Es menor; se puede ocultar comparando la ruta abierta.
- Probar en el iPhone, con el dedo, Responder desde el aviso de arriba y los interruptores de Equipo.
