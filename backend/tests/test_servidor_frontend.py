"""Static server of the daily copy (app.servidor_frontend)."""

from pathlib import Path

from starlette.testclient import TestClient

from app.servidor_frontend import cliente_permitido, crear_app, resolver


def _export(tmp_path: Path) -> Path:
    out = tmp_path / "out"
    (out / "oficina").mkdir(parents=True)
    (out / "_next" / "static" / "chunks").mkdir(parents=True)
    (out / "index.html").write_text("inicio", encoding="utf-8")
    (out / "oficina.html").write_text("cajas", encoding="utf-8")
    (out / "oficina" / "3d.html").write_text("tres", encoding="utf-8")
    (out / "404.html").write_text("no hay", encoding="utf-8")
    (out / "_next" / "static" / "chunks" / "a.js").write_text("x=1", encoding="utf-8")
    (tmp_path / "secreto.txt").write_text("no", encoding="utf-8")
    return out


def test_clean_urls_map_to_exported_files(tmp_path: Path) -> None:
    out = _export(tmp_path)
    assert resolver(out, "/") == (out / "index.html").resolve()
    assert resolver(out, "/oficina") == (out / "oficina.html").resolve()
    assert resolver(out, "/oficina/") == (out / "oficina.html").resolve()
    assert resolver(out, "/oficina/3d") == (out / "oficina" / "3d.html").resolve()
    assert resolver(out, "/no-existe") is None


def test_never_leaves_the_export_folder(tmp_path: Path) -> None:
    out = _export(tmp_path)
    assert resolver(out, "/../secreto.txt") is None
    assert resolver(out, "/..%2Fsecreto.txt") is None


def test_serves_pages_assets_and_404(tmp_path: Path) -> None:
    client = TestClient(crear_app(_export(tmp_path)))
    r = client.get("/oficina/3d")
    assert r.status_code == 200 and r.text == "tres"
    assert r.headers["cache-control"] == "no-cache"
    js = client.get("/_next/static/chunks/a.js")
    assert js.headers["content-type"].startswith("text/javascript")
    assert "immutable" in js.headers["cache-control"]
    falta = client.get("/nada")
    assert falta.status_code == 404 and falta.text == "no hay"


def test_only_loopback_and_tailscale_clients() -> None:
    assert cliente_permitido("127.0.0.1")
    assert cliente_permitido("::1")
    assert cliente_permitido("<TAILSCALE_IP>")
    assert not cliente_permitido("192.168.1.20")
    assert not cliente_permitido(None)


def test_next_segment_data_files(tmp_path: Path) -> None:
    out = _export(tmp_path)
    (out / "oficina" / "__next.oficina").mkdir()
    (out / "oficina" / "__next.oficina" / "__PAGE__.txt").write_text("rsc", encoding="utf-8")
    (out / "oficina" / "3d" / "__next.oficina" / "3d").mkdir(parents=True)
    (out / "oficina" / "3d" / "__next.oficina" / "3d" / "__PAGE__.txt").write_text(
        "rsc3d", encoding="utf-8"
    )
    client = TestClient(crear_app(out))
    assert client.get("/oficina/__next.oficina.__PAGE__.txt?_rsc=x").text == "rsc"
    assert client.get("/oficina/3d/__next.oficina.3d.__PAGE__.txt").text == "rsc3d"
