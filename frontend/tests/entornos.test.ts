import { afterEach, describe, expect, it } from "vitest";
import {
  adaptar,
  estadoInicial,
  ordenarFila,
} from "@/components/oficina3d/adaptador";
import {
  distribucionActual,
  leerDistribucion,
  useLayout,
  type PlacedItem,
} from "@/components/oficina3d/distribucion";
import {
  activarEntorno,
  ENTORNOS,
} from "@/components/oficina3d/entornos/activo";
import { ARCOS, CENTRO_PUENTE } from "@/components/oficina3d/entornos/puente";
import {
  rectPuesto,
  sitPoint,
  type Entorno,
  type Rect,
  type WP,
} from "@/components/oficina3d/entornos/tipos";
import { blockedStatic } from "@/components/oficina3d/escena/collision";
import {
  nearestNode,
  NODES,
  pathBetween,
} from "@/components/oficina3d/escena/nav";
import { seatFor } from "@/components/oficina3d/escena/roles";
import type { Agente } from "@/components/oficina/logica";

afterEach(() => {
  activarEntorno("original");
});

/** Corners of a desk plus its chair (local x ±0.75, z from -0.45 to +1.05), rotated. */
function esquinas(e: Entorno, i: number): WP[] {
  const p = e.puesto(i);
  const c = Math.cos(p.ry);
  const s = Math.sin(p.ry);
  return [
    [-0.75, -0.45],
    [0.75, -0.45],
    [0.75, 1.05],
    [-0.75, 1.05],
  ].map(([lx, lz]) => ({ x: p.x + lx * c + lz * s, z: p.z - lx * s + lz * c }));
}

/** Two convex polygons overlap (separating axis test). */
function poligonosSeTocan(a: WP[], b: WP[]): boolean {
  for (const pol of [a, b]) {
    for (let k = 0; k < pol.length; k++) {
      const p1 = pol[k];
      const p2 = pol[(k + 1) % pol.length];
      const eje = { x: -(p2.z - p1.z), z: p2.x - p1.x };
      const proy = (ps: WP[]) => ps.map((q) => q.x * eje.x + q.z * eje.z);
      const pa = proy(a);
      const pb = proy(b);
      if (
        Math.max(...pa) <= Math.min(...pb) ||
        Math.max(...pb) <= Math.min(...pa)
      )
        return false;
    }
  }
  return true;
}

function cajaDe(ps: WP[]): Rect {
  const xs = ps.map((q) => q.x);
  const zs = ps.map((q) => q.z);
  return {
    x0: Math.min(...xs),
    x1: Math.max(...xs),
    z0: Math.min(...zs),
    z1: Math.max(...zs),
  };
}

const rectComoPoligono = (r: Rect): WP[] => [
  { x: r.x0, z: r.z0 },
  { x: r.x1, z: r.z0 },
  { x: r.x1, z: r.z1 },
  { x: r.x0, z: r.z1 },
];

/** How many desks each environment must place without overlap. */
const CUPO: Record<string, number> = {
  original: 20,
  puente: 40,
  control: 40,
  // every fixed desk: 6 cabins, the general cabin and the extra desks
  cabinas: 103,
  // 17 islands and the extra desks
  estudio: 84,
};

describe("entorno Original sin cambios", () => {
  it("los 10 escritorios y el crecimiento en filas son los de antes", () => {
    activarEntorno("original");
    expect(seatFor(0)).toEqual({ x: -5.5, z: -3.2, ry: -Math.PI / 2 });
    expect(seatFor(9)).toEqual({ x: 13, z: 3, ry: Math.PI / 2 });
    expect(seatFor(12)).toEqual({ x: -4.4 + 2 * 2.2, z: -5.2, ry: Math.PI });
    expect(NODES.lounge_i).toBeDefined();
    expect(NODES.g2_1).toEqual({ x: 0, z: -1.8 });
  });
});

describe.each(ENTORNOS.map((e) => [e.clave, e] as const))(
  "entorno %s",
  (clave, e) => {
    it("los escritorios no se superponen ni tocan tu puesto, el mostrador o el descanso", () => {
      activarEntorno(clave);
      const n = CUPO[clave];
      const poligonos = Array.from({ length: n }, (_, i) => esquinas(e, i));
      for (let i = 0; i < n; i++) {
        for (let j = i + 1; j < n; j++) {
          expect(
            poligonosSeTocan(poligonos[i], poligonos[j]),
            `${clave}: puestos ${i} y ${j}`,
          ).toBe(false);
        }
      }
      const huellas = poligonos.map(cajaDe);
      const tu = rectPuesto({ ...e.tuPuesto });
      const tuGrande = {
        x0: tu.x0 - 0.3,
        x1: tu.x1 + 0.3,
        z0: tu.z0 - 0.4,
        z1: tu.z1 + 0.4,
      };
      const otros: Rect[] = [
        tuGrande,
        ...(e.mostrador ? [e.mostrador.rect] : []),
      ];
      for (const a of e.descanso.asientos)
        otros.push({
          x0: a.x - 0.3,
          x1: a.x + 0.3,
          z0: a.z - 0.3,
          z1: a.z + 0.3,
        });
      for (let i = 0; i < e.puestosBase; i++) {
        for (const o of otros)
          expect(
            poligonosSeTocan(poligonos[i], rectComoPoligono(o)),
            `${clave}: puesto ${i}`,
          ).toBe(false);
      }
      // No desk stands on a wall, a cabin, the counter or a decoration piece.
      if (clave !== "original")
        for (let i = 0; i < n; i++)
          for (const r of e.choques)
            expect(
              poligonosSeTocan(poligonos[i], rectComoPoligono(r)),
              `${clave}: puesto ${i} contra ${JSON.stringify(r)}`,
            ).toBe(false);
      for (const h of huellas) {
        expect(Math.abs(h.x0)).toBeLessThan(e.tamano.ancho / 2);
        expect(Math.abs(h.x1)).toBeLessThan(e.tamano.ancho / 2);
        expect(Math.abs(h.z0)).toBeLessThan(e.tamano.fondo / 2);
        expect(Math.abs(h.z1)).toBeLessThan(e.tamano.fondo / 2);
      }
    });

    it("caminos conectados: de la puerta a cada escritorio, tu puesto, el descanso y el mostrador", () => {
      activarEntorno(clave);
      expect(blockedStatic(e.entrada.x, e.entrada.z, 0.16)).toBe(false);
      const desde = nearestNode(e.entrada.x, e.entrada.z);
      const destinos: Array<[string, WP]> = [
        ...Array.from(
          { length: e.puestosGrafo ?? e.puestosBase },
          (_, i) => [`puesto ${i}`, sitPoint(e.puesto(i))] as [string, WP],
        ),
        ...(e.agrupacion?.puerta
          ? Array.from({ length: e.agrupacion.grupos }, (_, g) =>
              [0, 1, 2].map(
                (i) =>
                  [`puerta ${g}.${i}`, e.agrupacion!.puerta!(g, i)] as [
                    string,
                    WP,
                  ],
              ),
            ).flat()
          : []),
        ["tu puesto", sitPoint(e.tuPuesto)],
        ["sala de descanso", NODES[e.descanso.nodo]],
        ...e.descanso.asientos.map(
          (a, i) => [`asiento ${i}`, { x: a.ax, z: a.az }] as [string, WP],
        ),
        ...e.descanso.cerca.map((c, i) => [`de pie ${i}`, c] as [string, WP]),
        ...(e.mostrador
          ? Array.from(
              { length: 7 },
              (_, i) => [`fila ${i}`, e.mostrador!.fila(i)] as [string, WP],
            )
          : []),
      ];
      for (const [nombre, p] of destinos) {
        expect(p, `${clave}: ${nombre}`).toBeDefined();
        const hasta = nearestNode(p.x, p.z);
        expect(
          pathBetween(desde, hasta).length,
          `${clave}: ruta a ${nombre}`,
        ).toBeGreaterThan(0);
        const n = NODES[hasta];
        expect(
          Math.hypot(n.x - p.x, n.z - p.z),
          `${clave}: ${nombre} lejos del grafo`,
        ).toBeLessThan(clave === "original" ? 5 : 2.5); // Original: its hand-made graph
      }
    });
  },
);

describe("crecimiento con más agentes que escritorios", () => {
  it("Puente de mando: 10 en el primer arco; los siguientes en un segundo arco detrás", () => {
    const e = activarEntorno("puente");
    const radio = (i: number) => {
      const p = e.puesto(i);
      return Math.hypot(p.x - CENTRO_PUENTE.x, p.z - CENTRO_PUENTE.z);
    };
    for (let i = 0; i < 10; i++) expect(radio(i)).toBeCloseTo(ARCOS[0].radio);
    expect(radio(10)).toBeCloseTo(ARCOS[1].radio);
    // Every agent of the arc faces you: the monitor points to the centre.
    const p = e.puesto(3);
    const haciaMonitor = { x: -Math.sin(p.ry), z: -Math.cos(p.ry) };
    const haciaCentro = { x: CENTRO_PUENTE.x - p.x, z: CENTRO_PUENTE.z - p.z };
    expect(
      haciaMonitor.x * haciaCentro.x + haciaMonitor.z * haciaCentro.z,
    ).toBeGreaterThan(0);
  });

  it("Sala de control: filas de 5; la tercera fila queda detrás de la segunda", () => {
    const e = activarEntorno("control");
    expect(e.puesto(4).z).toBe(e.puesto(0).z);
    expect(e.puesto(5).z).toBeGreaterThan(e.puesto(0).z);
    expect(e.puesto(10).z).toBeGreaterThan(e.puesto(5).z);
  });
});

function agente(id: string, numero: number, haceSeg: number): Agente {
  return {
    agente: { session_id: id, proyecto: `E:\\${id}`, cuenta: "personal" },
    estado: {
      numero,
      nombre: `estado ${numero}`,
      desde: new Date(
        Date.parse("2026-10-10T18:00:00Z") - haceSeg * 1000,
      ).toISOString(),
    },
    espera: null,
    herramienta_actual: null,
    ultimo_evento: { tipo: null, hora: null },
    subagentes_activos: 0,
    pregunta_pendiente: numero === 14 ? "¿Sigo?" : null,
    cierre: null,
    proceso: null,
    indicadores: {
      herramientas_por_minuto: 0,
      tokens_por_minuto: 0,
      tokens_totales: 0,
      tokens_contexto: 0,
      tokens_motivo: null,
      minutos_con_actividad: 0,
      contexto_usado_pct: 0,
      errores_seguidos: 0,
      errores_motivo: null,
    },
    eventos_recientes: [],
  };
}

describe("fila del mostrador (Sala de control)", () => {
  const T = Date.parse("2026-10-10T18:00:00Z");

  it("el primero de la fila es el que más tiempo lleva esperando", () => {
    expect(
      ordenarFila([
        { id: "b", desde: "2026-10-10T18:00:00Z" },
        { id: "a", desde: "2026-10-10T17:55:00Z" },
        { id: "c", desde: "2026-10-10T17:59:00Z" },
      ]),
    ).toEqual({ a: 0, c: 1, b: 2 });
  });

  it("13 y 14 van a la fila frente a tu puesto; al dejar de esperar vuelven y la fila avanza", () => {
    const e = activarEntorno("control");
    const r1 = adaptar(
      [agente("a", 13, 300), agente("b", 14, 60), agente("c", 6, 10)],
      estadoInicial(),
      T,
    );
    const v = (r: typeof r1, id: string) => r.vistas.find((x) => x.id === id)!;
    expect(v(r1, "a")).toMatchObject({
      destino: "fila",
      fila: e.mostrador!.fila(0),
    });
    expect(v(r1, "b")).toMatchObject({
      destino: "fila",
      fila: e.mostrador!.fila(1),
    });
    expect(v(r1, "c")).toMatchObject({ destino: "escritorio", fila: null });
    // The queue faces your desk: the first spot is the closest to you.
    const f0 = e.mostrador!.fila(0);
    const f1 = e.mostrador!.fila(1);
    expect(Math.hypot(f0.x - e.tuPuesto.x, f0.z - e.tuPuesto.z)).toBeLessThan(
      Math.hypot(f1.x - e.tuPuesto.x, f1.z - e.tuPuesto.z),
    );
    const r2 = adaptar(
      [agente("a", 6, 1), agente("b", 14, 62), agente("c", 6, 12)],
      r1.estado,
      T + 2000,
    );
    expect(v(r2, "a")).toMatchObject({ destino: "escritorio", fila: null });
    expect(v(r2, "b").fila).toEqual(e.mostrador!.fila(0));
    // Desks do not change while queueing.
    expect(v(r2, "a").seatIndex).toBe(v(r1, "a").seatIndex);
  });

  it("con más de 5 en la fila, se dobla a lo largo del mostrador", () => {
    const e = activarEntorno("control");
    const m = e.mostrador!;
    const puntos = Array.from({ length: 9 }, (_, i) => m.fila(i));
    for (let i = 5; i < 9; i++) expect(puntos[i].z).toBe(puntos[0].z);
    const unicos = new Set(puntos.map((p) => `${p.x},${p.z}`));
    expect(unicos.size).toBe(9);
    for (const p of puntos) {
      expect(p.x).toBeGreaterThanOrEqual(m.rect.x0);
      expect(p.x).toBeLessThanOrEqual(m.rect.x1);
    }
  });

  it("en entornos sin mostrador, quien te espera se queda en su escritorio", () => {
    activarEntorno("puente");
    const r = adaptar([agente("a", 13, 30)], estadoInicial(), T);
    expect(r.vistas[0]).toMatchObject({ destino: "escritorio", fila: null });
  });
});

describe("guardado del entorno", () => {
  const planta = (id: string): PlacedItem => ({
    id,
    type: "plant",
    x: 1,
    z: 1,
    ry: 0,
  });

  it("cada entorno conserva su distribución y el JSON guarda el activo", () => {
    useLayout
      .getState()
      .cargar(leerDistribucion({ items: [planta("o")], tema: "calido" }));
    expect(useLayout.getState().entorno).toBe("original");
    useLayout.getState().cambiarEntorno("puente");
    expect(useLayout.getState().items).toEqual([]);
    useLayout.setState({ items: [planta("p")], tema: "noche" });
    const d = distribucionActual();
    expect(d).toMatchObject({
      entorno: "puente",
      items: [{ id: "o" }],
      tema: "calido",
    });
    expect(d.entornos.puente).toMatchObject({
      items: [{ id: "p" }],
      tema: "noche",
    });
    useLayout.getState().cambiarEntorno("original");
    expect(useLayout.getState().items.map((i) => i.id)).toEqual(["o"]);
    useLayout.getState().cambiarEntorno("puente");
    expect(useLayout.getState().items.map((i) => i.id)).toEqual(["p"]);
  });

  it("lee el entorno guardado y descarta entornos desconocidos", () => {
    const d = leerDistribucion({
      entorno: "control",
      entornos: { control: { items: [planta("c")] }, nave: {} },
    });
    expect(d.entorno).toBe("control");
    expect(Object.keys(d.entornos)).toEqual(["control"]);
    expect(leerDistribucion({ entorno: "otro" }).entorno).toBe("original");
    useLayout.getState().cargar(d);
    expect(useLayout.getState()).toMatchObject({
      entorno: "control",
      items: [{ id: "c" }],
    });
  });
});
