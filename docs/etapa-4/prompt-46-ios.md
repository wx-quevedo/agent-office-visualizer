# Prompt 46: chat vivo y notificaciones nativas en la app iOS

Fecha: 2026-10-13. Estado: código hecho y probado con pruebas unitarias. **La prueba real y la instalación en el iPhone quedaron pendientes** (se alcanzó el límite de uso).

## Qué se hizo (commit `530f96b`)

- **Teclado:** se baja al enviar, al tocar fuera del campo y al desplazar el chat (`scrollDismissesKeyboard(.immediately)`).
- **Estados:** "Enviado" y luego "Leído" junto a la hora, debajo de cada mensaje de Washington (`estado` y `leido` del Prompt 45). Los mensajes de Washington se muestran como texto plano y los del orquestador con formato.
- **Tres puntos animados** en una burbuja del orquestador cuando `en_vivo.estado` es `respondiendo` y todavía no hay texto. Quedan quietos si está activado reducir el movimiento.
- **Respuesta en vivo (`ChatVivo`):**
  - Al abrir el chat hace una lectura completa, y la repite cada 10 s por las órdenes.
  - Canal SSE `/chat/eventos` con `URLSession.bytes(...).lines` y la cookie de sesión. El `LectorSSE` entrega cada evento `chat` apenas su JSON está completo.
  - Tras 3 fallos seguidos sin datos, usa `/chat/en-vivo` cada segundo, solo mientras hay respuesta en curso o un mensaje sin leer.
  - Los `recientes` se unen por id, así que el final reemplaza a la burbuja parcial en el mismo lugar.
  - Se cierra al salir del chat o al pasar a segundo plano.
- **Notificaciones nativas (`Notificador`):**
  - La primera vez que llega un aviso, la app explica para qué sirven (Activar / Ahora no) y después aparece el pedido del sistema.
  - Hay una notificación local por clave (el identificador es la clave), también con la app abierta (`willPresent` con `.banner`), y se quita deslizando hacia arriba.
  - Al tocarla, abre el chat en la pregunta o en la tarjeta de la orden.
  - No notifica si el chat de ese proyecto está a la vista.
  - Responder e Ignorar quitan la notificación ya entregada.
  - Se eliminó el aviso flotante propio de la app; los avisos siguen en Decisiones con sus botones.
  - **Con la app cerrada no llegan:** son notificaciones locales. Hace falta push remoto, que requiere la membresía de Apple (Prompt 32).
- **Número de build:** un script posterior a la compilación en `project.yml` escribe en `CFBundleVersion` la cantidad de commits de git, antes de firmar. Hoy es 313. La versión se muestra al pie de Decisiones ("Versión 0.1.0 (build N)").
- **Pruebas:** 61 en total, todas pasan. Las 10 nuevas en `ChatVivoTests` cubren las marcas, la burbuja, la unión por id, cuándo usar el respaldo, el lector SSE, la decodificación, el contenido y la regla de las notificaciones, la versión y el cliente SSE y en vivo.

## Pendiente

- Prueba real en el simulador con prueba-46 (tiempos de leído, primer texto y final) y avisos-46 (notificación nativa, tocarla y que no notifique con el chat abierto). Hay que detener los dos al terminar.
- Capturas 46-enviado, 46-escribiendo, 46-final y 46-notificacion.
- Instalar en el iPhone: el intento falló con "The device disconnected immediately after connecting" (CoreDeviceError 4000). El teléfono sigue con la build anterior (1.0, build 1). Hay que reconectarlo, desbloquearlo y repetir la instalación con Xcode 27.

## Lo que falta en la API

- Nada nuevo por ahora; el SSE y la ruta liviana se usaron tal como están.
