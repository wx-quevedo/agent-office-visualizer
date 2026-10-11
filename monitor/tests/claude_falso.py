"""Un `claude -p --input-format stream-json` falso para las pruebas de equipos.

Anota sus argumentos y cada mensaje recibido en ``FALSO_REGISTRO`` (una línea JSON
por evento) y responde cada mensaje con un ``result``. Termina cuando se cierra su
entrada. Con ``FALSO_CAER=1`` termina enseguida (una sesión que no arranca)."""

import json
import os
import sys

registro = os.environ.get("FALSO_REGISTRO")


def anotar(d: dict) -> None:
    if registro:
        with open(registro, "a", encoding="utf-8") as f:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")


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
print(json.dumps({"type": "system", "subtype": "init", "session_id": sid}), flush=True)
for crudo in sys.stdin.buffer:
    linea = crudo.decode("utf-8")
    try:
        d = json.loads(linea)
    except ValueError:
        continue
    texto = d.get("message", {}).get("content")
    anotar({"evento": "mensaje", "pid": os.getpid(), "sid": sid, "texto": texto})
    print(
        json.dumps(
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "listo"}]}}
        ),
        flush=True,
    )
    print(
        json.dumps({"type": "result", "subtype": "success", "result": "listo", "session_id": sid}),
        flush=True,
    )
anotar({"evento": "fin", "pid": os.getpid(), "sid": sid})
