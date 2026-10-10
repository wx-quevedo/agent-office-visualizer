/**
 * Adapter: our engine (GET /api/v1/agents/state) → scene model of the
 * Agent Office 3D port. Pure logic, tested in tests/oficina3d.test.ts.
 */

import {
  detalleActual,
  loQuePide,
  nombreProyecto,
  recortar,
  type Agente,
} from "@/components/oficina/logica";
import type { AgentStatus, AgentView, SubagentView } from "./store";

export interface Comportamiento {
  status: AgentStatus;
  permission: boolean;
  question: boolean;
  resting: boolean;
  background: boolean;
}

/** Work states where consecutive errors show the agent as "blocked". */
const TRABAJO = new Set([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 16, 17]);

/**
 * State (1-21) and consecutive errors → scene behaviour. Returns null for 21
 * (closed agents are not drawn in the scene for now).
 *
 * 2, 3, 4, 7, 9 → thinking (hand on chin) · 5, 6, 8 → working (typing)
 * 13, 14 → review (seated, with a badge) · 15, 16 → waiting (seated)
 * 17 → collab · 11, 18, 20 → idle (stands up and walks)
 * 19 → idle, goes to the break room · 21 → not in the scene
 * Also: 1 (arrives) and 10 (compacting) → thinking; 12 (leaving) → idle.
 * Errors ≥ 1 in a work state → blocked (13 and 14 always win).
 */
export function comportamiento(
  numero: number,
  errores: number | null,
): Comportamiento | null {
  if (numero === 21) return null;
  const base: Comportamiento = {
    status: "idle",
    permission: numero === 13,
    question: numero === 14,
    resting: numero === 19,
    background: numero === 15 || numero === 16,
  };
  if (numero === 13 || numero === 14) return { ...base, status: "review" };
  if ((errores ?? 0) >= 1 && TRABAJO.has(numero))
    return { ...base, status: "blocked" };
  if ([1, 2, 3, 4, 7, 9, 10].includes(numero))
    return { ...base, status: "thinking" };
  if ([5, 6, 8].includes(numero)) return { ...base, status: "working" };
  if (numero === 15 || numero === 16) return { ...base, status: "waiting" };
  if (numero === 17) return { ...base, status: "collab" };
  return base; // 11, 12, 18, 19, 20
}

/**
 * Stable desks: an agent keeps its desk while it exists; a new agent takes the
 * lowest free desk. `prev` is not modified.
 */
export function asignarPuestos(
  prev: Record<string, number>,
  ids: string[],
): Record<string, number> {
  const out: Record<string, number> = {};
  const ocupados = new Set<number>();
  for (const id of ids) {
    if (prev[id] !== undefined) {
      out[id] = prev[id];
      ocupados.add(prev[id]);
    }
  }
  let libre = 0;
  for (const id of ids) {
    if (out[id] !== undefined) continue;
    while (ocupados.has(libre)) libre++;
    out[id] = libre;
    ocupados.add(libre);
  }
  return out;
}

/** Waiting for you for this long shows the "te espera hace rato" badge. */
export const ESPERA_LARGA_MS = 3 * 60 * 1000;

export interface Adaptado {
  vistas: AgentView[];
  puestos: Record<string, number>;
}

export function adaptar(
  agentes: Agente[],
  puestosPrevios: Record<string, number>,
  ahora: number,
): Adaptado {
  const enEscena = agentes
    .map((a) => ({
      a,
      c: comportamiento(a.estado.numero, a.indicadores.errores_seguidos),
    }))
    .filter((x): x is { a: Agente; c: Comportamiento } => x.c !== null);
  // Order by first appearance keeps desks stable; the engine sends most recent first.
  const ids = enEscena.map((x) => x.a.agente.session_id);
  const puestos = asignarPuestos(puestosPrevios, ids);
  const vistas = enEscena.map(({ a, c }): AgentView => {
    const id = a.agente.session_id;
    const desde = Date.parse(a.estado.desde);
    const subagents: SubagentView[] = Array.from(
      { length: a.subagentes_activos },
      (_, i) => ({
        key: `${id}-ayudante-${i}`,
        at: 0,
      }),
    );
    return {
      id,
      folderName: nombreProyecto(a),
      cuenta: a.agente.cuenta,
      seatIndex: puestos[id],
      status: c.status,
      permission: c.permission,
      question: c.question,
      stuck: (c.permission || c.question) && ahora - desde >= ESPERA_LARGA_MS,
      resting: c.resting,
      background: c.background,
      toolLabel: recortar(detalleActual(a), 48),
      toolCalls: Math.round((a.indicadores.herramientas_por_minuto ?? 0) * 5),
      subagents,
      inputTokens: a.indicadores.contexto_usado_pct ?? 0,
      contextWindow: 100,
      estado: a.estado,
      preguntaPendiente: a.pregunta_pendiente,
      lePide: c.permission ? (loQuePide(a)?.texto ?? null) : null,
      errores: a.indicadores.errores_seguidos ?? 0,
    };
  });
  return { vistas, puestos };
}

/** Header counters of the 3D view. */
export function contar3d(agentes: Agente[]): {
  espera: number;
  trabajando: number;
  inactivos: number;
} {
  let espera = 0;
  let trabajando = 0;
  let inactivos = 0;
  for (const a of agentes) {
    const n = a.estado.numero;
    if (n === 21) continue;
    if (n === 13 || n === 14) espera++;
    else if ([11, 18, 19, 20].includes(n)) inactivos++;
    else trabajando++;
  }
  return { espera, trabajando, inactivos };
}

/** Short account name for labels. */
export function cuentaCorta(cuenta: string | null): string {
  if (cuenta === "demo") return "Demo Org";
  if (cuenta === "personal") return "personal";
  return cuenta ?? "";
}
