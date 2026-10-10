/**
 * Placed furniture must not block the agents' paths or the work desks.
 * Pure logic, tested in tests/oficina3d-editor.test.ts and tests/entornos.test.ts.
 *
 * Original environment: every edge of its hand-made graph, the last step from
 * each desk chair to its node, the entrance and the break room are protected.
 * Grid environments (Puente de mando, Sala de control...): the routes the
 * agents really use are protected — from the entrance to every base desk, to
 * your desk, to the break room seats and standing spots, to the queue and
 * to the cabin doors (Cabinas: every fixed desk, not only the base ones).
 * Protected zones: each desk and its chair, and your desk.
 */

import { entornoActivo } from "./entornos/activo";
import {
  rectPuesto,
  sitPoint,
  type Entorno,
  type Rect,
  type WP,
} from "./entornos/tipos";
import type { PlacedItem } from "./distribucion";
import { EDGES, nearestNode, NODES, pathBetween } from "./escena/nav";
import { huella } from "./muebles";

/** Room an agent needs around a path (its radius plus a margin). */
const MARGEN = 0.22;
const PASO = 0.1;

type Segmento = [WP, WP];

/** Desks protected: the base ones, or every fixed desk (cabins, islands). */
function base(e: Entorno) {
  return Array.from({ length: e.puestosGrafo ?? e.puestosBase }, (_, i) =>
    e.puesto(i),
  );
}

function segmentosOriginal(e: Entorno): Segmento[] {
  const s: Segmento[] = EDGES.map(([a, b]) => [NODES[a], NODES[b]]);
  for (const p of base(e).map(sitPoint))
    s.push([p, NODES[nearestNode(p.x, p.z)]]);
  s.push(
    [e.puerta, e.entrada],
    [e.entrada, NODES[nearestNode(e.entrada.x, e.entrada.z)]],
  );
  const sala = NODES[e.descanso.nodo];
  if (sala) {
    const pasillo = e.descanso.pasillo ?? sala;
    s.push([sala, pasillo]);
    for (const a of e.descanso.asientos)
      s.push([pasillo, { x: a.ax, z: a.az }]);
    for (const c of e.descanso.cerca) s.push([sala, { x: c.x, z: c.z }]);
  }
  return s;
}

/** Route on the graph from the entrance to a point, as segments. */
function ruta(e: Entorno, destino: WP): Segmento[] {
  const nodos = pathBetween(
    nearestNode(e.entrada.x, e.entrada.z),
    nearestNode(destino.x, destino.z),
  );
  const puntos = [e.puerta, e.entrada, ...nodos, destino];
  const out: Segmento[] = [];
  for (let i = 1; i < puntos.length; i++) out.push([puntos[i - 1], puntos[i]]);
  return out;
}

function segmentosRutas(e: Entorno): Segmento[] {
  const destinos: WP[] = [
    ...base(e).map(sitPoint),
    sitPoint(e.tuPuesto),
    ...e.descanso.asientos.map((a) => ({ x: a.ax, z: a.az })),
    ...e.descanso.cerca,
  ];
  if (e.mostrador)
    for (let i = 0; i < 9; i++) destinos.push(e.mostrador.fila(i));
  const agr = e.agrupacion;
  if (agr?.puerta)
    for (let g = 0; g < agr.grupos; g++)
      for (let i = 0; i < 3; i++) destinos.push(agr.puerta(g, i));
  return destinos.flatMap((d) => ruta(e, d));
}

function zonasProtegidas(e: Entorno): Rect[] {
  const z: Rect[] = [];
  for (const p of base(e)) {
    z.push(rectPuesto(p));
    const s = sitPoint(p);
    z.push({ x0: s.x - 0.4, x1: s.x + 0.4, z0: s.z - 0.4, z1: s.z + 0.4 });
  }
  const t = e.tuPuesto;
  z.push({ x0: t.x - 1.1, x1: t.x + 1.1, z0: t.z - 0.55, z1: t.z + 0.55 });
  const s = sitPoint(t);
  z.push({ x0: s.x - 0.45, x1: s.x + 0.45, z0: s.z - 0.45, z1: s.z + 0.45 });
  return z;
}

// The protected geometry depends only on the environment: computed once per environment.
const cache = new Map<string, { segmentos: Segmento[]; zonas: Rect[] }>();
function geometria() {
  const e = entornoActivo();
  let g = cache.get(e.clave);
  if (!g) {
    g = {
      segmentos:
        e.clave === "original" ? segmentosOriginal(e) : segmentosRutas(e),
      zonas: zonasProtegidas(e),
    };
    cache.set(e.clave, g);
  }
  return g;
}

function rectDe(it: PlacedItem, margen: number): Rect {
  const f = huella(it.type, it.ry);
  return {
    x0: it.x - f.hx - margen,
    x1: it.x + f.hx + margen,
    z0: it.z - f.hz - margen,
    z1: it.z + f.hz + margen,
  };
}

function dentro(r: Rect, x: number, z: number): boolean {
  return x > r.x0 && x < r.x1 && z > r.z0 && z < r.z1;
}

function cortaSegmento(r: Rect, [a, b]: Segmento): boolean {
  const d = Math.hypot(b.x - a.x, b.z - a.z);
  const pasos = Math.max(1, Math.ceil(d / PASO));
  for (let i = 0; i <= pasos; i++) {
    const t = i / pasos;
    if (dentro(r, a.x + (b.x - a.x) * t, a.z + (b.z - a.z) * t)) return true;
  }
  return false;
}

function seTocan(a: Rect, b: Rect): boolean {
  return a.x0 < b.x1 && a.x1 > b.x0 && a.z0 < b.z1 && a.z1 > b.z0;
}

export type MotivoBloqueo = "camino" | "escritorio";

export interface Bloqueo {
  id: string;
  motivo: MotivoBloqueo;
}

/** Pieces that block a path or a desk of the active environment (empty: it can be saved). */
export function bloqueos(items: PlacedItem[]): Bloqueo[] {
  const { segmentos, zonas } = geometria();
  const out: Bloqueo[] = [];
  for (const it of items) {
    const r = rectDe(it, 0);
    if (zonas.some((z) => seTocan(r, z))) {
      out.push({ id: it.id, motivo: "escritorio" });
      continue;
    }
    const conMargen = rectDe(it, MARGEN);
    if (segmentos.some((s) => cortaSegmento(conMargen, s)))
      out.push({ id: it.id, motivo: "camino" });
  }
  return out;
}
