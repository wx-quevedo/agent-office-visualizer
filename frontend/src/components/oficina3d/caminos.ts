/**
 * Placed furniture must not block the agents' paths or the work desks.
 * Pure logic, tested in tests/oficina3d-editor.test.ts.
 *
 * Protected paths: every edge of the navigation graph (nav.ts), the last step
 * from each desk chair to its graph node, the entrance (door → inside → graph),
 * and the break room (corridor, sofa approach points, standing spots).
 * Protected zones: each desk and its chair.
 */

import {
  ASIENTOS_SOFA,
  ENTRADA,
  LUGARES_CERCA,
  PASILLO_SOFA,
  PUERTA,
} from "./comportamiento";
import type { PlacedItem } from "./distribucion";
import { EDGES, nearestNode, NODES, type WP } from "./escena/nav";
import { SEAT_COUNT, seatFor, sitPoint } from "./escena/roles";
import { huella } from "./muebles";

/** Room an agent needs around a path (its radius plus a margin). */
const MARGEN = 0.22;
const PASO = 0.1;

type Segmento = [WP, WP];
interface Rect {
  x0: number;
  x1: number;
  z0: number;
  z1: number;
}

function segmentosProtegidos(): Segmento[] {
  const s: Segmento[] = EDGES.map(([a, b]) => [NODES[a], NODES[b]]);
  for (let i = 0; i < SEAT_COUNT; i++) {
    const p = sitPoint(seatFor(i));
    s.push([p, NODES[nearestNode(p.x, p.z)]]);
  }
  s.push(
    [PUERTA, ENTRADA],
    [ENTRADA, NODES[nearestNode(ENTRADA.x, ENTRADA.z)]],
  );
  const sala = NODES.lounge_i;
  if (sala) {
    s.push([sala, PASILLO_SOFA]);
    for (const a of ASIENTOS_SOFA) s.push([PASILLO_SOFA, { x: a.ax, z: a.az }]);
    for (const c of LUGARES_CERCA) s.push([sala, { x: c.x, z: c.z }]);
  }
  return s;
}

function zonasProtegidas(): Rect[] {
  const z: Rect[] = [];
  for (let i = 0; i < SEAT_COUNT; i++) {
    const seat = seatFor(i);
    const hx =
      Math.abs(0.75 * Math.cos(seat.ry)) + Math.abs(0.4 * Math.sin(seat.ry));
    const hz =
      Math.abs(0.75 * Math.sin(seat.ry)) + Math.abs(0.4 * Math.cos(seat.ry));
    z.push({
      x0: seat.x - hx,
      x1: seat.x + hx,
      z0: seat.z - hz,
      z1: seat.z + hz,
    });
    const p = sitPoint(seat);
    z.push({ x0: p.x - 0.4, x1: p.x + 0.4, z0: p.z - 0.4, z1: p.z + 0.4 });
  }
  return z;
}

// The protected geometry does not change at runtime: computed once.
let cache: { segmentos: Segmento[]; zonas: Rect[] } | null = null;
function geometria() {
  cache ??= { segmentos: segmentosProtegidos(), zonas: zonasProtegidas() };
  return cache;
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

/** Pieces that block a path or a desk (empty: the layout can be saved). */
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
