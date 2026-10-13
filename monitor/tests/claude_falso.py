"""Un `claude -p --input-format stream-json` falso para las pruebas de equipos.

Anota sus argumentos y cada mensaje recibido en ``FALSO_REGISTRO`` (una línea JSON
por evento) y responde cada mensaje con un ``result``. Termina cuando se cierra su
entrada. Con ``FALSO_CAER=1`` termina enseguida (una sesión que no arranca).

Respuestas (Prompt 38):
- Un mensaje que empieza con ``di:`` se responde con el resto del texto (así las
  pruebas hacen que el orquestador proponga órdenes), más un mensaje de un subagente
  que el monitor debe ignorar.
- Una orden (``Orden N ...``) tarda ``FALSO_DEMORA`` segundos y responde
  "Hecho: <primera línea de la orden>"; si la orden dice FALLA, el turno termina con error.
- Un mensaje que empieza con ``lento:`` se responde con el resto del texto, de a 4
  caracteres cada ``FALSO_PAUSA`` segundos (Prompt 45).
- Cualquier otro mensaje se responde "listo".

Con ``--include-partial-messages`` (Prompt 45), antes del mensaje completo manda la
respuesta en ``stream_event`` (message_start, content_block_start y text_delta), como el
claude real.
"""

import json
import os
import sys
import time

registro = os.environ.get("FALSO_REGISTRO")


def anotar(d: dict) -> None:
    """Una línea en el registro. Con candado: en Windows, dos procesos que agregan al
    mismo archivo a la vez pueden pisarse la línea."""
    if not registro:
        return
    with open(registro + ".candado", "a+b") as candado:
        if os.name == "nt":
            import msvcrt

            candado.seek(0)
            while True:  # LK_LOCK reintenta cada 1 s: demasiado lento para las pruebas
                try:
                    msvcrt.locking(candado.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.005)
        else:
            import fcntl

            fcntl.flock(candado.fileno(), fcntl.LOCK_EX)
        try:
            with open(registro, "a", encoding="utf-8") as f:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
        finally:
            if os.name == "nt":
                candado.seek(0)
                msvcrt.locking(candado.fileno(), msvcrt.LK_UNLCK, 1)


def decir(d: dict) -> None:
    # En UTF-8, como el claude real (la consola de Windows usaría cp1252).
    sys.stdout.buffer.write((json.dumps(d, ensure_ascii=False) + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()


args = sys.argv[1:]
sid = None
for opcion in ("--session-id", "--resume"):
    if opcion in args:
        sid = args[args.index(opcion) + 1]
anotar(
    {
        "evento": "inicio",
        "pid": os.getpid(),
        "args": args,
        "cwd": os.getcwd(),
        "config": os.environ.get("CLAUDE_CONFIG_DIR"),
    }
)
if os.environ.get("FALSO_CAER") == "1":
    sys.exit(3)
decir({"type": "system", "subtype": "init", "session_id": sid})
for crudo in sys.stdin.buffer:
    linea = crudo.decode("utf-8")
    try:
        d = json.loads(linea)
    except ValueError:
        continue
    texto = d.get("message", {}).get("content") or ""
    anotar({"evento": "mensaje", "pid": os.getpid(), "sid": sid, "texto": texto, "t": time.time()})
    es_error = False
    lento = texto.startswith("lento:")
    if lento:
        respuesta = texto[6:].strip()
    elif texto.startswith("di:"):
        respuesta = texto[3:].strip()
        decir(
            {
                "type": "assistant",
                "parent_tool_use_id": "toolu_x",
                "message": {"content": [{"type": "text", "text": "texto de un subagente"}]},
            }
        )
    elif texto.startswith("Orden "):
        time.sleep(float(os.environ.get("FALSO_DEMORA") or 0))
        cuerpo = texto.split("\n\n", 1)[-1]
        respuesta = "Hecho: " + cuerpo.splitlines()[0]
        es_error = "FALLA" in cuerpo
    else:
        respuesta = "listo"
    if "--include-partial-messages" in args:
        if lento:  # como el real: tarda en empezar a responder
            time.sleep(float(os.environ.get("FALSO_PAUSA") or 0.05))
        decir({"type": "stream_event", "event": {"type": "message_start"}})
        decir(
            {
                "type": "stream_event",
                "event": {
                    "type": "content_block_start",
                    "content_block": {"type": "text", "text": ""},
                },
            }
        )
        paso = 4 if lento else max(1, len(respuesta))
        for i in range(0, len(respuesta), paso):
            if lento:
                time.sleep(float(os.environ.get("FALSO_PAUSA") or 0.05))
            decir(
                {
                    "type": "stream_event",
                    "event": {
                        "type": "content_block_delta",
                        "delta": {"type": "text_delta", "text": respuesta[i : i + paso]},
                    },
                }
            )
    decir({"type": "assistant", "message": {"content": [{"type": "text", "text": respuesta}]}})
    decir(
        {
            "type": "result",
            "subtype": "error_during_execution" if es_error else "success",
            "is_error": es_error,
            "result": respuesta,
            "session_id": sid,
        }
    )
    anotar({"evento": "respuesta", "pid": os.getpid(), "sid": sid, "t": time.time()})
anotar({"evento": "fin", "pid": os.getpid(), "sid": sid})
