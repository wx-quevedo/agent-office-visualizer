// ── Navigation (waypoint graph; adapted from Agent Office 3D, MIT) ──
// The graph comes from the active environment (entornos/): the Original one
// is the hand-made grid plus a door and an inner node per room; the others
// use a grid over the open room. Rebuilt when the environment changes.
// NODES and EDGES are live bindings: importers always see the current graph.

import { alCambiarEntorno, entornoActivo } from "../entornos/activo";
import { ROLE_ROOMS } from "../entornos/original";
import type { WP } from "../entornos/tipos";
import { blockedStatic } from "./collision";

export type { WP };

export let NODES: Record<string, WP> = {};
/** Graph edges (also used by the editor to protect the paths). */
export let EDGES: [string, string][] = [];
let ADJ: Record<string, string[]> = {};
let KEYS: string[] = [];

/** Builds the graph of the active environment (fixed boxes and base desks only). */
export function reconstruirGrafo(): void {
  const e = entornoActivo();
  const base = Array.from({ length: e.puestosBase }, (_, i) => e.puesto(i));
  const g = e.grafo(blockedStatic, base);
  NODES = g.nodes;
  EDGES = g.edges;
  ADJ = {};
  for (const k of Object.keys(NODES)) ADJ[k] = [];
  for (const [a, b] of EDGES) {
    ADJ[a].push(b);
    ADJ[b].push(a);
  }
  KEYS = Object.keys(NODES);
}

reconstruirGrafo();
alCambiarEntorno(() => reconstruirGrafo());

export function nearestNode(x: number, z: number): string {
  let best = KEYS[0];
  let bd = Infinity;
  for (const k of KEYS) {
    const n = NODES[k];
    const d = (n.x - x) ** 2 + (n.z - z) ** 2;
    if (d < bd) {
      bd = d;
      best = k;
    }
  }
  return best;
}

/** Shortest path (breadth first) between two nodes; empty when unreachable. */
export function pathBetween(from: string, to: string): WP[] {
  if (!NODES[from] || !NODES[to]) return [];
  if (from === to) return [NODES[to]];
  const prev: Record<string, string | null> = { [from]: null };
  const q = [from];
  while (q.length) {
    const cur = q.shift()!;
    if (cur === to) break;
    for (const n of ADJ[cur] ?? []) {
      if (!(n in prev)) {
        prev[n] = cur;
        q.push(n);
      }
    }
  }
  if (!(to in prev)) return [];
  const out: WP[] = [];
  let c: string | null = to;
  while (c) {
    out.unshift(NODES[c]);
    c = prev[c];
  }
  return out;
}

export function randomNodeKey(): string {
  return KEYS[Math.floor(Math.random() * KEYS.length)];
}

/** First trip after finishing work: the break room(s) of the environment. */
export function breakRoom(): string {
  const d = entornoActivo().paseo.descanso.filter((k) => NODES[k]);
  return d.length ? d[Math.floor(Math.random() * d.length)] : randomNodeKey();
}

/**
 * Where an idle agent walks. Original: a room that fits its role (25% any
 * node). Other environments: one of their walking spots (30% any node).
 */
export function idleDestination(role: string | undefined): string {
  const e = entornoActivo();
  if (e.clave === "original") {
    if (Math.random() < 0.25) return randomNodeKey();
    const rooms = (role && ROLE_ROOMS[role]) || e.paseo.destinos;
    return rooms[Math.floor(Math.random() * rooms.length)];
  }
  if (Math.random() < 0.3) return randomNodeKey();
  const d = e.paseo.destinos.filter((k) => NODES[k]);
  return d.length ? d[Math.floor(Math.random() * d.length)] : randomNodeKey();
}
