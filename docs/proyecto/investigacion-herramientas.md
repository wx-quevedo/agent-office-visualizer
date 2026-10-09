# Investigación: cómo muestran los agentes otras herramientas

Versión 2026-10-09. Documento con capturas: https://claude.ai/code/artifact/1bfdcfb5-40b3-4d66-bf90-7362c755cafd

Las cuatro herramientas revisadas muestran lo mismo que claude-office (un personaje por sesión que trabaja, espera o descansa), pero ninguna cubre lo que buscamos: un agente grande y protagonista, que muestre a quién espera y que descanse cuando el usuario no está.

## Herramientas

| Herramienta | Dónde corre | Qué aporta | Límite | Enlace |
| --- | --- | --- | --- | --- |
| Pixel Agents | Extensión de VS Code | Personajes grandes y expresivos, zonas de descanso (cocina, sala), globos de diálogo al esperar, sonido al terminar o pedir permiso, editor de oficina | Solo dentro de VS Code; no indica a quién espera ni el esfuerzo | https://github.com/pablodelucca/pixel-agents |
| pixtuoid | Terminal | Etiqueta de estado sobre cada personaje, "?" al esperar y zzz al terminar, monitor con color por herramienta, pila de papeles por tokens, contadores globales, duración y % activo al pasar el mouse, panel de árbol de agentes | Windows experimental; corre en la terminal | https://github.com/IvanWng97/pixtuoid |
| PixelHQ | App de iPhone | Oficina en el celular con modo demo; el puente solo envía metadatos | Solo en la misma red Wi-Fi; sin soporte documentado para Windows ni dos cuentas | https://apps.apple.com/app/pixelhq/id6758467298 |
| pixelagents (YehudaLevi) | Web local | Una tarjeta por agente, brillo rojo "waiting on you", campana y sonido, subagentes como mini personajes, tamaños S/M/L, registro de eventos en vivo, durmiendo tras 5 min, confeti al terminar | Poco ambiente; personajes pequeños | https://github.com/YehudaLevi/pixelagents |

## Lo que tenemos frente a lo que nos sirve

| Aspecto | claude-office (hoy) | Lo que nos sirve de otras | Fuente |
| --- | --- | --- | --- |
| Tamaño del agente | Pequeño, en una oficina grande | Personajes más grandes y expresivos; tamaños S/M/L | Pixel Agents, pixelagents |
| Todo en una oficina | Command Center con columnas: te necesita, trabajando, terminado | Contadores globales siempre visibles | pixtuoid, pixelagents |
| Esperando | Alerta dentro de la página | Brillo rojo y "?" sobre el personaje; globo de diálogo | pixelagents, pixtuoid, Pixel Agents |
| A quién espera | No lo muestra | Ninguna lo muestra (idea propia) | — |
| Qué está haciendo | Globo con resumen y registro de eventos | Color del monitor por herramienta; etiqueta de estado | pixtuoid |
| Esfuerzo y tiempo | Basurero de contexto, contador de herramientas, pizarra | Pila de papeles por tokens; duración y % activo al pasar el mouse | pixtuoid |
| Descanso | Sin estado propio | Zzz y durmiendo tras 5 minutos; zonas de cocina y sala | pixtuoid, pixelagents, Pixel Agents |
| Avisos | Sin sonido ni notificación | Sonido y notificación del navegador | Pixel Agents, pixelagents |
| Celular | Web adaptable (por Tailscale) | App nativa con modo demo | PixelHQ |
| Subagentes | Empleados que salen del ascensor | Mini personajes al pie del escritorio (más discretos) | pixelagents |
