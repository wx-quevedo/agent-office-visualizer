/**
 * Behaviour layer of the 3D office, separate from the engine state.
 * Pure logic, tested in tests/oficina3d.test.ts.
 *
 * state (1-21) + consecutive errors → where the character goes (destino),
 * what it does there (pose), what its label says, and the drawn badge on its
 * monitor. The scene components only read the result.
 */

import { entornoActivo } from "./entornos/activo";
import type { PuntoSofa } from "./entornos/tipos";
import type { AgentStatus } from "./store";

/** Where the character goes. */
/** "fila": queueing at the counter of the environment (13 and 14 in Sala de control). */
export type Destino = "escritorio" | "pasear" | "sofa" | "salida" | "fila";

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
// The places come from the active environment (entornos/); the Original ones
// are re-exported here for compatibility.

export type { PuntoSofa } from "./entornos/tipos";
export {
  ASIENTOS_SOFA,
  ENTRADA,
  LUGARES_CERCA,
  PASILLO_SOFA,
  PUERTA,
} from "./entornos/original";

export type LugarDescanso = { tipo: "sofa" | "cerca"; indice: number };

/**
 * Resting agents (19), ordered by desk so the assignment is stable: the first
 * ones get a sofa seat of the active environment, the rest stand nearby.
 */
export function asignarDescanso(
  descansan: Array<{ id: string; seatIndex: number }>,
): Record<string, LugarDescanso> {
  const { asientos, cerca } = entornoActivo().descanso;
  const orden = [...descansan].sort(
    (a, b) => a.seatIndex - b.seatIndex || a.id.localeCompare(b.id),
  );
  const out: Record<string, LugarDescanso> = {};
  orden.forEach((a, i) => {
    out[a.id] =
      i < asientos.length
        ? { tipo: "sofa", indice: i }
        : { tipo: "cerca", indice: (i - asientos.length) % cerca.length };
  });
  return out;
}

export function puntoDescanso(l: LugarDescanso): PuntoSofa {
  const { asientos, cerca } = entornoActivo().descanso;
  return l.tipo === "sofa" ? asientos[l.indice] : cerca[l.indice];
}
