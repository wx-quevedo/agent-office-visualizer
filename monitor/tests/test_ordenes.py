"""Chat y órdenes con el monitor de intermediario (etapa 4, Prompt 38), con un
`claude` falso: orden propuesta, aprobada, editada, rechazada, en cola, reinicio a
la mitad y un destino fuera del proyecto."""

from __future__ import annotations

import json
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from test_equipos import _encargo, _esperar, _eventos, _gestor

from visualizador_monitor.cliente import Respuesta, SinConexion
from visualizador_monitor.equipos import Equipos, extraer_ordenes

PID = "a" * 32


def test_extraer_ordenes() -> None:
    texto = (
        "Te propongo dos pasos.\n\n"
        '<orden agente="agente" estimado="2 min" dificultad="baja">\nCrea hola.txt\n</orden>\n\n'
        "Y después:\n<ORDEN agente='x'>sin comillas dobles</ORDEN>\n"
        '<orden agente="agente-2">Otra\ncon dos líneas</orden>'
    )
    ordenes, limpio = extraer_ordenes(texto)
    assert ordenes == [
        {"agente": "agente", "texto": "Crea hola.txt", "estimado": "2 min", "dificultad": "baja"},
        {"agente": "", "texto": "sin comillas dobles", "estimado": None, "dificultad": None},
        {
            "agente": "agente-2",
            "texto": "Otra\ncon dos líneas",
            "estimado": None,
            "dificultad": None,
        },
    ]
    assert limpio == "Te propongo dos pasos.\n\nY después:"
    assert extraer_ordenes("Solo charla.") == ([], "Solo charla.")


class Servidor:
    """Recibe lo que manda el monitor; a las órdenes propuestas les da un id."""

    def __init__(self) -> None:
        self.posts: list[tuple[str, dict[str, Any]]] = []
        self.caido = False
        self.estado = 200

    def post_json(self, ruta: str, datos: dict[str, Any], timeout: float = 5.0) -> Respuesta:
        if self.caido:
            raise SinConexion("x")
        if self.estado >= 400:
            return Respuesta(self.estado, {"detail": "agente no es de este proyecto"})
        self.posts.append((ruta, datos))
        if ruta == "/api/v1/maquinas/ordenes":
            return Respuesta(200, {"id": uuid.uuid4().hex, "numero": 1, "estado": "por_aprobar"})
        return Respuesta(200, {})

    def de(self, ruta: str) -> list[dict[str, Any]]:
        return [d for r, d in self.posts if r == ruta]


def _mensajes(registro: Path, sid: str) -> list[str]:
    return [e["texto"] for e in _eventos(registro) if e["evento"] == "mensaje" and e["sid"] == sid]


def _girar(g: Equipos, srv: Servidor, cond: Any, s: float = 10.0) -> bool:
    def paso() -> bool:
        g.atender()
        g.vaciar_salida(srv)  # type: ignore[arg-type]
        return bool(cond())

    return _esperar(paso, s)


def _listo(tmp_path: Path, **extra: Any) -> tuple[Equipos, Servidor, Path, dict[str, Any]]:
    """Un equipo creado, con los saludos ya respondidos."""
    registro = tmp_path / "registro.jsonl"
    g = _gestor(tmp_path, registro, **extra)
    enc = _encargo(proyecto_id=PID, nombre="prueba-38")
    assert g.procesar(enc)["ok"]
    srv = Servidor()
    assert _girar(g, srv, lambda: srv.de("/api/v1/maquinas/chat"))
    assert _girar(g, srv, lambda: not any(s.ocupada() for s in g.sesiones.values()))
    return g, srv, registro, enc


def _sids(enc: dict[str, Any]) -> tuple[str, str]:
    return enc["equipo"][0]["session_id"], enc["equipo"][1]["session_id"]


def _mensaje(texto: str) -> dict[str, Any]:
    return {**_encargo("mensaje", proyecto_id=PID), "mensaje_id": uuid.uuid4().hex, "texto": texto}


def _orden(texto: str, agente: str = "agente", numero: int = 1, **extra: Any) -> dict[str, Any]:
    return {
        **_encargo("orden", proyecto_id=extra.pop("proyecto_id", PID)),
        "orden_id": extra.pop("orden_id", uuid.uuid4().hex),
        "numero": numero,
        "agente": agente,
        "texto": texto,
        **extra,
    }


def test_orden_propuesta_aprobada_editada_y_rechazada(tmp_path: Path) -> None:
    g, srv, registro, enc = _listo(tmp_path)
    orq, agente = _sids(enc)
    try:
        # El saludo del orquestador llegó al chat; el texto del subagente nunca.
        assert srv.de("/api/v1/maquinas/chat")[0]["texto"] == "listo"
        # Washington le escribe; el orquestador propone una orden.
        propuesta = (
            "di: Propongo crear el archivo.\n"
            '<orden agente="agente" estimado="1 min" dificultad="baja">Crea hola.txt: Hola</orden>'
        )
        assert g.procesar(_mensaje(propuesta))["ok"]
        assert _girar(g, srv, lambda: srv.de("/api/v1/maquinas/ordenes"))
        [o] = srv.de("/api/v1/maquinas/ordenes")
        assert (o["proyecto_id"], o["agente"], o["texto"]) == (PID, "agente", "Crea hola.txt: Hola")
        assert (o["estimado"], o["dificultad"]) == ("1 min", "baja")
        chat = [c["texto"] for c in srv.de("/api/v1/maquinas/chat")]
        assert chat[-1] == "Propongo crear el archivo." and "texto de un subagente" not in chat
        # Propuesta no es aprobada: el agente no recibió nada más que su saludo.
        time.sleep(0.3)
        assert len(_mensajes(registro, agente)) == 1
        # Aprobada con el texto editado: solo ese texto le llega al agente.
        oid = uuid.uuid4().hex
        assert g.procesar(_orden("Crea hola.txt: Prueba 38", orden_id=oid, editada=True))["ok"]
        ruta = f"/api/v1/maquinas/ordenes/{oid}"
        assert _girar(g, srv, lambda: any(d["estado"] == "terminada" for d in srv.de(ruta)))
        recibidas = _mensajes(registro, agente)
        assert recibidas[-1] == (
            "Orden 1 del orquestador, aprobada por Washington:\n\nCrea hola.txt: Prueba 38"
        )
        assert [d["estado"] for d in srv.de(ruta)] == ["en_curso", "terminada"]
        assert srv.de(ruta)[-1]["resumen"] == "Hecho: Crea hola.txt: Prueba 38"
        # El resultado vuelve al orquestador.
        assert _girar(
            g, srv, lambda: any("Resultado de la orden 1" in t for t in _mensajes(registro, orq))
        )
        # Y sabe que Washington la editó y con qué texto la recibió el agente.
        [res] = [t for t in _mensajes(registro, orq) if "Resultado de la orden 1" in t]
        assert res.startswith("Washington editó esta orden") and "Prueba 38" in res
        # Repetir el encargo (reentrega del servidor) no la vuelve a mandar.
        assert g.procesar(_orden("Crea hola.txt: Prueba 38", orden_id=oid))["ok"]
        time.sleep(0.3)
        g.atender()
        assert sum(m.startswith("Orden 1") for m in _mensajes(registro, agente)) == 1
        # Rechazo: el orquestador recibe el motivo; el agente, nada.
        rechazo = {
            **_encargo("rechazo", proyecto_id=PID),
            "orden_id": uuid.uuid4().hex,
            "numero": 2,
            "agente": "agente",
            "motivo": "Todavía no.",
        }
        antes = len(_mensajes(registro, agente))
        assert g.procesar(rechazo)["ok"]
        assert _girar(
            g,
            srv,
            lambda: (
                "Washington rechazó la orden 2 para agente. Motivo: Todavía no."
                in _mensajes(registro, orq)
            ),
        )
        assert len(_mensajes(registro, agente)) == antes
    finally:
        g.detener_todo()


def test_destino_fuera_del_proyecto(tmp_path: Path) -> None:
    g, srv, registro, enc = _listo(tmp_path)
    orq, agente = _sids(enc)
    try:
        n = len(srv.de("/api/v1/maquinas/ordenes"))
        # El orquestador apunta a sí mismo y a una sesión que no es de su equipo.
        g.procesar(
            _mensaje(
                'di: <orden agente="orquestador">hazlo tú</orden>'
                '<orden agente="otro-proyecto-agente">x</orden>'
            )
        )
        assert _girar(
            g,
            srv,
            lambda: sum("no es un agente de código" in t for t in _mensajes(registro, orq)) == 2,
        )
        time.sleep(0.3)
        g.atender()
        g.vaciar_salida(srv)  # type: ignore[arg-type]
        assert len(srv.de("/api/v1/maquinas/ordenes")) == n
        assert len(_mensajes(registro, agente)) == 1
        # Una orden aprobada para un destino ajeno tampoco se encola.
        for malo in (
            _orden("x", agente="orquestador"),
            _orden("x", agente="agente-9"),
            _orden("x", proyecto_id="b" * 32),
            _orden("", agente="agente"),
        ):
            assert not g.procesar(malo)["ok"]
        assert not any(g.proyectos[PID].colas.get(x) for x in ("agente", "agente-9"))
        # Si el servidor rechaza una orden propuesta, el orquestador se entera.
        srv.estado = 422
        g.procesar(_mensaje('di: <orden agente="agente">y</orden>'))
        assert _girar(
            g,
            srv,
            lambda: any("no se registró en el servidor" in t for t in _mensajes(registro, orq)),
        )
    finally:
        g.detener_todo()


def test_orden_en_cola_si_el_agente_esta_ocupado(tmp_path: Path) -> None:
    g, srv, registro, enc = _listo(tmp_path, env={"FALSO_DEMORA": "1.0"})
    _, agente = _sids(enc)
    try:
        g.procesar(_orden("primera", numero=1))
        g.procesar(_orden("segunda", numero=2))
        g.atender()
        assert [m.split("\n\n")[-1] for m in _mensajes(registro, agente)[1:]] == ["primera"]
        assert [i["texto"] for i in g.proyectos[PID].colas["agente"]] == ["segunda"]
        time.sleep(0.4)
        g.atender()
        assert len(_mensajes(registro, agente)) == 2  # sigue ocupado: la segunda espera
        assert _girar(g, srv, lambda: len(_mensajes(registro, agente)) == 3)
        eventos = [e for e in _eventos(registro) if e.get("sid") == agente]
        fin_primera = next(
            e["t"] for e in eventos if e["evento"] == "respuesta" and e["t"] > eventos[1]["t"]
        )
        llega_segunda = [e for e in eventos if e["evento"] == "mensaje"][2]["t"]
        assert llega_segunda >= fin_primera
    finally:
        g.detener_todo()


def test_orden_que_falla(tmp_path: Path) -> None:
    g, srv, _, _ = _listo(tmp_path)
    try:
        oid = uuid.uuid4().hex
        g.procesar(_orden("esto FALLA", orden_id=oid))
        ruta = f"/api/v1/maquinas/ordenes/{oid}"
        assert _girar(g, srv, lambda: any(d["estado"] == "fallida" for d in srv.de(ruta)))
    finally:
        g.detener_todo()


def test_reinicio_a_la_mitad_no_pierde_ordenes(tmp_path: Path) -> None:
    """Una orden en curso y otra en cola cuando el monitor se cae: al volver, la que
    estaba en curso se informa fallida (pudo quedar a medias) y la de la cola llega."""
    g, srv, registro, enc = _listo(tmp_path, env={"FALSO_DEMORA": "3.0"})
    orq, agente = _sids(enc)
    en_curso, en_cola = uuid.uuid4().hex, uuid.uuid4().hex
    g.procesar(_orden("larga", numero=1, orden_id=en_curso))
    g.procesar(_orden("después", numero=2, orden_id=en_cola))
    g.atender()
    assert g.proyectos[PID].en_curso["agente"]["orden_id"] == en_curso
    # Lo que falta mandar tampoco se pierde sin conexión.
    srv.caido = True
    g.vaciar_salida(srv)  # type: ignore[arg-type]
    assert g.salida
    # El monitor se cae de golpe: sus procesos mueren (solo los suyos).
    ajeno = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        for s in g.sesiones.values():
            s.proceso.kill()
            s.proceso.wait(5)
        guardado = json.loads((tmp_path / "monitor" / "equipos.json").read_text(encoding="utf-8"))
        assert guardado["proyectos"][PID]["colas"]["agente"][0]["orden_id"] == en_cola
        g2 = _gestor(tmp_path, registro, env={"FALSO_DEMORA": "0"})
        assert g2.retomar() == 1
        srv.caido = False
        try:
            ruta = f"/api/v1/maquinas/ordenes/{en_curso}"
            assert _girar(g2, srv, lambda: any(d["estado"] == "fallida" for d in srv.de(ruta)))
            assert "monitor se reinició" in srv.de(ruta)[-1]["resumen"]
            ruta2 = f"/api/v1/maquinas/ordenes/{en_cola}"
            assert _girar(g2, srv, lambda: any(d["estado"] == "terminada" for d in srv.de(ruta2)))
            assert _mensajes(registro, agente)[-1].endswith("después")
            assert _girar(
                g2, srv, lambda: any("se interrumpió" in t for t in _mensajes(registro, orq))
            )
            assert ajeno.poll() is None
        finally:
            g2.detener_todo()
    finally:
        ajeno.kill()


def test_pausar_detener_y_reanudar_conservan_la_cola(tmp_path: Path) -> None:
    g, srv, registro, enc = _listo(tmp_path)
    orq, agente = _sids(enc)
    try:
        r = g.procesar(_encargo("detener", proyecto_id=PID))
        assert r["ok"] and {m["estado"] for m in r["miembros"]} == {"detenido"}
        assert (tmp_path / "Agents" / "prueba-38" / "PROJECT.md").is_file()
        # Con el equipo detenido, lo aprobado y los mensajes esperan.
        g.procesar(_orden("al volver"))
        g.procesar(_mensaje("¿Sigues ahí?"))
        g.atender()
        assert g.proyectos[PID].colas["agente"] and g.proyectos[PID].colas["orquestador"]
        r = g.procesar(_encargo("reanudar", proyecto_id=PID))
        assert r["ok"] and {m["estado"] for m in r["miembros"]} == {"activo"}
        assert _girar(g, srv, lambda: _mensajes(registro, agente)[-1].endswith("al volver"))
        assert _girar(g, srv, lambda: "¿Sigues ahí?" in _mensajes(registro, orq))
        assert g.procesar(_encargo("pausar", proyecto_id=PID))["miembros"][0]["estado"] == "pausado"
    finally:
        g.detener_todo()


def test_agregar_agente(tmp_path: Path) -> None:
    g, srv, registro, enc = _listo(tmp_path)
    orq, _ = _sids(enc)
    try:
        equipo = [
            *enc["equipo"],
            {
                "rol": "agente",
                "nombre": "agente-2",
                "modelo": "haiku",
                "esfuerzo": "low",
                "session_id": str(uuid.uuid4()),
            },
        ]
        r = g.procesar({**_encargo("agregar", proyecto_id=PID), "equipo": equipo})
        assert r["ok"] and [m["nombre"] for m in r["miembros"]][-1] == "agente-2"
        inicio = [e for e in _eventos(registro) if e["evento"] == "inicio"][-1]
        assert inicio["args"][inicio["args"].index("--session-id") + 1] == equipo[-1]["session_id"]
        assert _girar(g, srv, lambda: any("agente-2" in t for t in _mensajes(registro, orq)))
        # Solo se lanzó el nuevo; repetir el encargo no lanza nada.
        assert len([e for e in _eventos(registro) if e["evento"] == "inicio"]) == 3
        assert g.procesar({**_encargo("agregar", proyecto_id=PID), "equipo": equipo})["ok"]
        assert len([e for e in _eventos(registro) if e["evento"] == "inicio"]) == 3
        # Ya recibe órdenes.
        oid = uuid.uuid4().hex
        g.procesar(_orden("para el nuevo", agente="agente-2", orden_id=oid))
        ruta = f"/api/v1/maquinas/ordenes/{oid}"
        assert _girar(g, srv, lambda: any(d["estado"] == "terminada" for d in srv.de(ruta)))
    finally:
        g.detener_todo()


def test_citas_y_relleno_no_son_ordenes() -> None:
    cita = 'No veo el formato `<orden agente="agente">x</orden>` en mis instrucciones.'
    assert extraer_ordenes(cita) == ([], cita)
    [o], limpio = extraer_ordenes('<orden agente="agente" estimado="...">...</orden>')
    assert o["texto"] == "" and limpio == ""
    [o], limpio = extraer_ordenes('Va:\n```\n<orden agente="agente">Crea `hola.txt`</orden>\n```')
    assert o["texto"] == "Crea `hola.txt`" and limpio == "Va:"


def test_rol_actualizado_al_retomar(tmp_path: Path) -> None:
    """Claude Code ignora un --append-system-prompt nuevo al usar --resume: una sesión
    que nació con otro rol (o con un monitor anterior, sin huella) recibe una vez el
    rol nuevo como primer mensaje al retomarla."""
    g, srv, registro, enc = _listo(tmp_path)
    orq, agente = _sids(enc)
    g.detener_todo()
    # Como si vinieran de la 0.4.0: sin huella de rol.
    datos = json.loads((tmp_path / "monitor" / "equipos.json").read_text(encoding="utf-8"))
    for m in datos["proyectos"][PID]["miembros"]:
        m.pop("rol_huella", None)
    (tmp_path / "monitor" / "equipos.json").write_text(json.dumps(datos), encoding="utf-8")
    g2 = _gestor(tmp_path, registro)
    try:
        assert g2.retomar() == 1
        assert _girar(
            g2,
            srv,
            lambda: (
                any(
                    t.startswith("Actualización de tus instrucciones")
                    for t in _mensajes(registro, orq)
                )
                and any(
                    t.startswith("Actualización de tus instrucciones")
                    for t in _mensajes(registro, agente)
                )
            ),
        )
        rol = [t for t in _mensajes(registro, orq) if t.startswith("Actualización")][0]
        assert '<orden agente="NOMBRE"' in rol and "agente" in rol
    finally:
        g2.detener_todo()
    # Un tercer arranque con el mismo rol ya no lo repite.
    g3 = _gestor(tmp_path, registro)
    try:
        antes = len(_mensajes(registro, orq))
        assert g3.retomar() == 1
        time.sleep(0.5)
        g3.atender()
        time.sleep(0.3)
        assert len(_mensajes(registro, orq)) == antes
    finally:
        g3.detener_todo()
