/**
 * Environment "Original": the office of Agent Office 3D (MIT) as it was in the
 * port, unchanged. The data below was moved here from roles.ts (desks),
 * collision.ts (boxes), nav.ts (graph) and comportamiento.ts (sofa, door);
 * the building is drawn by escena/OfficeDecor.tsx. Only addition: your desk.
 */

import {
  type Bloqueado,
  type Entorno,
  type Grafo,
  type Puesto,
  type PuntoSofa,
  type Rect,
  type WP,
} from "./tipos";

// Desks: everybody faces the centre. 1-6: two main columns (x = ±5.5);
// 7-10: the extra desks at x = ±13.
export const SEATS: Puesto[] = [
  { x: -5.5, z: -3.2, ry: -Math.PI / 2 },
  { x: -5.5, z: 0, ry: -Math.PI / 2 },
  { x: -5.5, z: 3.2, ry: -Math.PI / 2 },
  { x: 5.5, z: -3.2, ry: Math.PI / 2 },
  { x: 5.5, z: 0, ry: Math.PI / 2 },
  { x: 5.5, z: 3.2, ry: Math.PI / 2 },
  { x: -13, z: -3, ry: -Math.PI / 2 },
  { x: -13, z: 3, ry: -Math.PI / 2 },
  { x: 13, z: -3, ry: Math.PI / 2 },
  { x: 13, z: 3, ry: Math.PI / 2 },
];

/** Desk i; past the 10 desks, tidy rows in the open central area. */
function puesto(index: number): Puesto {
  if (index >= 0 && index < SEATS.length) return SEATS[index];
  const o = index - SEATS.length;
  const col = o % 5;
  const row = Math.floor(o / 5);
  return { x: -4.4 + col * 2.2, z: -5.2 - row * 2.0, ry: Math.PI };
}

/** Your desk: near the reception, facing the hall. */
export const TU_PUESTO_ORIGINAL: Puesto = { x: 4.8, z: 8.3, ry: 0 };

// Break room (bottom centre): two sofas against the far wall, facing the camera.
export const ASIENTOS_SOFA: PuntoSofa[] = [11.35, 12.45, 13.85, 14.95].map(
  (z) => ({
    x: -1.7,
    z,
    ry: -Math.PI / 2,
    ax: -0.75,
    az: z,
  }),
);
export const PASILLO_SOFA: WP = { x: -0.75, z: 15.2 };
export const LUGARES_CERCA: PuntoSofa[] = [
  [2.4, 12.0],
  [2.6, 14.2],
  [3.8, 11.2],
  [4.0, 13.2],
  [3.6, 15.0],
  [5.2, 12.0],
  [5.4, 14.2],
  [1.8, 10.4],
].map(([x, z]) => ({
  x,
  z,
  ry: Math.atan2(-(-1.7 - x), -(13.1 - z)),
  ax: x,
  az: z,
}));

// Entrance door on the west wall and the point just inside.
export const PUERTA: WP = { x: -22.55, z: 4 };
export const ENTRADA: WP = { x: -21.2, z: 4 };

/** Fixed collision boxes of the original building (walls, rooms, furniture). */
function choquesOriginal(): Rect[] {
  const B: Rect[] = [];
  const T = 0.16;
  const r = (x0: number, x1: number, z0: number, z1: number) =>
    B.push({
      x0: Math.min(x0, x1),
      x1: Math.max(x0, x1),
      z0: Math.min(z0, z1),
      z1: Math.max(z0, z1),
    });
  r(-23, 23, -16.2, -15.8);
  r(-23, 23, 15.8, 16.2);
  r(-23.2, -22.8, -16, 16);
  r(22.8, 23.2, -16, 16);
  const top = [
    { x0: -23, x1: -9, cx: -16, door: 2.6 },
    { x0: -9, x1: -1, cx: -5, door: 2 },
    { x0: -1, x1: 8, cx: 3.5, door: 2 },
    { x0: 8, x1: 15, cx: 11.5, door: 2 },
    { x0: 15, x1: 23, cx: 19, door: 2 },
  ];
  for (const m of top) {
    r(m.x0, m.cx - m.door / 2, -9.5 - T, -9.5 + T);
    r(m.cx + m.door / 2, m.x1, -9.5 - T, -9.5 + T);
  }
  for (const x of [-9, -1, 8, 15]) r(x - T, x + T, -16, -9.5);
  const bot = [
    { x0: -23, x1: -11, cx: -17, door: 2.4 },
    { x0: -11, x1: -3, cx: -7, door: 2 },
    { x0: -3, x1: 7, cx: 2, door: 2 },
    { x0: 7, x1: 15, cx: 11, door: 2 },
    { x0: 15, x1: 23, cx: 19, door: 2 },
  ];
  for (const m of bot) {
    r(m.x0, m.cx - m.door / 2, 9.5 - T, 9.5 + T);
    r(m.cx + m.door / 2, m.x1, 9.5 - T, 9.5 + T);
  }
  for (const x of [-11, -3, 7, 15]) r(x - T, x + T, 9.5, 16);
  r(-1.7, 1.7, 7.0, 8.0);
  r(-22, -10, -16.0, -14.8);
  r(-22, -10, -11.6, -10.4);
  r(-7.6, -2.4, -16.0, -14.8);
  r(1.9, 5.1, -14.1, -10.9);
  r(9, 12.6, -16, -13.8);
  r(13.2, 15, -16, -14.6);
  r(18, 20, -13.8, -11.8);
  r(-22.6, -14.4, 15.4, 15.9);
  r(-22.6, -14.4, 10.4, 11.6);
  r(-14.8, -12.2, 12, 14);
  r(-7.8, -6.2, 14, 15.2);
  r(-2.3, -1.3, 10.8, 13.0); // lounge sofa A
  r(-2.3, -1.3, 13.3, 15.5); // lounge sofa B
  r(-0.3, 0.9, 12.55, 13.75); // lounge coffee table
  r(8.7, 10.3, 13.8, 15.2);
  r(11.7, 13.3, 13.8, 15.2);
  r(18, 20, 12, 14);
  for (const [x, z] of [
    [-7, 5],
    [7, -5],
  ])
    r(x - 0.22, x + 0.22, z - 0.22, z + 0.22); // lamps
  for (const [x, z] of [
    [-1.5, 5],
    [1.5, 5],
    [-16, 6],
    [16, 6],
    [-16, -6],
    [16, -6],
  ])
    r(x - 0.28, x + 0.28, z - 0.28, z + 0.28); // plants
  // Your desk (2.0 × 0.9 m) near the reception.
  r(
    TU_PUESTO_ORIGINAL.x - 1.05,
    TU_PUESTO_ORIGINAL.x + 1.05,
    TU_PUESTO_ORIGINAL.z - 0.5,
    TU_PUESTO_ORIGINAL.z + 0.5,
  );
  return B;
}

// Rooms: [key, centre x, side]. Their door and inner node join the graph.
const ROOMS: [string, number, "top" | "bottom"][] = [
  ["server", -16, "top"],
  ["kitchen", -5, "top"],
  ["meeting", 3.5, "top"],
  ["bathroom", 11.5, "top"],
  ["glassA", 19, "top"],
  ["library", -17, "bottom"],
  ["focus", -7, "bottom"],
  ["lounge", 2, "bottom"],
  ["glassB", 11, "bottom"],
  ["glassC", 19, "bottom"],
];

/** The hand-made graph of the original office: central grid plus a door and inner node per room. */
function grafoOriginal(blocked: Bloqueado): Grafo {
  const nodes: Record<string, WP> = {};
  const edges: [string, string][] = [];
  const CX = [-17, -9, 0, 9, 17];
  const CZ = [-6.5, -1.8, 1.8, 6.5];
  const grid: string[][] = [];
  const gridKeys: string[] = [];
  CX.forEach((x, i) => {
    grid[i] = [];
    CZ.forEach((z, j) => {
      const k = `g${i}_${j}`;
      nodes[k] = { x, z };
      grid[i][j] = k;
      gridKeys.push(k);
    });
  });
  for (let i = 0; i < CX.length; i++) {
    for (let j = 0; j < CZ.length; j++) {
      if (i + 1 < CX.length) edges.push([grid[i][j], grid[i + 1][j]]);
      if (j + 1 < CZ.length) edges.push([grid[i][j], grid[i][j + 1]]);
    }
  }
  const clearPath = (
    ax: number,
    az: number,
    bx: number,
    bz: number,
    rad = 0.22,
  ) => {
    const d = Math.hypot(bx - ax, bz - az);
    const steps = Math.max(2, Math.ceil(d / 0.1));
    for (let i = 0; i <= steps; i++) {
      const t = i / steps;
      if (blocked(ax + (bx - ax) * t, az + (bz - az) * t, rad)) return false;
    }
    return true;
  };
  for (const [key, cx, side] of ROOMS) {
    const doorZ = side === "top" ? -9.0 : 9.0;
    const inward = side === "top" ? -1 : 1;
    // Inner node: walk in from the door up to the first obstacle.
    let iz = doorZ;
    for (let z = doorZ; Math.abs(z - doorZ) <= 6.5; z += inward * 0.25) {
      if (blocked(cx, z, 0.32)) break;
      iz = z;
    }
    nodes[`${key}_d`] = { x: cx, z: doorZ };
    nodes[`${key}_i`] = { x: cx, z: iz };
    edges.push([`${key}_d`, `${key}_i`]);
    // Door to the nearest grid node with a clear path.
    const near = [...gridKeys].sort((a, b) => {
      const A = nodes[a];
      const B = nodes[b];
      return (
        (A.x - cx) ** 2 +
        (A.z - doorZ) ** 2 -
        ((B.x - cx) ** 2 + (B.z - doorZ) ** 2)
      );
    });
    const best =
      near.find((gk) => clearPath(cx, doorZ, nodes[gk].x, nodes[gk].z)) ??
      near[0];
    edges.push([`${key}_d`, best]);
  }
  return { nodes, edges };
}

/** Rooms per role for walking around (only meaningful in this office). */
export const ROLE_ROOMS: Record<string, string[]> = {
  research: ["library_i", "focus_i", "kitchen_i"],
  docs: ["library_i", "focus_i", "lounge_i"],
  frontend: ["kitchen_i", "lounge_i", "meeting_i"],
  backend: ["server_i", "kitchen_i", "lounge_i"],
  data: ["focus_i", "library_i", "kitchen_i"],
  qa: ["meeting_i", "lounge_i", "kitchen_i"],
};

export const ORIGINAL: Entorno = {
  clave: "original",
  nombre: "Original",
  tamano: { ancho: 46, fondo: 32 },
  zoom: 20,
  puestosBase: SEATS.length,
  puesto,
  tuPuesto: TU_PUESTO_ORIGINAL,
  placaNombre: false,
  resaltarEspera: false,
  descanso: {
    asientos: ASIENTOS_SOFA,
    cerca: LUGARES_CERCA,
    pasillo: PASILLO_SOFA,
    nodo: "lounge_i",
  },
  puerta: PUERTA,
  entrada: ENTRADA,
  mostrador: null,
  choques: choquesOriginal(),
  grafo: (bloqueado) => grafoOriginal(bloqueado),
  encuentros: ["kitchen_i", "lounge_i", "meeting_i", "library_i", "focus_i"],
  paseo: {
    descanso: ["kitchen_i", "lounge_i"],
    destinos: ROOMS.map(([k]) => `${k}_i`),
  },
  limites: { x: 22.5, z: 15.5 },
};
