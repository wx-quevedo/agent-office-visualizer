from __future__ import annotations

import json
from pathlib import Path

from conftest import TOKEN, ServidorFalso, puerto_libre

from visualizador_monitor.cliente import Servidor
from visualizador_monitor.cola import Cola
from visualizador_monitor.reenvio import EstadoConexion, enviar_uno


def _vaciar(cola: Cola, srv: Servidor, estado: EstadoConexion) -> None:
    while enviar_uno(cola, srv, estado) is True:
        pass


def test_envia_en_orden_con_id_y_token(tmp_path: Path, servidor: ServidorFalso) -> None:
    cola = Cola(tmp_path / "c.db")
    ids = [cola.agregar("/api/v1/events", json.dumps({"n": i}).encode()) for i in range(3)]
    estado = EstadoConexion()
    _vaciar(cola, Servidor(servidor.url, TOKEN), estado)
    assert [e["n"] for e in servidor.eventos()] == [0, 1, 2]
    assert [p.cabeceras["X-Evento-Id"] for p in servidor.pedidos] == ids
    assert all(p.cabeceras["Authorization"] == f"Bearer {TOKEN}" for p in servidor.pedidos)
    assert cola.pendientes() == 0
    assert estado.conectado is True


def test_corte_encola_y_al_volver_manda_todo_sin_duplicados(tmp_path: Path) -> None:
    puerto = puerto_libre()
    cola = Cola(tmp_path / "c.db")
    estado = EstadoConexion()
    srv = Servidor(f"http://127.0.0.1:{puerto}", TOKEN)
    for i in range(4):
        cola.agregar("/api/v1/events", json.dumps({"n": i}).encode())
    assert enviar_uno(cola, srv, estado) is False  # servidor apagado
    assert estado.conectado is False
    assert cola.pendientes() == 4
    assert "sin conexión" in str(cola.resumen()["ultimo_error"])

    falso = ServidorFalso(puerto)
    falso.arrancar()
    try:
        cola.reintentar_ya()
        _vaciar(cola, srv, estado)
        assert [e["n"] for e in falso.eventos()] == [0, 1, 2, 3]
        assert cola.pendientes() == 0
        assert estado.conectado is True
    finally:
        falso.detener()


def test_reintento_del_mismo_id_el_servidor_lo_ignora(
    tmp_path: Path, servidor: ServidorFalso
) -> None:
    """Si la respuesta se pierde, el mismo envío vuelve con el mismo id."""
    cola = Cola(tmp_path / "c.db")
    eid = cola.agregar("/api/v1/events", b'{"n": 1}')
    srv = Servidor(servidor.url, TOKEN)
    srv.pedir("POST", "/api/v1/events", b'{"n": 1}', cabeceras={"X-Evento-Id": eid})
    _vaciar(cola, srv, EstadoConexion())
    assert len(servidor.ids_vistos) == 1
    assert cola.pendientes() == 0


def test_rechazo_definitivo_se_descarta(tmp_path: Path, servidor: ServidorFalso) -> None:
    servidor.respuestas["/api/v1/events"] = (422, {"detail": "inválido"})
    cola = Cola(tmp_path / "c.db")
    cola.agregar("/api/v1/events", b"{}")
    assert enviar_uno(cola, Servidor(servidor.url, TOKEN), EstadoConexion()) is True
    assert cola.pendientes() == 0
    assert "422" in str(cola.resumen()["ultimo_descarte"])


def test_token_rechazado_espera_y_no_pierde_nada(tmp_path: Path, servidor: ServidorFalso) -> None:
    cola = Cola(tmp_path / "c.db")
    cola.agregar("/api/v1/events", b"{}")
    estado = EstadoConexion()
    assert enviar_uno(cola, Servidor(servidor.url, "vam_otro_token_invalido"), estado) is False
    assert cola.pendientes() == 1
    assert cola.siguiente() is None  # 60 s de espera
    assert "token" in str(estado.ultimo_error)


def test_error_del_servidor_reintenta(tmp_path: Path, servidor: ServidorFalso) -> None:
    servidor.respuestas["/api/v1/events"] = (503, {"detail": "ocupado"})
    cola = Cola(tmp_path / "c.db")
    cola.agregar("/api/v1/events", b"{}")
    assert enviar_uno(cola, Servidor(servidor.url, TOKEN), EstadoConexion()) is False
    assert cola.pendientes() == 1


def test_no_sigue_redirecciones_ni_pierde_el_evento(
    tmp_path: Path, servidor: ServidorFalso
) -> None:
    """Una redirección no lleva el token a otro destino ni convierte el POST en GET."""
    otro = ServidorFalso(puerto_libre())
    otro.arrancar()
    try:
        servidor.respuestas["/api/v1/events"] = (302, {"Location": f"{otro.url}/api/v1/events"})
        cola = Cola(tmp_path / "c.db")
        cola.agregar("/api/v1/events", b"{}")
        assert enviar_uno(cola, Servidor(servidor.url, TOKEN), EstadoConexion()) is False
        assert cola.pendientes() == 1
        assert otro.pedidos == []
    finally:
        otro.detener()


def test_404_del_proxy_no_descarta(tmp_path: Path, servidor: ServidorFalso) -> None:
    servidor.respuestas["/api/v1/events"] = (404, {"detail": "Not Found"})
    cola = Cola(tmp_path / "c.db")
    cola.agregar("/api/v1/events", b"{}")
    assert enviar_uno(cola, Servidor(servidor.url, TOKEN), EstadoConexion()) is False
    assert cola.pendientes() == 1
