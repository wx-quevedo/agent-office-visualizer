/**
 * Adapter: our engine (GET /api/v1/agents/state) → scene model of the
 * Agent Office 3D port. Pure logic, tested in tests/oficina3d.test.ts.
 *
 * Besides the behaviour of each state (comportamiento.ts) it keeps what the
 * scene needs between reads: stable desks, who is already drawn (agents that
 * appear later walk in from the door; on the first load they are placed
 * directly), who is walking out, and closed desks (note with the question,
 * or an empty desk kept for one hour).
 */

import {
  cerradoVisible,
  detalleActual,
  loQuePide,
  nombreProyecto,
  recortar,
  type Agente,
} from "@/components/oficina/logica";
import {
  asignarDescanso,
  comportamiento,
  etiqueta,
  puntoDescanso,
  type Comportamiento,
} from "./comportamiento";
import type { AgentView, SubagentView } from "./store";

export { comportamiento } from "./comportamiento";

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

/** Memory of the adapter between reads. */
export interface EstadoAdaptador {
  puestos: Record<string, number>;
  /** Agents drawn in the previous read. */
  enEscena: string[];
  /** True until the first read: agents are placed, they do not walk in. */
  primera: boolean;
}

export function estadoInicial(): EstadoAdaptador {
  return { puestos: {}, enEscena: [], primera: true };
}

/** A desk of a closed agent (21): note with the question, or empty and kept. */
export interface EscritorioCerrado {
  seatIndex: number;
  sessionId: string;
  proyecto: string;
  cuenta: string | null;
  pregunta: string | null;
}

export interface Adaptado {
  vistas: AgentView[];
  cerrados: EscritorioCerrado[];
  estado: EstadoAdaptador;
  /** Agents that came back after leaving: forget that they left. */
  reentradas: string[];
}

const SALIDA = comportamiento(12, 0) as Comportamiento;

/**
 * @param salidos agents whose character already went out through the door
 *   (reported by the scene); they are not drawn while in 12 or 21.
 */
export function adaptar(
  agentes: Agente[],
  previo: EstadoAdaptador,
  ahora: number,
  salidos: ReadonlySet<string> = new Set(),
): Adaptado {
  const antes = new Set(previo.enEscena);
  const reentradas: string[] = [];
  const escena: Array<{
    a: Agente;
    c: Comportamiento;
    origen: "lugar" | "puerta";
  }> = [];
  const cerradosQueGuardan: Agente[] = [];

  for (const a of agentes) {
    const id = a.agente.session_id;
    const n = a.estado.numero;
    const c = comportamiento(n, a.indicadores.errores_seguidos);
    const nuevo = !previo.primera && !antes.has(id);
    if (c === null) {
      // 21 — closed. Walks out if it was drawn; its desk is kept while visible.
      if (antes.has(id) && !salidos.has(id))
        escena.push({ a, c: SALIDA, origen: "lugar" });
      if (cerradoVisible(a, ahora)) cerradosQueGuardan.push(a);
      continue;
    }
    if (n === 12 && (salidos.has(id) || nuevo)) continue; // already out, or appeared leaving
    if (salidos.has(id)) reentradas.push(id); // reopened: walks in again
    escena.push({ a, c, origen: nuevo ? "puerta" : "lugar" });
  }

  // Who holds a desk, in the engine order (closed desks keep theirs).
  const conPuesto = new Set([
    ...escena.map((x) => x.a.agente.session_id),
    ...cerradosQueGuardan.map((a) => a.agente.session_id),
  ]);
  const ids = agentes
    .map((a) => a.agente.session_id)
    .filter((id) => conPuesto.has(id));
  const puestos = asignarPuestos(previo.puestos, ids);

  const descanso = asignarDescanso(
    escena
      .filter((x) => x.c.destino === "sofa")
      .map((x) => ({
        id: x.a.agente.session_id,
        seatIndex: puestos[x.a.agente.session_id],
      })),
  );

  const vistas = escena.map(({ a, c, origen }): AgentView => {
    const id = a.agente.session_id;
    const desde = Date.parse(a.estado.desde);
    const subagents: SubagentView[] = Array.from(
      { length: a.subagentes_activos },
      (_, i) => ({
        key: `${id}-ayudante-${i}`,
        at: 0,
      }),
    );
    const lugar = descanso[id];
    const proyecto = nombreProyecto(a);
    return {
      id,
      folderName: proyecto,
      cuenta: a.agente.cuenta,
      seatIndex: puestos[id],
      status: c.status,
      destino: c.destino,
      pose: c.pose,
      monitor: c.monitor,
      origen,
      descanso: lugar
        ? { tipo: lugar.tipo, indice: lugar.indice, ...puntoDescanso(lugar) }
        : null,
      etiqueta: etiqueta(
        proyecto,
        a.estado.numero,
        a.indicadores.errores_seguidos,
        a.agente.cuenta,
      ),
      permission: c.espera === "permiso",
      question: c.espera === "pregunta",
      stuck: c.espera !== null && ahora - desde >= ESPERA_LARGA_MS,
      toolLabel: recortar(detalleActual(a), 48),
      toolCalls: Math.round((a.indicadores.herramientas_por_minuto ?? 0) * 5),
      subagents,
      inputTokens: a.indicadores.contexto_usado_pct ?? 0,
      contextWindow: 100,
      estado: a.estado,
      preguntaPendiente: a.pregunta_pendiente,
      lePide: c.espera === "permiso" ? (loQuePide(a)?.texto ?? null) : null,
      errores: a.indicadores.errores_seguidos ?? 0,
    };
  });

  const enEscena = new Set(vistas.map((v) => v.id));
  const cerrados: EscritorioCerrado[] = cerradosQueGuardan
    .filter((a) => !enEscena.has(a.agente.session_id)) // still walking out: no note yet
    .map((a) => ({
      seatIndex: puestos[a.agente.session_id],
      sessionId: a.agente.session_id,
      proyecto: nombreProyecto(a),
      cuenta: a.agente.cuenta,
      pregunta: a.pregunta_pendiente,
    }));

  return {
    vistas,
    cerrados,
    estado: { puestos, enEscena: [...enEscena], primera: false },
    reentradas,
  };
}

/** Header counters of the 3D view (closed agents are not counted). */
export function contar3d(agentes: Agente[]): {
  espera: number;
  trabajando: number;
  libres: number;
} {
  let espera = 0;
  let trabajando = 0;
  let libres = 0;
  for (const a of agentes) {
    const n = a.estado.numero;
    if (n === 21) continue;
    if (n === 13 || n === 14) espera++;
    else if ([1, 11, 12, 18, 19, 20].includes(n)) libres++;
    else trabajando++;
  }
  return { espera, trabajando, libres };
}
