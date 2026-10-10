import { create } from "zustand";
import type {
  Destino,
  Etiqueta,
  Monitor,
  Pose,
  PuntoSofa,
} from "./comportamiento";
import type { EscritorioCerrado } from "./adaptador";
import type { PuntoFila } from "./entornos/tipos";

// ── Scene state of /oficina/3d (replaces the Agent Office 3D store) ──
// Filled by the adapter from GET /api/v1/agents/state; the scene components
// only read it. Ids are our session_id strings.

export type AgentStatus =
  | "idle"
  | "thinking"
  | "working"
  | "review"
  | "blocked"
  | "collab"
  /** Seated, waiting for a program or an upload (15, 16). */
  | "waiting";

export interface SubagentView {
  key: string;
  label?: string;
  kind?: string;
  at: number;
}

export interface AgentView {
  id: string;
  folderName: string;
  /** "personal" | "demo" | null */
  cuenta: string | null;
  customName?: string;
  role?: string;
  seatIndex: number;
  status: AgentStatus;
  /** Behaviour layer (comportamiento.ts): where it goes and what it does. */
  destino: Destino;
  pose: Pose;
  /** Drawn badge over the monitor (15 hourglass, 16 progress bar). */
  monitor: Monitor;
  /** "puerta": appeared after the first load, walks in from the entrance. */
  origen: "lugar" | "puerta";
  /** Resting (19): sofa seat or a standing spot nearby. */
  descanso: (PuntoSofa & { tipo: "sofa" | "cerca"; indice: number }) | null;
  /** Where it waits for you standing: the counter queue (Sala de control) or the door of its cabin (Cabinas), or null. */
  fila: PuntoFila | null;
  etiqueta: Etiqueta;
  /** Waiting for your permission (13). */
  permission: boolean;
  /** Waiting for your answer (14). */
  question: boolean;
  /** Waiting for you for 3+ minutes. */
  stuck: boolean;
  permissionMode?: string;
  toolLabel?: string;
  toolCalls: number;
  subagents: SubagentView[];
  /** Context usage: inputTokens / contextWindow (we send the percentage). */
  inputTokens: number;
  contextWindow: number;
  estado: { numero: number; nombre: string; desde: string };
  preguntaPendiente: string | null;
  lePide: string | null;
  errores: number;
}

export type CameraMode = "iso" | "fpv";

interface OfficeState {
  agents: Record<string, AgentView>;
  order: string[];
  selectedId: string | null;
  hoveredId: string | null;
  cameraMode: CameraMode;
  /** You are present (presence of the engine): you sit at your desk. */
  presente: boolean;
  setPresente(v: boolean): void;
  /** Owner of each used group (cabin, island): project or GRUPO_GENERAL. */
  grupos: Record<number, string>;
  setGrupos(g: Record<number, string>): void;
  /** Desks of closed agents (note with the question, or empty and kept). */
  cerrados: EscritorioCerrado[];
  /** Agents whose character already went out through the door. */
  salidos: Set<string>;
  setCerrados(list: EscritorioCerrado[]): void;
  marcarSalido(id: string): void;
  olvidarSalidos(ids: string[]): void;
  /** Opens the agent detail (/oficina?agente=<id>); set by the page. */
  abrir: (id: string) => void;
  setAbrir(f: (id: string) => void): void;
  setAgents(list: AgentView[]): void;
  /** Click on an agent or a desk: opens its detail. */
  select(id: string | null): void;
  hover(id: string | null): void;
}

export const useOffice = create<OfficeState>()((set, get) => ({
  agents: {},
  order: [],
  selectedId: null,
  hoveredId: null,
  cameraMode: "iso",
  presente: false,
  setPresente: (v) => {
    if (get().presente !== v) set({ presente: v });
  },
  grupos: {},
  setGrupos: (g) => {
    if (JSON.stringify(g) !== JSON.stringify(get().grupos)) set({ grupos: g });
  },
  cerrados: [],
  salidos: new Set<string>(),
  setCerrados: (list) => {
    if (JSON.stringify(list) !== JSON.stringify(get().cerrados))
      set({ cerrados: list });
  },
  marcarSalido: (id) => {
    if (get().salidos.has(id)) return;
    set({ salidos: new Set([...get().salidos, id]) });
  },
  olvidarSalidos: (ids) => {
    if (!ids.some((id) => get().salidos.has(id))) return;
    set({
      salidos: new Set([...get().salidos].filter((id) => !ids.includes(id))),
    });
  },
  abrir: () => undefined,
  setAbrir: (f) => set({ abrir: f }),
  setAgents: (list) => {
    const prev = get().agents;
    const agents: Record<string, AgentView> = {};
    for (const a of list) {
      const old = prev[a.id];
      // Keep the same object when nothing changed (memoized avatars do not re-render).
      agents[a.id] = old && JSON.stringify(old) === JSON.stringify(a) ? old : a;
    }
    const order = list.map((a) => a.id);
    const sameOrder =
      order.length === get().order.length &&
      order.every((id, i) => id === get().order[i]);
    set({ agents, order: sameOrder ? get().order : order });
  },
  select: (id) => {
    if (id) get().abrir(id);
  },
  hover: (id) => set({ hoveredId: id }),
}));
