/**
 * Behaviour layer of the 3D office, separate from the engine state.
 * Pure logic, tested in tests/oficina3d.test.ts.
 *
 * state (1-21) + consecutive errors → where the character goes (destino),
 * what it does there (pose), what its label says, and the drawn badge on its
 * monitor. The scene components only read the result.
 */

import type { AgentStatus } from "./store";

/** Where the character goes. */
export type Destino = "escritorio" | "pasear" | "sofa" | "salida";

/** What the character does at its place. */
export type Pose =
  | "pensar" // hand on chin
  | "teclear" // typing
  | "quieto" // seated, still (waits for a program or an upload)
  | "brazoAlzado" // asks for permission: one arm up while it lasts
  | "mirarCamara" // asked a question: turns towards you
  | "libre"; // standing, walking or resting

/** Badge drawn over the monitor (no emojis). */
export type Monitor = "reloj" | "progreso" | null;

export interface Comportamiento {
  /** Colour and base animation of the original scene. */
  status: AgentStatus;
  destino: Destino;
  pose: Pose;
  /** Waiting for you: permission (13) or answer (14). */
  espera: "permiso" | "pregunta" | null;
  monitor: Monitor;
}

/** Work states: errors ≥ 1 there show the agent as "con errores". */
export const ESTADOS_TRABAJO = new Set([
  1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 16, 17,
]);

/**
 * 21 states → behaviour. 21 (closed) returns null: the character is not in
 * the scene (its desk may show a note, see escritoriosCerrados).
 */
export function comportamiento(
  numero: number,
  errores: number | null,
): Comportamiento | null {
  if (numero === 21) return null;
  const c = base(numero);
  if ((errores ?? 0) >= 1 && ESTADOS_TRABAJO.has(numero))
    return { ...c, status: "blocked" };
  return c;
}

function base(n: number): Comportamiento {
  const sentado = (
    status: AgentStatus,
    pose: Pose,
    monitor: Monitor = null,
  ): Comportamiento => ({
    status,
    destino: "escritorio",
    pose,
    espera: null,
    monitor,
  });
  switch (n) {
    case 1: // arrives: walks from the door to its desk (if it is new)
    case 2:
    case 3:
    case 4:
    case 7:
    case 9:
    case 10:
      return sentado("thinking", "pensar");
    case 5:
    case 6:
    case 8:
      return sentado("working", "teclear");
    case 13:
      return { ...sentado("review", "brazoAlzado"), espera: "permiso" };
    case 14:
      return { ...sentado("review", "mirarCamara"), espera: "pregunta" };
    case 15:
      return sentado("waiting", "quieto", "reloj");
    case 16:
      return sentado("waiting", "quieto", "progreso");
    case 17:
      return sentado("collab", "teclear");
    case 20: // comes back: walks to its desk
      return sentado("idle", "libre");
    case 19:
      return {
        status: "idle",
        destino: "sofa",
        pose: "libre",
        espera: null,
        monitor: null,
      };
    case 12:
      return {
        status: "idle",
        destino: "salida",
        pose: "libre",
        espera: null,
        monitor: null,
      };
    default: // 11, 18
      return {
        status: "idle",
        destino: "pasear",
        pose: "libre",
        espera: null,
        monitor: null,
      };
  }
}

// -- labels ------------------------------------------------------------------------

const ACTIVIDAD: Record<number, string> = {
  2: "Recibe encargo",
  3: "Pensando",
  4: "Leyendo",
  5: "Escribiendo",
  6: "Terminal",
  7: "Web",
  8: "App externa",
  9: "Planificando",
  10: "Compactando",
  15: "Esperando un programa",
  16: "Subiendo",
  17: "Con subagentes",
};

export interface Etiqueta {
  proyecto: string;
  /** Short activity while seated working; null when free (posture says it). */
  actividad: string | null;
  /** "Te pide permiso" | "Te preguntó" (dark border). */
  espera: string | null;
  errores: boolean;
  /** Demo Org account: the label shows the isotype (alt "Demo Org"); personal: nothing. */
  demo: boolean;
}

/**
 * The label only says what the posture does not show: walking = free,
 * seated = working. Free (1, 11, 12, 18, 19, 20): only the project.
 */
export function etiqueta(
  proyecto: string,
  numero: number,
  errores: number | null,
  cuenta: string | null,
): Etiqueta {
  const espera =
    numero === 13 ? "Te pide permiso" : numero === 14 ? "Te preguntó" : null;
  return {
    proyecto,
    actividad: espera ? null : (ACTIVIDAD[numero] ?? null),
    espera,
    errores: (errores ?? 0) >= 1 && ESTADOS_TRABAJO.has(numero),
    demo: cuenta === "demo",
  };
}

// -- break room sofa ------------------------------------------------------------------

export interface PuntoSofa {
  /** Where the character sits (or stands). */
  x: number;
  z: number;
  /** Facing (rotation.y of the character). */
  ry: number;
  /** Approach point in front of the seat, reachable on foot. */
  ax: number;
  az: number;
}

/**
 * The two sofas of the break room (OfficeDecor: against the far wall at
 * x = -1.8, z = 11.9 and 14.4, facing +x towards the camera): two seats each.
 * The approach point is in front of each seat.
 */
export const ASIENTOS_SOFA: PuntoSofa[] = [11.35, 12.45, 13.85, 14.95].map(
  (z) => ({ x: -1.7, z, ry: -Math.PI / 2, ax: -0.75, az: z }),
);

/** Corridor point between the door side and the sofas (avoids the coffee table). */
export const PASILLO_SOFA = { x: -0.75, z: 15.2 };

/** Standing spots near the sofas for agents that found no seat; they face the sofas. */
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

export type LugarDescanso = { tipo: "sofa" | "cerca"; indice: number };

/**
 * Resting agents (19), ordered by desk so the assignment is stable: the first
 * ones get a sofa seat, the rest stand nearby.
 */
export function asignarDescanso(
  descansan: Array<{ id: string; seatIndex: number }>,
): Record<string, LugarDescanso> {
  const orden = [...descansan].sort(
    (a, b) => a.seatIndex - b.seatIndex || a.id.localeCompare(b.id),
  );
  const out: Record<string, LugarDescanso> = {};
  orden.forEach((a, i) => {
    out[a.id] =
      i < ASIENTOS_SOFA.length
        ? { tipo: "sofa", indice: i }
        : {
            tipo: "cerca",
            indice: (i - ASIENTOS_SOFA.length) % LUGARES_CERCA.length,
          };
  });
  return out;
}

export function puntoDescanso(l: LugarDescanso): PuntoSofa {
  return l.tipo === "sofa" ? ASIENTOS_SOFA[l.indice] : LUGARES_CERCA[l.indice];
}

// -- entrance -------------------------------------------------------------------------

/** Entrance door on the west wall (OfficeDecor draws it) and the point inside it. */
export const PUERTA = { x: -22.55, z: 4 };
export const ENTRADA = { x: -21.2, z: 4 };
