import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { bloqueos } from "@/components/oficina3d/caminos";
import {
  distribucionActual,
  leerDistribucion,
  useLayout,
  type PlacedItem,
} from "@/components/oficina3d/distribucion";
import { ajustar, useEditor } from "@/components/oficina3d/editor";
import { NODES } from "@/components/oficina3d/escena/nav";
import { seatFor, sitPoint } from "@/components/oficina3d/escena/roles";
import { MUEBLES } from "@/components/oficina3d/muebles";
import { TEMAS, temaPorClave } from "@/components/oficina3d/temas";
import { t } from "@/components/oficina3d/textos";

const planta = (
  id: string,
  x: number,
  z: number,
  type = "plant",
): PlacedItem => ({
  id,
  type,
  x,
  z,
  ry: 0,
});

function reiniciar() {
  useLayout.setState({
    items: [],
    floorColor: null,
    wallColor: null,
    tema: "claro",
    origen: null,
  });
  useEditor.setState({
    activo: false,
    paleta: null,
    seleccion: null,
    arrastrando: null,
    inicioArrastre: null,
    original: null,
    pasado: [],
    futuro: [],
    guardando: false,
    mensaje: null,
  });
}

describe("caminos de los agentes", () => {
  it("un mueble sobre un nodo del grafo tapa un camino", () => {
    const n = NODES.g2_1; // central grid node
    expect(bloqueos([planta("a", n.x, n.z)])).toEqual([
      { id: "a", motivo: "camino" },
    ]);
  });

  it("un mueble encima de un escritorio de trabajo o de su silla lo tapa", () => {
    const s = seatFor(0);
    expect(bloqueos([planta("e", s.x, s.z, "desk")])).toEqual([
      { id: "e", motivo: "escritorio" },
    ]);
    const p = sitPoint(s);
    expect(bloqueos([planta("s", p.x, p.z)])[0]?.motivo).toBe("escritorio");
  });

  it("la entrada y el pasillo del sofá también están protegidos", () => {
    expect(bloqueos([planta("p", -21.5, 4)])).toHaveLength(1);
    expect(bloqueos([planta("q", -0.75, 14.5)])).toHaveLength(1);
  });

  it("un rincón libre no tapa nada", () => {
    expect(
      bloqueos([planta("r", -21.5, -12.5), planta("t", 21.5, 6.5, "lamp")]),
    ).toEqual([]);
  });
});

describe("editor", () => {
  beforeEach(reiniciar);
  afterEach(() => vi.unstubAllGlobals());

  it("coloca en la cuadrícula de 0,5 m y dentro de la oficina", () => {
    expect(ajustar(1.26, 22.5)).toBe(1.5);
    expect(ajustar(40, 22.5)).toBe(22.5);
    const ed = useEditor.getState();
    ed.entrar();
    ed.elegirPaleta("plant");
    useEditor.getState().colocar(-21.3, -12.6);
    const [it] = useLayout.getState().items;
    expect(it).toMatchObject({ type: "plant", x: -21.5, z: -12.5, ry: 0 });
    expect(useEditor.getState().seleccion).toBe(it.id);
  });

  it("arrastrar deja un solo paso de historia; rotar va de 45 en 45 grados", () => {
    useLayout.setState({ items: [planta("a", -21.5, -12.5)] });
    const ed = useEditor.getState();
    ed.entrar();
    ed.empezarArrastre("a");
    useEditor.getState().arrastrar(-21, -12);
    useEditor.getState().arrastrar(-20.6, -11.4);
    useEditor.getState().terminarArrastre();
    expect(useLayout.getState().items[0]).toMatchObject({ x: -20.5, z: -11.5 });
    expect(useEditor.getState().pasado).toHaveLength(1);
    useEditor.getState().rotar("a");
    expect(useLayout.getState().items[0].ry).toBeCloseTo(Math.PI / 4);
    for (let i = 0; i < 7; i++) useEditor.getState().rotar("a");
    expect(useLayout.getState().items[0].ry).toBeCloseTo(0);
  });

  it("deshacer y rehacer; cancelar vuelve a lo que había al entrar", () => {
    useLayout.setState({ items: [planta("a", -21.5, -12.5)] });
    const ed = useEditor.getState();
    ed.entrar();
    ed.borrar("a");
    expect(useLayout.getState().items).toEqual([]);
    useEditor.getState().deshacer();
    expect(useLayout.getState().items.map((i) => i.id)).toEqual(["a"]);
    useEditor.getState().rehacer();
    expect(useLayout.getState().items).toEqual([]);
    useEditor.getState().aplicarTema("noche");
    expect(useLayout.getState()).toMatchObject({
      tema: "noche",
      floorColor: "#40454e",
    });
    useEditor.getState().cancelar();
    expect(useLayout.getState().items.map((i) => i.id)).toEqual(["a"]);
    expect(useLayout.getState().tema).toBe("claro");
    expect(useEditor.getState().activo).toBe(false);
  });

  it("no guarda mientras un mueble tapa un camino", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    const n = NODES.g2_1;
    useLayout.setState({ items: [planta("a", n.x, n.z)] });
    useEditor.getState().entrar();
    expect(await useEditor.getState().guardar()).toBe(false);
    expect(fetch).not.toHaveBeenCalled();
    expect(useEditor.getState().mensaje).toMatch(/tapan un camino/);
  });

  it("guarda con PUT en el backend y sale del modo edición", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue({ ok: true, json: async () => ({}) });
    vi.stubGlobal("fetch", fetch);
    useEditor.getState().entrar();
    useEditor.getState().aplicarTema("bosque");
    expect(await useEditor.getState().guardar()).toBe(true);
    const [url, init] = fetch.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/v1\/oficina3d\/distribucion$/);
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body)).toMatchObject({
      tema: "bosque",
      wallColor: "#ced4c3",
    });
    expect(useEditor.getState().activo).toBe(false);
    expect(useLayout.getState().origen).toBe("guardada");
  });

  it("importar una distribución la deja lista para guardar", () => {
    useEditor.getState().entrar();
    useEditor
      .getState()
      .importar(
        leerDistribucion({ items: [planta("x", -21.5, -12.5)], tema: "rosa" }),
      );
    expect(distribucionActual()).toMatchObject({
      tema: "rosa",
      items: [{ id: "x" }],
    });
    expect(useEditor.getState().pasado).toHaveLength(1);
  });
});

describe("distribución y temas", () => {
  it("descarta muebles desconocidos, fuera de la oficina o repetidos", () => {
    const d = leerDistribucion({
      items: [
        planta("1", 1, 2),
        planta("2", 30, 0),
        planta("1", 0, 0),
        { id: "3", type: "nave", x: 0, z: 0, ry: 0 },
        { id: "../4", type: "plant", x: 0, z: 0, ry: 0 },
      ],
      floorColor: "#d8c7a8",
      wallColor: "rojo",
      tema: "Fresco!",
    });
    expect(d.items.map((i) => i.id)).toEqual(["1"]);
    expect(d).toMatchObject({
      floorColor: "#d8c7a8",
      wallColor: null,
      tema: "claro",
    });
  });

  it("9 temas del original con nombre en español, más el claro actual por defecto", () => {
    expect(TEMAS).toHaveLength(10);
    expect(TEMAS[0]).toMatchObject({ key: "claro", floor: null, wall: null });
    expect(TEMAS.map((x) => x.nombre)).toContain("Océano");
    expect(temaPorClave("inexistente").key).toBe("claro");
    expect(TEMAS.every((x) => /^[a-z]+$/.test(x.key))).toBe(true);
  });

  it("el catálogo y los textos del editor están en español", () => {
    expect(MUEBLES.map((m) => m.label)).toEqual([
      "Planta",
      "Escritorio",
      "Sofá",
      "Mesa de centro",
      "Mesa de reuniones",
      "Librero",
      "Lámpara",
    ]);
    expect(t("barra.editar")).toBe("Editar oficina");
  });
});
