/**
 * What an office environment ("entorno") defines. Pure data and functions
 * (no React, no three.js): the scene draws and moves the agents from it, and
 * tests/entornos.test.ts checks every environment.
 */

export interface WP {
  x: number;
  z: number;
}

export interface Rect {
  x0: number;
  x1: number;
  z0: number;
  z1: number;
}

/** A desk: centre and rotation. The monitor is on the local -z side, the chair on +z. */
export interface Puesto {
  x: number;
  z: number;
  ry: number;
}

/** A place to rest (sofa seat or standing spot): where, facing, and its approach point. */
export interface PuntoSofa {
  x: number;
  z: number;
  ry: number;
  ax: number;
  az: number;
}

/** A spot in the queue at the counter: where the agent stands and where it faces. */
export interface PuntoFila {
  x: number;
  z: number;
  ry: number;
}

export interface Grafo {
  nodes: Record<string, WP>;
  edges: [string, string][];
}

/** Collision test of the environment (walls, fixed furniture, desks). */
export type Bloqueado = (x: number, z: number, rad: number) => boolean;

export type ClaveEntorno =
  "original" | "puente" | "control" | "cabinas" | "estudio";

/** Owner of a group that holds agents of several projects. */
export const GRUPO_GENERAL = "*general*";

/**
 * Environments that seat the agents by project (Cabinas, Estudio): the desks
 * come in groups (a cabin, an island). A group belongs to one project while it
 * has agents, or to the general group. Seat index i = a desk of a group.
 */
export interface Agrupacion {
  /** Group of seat i and its place inside the group. */
  grupoDe(asiento: number): { g: number; k: number };
  /** Seat index of place k of group g. */
  asiento(g: number, k: number): number;
  /** Places of group g (Infinity: an open general area that keeps growing). */
  capacidad(g: number): number;
  /** Number of groups. Seats past them are extra desks of the general group. */
  grupos: number;
  /** Group that is always the general one (Cabinas), or null (Estudio: free groups become general when needed). */
  generalFijo: number | null;
  /** Agents a project needs to get a group of its own. */
  umbralPropio: number;
  /** Free groups kept for the general one before giving a project its own. */
  reservaGeneral: number;
  /** An agent waiting for you walks to the door of its group (Cabinas), or null (stays seated). */
  puerta: ((g: number, orden: number) => PuntoFila) | null;
}

/** Fixed decoration piece (drawn by entornos/decoracion.tsx, blocks paths when it stands on the floor). */
export type TipoPieza =
  | "planta"
  | "plantaGrande"
  | "arbol"
  | "arbusto"
  | "macetero"
  | "lampara"
  | "librero"
  | "sofa"
  | "mesaCafe"
  | "banca"
  | "mesaReuniones"
  | "pizarra"
  | "cafeteria"
  | "cuadro"
  | "reloj"
  | "alfombra"
  | "cesped";

export interface Pieza {
  tipo: TipoPieza;
  x: number;
  z: number;
  ry?: number;
  /** Rugs, lawns and planters: size; others: ignored. */
  ancho?: number;
  fondo?: number;
  color?: string;
  escala?: number;
}

/** Half sizes (x, z) of a piece standing on the floor, before rotation; null: does not block. */
const MEDIDAS: Partial<Record<TipoPieza, [number, number]>> = {
  planta: [0.28, 0.28],
  plantaGrande: [0.4, 0.4],
  arbol: [0.55, 0.55],
  arbusto: [0.5, 0.5],
  lampara: [0.25, 0.25],
  librero: [0.62, 0.2],
  sofa: [1.15, 0.5],
  mesaCafe: [0.6, 0.35],
  banca: [0.85, 0.3],
  mesaReuniones: [1.9, 1.9],
  pizarra: [1.0, 0.15],
  cafeteria: [3.3, 0.4],
};

/** Collision box of a piece (null for rugs, lawns, paintings and clocks). */
export function huellaPieza(p: Pieza): Rect | null {
  let m = MEDIDAS[p.tipo];
  if (p.tipo === "macetero") m = [(p.ancho ?? 2) / 2, (p.fondo ?? 0.5) / 2];
  if (!m) return null;
  const e = p.escala ?? 1;
  const r = p.ry ?? 0;
  const c = Math.abs(Math.cos(r));
  const s = Math.abs(Math.sin(r));
  const hx = (m[0] * c + m[1] * s) * e;
  const hz = (m[0] * s + m[1] * c) * e;
  return { x0: p.x - hx, x1: p.x + hx, z0: p.z - hz, z1: p.z + hz };
}

export interface Entorno {
  clave: ClaveEntorno;
  nombre: string;
  /** Room shell (floor and outer walls), centred on the origin. */
  tamano: { ancho: number; fondo: number };
  /** Default camera zoom on a PC. */
  zoom: number;
  /** Desks always drawn (even empty). */
  puestosBase: number;
  /** Desk of the agent in position i; grows past the base (rows, arcs...) without overlapping. */
  puesto(i: number): Puesto;
  /** Your desk (bigger, with a "Tú" sign). The person sits on its chair. */
  tuPuesto: Puesto;
  /** Project name visible on each desk (back of the monitor). */
  placaNombre: boolean;
  /** The desk of an agent waiting for you lights up. */
  resaltarEspera: boolean;
  descanso: {
    asientos: PuntoSofa[];
    cerca: PuntoSofa[];
    /** Corridor point before the sofa seats (null: go straight). */
    pasillo: WP | null;
    /** Graph node of the break room. */
    nodo: string;
  };
  /** Entrance door (on the wall) and the point just inside. */
  puerta: WP;
  entrada: WP;
  /** Counter with a queue (13 and 14 walk there), or null. */
  mostrador: { rect: Rect; fila(i: number): PuntoFila } | null;
  /** Fixed collision boxes (walls, fixed furniture, your desk, counter). */
  choques: Rect[];
  /** Navigation graph, built with the collision test of this environment. */
  grafo(bloqueado: Bloqueado, puestosBase: Puesto[]): Grafo;
  /** Nodes where two idle agents meet. */
  encuentros: string[];
  /** Nodes for the first break after work, and for walking around. */
  paseo: { descanso: string[]; destinos: string[] };
  /** Limits for placed furniture (editor). */
  limites: { x: number; z: number };
  /** Seats by project (cabins, islands), or none: lowest free desk. */
  agrupacion?: Agrupacion;
  /** Desks the navigation graph walks around (default: the base desks). */
  puestosGrafo?: number;
  /** Extra empty desks drawn next to the used ones (default: none). */
  puestosVisibles?: (ocupados: number[]) => number[];
  /** The agent waiting for you turns (with its chair) towards your desk. */
  girarHaciaTi?: boolean;
  /** Fixed decoration drawn from data (its pieces on the floor block paths). */
  decoracion?: Pieza[];
  /** Coloured floor area of the room (theme floor colour); default 30 × 14 in the centre. */
  pisoCentral?: Rect;
}

// -- helpers shared by the environments -------------------------------------------

/** Chair point of a desk (where the agent sits): 0.72 m to the local +z. */
export function sitPoint(p: Puesto): WP {
  return { x: p.x + 0.72 * Math.sin(p.ry), z: p.z + 0.72 * Math.cos(p.ry) };
}

/** Rotation of a desk whose monitor points from (x, z) towards (hx, hz). */
export function ryHacia(x: number, z: number, hx: number, hz: number): number {
  return Math.atan2(-(hx - x), -(hz - z));
}

/** Facing (rotation of a standing character) from (x, z) towards (hx, hz). */
export const mirarHacia = ryHacia;

/** Collision box of a desk (1.5 × 0.8 m plus margin), rotated. */
export function rectPuesto(p: Puesto): Rect {
  const hx =
    Math.abs(0.75 * Math.cos(p.ry)) + Math.abs(0.4 * Math.sin(p.ry)) + 0.05;
  const hz =
    Math.abs(0.75 * Math.sin(p.ry)) + Math.abs(0.4 * Math.cos(p.ry)) + 0.05;
  return { x0: p.x - hx, x1: p.x + hx, z0: p.z - hz, z1: p.z + hz };
}

/** Box with half sizes (hx, hz) around (x, z). */
export function caja(x: number, z: number, hx: number, hz: number): Rect {
  return { x0: x - hx, x1: x + hx, z0: z - hz, z1: z + hz };
}

/** Outer walls of a room centred on the origin. */
export function paredes(ancho: number, fondo: number): Rect[] {
  const W = ancho / 2;
  const D = fondo / 2;
  return [
    { x0: -W, x1: W, z0: -D - 0.2, z1: -D + 0.2 },
    { x0: -W, x1: W, z0: D - 0.2, z1: D + 0.2 },
    { x0: -W - 0.2, x1: -W + 0.2, z0: -D, z1: D },
    { x0: W - 0.2, x1: W + 0.2, z0: -D, z1: D },
  ];
}

function tramoLibre(bloqueado: Bloqueado, a: WP, b: WP, rad: number): boolean {
  const d = Math.hypot(b.x - a.x, b.z - a.z);
  const pasos = Math.max(2, Math.ceil(d / 0.1));
  for (let i = 0; i <= pasos; i++) {
    const t = i / pasos;
    if (bloqueado(a.x + (b.x - a.x) * t, a.z + (b.z - a.z) * t, rad))
      return false;
  }
  return true;
}

/**
 * Navigation graph for an open room: a grid of nodes every `paso` metres
 * where nothing blocks, linked to their 8 neighbours when the step is clear;
 * named nodes (break room, entrance, meeting points...) are linked to the
 * nearby grid nodes. The base desks block too, so paths go around them.
 */
export function grafoCuadricula(
  bloqueado: Bloqueado,
  puestosBase: Puesto[],
  limX: number,
  limZ: number,
  paso: number,
  especiales: Record<string, WP>,
): Grafo {
  const mesas = puestosBase.map(rectPuesto);
  const ocupado: Bloqueado = (x, z, r) =>
    bloqueado(x, z, r) ||
    mesas.some(
      (m) => x > m.x0 - r && x < m.x1 + r && z > m.z0 - r && z < m.z1 + r,
    );
  const nodes: Record<string, WP> = {};
  const edges: [string, string][] = [];
  const clave = (i: number, j: number) => `c${i}_${j}`;
  const nx = Math.floor((2 * limX) / paso);
  const nz = Math.floor((2 * limZ) / paso);
  for (let i = 0; i <= nx; i++) {
    for (let j = 0; j <= nz; j++) {
      const p = { x: -limX + i * paso, z: -limZ + j * paso };
      if (!ocupado(p.x, p.z, 0.3)) nodes[clave(i, j)] = p;
    }
  }
  for (let i = 0; i <= nx; i++) {
    for (let j = 0; j <= nz; j++) {
      const a = clave(i, j);
      if (!nodes[a]) continue;
      for (const [di, dj] of [
        [1, 0],
        [0, 1],
        [1, 1],
        [1, -1],
      ]) {
        const b = clave(i + di, j + dj);
        if (nodes[b] && tramoLibre(ocupado, nodes[a], nodes[b], 0.22))
          edges.push([a, b]);
      }
    }
  }
  const malla = Object.keys(nodes);
  for (const [nombre, p] of Object.entries(especiales)) {
    nodes[nombre] = p;
    const cerca = malla
      .filter(
        (k) => Math.hypot(nodes[k].x - p.x, nodes[k].z - p.z) <= paso * 1.6,
      )
      .filter((k) => tramoLibre(ocupado, p, nodes[k], 0.22));
    for (const k of cerca) edges.push([nombre, k]);
  }
  return { nodes, edges };
}
