"""Chat con el orquestador y órdenes a los agentes de código (etapa 4, Prompt 38)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core import acceso as acceso_mod
from app.core.acceso import Acceso
from app.core.agent_state_engine import AgentStateEngine, Thresholds, override_state_engine
from app.core.proyectos_equipo import ProyectoError, ProyectosEquipo, set_proyectos_equipo

T0 = datetime(2026, 10, 12, 15, 0, tzinfo=UTC)
ORQ = {"modelo": "haiku", "esfuerzo": "low"}
AGENTE = {"modelo": "haiku", "esfuerzo": "low"}
ACTIVOS = [
    {"nombre": "orquestador", "estado": "activo"},
    {"nombre": "agente", "estado": "activo"},
]


def _activo(r: ProyectosEquipo, nombre: str = "prueba-38", maquina: str = "alienware") -> str:
    p = r.crear(nombre, maquina, "personal", "vacia", ORQ, [AGENTE], False, "E:\\Agents")
    [enc] = r.encargos_pendientes(maquina)
    r.informar_encargo(maquina, enc["id"], True, None, None, ACTIVOS)
    return p["id"]


def test_chat_ida_y_vuelta(tmp_path: Path) -> None:
    reloj = [T0]
    r = ProyectosEquipo(tmp_path, clock=lambda: reloj[0])
    pid = _activo(r)
    m = r.escribir(pid, "  Hola, ¿qué propones?  ")
    assert m["autor"] == "washington" and m["texto"] == "Hola, ¿qué propones?"
    [enc] = r.encargos_pendientes("alienware")
    assert enc["tipo"] == "mensaje" and enc["texto"] == "Hola, ¿qué propones?"
    assert enc["mensaje_id"] == m["id"] and enc["proyecto_id"] == pid
    reloj[0] = T0 + timedelta(seconds=5)
    # La respuesta del orquestador: repetirla (reintento del monitor) no la duplica.
    assert not r.respuesta_orquestador("alienware", pid, "resp-0001", "Propongo X.")["repetido"]
    assert r.respuesta_orquestador("alienware", pid, "resp-0001", "Propongo X.")["repetido"]
    # Otra máquina no puede escribir en el chat de este proyecto.
    with pytest.raises(ProyectoError) as e:
        r.respuesta_orquestador("torre", pid, "resp-0002", "intruso")
    assert e.value.status == 404
    assert [(x["autor"], x["texto"]) for x in r.mensajes(pid)] == [
        ("washington", "Hola, ¿qué propones?"),
        ("orquestador", "Propongo X."),
    ]
    with pytest.raises(ProyectoError):
        r.escribir(pid, "   ")


def test_sin_equipo_no_hay_chat(tmp_path: Path) -> None:
    r = ProyectosEquipo(tmp_path, clock=lambda: T0)
    p = r.crear("nuevo", "alienware", "personal", "vacia", ORQ, [AGENTE], False, "E:\\Agents")
    with pytest.raises(ProyectoError) as e:
        r.escribir(p["id"], "hola")
    assert e.value.status == 409


def test_orden_aprobada_con_cambios_y_su_avance(tmp_path: Path) -> None:
    reloj = [T0]
    r = ProyectosEquipo(tmp_path, clock=lambda: reloj[0])
    pid = _activo(r)
    o = r.proponer_orden(
        "alienware", pid, "orden-0001", "agente", "Crea hola.txt con: Hola", "2 min", "baja"
    )
    assert o["estado"] == "por_aprobar" and o["numero"] == 1 and o["proyecto"] == "prueba-38"
    assert o["estimado"] == "2 min" and o["dificultad"] == "baja" and not o["editada"]
    # Nada sale para el monitor mientras no se apruebe.
    assert r.encargos_pendientes("alienware") == []
    # El reintento del monitor devuelve la misma orden.
    assert r.proponer_orden("alienware", pid, "orden-0001", "agente", "x")["id"] == o["id"]
    assert r.por_aprobar() == {pid: 1}
    # El monitor no puede aprobarla ni ponerla en curso.
    with pytest.raises(ProyectoError) as e:
        r.informar_orden("alienware", o["id"], "en_curso", None)
    assert e.value.status == 409
    with pytest.raises(ProyectoError):
        r.informar_orden("alienware", o["id"], "aprobada", None)
    reloj[0] = T0 + timedelta(minutes=1)
    v = r.aprobar(o["id"], "Crea hola.txt con: Prueba 38", "web")
    assert (
        v["estado"] == "aprobada" and v["editada"] and v["texto"] == "Crea hola.txt con: Prueba 38"
    )
    assert v["texto_propuesto"] == "Crea hola.txt con: Hola"
    assert v["decidido_por"] == "web" and v["decidido"] == (T0 + timedelta(minutes=1)).isoformat()
    with pytest.raises(ProyectoError) as e:
        r.aprobar(o["id"], None, "web")
    assert e.value.status == 409
    [enc] = r.encargos_pendientes("alienware")
    assert enc["tipo"] == "orden" and enc["orden_id"] == o["id"] and enc["agente"] == "agente"
    assert enc["texto"] == "Crea hola.txt con: Prueba 38" and enc["numero"] == 1
    assert enc["editada"] is True
    # Avance: en curso y terminada con su resumen (repetir no falla).
    assert r.informar_orden("alienware", o["id"], "en_curso", None) == {"estado": "en_curso"}
    assert r.informar_orden("alienware", o["id"], "en_curso", None) == {"estado": "en_curso"}
    with pytest.raises(ProyectoError):
        r.informar_orden("torre", o["id"], "terminada", "x")
    r.informar_orden("alienware", o["id"], "terminada", "Creé hola.txt.")
    final = r.orden(o["id"])
    assert final is not None and final["estado"] == "terminada"
    assert final["resumen"] == "Creé hola.txt."
    with pytest.raises(ProyectoError):
        r.informar_orden("alienware", o["id"], "fallida", "x")
    assert r.por_aprobar() == {}


def test_aprobar_sin_cambios_y_texto_igual(tmp_path: Path) -> None:
    r = ProyectosEquipo(tmp_path, clock=lambda: T0)
    pid = _activo(r)
    a = r.proponer_orden("alienware", pid, "orden-0001", "agente", "Haz A")
    b = r.proponer_orden("alienware", pid, "orden-0002", "agente", "Haz B")
    assert b["numero"] == 2
    assert not r.aprobar(a["id"], None, "app")["editada"]
    # El mismo texto no cuenta como editado; uno vacío no se acepta.
    with pytest.raises(ProyectoError):
        r.aprobar(b["id"], "   ", "web")
    assert not r.aprobar(b["id"], "Haz B", "web")["editada"]


def test_rechazo_con_motivo(tmp_path: Path) -> None:
    r = ProyectosEquipo(tmp_path, clock=lambda: T0)
    pid = _activo(r)
    o = r.proponer_orden("alienware", pid, "orden-0001", "agente", "Borra todo")
    with pytest.raises(ProyectoError):
        r.rechazar(o["id"], "  ", "web")
    v = r.rechazar(o["id"], "Es demasiado riesgo.", "web")
    assert v["estado"] == "rechazada" and v["motivo"] == "Es demasiado riesgo."
    [enc] = r.encargos_pendientes("alienware")
    assert enc["tipo"] == "rechazo" and enc["motivo"] == "Es demasiado riesgo."
    assert enc["numero"] == 1 and enc["orden_id"] == o["id"]
    # Una orden rechazada nunca pasa a en curso.
    with pytest.raises(ProyectoError):
        r.informar_orden("alienware", o["id"], "en_curso", None)


def test_destino_fuera_del_proyecto(tmp_path: Path) -> None:
    r = ProyectosEquipo(tmp_path, clock=lambda: T0)
    pid = _activo(r)
    otro = _activo(r, "otro")
    for agente in ("orquestador", "agente-9", "otro-agente"):
        with pytest.raises(ProyectoError) as e:
            r.proponer_orden("alienware", pid, f"orden-{agente}", agente, "x")
        assert e.value.status == 422
    # Una máquina no propone órdenes en proyectos de otra.
    with pytest.raises(ProyectoError) as e:
        r.proponer_orden("torre", otro, "orden-torre1", "agente", "x")
    assert e.value.status == 404
    assert r.ordenes() == []


def test_aprobacion_automatica(tmp_path: Path) -> None:
    r = ProyectosEquipo(tmp_path, clock=lambda: T0)
    pid = _activo(r)
    previa = r.proponer_orden("alienware", pid, "orden-0001", "agente", "Antes")
    assert r.auto_aprobar(pid, True)["auto_aprobar"] is True
    o = r.proponer_orden("alienware", pid, "orden-0002", "agente", "Sola")
    assert o["estado"] == "aprobada" and o["decidido_por"] == "automatico"
    [enc] = r.encargos_pendientes("alienware")
    assert enc["tipo"] == "orden" and enc["orden_id"] == o["id"] and enc["editada"] is False
    # La que ya esperaba sigue esperando a Washington.
    assert r.orden(previa["id"])["estado"] == "por_aprobar"  # type: ignore[index]
    r.auto_aprobar(pid, False)
    assert r.proponer_orden("alienware", pid, "orden-0003", "agente", "x")["estado"] == (
        "por_aprobar"
    )


def test_orden_que_el_monitor_no_pudo_encolar(tmp_path: Path) -> None:
    r = ProyectosEquipo(tmp_path, clock=lambda: T0)
    pid = _activo(r)
    o = r.proponer_orden("alienware", pid, "orden-0001", "agente", "x")
    r.aprobar(o["id"], None, "web")
    [enc] = r.encargos_pendientes("alienware")
    r.informar_encargo(
        "alienware", enc["id"], False, "Ese agente no es de este proyecto.", None, []
    )
    v = r.orden(o["id"])
    assert v is not None and v["estado"] == "fallida" and "agente" in (v["motivo"] or "")
    assert r.proyecto(pid)["estado"] == "activo"  # type: ignore[index]


def test_detener_y_reanudar(tmp_path: Path) -> None:
    r = ProyectosEquipo(tmp_path, clock=lambda: T0)
    pid = _activo(r)
    assert r.detener(pid)["estado"] == "deteniendo"
    with pytest.raises(ProyectoError):
        r.detener(pid)
    [enc] = r.encargos_pendientes("alienware")
    assert enc["tipo"] == "detener"
    detenidos = [{"nombre": m["nombre"], "estado": "detenido"} for m in ACTIVOS]
    r.informar_encargo("alienware", enc["id"], True, None, None, detenidos)
    p = r.proyecto(pid)
    assert p is not None and p["estado"] == "detenido"
    assert {m["estado"] for m in p["equipo"]} == {"detenido"}
    # Con el equipo detenido se puede escribir (el monitor lo guarda) y reanudar.
    r.escribir(pid, "Para cuando vuelvas")
    assert r.reanudar(pid)["estado"] == "reanudando"
    tipos = [e["tipo"] for e in r.encargos_pendientes("alienware")]
    assert tipos == ["mensaje", "reanudar"]
    # Un proyecto que no llegó a crearse no se detiene.
    q = r.crear("roto", "alienware", "personal", "vacia", ORQ, [AGENTE], False, "E:\\Agents")
    [enc] = r.encargos_pendientes("alienware")
    r.informar_encargo("alienware", enc["id"], False, "Ya existe", None, [])
    with pytest.raises(ProyectoError) as e:
        r.detener(q["id"])
    assert e.value.status == 409


def test_agregar_agente(tmp_path: Path) -> None:
    r = ProyectosEquipo(tmp_path, clock=lambda: T0)
    pid = _activo(r)
    p = r.agregar_agente(pid, "sonnet", "medium")
    nuevo = p["equipo"][-1]
    assert (nuevo["rol"], nuevo["nombre"], nuevo["estado"]) == ("agente", "agente-2", "pendiente")
    assert len(nuevo["session_id"]) == 36
    [enc] = r.encargos_pendientes("alienware")
    assert enc["tipo"] == "agregar" and enc["miembro"] == "agente-2"
    assert [m["nombre"] for m in enc["equipo"]] == ["orquestador", "agente", "agente-2"]
    # Ya es destino válido de órdenes.
    assert r.proponer_orden("alienware", pid, "orden-0001", "agente-2", "x")["agente"] == "agente-2"
    r.agregar_agente(pid, "sonnet", "medium")
    r.agregar_agente(pid, "sonnet", "medium")
    with pytest.raises(ProyectoError) as e:
        r.agregar_agente(pid, "sonnet", "medium")
    assert e.value.status == 409
    nombres = [m["nombre"] for m in r.proyecto(pid)["equipo"]]  # type: ignore[index]
    assert nombres == ["orquestador", "agente", "agente-2", "agente-3", "agente-4"]
    with pytest.raises(ProyectoError):
        r.agregar_agente(pid, "sonnet", "nada")


def test_migra_desde_la_version_1(tmp_path: Path) -> None:
    """Una base del Prompt 37 sube al esquema 2 sin perder los proyectos."""
    from app.core.proyectos_equipo import _MIGRACIONES  # pyright: ignore[reportPrivateUsage]

    db = sqlite3.connect(tmp_path / "proyectos.db")
    for sql in _MIGRACIONES[1]:
        db.execute(sql)
    db.execute(
        """INSERT INTO proyectos (id, nombre, maquina, cuenta, ruta, plantilla, estado,
            auto_aprobar, creado, actualizado) VALUES ('p1','viejo','alienware','personal',
            'E:\\Agents\\viejo','vacia','activo',0,'2026-10-12','2026-10-12')"""
    )
    db.execute("PRAGMA user_version = 1")
    db.commit()
    db.close()
    r = ProyectosEquipo(tmp_path, clock=lambda: T0)
    assert r.version() == 3
    assert r.proyecto("p1")["nombre"] == "viejo"  # type: ignore[index]
    assert r.ordenes("p1") == [] and r.mensajes("p1") == []


# -- rutas -------------------------------------------------------------------------------


@pytest.fixture
def cliente(tmp_path: Path) -> Iterator[tuple[TestClient, ProyectosEquipo]]:
    from app.main import app

    acc = Acceso(tmp_path / "acceso.db", secreto="s", clock=lambda: T0)
    acc.registrar_maquina("alienware", "Alienware", "windows")
    acceso_mod.set_acceso(acc)
    reg = ProyectosEquipo(tmp_path, clock=lambda: T0)
    set_proyectos_equipo(reg)
    override_state_engine(AgentStateEngine(Thresholds(), clock=lambda: T0 + timedelta(seconds=30)))
    try:
        yield TestClient(app), reg
    finally:
        acceso_mod.set_acceso(None)
        set_proyectos_equipo(None)
        override_state_engine(None)


def test_rutas_de_chat_y_ordenes(cliente: tuple[TestClient, ProyectosEquipo]) -> None:
    c, reg = cliente
    pid = _activo(reg)
    api = "/api/v1"
    r = c.post(f"{api}/proyectos-creados/{pid}/chat", json={"texto": "Hola"})
    assert r.status_code == 201 and r.json()["autor"] == "washington"
    assert c.post(f"{api}/proyectos-creados/{pid}/chat", json={"texto": ""}).status_code == 422
    [enc] = c.get(f"{api}/maquinas/encargos").json()["encargos"]
    assert enc["tipo"] == "mensaje"
    assert c.post(f"{api}/maquinas/encargos/{enc['id']}", json={"ok": True}).status_code == 200
    r = c.post(
        f"{api}/maquinas/chat",
        json={"proyecto_id": pid, "origen_id": "resp-0001", "texto": "Te propongo una orden."},
    )
    assert r.status_code == 200
    r = c.post(
        f"{api}/maquinas/ordenes",
        json={
            "proyecto_id": pid,
            "origen_id": "orden-0001",
            "agente": "agente",
            "texto": "Crea hola.txt",
            "estimado": "1 min",
        },
    )
    assert r.json()["estado"] == "por_aprobar"
    oid = r.json()["id"]
    malo = {"proyecto_id": pid, "origen_id": "orden-0002", "agente": "orquestador", "texto": "x"}
    assert c.post(f"{api}/maquinas/ordenes", json=malo).status_code == 422
    chat = c.get(f"{api}/proyectos-creados/{pid}/chat").json()
    assert [m["autor"] for m in chat["mensajes"]] == ["washington", "orquestador"]
    assert [o["id"] for o in chat["ordenes"]] == [oid]
    assert c.get(f"{api}/proyectos-creados/{pid}").json()["ordenes_por_aprobar"] == 1
    # Decisiones: la orden primero, en el conteo y en el contador de la oficina.
    d = c.get(f"{api}/decisiones").json()
    assert d["pendientes"][0]["tipo"] == "orden" and d["pendientes"][0]["id"] == oid
    assert d["pendientes"][0]["orden"]["agente"] == "agente"
    assert d["pendientes"][0]["session_id"]
    assert d["conteo"]["orden"] == 1 and d["conteo"]["total"] == 1
    assert c.get(f"{api}/agents/state").json()["decisiones_pendientes"] == 1
    assert [o["id"] for o in c.get(f"{api}/ordenes?estado=por_aprobar").json()["ordenes"]] == [oid]
    assert c.get(f"{api}/ordenes?estado=otra").status_code == 422
    # Aprobar con cambios.
    r = c.post(f"{api}/ordenes/{oid}/aprobar", json={"texto": "Crea hola.txt: Prueba 38"})
    assert r.json()["estado"] == "aprobada" and r.json()["editada"]
    assert c.post(f"{api}/ordenes/{oid}/rechazar", json={"motivo": "x"}).status_code == 409
    assert c.get(f"{api}/decisiones").json()["conteo"]["orden"] == 0
    [enc] = c.get(f"{api}/maquinas/encargos").json()["encargos"]
    assert enc["tipo"] == "orden" and enc["texto"] == "Crea hola.txt: Prueba 38"
    r = c.post(f"{api}/maquinas/ordenes/{oid}", json={"estado": "terminada", "resumen": "Listo."})
    assert r.json() == {"estado": "terminada"}
    assert c.post(f"{api}/maquinas/ordenes/{oid}", json={"estado": "aprobada"}).status_code == 422
    # Rechazo, interruptor, agregar y detener.
    otra = c.post(
        f"{api}/maquinas/ordenes",
        json={"proyecto_id": pid, "origen_id": "orden-0003", "agente": "agente", "texto": "y"},
    ).json()["id"]
    assert c.post(f"{api}/ordenes/{otra}/rechazar", json={"motivo": ""}).status_code == 422
    r = c.post(f"{api}/ordenes/{otra}/rechazar", json={"motivo": "No ahora", "dispositivo": "app"})
    assert r.json()["estado"] == "rechazada" and r.json()["decidido_por"] == "app"
    r = c.post(f"{api}/proyectos-creados/{pid}/auto-aprobar", json={"activo": True})
    assert r.json()["auto_aprobar"] is True
    r = c.post(
        f"{api}/proyectos-creados/{pid}/agentes", json={"modelo": "haiku", "esfuerzo": "low"}
    )
    assert r.status_code == 201 and r.json()["equipo"][-1]["nombre"] == "agente-2"
    assert c.post(f"{api}/proyectos-creados/{pid}/detener").json()["estado"] == "deteniendo"
    assert c.post(f"{api}/proyectos-creados/nada/detener").status_code == 404
    assert c.get(f"{api}/proyectos-creados/nada/chat").status_code == 404


def test_las_rutas_nuevas_de_maquina_son_de_ingesta() -> None:
    from app.api.acceso_middleware import es_ingesta

    assert es_ingesta("POST", "/api/v1/maquinas/chat")
    assert es_ingesta("POST", "/api/v1/maquinas/ordenes")
    assert es_ingesta("POST", "/api/v1/maquinas/ordenes/abc123")
    # Aprobar o rechazar nunca con token de máquina.
    assert not es_ingesta("POST", "/api/v1/ordenes/abc123/aprobar")
    assert not es_ingesta("POST", "/api/v1/ordenes/abc123/rechazar")
    assert not es_ingesta("POST", "/api/v1/proyectos-creados/abc/auto-aprobar")
    assert not es_ingesta("POST", "/api/v1/maquinas/ordenes/abc/aprobar")
