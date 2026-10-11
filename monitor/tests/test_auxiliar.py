"""Auxiliar de los avisos (etapa 2.4): entrada, enmascarado, cuenta, aislamiento,
tope de tiempo, respaldo, caché, límite por minuto y el hilo que lo usa."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from visualizador_monitor import auxiliar as aux
from visualizador_monitor.auxiliar import (
    Auxiliar,
    TiempoAgotado,
    armar_entrada,
    comando,
    cuenta_para,
    enmascarar,
    entorno,
    es_de_auxiliar,
    limpiar_salida,
)
from visualizador_monitor.cliente import Respuesta

HOME = Path("C:/Users/w") if sys.platform == "win32" else Path("/home/w")
PERSONAL = HOME / ".claude"
DEMO = HOME / ".claude-demo"
CUENTAS = [str(PERSONAL), str(DEMO)]


def _aviso(**extra: Any) -> dict[str, Any]:
    return {
        "clave": "s1:permiso:abc",
        "tipo": "permiso",
        "proyecto": "SkyNest",
        "cuenta": "personal",
        "transcript": str(PERSONAL / "projects" / "e--Test-SkyNest" / "s1.jsonl"),
        "datos": {
            "herramienta": "PowerShell",
            "detalle": "Remove-Item -Recurse Library\\ScriptAssemblies",
        },
        **extra,
    }


def _salida(
    texto: str = "SkyNest quiere borrar una carpeta de compilación de Unity y necesita tu permiso.",
    **extra: Any,
) -> bytes:
    datos = {
        "result": texto,
        "is_error": False,
        "usage": {
            "input_tokens": 2,
            "cache_creation_input_tokens": 754,
            "cache_read_input_tokens": 0,
            "output_tokens": 20,
        },
        "total_cost_usd": 0.0002,
        "modelUsage": {"claude-haiku-5-5": {}},
        **extra,
    }
    return json.dumps(datos).encode()


class Ejecutor:
    def __init__(
        self, codigo: int = 0, salida: bytes | None = None, error: Exception | None = None
    ) -> None:
        self.llamadas: list[dict[str, Any]] = []
        self.codigo = codigo
        self.salida = _salida() if salida is None else salida
        self.error = error

    def __call__(
        self, cmd: list[str], entrada: bytes, cwd: Path, env: dict[str, str], tope: float
    ) -> tuple[int, bytes]:
        self.llamadas.append(
            {"cmd": cmd, "entrada": entrada.decode(), "cwd": cwd, "env": env, "tope": tope}
        )
        if self.error is not None:
            raise self.error
        return self.codigo, self.salida


def _auxiliar(tmp_path: Path, ejecutor: Ejecutor, **kw: Any) -> Auxiliar:
    return Auxiliar(
        CUENTAS,
        base=tmp_path,
        ejecutor=ejecutor,
        claude="claude.exe",
        entorno_base={
            "PATH": "x",
            "CLAUDECODE": "1",
            "CLAUDE_CODE_CHILD_SESSION": "1",
            "ANTHROPIC_API_KEY": "sk-ant-x",
            "USERPROFILE": str(HOME),
        },
        **kw,
    )


# -- entrada y enmascarado ------------------------------------------------------------


def test_armado_de_la_entrada() -> None:
    e = armar_entrada(_aviso())
    assert e.splitlines() == [
        "Proyecto: SkyNest",
        "Tipo de aviso: permiso pendiente",
        "Herramienta: PowerShell",
        "Comando o detalle: Remove-Item -Recurse Library\\ScriptAssemblies",
    ]
    largo = armar_entrada(_aviso(datos={"pregunta": "x " * 2000}))
    assert len(largo) <= aux.MAX_ENTRADA
    # En la prosa las rutas quedan con su último nombre; el comando del permiso, entero.
    prosa = armar_entrada(
        _aviso(tipo="pregunta", datos={"pregunta": "¿Reviso src/components/avisos?"})
    )
    assert "Pregunta: ¿Reviso avisos?" in prosa
    termino = armar_entrada(
        {
            "tipo": "termino",
            "proyecto": "server-monitor",
            "datos": {"pedido": "Corregir el login", "commits": 1},
        }
    )
    assert "Tipo de aviso: tarea terminada" in termino
    assert "Lo que se le pidió: Corregir el login" in termino
    assert "Commits: 1" in termino


@pytest.mark.parametrize(
    ("texto", "no_debe_quedar"),
    [
        (
            "curl -H 'Authorization: Bearer abcdefghijklmnop123456' https://x",
            "abcdefghijklmnop123456",
        ),
        ("export ANTHROPIC_API_KEY=sk-ant-api03-AbCdEf1234567890", "sk-ant-api03-AbCdEf1234567890"),
        (
            "git push https://user:ghp_ABCDEFGHIJKLMNOPQRSTUVWX12@github.com/x.git",
            "ghp_ABCDEFGHIJKLMNOPQRSTUVWX12",
        ),
        ("mysql -u root --password hunter2 db", "hunter2"),
        ('$env:DB_PASSWORD = "s3cr3t-valor"', "s3cr3t-valor"),
        ('{"client_secret": "abcd1234efgh"}', "abcd1234efgh"),
        ("token vam_abcdefgh12345678", "vam_abcdefgh12345678"),
        ("aws AKIAABCDEFGHIJKLMNOP s3 ls", "AKIAABCDEFGHIJKLMNOP"),
        (
            "jwt eyJhbGciOiJI.eyJzdWIiOiIx.SflKxwRJSMeKKF2QT4",
            "eyJhbGciOiJI.eyJzdWIiOiIx.SflKxwRJSMeKKF2QT4",
        ),
        ("clave Zx8kP2mQ9vR4tY7wL1nB5cJ3hG6fD0sA9uE2", "Zx8kP2mQ9vR4tY7wL1nB5cJ3hG6fD0sA9uE2"),
        ("-----BEGIN RSA PRIVATE KEY-----\nMIIEow\n-----END RSA PRIVATE KEY-----", "MIIEow"),
    ],
)
def test_enmascarado_de_secretos(texto: str, no_debe_quedar: str) -> None:
    limpio = enmascarar(texto)
    assert no_debe_quedar not in limpio
    assert "[secreto]" in limpio


def test_enmascarado_no_toca_texto_normal() -> None:
    for texto in (
        "Remove-Item -Recurse Library\\ScriptAssemblies",
        "git commit --author Washington -m arreglo",
        "npm run build",
        "¿Publico la versión nueva?",
    ):
        assert enmascarar(texto) == texto


def test_la_entrada_va_enmascarada() -> None:
    e = armar_entrada(
        _aviso(
            datos={
                "herramienta": "Bash",
                "detalle": "export GITHUB_TOKEN=ghp_1234567890abcdefghijklmnop",
            }
        )
    )
    assert "ghp_" not in e and "[secreto]" in e


# -- cuenta, entorno y aislamiento ----------------------------------------------------


def test_eleccion_de_cuenta() -> None:
    cuentas = [Path(c) for c in CUENTAS]
    assert cuenta_para(str(DEMO / "projects" / "x" / "s.jsonl"), "personal", cuentas) == DEMO
    assert cuenta_para(str(PERSONAL / "projects" / "x" / "s.jsonl"), "demo", cuentas) == PERSONAL
    # Sin transcripción: según la cuenta que dice el servidor, nunca la otra.
    assert cuenta_para(None, "demo", cuentas) == DEMO
    assert cuenta_para(None, "personal", cuentas) == PERSONAL
    assert cuenta_para(None, "demo", [PERSONAL]) is None
    assert cuenta_para(None, None, cuentas) is None
    # Una transcripción fuera de las cuentas o una ruta de red: ninguna cuenta.
    assert cuenta_para(str(HOME / "otra" / "s.jsonl"), "personal", cuentas) is None
    assert cuenta_para("\\\\servidor\\c\\s.jsonl", "personal", cuentas) is None


def test_entorno_limpio_con_la_cuenta() -> None:
    base = {
        "PATH": "x",
        "CLAUDECODE": "1",
        "CLAUDE_CONFIG_DIR": "otra",
        "ANTHROPIC_API_KEY": "k",
        "claude_x": "1",
    }
    personal = entorno(PERSONAL, base, home=HOME)
    assert not any(k.upper().startswith(("CLAUDE_CODE_CHILD", "ANTHROPIC")) for k in personal)
    assert (
        "CLAUDECODE" not in personal
        and "CLAUDE_CONFIG_DIR" not in personal
        and "claude_x" not in personal
    )
    assert personal["CLAUDE_CODE_SKIP_PROMPT_HISTORY"] == "1"
    assert personal["PATH"] == "x"
    assert entorno(DEMO, base, home=HOME)["CLAUDE_CONFIG_DIR"] == str(DEMO)


def test_comando_aislado() -> None:
    c = comando("claude.exe")
    for opcion in (
        "-p",
        "--safe-mode",
        "--strict-mcp-config",
        "--disable-slash-commands",
        "--no-session-persistence",
    ):
        assert opcion in c
    assert c[c.index("--model") + 1] == "haiku"
    assert c[c.index("--effort") + 1] == "low"
    assert c[c.index("--tools") + 1] == ""
    assert c[c.index("--setting-sources") + 1] == ""
    assert c[c.index("--disallowedTools") + 1] == "mcp__*"
    assert json.loads(c[c.index("--settings") + 1]) == {"disableAllHooks": True}
    assert c[c.index("--max-turns") + 1] == "1"
    assert not {"--resume", "-r", "--continue", "-c", "--bare"} & set(c)


def test_filtro_de_eventos_de_la_carpeta_auxiliar() -> None:
    carpeta = str(HOME / ".visualizador-monitor" / "auxiliar")
    assert es_de_auxiliar({"session_id": "a", "data": {"project_dir": carpeta}})
    assert es_de_auxiliar({"session_id": "a", "data": {"working_dir": carpeta + "\\sub"}})
    assert es_de_auxiliar({"session_id": "a", "cwd": carpeta.upper()})
    assert not es_de_auxiliar(
        {"session_id": "a", "data": {"project_dir": "E:/visualizador-agentes"}}
    )
    assert not es_de_auxiliar(
        {
            "session_id": "a",
            "data": {"project_dir": str(HOME / ".visualizador-monitor" / "auxiliar2")},
        }
    )


# -- llamada: éxito, respaldo, tope, caché y límite ------------------------------------


def test_resumen_correcto_con_su_consumo(tmp_path: Path) -> None:
    ej = Ejecutor()
    r = _auxiliar(tmp_path, ej).resumir(_aviso())
    assert (
        r.texto
        == "SkyNest quiere borrar una carpeta de compilación de Unity y necesita tu permiso."
    )
    assert r.llamo and r.cuenta == "personal" and r.modelo == "claude-haiku-5-5"
    assert (r.tokens_entrada, r.tokens_salida, r.costo_usd) == (756, 20, 0.0002)
    llamada = ej.llamadas[0]
    assert llamada["cwd"] == tmp_path / "auxiliar" and llamada["cwd"].is_dir()
    assert list(llamada["cwd"].iterdir()) == []  # carpeta vacía, sin CLAUDE.md
    assert "Remove-Item" in llamada["entrada"]  # por la entrada estándar
    assert not any("Remove-Item" in p for p in llamada["cmd"])  # nunca en la línea de comandos
    assert "CLAUDECODE" not in llamada["env"] and "ANTHROPIC_API_KEY" not in llamada["env"]
    assert llamada["tope"] == aux.TOPE_S


def test_demo_usa_su_cuenta(tmp_path: Path) -> None:
    ej = Ejecutor()
    r = _auxiliar(tmp_path, ej).resumir(
        _aviso(cuenta="demo", transcript=str(DEMO / "projects" / "x" / "s.jsonl"))
    )
    assert r.cuenta == "demo"
    assert ej.llamadas[0]["env"]["CLAUDE_CONFIG_DIR"] == str(DEMO)


@pytest.mark.parametrize(
    ("ejecutor", "motivo", "llamo"),
    [
        (Ejecutor(error=TiempoAgotado()), "tiempo_agotado", True),
        (Ejecutor(error=OSError("no existe")), "error_OSError", False),
        (Ejecutor(codigo=1), "error_del_auxiliar", True),
        (Ejecutor(salida=_salida(is_error=True)), "error_del_auxiliar", True),
        (Ejecutor(salida=b"no es json"), "salida_ilegible", True),
        (Ejecutor(salida=_salida("SkyNest corre `rm -rf x`")), "salida_invalida", True),
        (Ejecutor(salida=_salida("")), "salida_invalida", True),
    ],
)
def test_respaldo_cuando_falla(
    tmp_path: Path, ejecutor: Ejecutor, motivo: str, llamo: bool
) -> None:
    r = _auxiliar(tmp_path, ejecutor).resumir(_aviso())
    assert r.texto is None and r.motivo == motivo and r.llamo is llamo


def test_sin_cuenta_o_sin_claude_no_llama(tmp_path: Path) -> None:
    ej = Ejecutor()
    a = _auxiliar(tmp_path, ej)
    assert a.resumir(_aviso(cuenta=None, transcript=str(HOME / "x.jsonl"))).motivo == "sin_cuenta"
    sin = Auxiliar(CUENTAS, base=tmp_path, ejecutor=ej, claude=None, entorno_base={})
    sin_claude = sin.resumir(_aviso()) if aux.buscar_claude() is None else None
    if sin_claude is not None:
        assert sin_claude.motivo == "sin_claude"
    assert ej.llamadas == [] or sin_claude is None


def test_cache_por_aviso_y_por_texto(tmp_path: Path) -> None:
    ej = Ejecutor()
    a = _auxiliar(tmp_path, ej)
    primero = a.resumir(_aviso())
    segundo = a.resumir(_aviso())  # misma clave
    tercero = a.resumir(_aviso(clave="s1:permiso:recordatorio"))  # mismo texto
    assert len(ej.llamadas) == 1
    assert segundo.texto == tercero.texto == primero.texto
    assert segundo.desde_cache and not segundo.llamo
    a.resumir(
        _aviso(clave="s1:permiso:otro", datos={"herramienta": "Bash", "detalle": "npm install"})
    )
    assert len(ej.llamadas) == 2


def test_limite_por_minuto(tmp_path: Path) -> None:
    ahora = [1000.0]
    ej = Ejecutor()
    a = _auxiliar(tmp_path, ej, reloj=lambda: ahora[0], por_minuto=2)
    for i in range(3):
        a.resumir(_aviso(clave=f"c{i}", datos={"detalle": f"comando {i}"}))
    assert len(ej.llamadas) == 2
    assert a.resumir(_aviso(clave="c9", datos={"detalle": "otro"})).motivo == "limite_por_minuto"
    ahora[0] += 61
    assert a.resumir(_aviso(clave="c9", datos={"detalle": "otro"})).texto is not None


def test_tope_de_tiempo_real_detiene_el_proceso(tmp_path: Path) -> None:
    lento = [sys.executable, "-c", "import time; time.sleep(30)"]
    inicio = time.monotonic()
    with pytest.raises(TiempoAgotado):
        aux.ejecutar(lento, b"", tmp_path, dict(__import__("os").environ), 1.0)
    assert time.monotonic() - inicio < 6


def test_limpiar_salida() -> None:
    assert limpiar_salida('"SkyNest terminó la tarea."', "SkyNest") == "SkyNest terminó la tarea."
    assert (
        limpiar_salida("El agente de SkyNest terminó.", "SkyNest")
        == "El agente de SkyNest terminó."
    )
    assert limpiar_salida("Terminó la tarea.", "SkyNest") == "SkyNest: terminó la tarea."
    assert limpiar_salida("server-monitor te pregunta algo.", "server-monitor") == (
        "server-monitor te pregunta algo."
    )
    largo = limpiar_salida("SkyNest " + "palabra " * 40, "SkyNest")
    assert largo is not None and len(largo.split()) <= aux.MAX_PALABRAS
    for malo in ("SkyNest corre `npm`", "SkyNest usa [secreto]", "SkyNest ve https://x.com"):
        assert limpiar_salida(malo, "SkyNest") is None
    # Las rutas quedan con su último nombre; "y/o" o "5/10" no son rutas.
    assert limpiar_salida("SkyNest edita src/app/main.py", "SkyNest") == "SkyNest edita main.py"
    assert limpiar_salida("SkyNest borra E:\\Unity\\Library\\x", "SkyNest") == "SkyNest borra x"
    assert limpiar_salida("SkyNest pasó 5/10 pruebas y/o falló", "SkyNest") == (
        "SkyNest pasó 5/10 pruebas y/o falló"
    )


# -- el hilo -------------------------------------------------------------------------


class ServidorFalso:
    def __init__(self, avisos: list[dict[str, Any]]) -> None:
        self.avisos = avisos
        self.recibidos: list[dict[str, Any]] = []

    def pedir(
        self,
        metodo: str,
        ruta: str,
        cuerpo: bytes | None = None,
        timeout: float = 5.0,
        cabeceras: Any = None,
    ) -> Respuesta:
        assert (metodo, ruta) == ("GET", "/api/v1/maquinas/avisos")
        return Respuesta(200, {"activos": True, "avisos": self.avisos})

    def post_json(self, ruta: str, datos: dict[str, Any], timeout: float = 5.0) -> Respuesta:
        assert ruta == "/api/v1/maquinas/resumenes"
        self.recibidos.append(datos)
        return Respuesta(200, {"estado": "listo"})


def test_resumidor_manda_frase_y_fallo_una_vez(tmp_path: Path) -> None:
    from visualizador_monitor.resumidor import Resumidor

    falso = ServidorFalso([_aviso(), _aviso(clave="s2:pregunta:x", cuenta=None, transcript=None)])
    r = Resumidor(falso, _auxiliar(tmp_path, Ejecutor()), lambda: True)  # type: ignore[arg-type]
    assert r.ronda() == 2
    r._pool.shutdown(wait=True)  # pyright: ignore[reportPrivateUsage]
    por_clave = {d["clave"]: d for d in falso.recibidos}
    assert por_clave["s1:permiso:abc"]["texto"].startswith("SkyNest")
    assert por_clave["s1:permiso:abc"]["metricas"]["llamo"] is True
    assert por_clave["s2:pregunta:x"]["texto"] is None
    assert por_clave["s2:pregunta:x"]["metricas"]["motivo"] == "sin_cuenta"
    # Ya enviados: la ronda siguiente no los repite.
    r._pool = __import__("concurrent.futures").futures.ThreadPoolExecutor(1)  # pyright: ignore[reportPrivateUsage]
    assert r.ronda() == 0


# -- revisión independiente (etapa 2.4) -------------------------------------------------

SE_ESCAPABAN = [
    ("mysql -u root -pHunter2 app", "Hunter2"),
    ("mysql -u root -p Hunter2 app", "Hunter2"),
    ("sqlcmd -S srv -U sa -P S3cr3t", "S3cr3t"),
    ("sshpass -p Clave123 ssh host", "Clave123"),
    ("docker login -u yo -p Clave123 registry", "Clave123"),
    ("az login -u yo -p Clave123", "Clave123"),
    ("redis-cli -h h -a Clave123 ping", "Clave123"),
    ("openssl enc -aes256 -k Clave123 -in a", "Clave123"),
    ("zip -P Clave123 a.zip b", "Clave123"),
    ("7z a -pClave123 a.7z b", "Clave123"),
    ("curl -u admin:Clave123 https://x", "Clave123"),
    ("curl --user admin:Clave123 https://x", "Clave123"),
    ("net user admin Clave123 /add", "Clave123"),
    ("net use Z: \\srv\c /user:dom\yo Clave123", "Clave123"),
    ("ConvertTo-SecureString 'Clave123' -AsPlainText -Force", "Clave123"),
    ("ConvertTo-SecureString -String Clave123 -AsPlainText", "Clave123"),
    ("[Environment]::SetEnvironmentVariable('DB_PASSWORD','Clave123')", "Clave123"),
    ("echo 'Clave123' | sudo -S apt update", "Clave123"),
    ("curl -H 'Cookie: session=abc123def' https://x", "abc123def"),
    ("https://cuenta.blob.core.windows.net/c?sv=2020&sig=AbCd%2Fef12", "AbCd%2Fef12"),
    ("export GH_PAT=abcd1234", "abcd1234"),
    ("curl https://hooks.slack.com/services/T000/B000/XXXX", "T000/B000/XXXX"),
    ("Server=db;Database=x;User Id=sa;Password=Clave123;", "Clave123"),
    (
        "aws configure set aws_secret_access_key wJalrXUtnFEMIK7MDENGbPxRfiCYEXAMPLEKEY",
        "wJalrXUtnFEMIK7MDENGbPxRfiCYEXAMPLEKEY",
    ),
]


@pytest.mark.parametrize(("texto", "secreto"), SE_ESCAPABAN)
def test_secretos_de_comandos(texto: str, secreto: str) -> None:
    assert secreto not in enmascarar(texto)


@pytest.mark.parametrize(
    "texto",
    [
        "Agrega basic authentication al login",
        "Revisa el token counting del contexto",
        "El Authorization middleware falla",
        "SELECT * FROM u WHERE password_hash = ?",
        "{auth: true, retries: 3}",
        "git show 3f2a9c1e5b7d4a6f8e0c2b4d6f8a0c2e4b6d8f0a",
        "sesión 66a913b9-11fb-4759-83fc-02d46093d351",
        "C:/Users/w/AppData/Local/Temp/claude/0123456789abcdef0123456789abcdef/x.txt",
        "git commit --author Washington -m arreglo",
    ],
)
def test_sin_falsos_positivos_molestos(texto: str) -> None:
    assert enmascarar(texto) == texto


def test_la_frase_no_puede_repetir_secretos_ni_datos_de_la_entrada() -> None:
    assert limpiar_salida("SkyNest pide usar ghp_abcdefghijklmnopqrstuvwxyz12", "SkyNest") is None
    assert (
        limpiar_salida("SkyNest usa la clave wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", "SkyNest")
        is None
    )
    entrada = "Proyecto: buscapez\nComando o detalle: mysql -u root -pHunter2x9 app"
    assert (
        limpiar_salida("buscapez quiere entrar con Hunter2x9 a la base.", "buscapez", entrada)
        is None
    )
    assert limpiar_salida("buscapez quiere entrar a la base de datos.", "buscapez", entrada) == (
        "buscapez quiere entrar a la base de datos."
    )


def test_entorno_sin_telemetria_ni_inyecciones() -> None:
    base = {"PATH": "x", "OTEL_EXPORTER_OTLP_ENDPOINT": "http://y", "NODE_OPTIONS": "--require z"}
    env = entorno(PERSONAL, base, home=HOME)
    assert "OTEL_EXPORTER_OTLP_ENDPOINT" not in env and "NODE_OPTIONS" not in env
    for clave in (
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC",
        "DISABLE_TELEMETRY",
        "DISABLE_ERROR_REPORTING",
        "CLAUDE_CODE_DISABLE_AUTO_MEMORY",
        "CLAUDE_CODE_DISABLE_CLAUDE_MDS",
        "VISUALIZADOR_AUXILIAR",
    ):
        assert env[clave] == "1"
    assert env["ENABLE_CLAUDEAI_MCP_SERVERS"] == "false"


def test_filtro_por_la_carpeta_real_y_por_la_marca(tmp_path: Path) -> None:
    otra = tmp_path / "monitor-en-otro-lado" / "auxiliar"
    otra.mkdir(parents=True)
    evento = {"session_id": "a", "data": {"project_dir": str(otra)}}
    assert not es_de_auxiliar(evento)
    assert es_de_auxiliar(evento, otra)
    assert es_de_auxiliar({"session_id": "a", "data": {"working_dir": str(otra / "sub")}}, otra)
    assert es_de_auxiliar({"session_id": "a", "data": {"auxiliar": True}})
    assert not es_de_auxiliar({"session_id": "a", "data": {"project_dir": str(tmp_path)}}, otra)


def test_al_detener_no_quedan_auxiliares(tmp_path: Path) -> None:
    import threading

    lento = [sys.executable, "-c", "import time; time.sleep(30)"]
    errores: list[BaseException] = []

    def correr() -> None:
        try:
            aux.ejecutar(lento, b"", tmp_path, dict(__import__("os").environ), 20)
        except BaseException as e:  # noqa: BLE001
            errores.append(e)

    hilo = threading.Thread(target=correr)
    hilo.start()
    fin = time.monotonic() + 5
    while not aux._ACTIVOS and time.monotonic() < fin:  # pyright: ignore[reportPrivateUsage]
        time.sleep(0.05)
    assert aux.detener_todos() == 1
    hilo.join(timeout=10)
    assert not hilo.is_alive()
    assert not aux._ACTIVOS  # pyright: ignore[reportPrivateUsage]


def test_un_permiso_que_es_pregunta_llega_como_pregunta() -> None:
    e = armar_entrada(
        {
            "tipo": "permiso",
            "como": "pregunta",
            "proyecto": "vive-demo",
            "datos": {"pregunta": "¿Cómo sigo?"},
        }
    )
    assert "Tipo de aviso: pregunta del agente" in e and "Pregunta: ¿Cómo sigo?" in e


def test_el_corte_de_25_palabras_cierra_bien() -> None:
    larga = (
        "server-monitor necesita que pegues un comando en una ventana nueva de PowerShell "
        "para leer las capas de 143 imágenes; solo lee, no cambia nada, y tarda uno o dos minutos."
    )
    corta = limpiar_salida(larga, "server-monitor")
    assert corta is not None and len(corta.split()) <= aux.MAX_PALABRAS
    assert not corta.endswith(" y.") and corta.endswith(".")
    sin_pausa = limpiar_salida("SkyNest " + "trabaja " * 23 + "en la escena del home", "SkyNest")
    assert sin_pausa is not None and not sin_pausa.endswith((" en.", " la."))
