import { create } from "zustand";

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
  /** Waiting for your permission (13). */
  permission: boolean;
  /** Waiting for your answer (14). */
  question: boolean;
  /** Waiting for you for 3+ minutes. */
  stuck: boolean;
  /** Resting in the break room because you are away (19). */
  resting: boolean;
  /** Waiting for a program or an upload (15, 16). */
  background: boolean;
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
