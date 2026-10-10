import { entornoActivo } from "../entornos/activo";
import { seatFor } from "./roles";

// ── Collision (AABB boxes; adapted from Agent Office 3D, MIT) ──
// Walls and fixed furniture come from the active environment (entornos/);
// the agents' desks in use and the furniture placed with the editor are
// added at runtime. Characters slide along them instead of going through.

export interface Rect {
  x0: number;
  x1: number;
  z0: number;
  z1: number;
}

let placedRects: Rect[] = [];
export function setPlacedRects(rects: Rect[]): void {
  placedRects = rects;
}

let seatRects: Rect[] = [];
export function setActiveSeats(seatIndexes: number[]): void {
  seatRects = seatIndexes.map((i) => {
    const s = seatFor(i);
    const hx =
      Math.abs(0.75 * Math.cos(s.ry)) + Math.abs(0.4 * Math.sin(s.ry)) + 0.05;
    const hz =
      Math.abs(0.75 * Math.sin(s.ry)) + Math.abs(0.4 * Math.cos(s.ry)) + 0.05;
    return { x0: s.x - hx, x1: s.x + hx, z0: s.z - hz, z1: s.z + hz };
  });
}

function dentro(list: Rect[], x: number, z: number, rad: number): boolean {
  for (const b of list) {
    if (x > b.x0 - rad && x < b.x1 + rad && z > b.z0 - rad && z < b.z1 + rad)
      return true;
  }
  return false;
}

/** Only the fixed boxes of the active environment (walls, fixed furniture). */
export function blockedStatic(x: number, z: number, rad: number): boolean {
  return dentro(entornoActivo().choques, x, z, rad);
}

/** Does a circle of radius `rad` at (x, z) touch anything (fixed, desks in use, placed furniture)? */
export function blocked(x: number, z: number, rad: number): boolean {
  return (
    blockedStatic(x, z, rad) ||
    dentro(seatRects, x, z, rad) ||
    dentro(placedRects, x, z, rad)
  );
}

export function slide(
  x: number,
  z: number,
  dx: number,
  dz: number,
  rad: number,
): { x: number; z: number } {
  if (blocked(x, z, rad)) return { x: x + dx, z: z + dz };
  let nx = x;
  let nz = z;
  if (dx !== 0 && !blocked(x + dx, z, rad)) nx = x + dx;
  if (dz !== 0 && !blocked(nx, z + dz, rad)) nz = z + dz;
  return { x: nx, z: nz };
}
