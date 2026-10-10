"""GET/PUT /api/v1/oficina3d/distribucion: office layout of the 3D view."""

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import oficina3d
from app.config import get_settings

URL = "/api/v1/oficina3d/distribucion"


@pytest.fixture
def ruta(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    destino = tmp_path / "datos" / "distribucion.json"
    monkeypatch.setattr(get_settings(), "OFICINA3D_DISTRIBUCION_PATH", str(destino))
    return destino


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(oficina3d.router, prefix="/api/v1/oficina3d")
    return TestClient(app)


def mueble(i: str = "m1", **extra: object) -> dict[str, object]:
    return {"id": i, "type": "plant", "x": 1.5, "z": -2.0, "ry": 0.0, **extra}


def test_without_saved_file_returns_the_repository_base(client: TestClient, ruta: Path) -> None:
    r = client.get(URL)
    assert r.status_code == 200
    body = r.json()
    assert body["origen"] == "base"
    base = json.loads(oficina3d.BASE_REPO.read_text(encoding="utf-8"))
    assert body["distribucion"]["items"] == base["items"]
    assert not ruta.exists()


def test_put_saves_in_the_copy_data_folder_and_get_reads_it(client: TestClient, ruta: Path) -> None:
    d = {
        "version": 1,
        "items": [mueble("a"), mueble("b", type="sofa", x=-3.0, z=12.0, ry=1.5708)],
        "floorColor": "#c4cfd8",
        "wallColor": "#d4d9df",
        "tema": "fresco",
    }
    r = client.put(URL, json=d)
    assert r.status_code == 200, r.text
    assert ruta.exists()
    guardado = json.loads(ruta.read_text(encoding="utf-8"))
    assert [m["id"] for m in guardado["items"]] == ["a", "b"]
    leido = client.get(URL).json()
    assert leido["origen"] == "guardada"
    assert leido["distribucion"]["tema"] == "fresco"
    assert leido["distribucion"]["items"][1]["type"] == "sofa"


@pytest.mark.parametrize(
    "malo",
    [
        {"items": [mueble(type="nave-espacial")]},  # unknown furniture
        {"items": [mueble(x=30.0)]},  # outside the office
        {"items": [mueble(z=-16.5)]},
        {"items": [mueble(), mueble()]},  # repeated id
        {"items": [mueble(id="../x")]},
        {"floorColor": "javascript:alert(1)"},
        {"items": [], "extra": True},  # unknown field
        {"items": [mueble(ry=float("nan"))]},
    ],
)
def test_invalid_layouts_are_rejected_and_nothing_is_written(
    client: TestClient, ruta: Path, malo: dict[str, object]
) -> None:
    r = client.put(URL, content=json.dumps({"version": 1, **malo}, allow_nan=True))
    assert r.status_code == 422, r.text
    assert not ruta.exists()


def test_too_big_or_not_json(client: TestClient, ruta: Path) -> None:
    assert client.put(URL, content=b"{" + b" " * (oficina3d.MAX_BYTES + 1)).status_code == 413
    assert client.put(URL, content=b"no es json").status_code == 422
    muchos = {"items": [mueble(f"m{i}") for i in range(oficina3d.MAX_MUEBLES + 1)]}
    assert client.put(URL, json=muchos).status_code == 422
    assert not ruta.exists()


def test_corrupt_saved_file_falls_back_to_the_base(client: TestClient, ruta: Path) -> None:
    ruta.parent.mkdir(parents=True)
    ruta.write_text("{roto", encoding="utf-8")
    assert client.get(URL).json()["origen"] == "base"


def test_default_path_is_next_to_the_event_log(monkeypatch: pytest.MonkeyPatch) -> None:
    s = get_settings()
    monkeypatch.setattr(s, "OFICINA3D_DISTRIBUCION_PATH", "")
    monkeypatch.setattr(s, "STATE_EVENT_LOG_PATH", "C:/datos-diario/agent_events.db")
    assert oficina3d.ruta_distribucion() == Path("C:/datos-diario/distribucion.json")


def test_known_furniture_matches_the_frontend_catalog() -> None:
    catalogo = (
        oficina3d.BASE_REPO.parents[2]
        / "src"
        / "components"
        / "oficina3d"
        / "muebles.ts"
    ).read_text(encoding="utf-8")
    for tipo in oficina3d.TIPOS_MUEBLE:
        assert f'type: "{tipo}"' in catalogo
    assert catalogo.count('type: "') == len(oficina3d.TIPOS_MUEBLE)
