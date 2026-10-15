# Prompt 46: chat vivo y notificaciones nativas en la app iOS

Fecha: 2026-10-13. Estado: hecho. Código en `530f96b`, prueba real en el simulador, dos correcciones (`e09cf77` y el número de build) e instalación en el iPhone (build 317).

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

## Prueba real (2026-10-13, simulador iPhone 17 Pro Max, iOS 26.5, Xcode 26.6, servidor https://agents.example.com)

La sesión de la app seguía activa. Hubo que volver a registrar Face ID en el simulador (pedía el código del iPhone); no se escribió ningún código.

**prueba-46** (Vacía, Haiku con esfuerzo bajo; marcado solo como prueba):
- Desde la app se envió "Explícame en 10 puntos cómo organizarías este proyecto". El teclado se bajó al enviar.
- Debajo del mensaje se vio "Enviado" (captura 46-enviado) y luego "Leído".
- Después aparecieron los tres puntos, y el texto creció en la misma burbuja con "Escribiendo…" (46-escribiendo) hasta el final, que la reemplazó sin saltos (46-final).
- Tiempos, medidos consultando `/chat/en-vivo` cada 100 ms desde la web y contados desde que el servidor guardó el mensaje (04:22:40.02 UTC):

| Pedido | Leído (hora del servidor) | Leído visto | Primer texto parcial | Final | Parciales distintos |
| --- | --- | --- | --- | --- | --- |
| "Explícame en 10 puntos cómo organizarías este proyecto" (1969 caracteres) | 2,67 s | 3,58 s | 6,79 s | 10,61 s (guardado a los 9,95 s) | 4 |

- El último parcial medía 1969 caracteres, lo mismo que el final: la burbuja no saltó.

**avisos-46** (Vacía, Haiku, sin marcar como prueba):
- Con la app en Decisiones, la primera pregunta del orquestador mostró la explicación de la app ("Avisos de los orquestadores", Activar / Ahora no) y después el pedido de permiso del sistema. Se aceptaron los dos en el simulador.
- La pregunta llegó como notificación nativa con la app abierta (46-notificacion).
- Más tarde, con la app en Oficina, llegó otra pregunta como banner nativo, una sola vez.
- **Toque de notificación: se verifica en el iPhone.** En el simulador, los toques automáticos de la herramienta no llegan a los banners ni al Centro de notificaciones del sistema (en el registro de SpringBoard no aparece ninguna acción del usuario). Además, el sistema tarda unos 11 s en publicar cada notificación. Washington lo prueba en el iPhone real.
- **Con el chat de avisos-46 abierto**, se le pidió una pregunta de sí o no. El servidor creó el aviso ("¿Quieres que el botón sea de color azul?") y la app no publicó ninguna notificación: el registro de SpringBoard no tiene "Posting notification" de la app en ese tramo, y la pregunta se vio solo en el chat.
- Durante la prueba aparecieron un permiso real de vive-demo y una pregunta real de mi-proyecto; no se tocaron.

**Al terminar**, prueba-46 y avisos-46 quedaron detenidos y no se aprobó ninguna orden.

## Correcciones

- **Toque en la notificación (`e09cf77`):**
  - El delegado ahora usa las variantes con `completionHandler` de `willPresent` y `didReceive`.
  - Si la app abre desde la notificación antes de instalar la navegación, el toque queda guardado y se aplica después.
  - Se registra el toque con `Logger` (categoría `notificaciones`) para revisarlo en el iPhone.
- **Número de build:**
  - El script posterior a la compilación de `530f96b` corría antes de que Xcode procesara el Info.plist, así que la app para el iPhone quedaba con el build 1.
  - Al ordenarlo después, cambiaba el Info.plist ya firmado y la instalación fallaba con "Failed to verify code signature".
  - Ahora un script previo escribe la cantidad de commits en el Info.plist de origen (lo genera XcodeGen y no se versiona), solo si cambió. Xcode lo procesa y firma con ese número.
  - Se probó con una compilación limpia y con una incremental forzando otro número (`NUMERO_BUILD=9999`); la firma fue válida en ambas.

## Instalación en el iPhone

- **Equipo:** iPhone 16 Pro Max de Washington, conectado por cable. Compilada con Xcode 27 y el Personal Team (KVU83MD66W), firma válida. Se abrió con `devicectl device process launch`.
- **Antes:** `xcrun devicectl device info apps` mostraba "Agentes com.inmersoft.visualizadoragentes 1.0 1".
- **Después:** "Agentes com.inmersoft.visualizadoragentes 0.1.0 317".

## Pruebas unitarias

61, todas pasan, con el notificador corregido y el nuevo `project.yml`.

## Pendiente

- Verificar en el iPhone que tocar la notificación abre el chat del proyecto en la pregunta.
- Con la app cerrada no llegan notificaciones hasta tener push remoto (membresía de Apple, Prompt 32).

## Lo que falta en la API

- Nada nuevo; el SSE y la ruta liviana se usaron tal como están.
