import type { AgentStatus } from "../store";

// ── Agent badges (adapted from Agent Office 3D, MIT) ──
// Every badge comes from an OBSERVED state, never an invented mood. Short
// texts instead of the original emojis (Washington's rule: no emojis):
//   error        → consecutive tool errors (status "blocked")
//   esperaLarga  → waiting for you (13/14) for 3+ minutes
//   contexto     → context usage at 85%+
//   pensando     → 25 s+ thinking without a break
//   listo        → the turn ended (work → idle), for a short time
//   charla       → two idle agents meeting

export type Distintivo =
  "" | "error" | "esperaLarga" | "contexto" | "pensando" | "listo" | "charla";

/** "Hot" context threshold (inputTokens / contextWindow). */
export const CONTEXT_HOT = 0.85;
/** Continuous thinking for this long shows the "pensando" badge. */
export const LONG_THINK_MS = 25000;
/** How long temporary badges stay. */
export const EMOTE_MS = { done: 3200, hot: 6000 } as const;

export function contextHot(
  inputTokens: number,
  contextWindow: number,
): boolean {
  if (!(contextWindow > 0)) return false;
  return inputTokens / contextWindow >= CONTEXT_HOT;
}

export interface EmoteInput {
  meeting?: "" | "charla";
  status: AgentStatus;
  stuck?: boolean;
  hot?: boolean;
  timed?: Distintivo;
}

/** Priority: meeting → error → long wait → full context → timed. */
export function emoteFor(o: EmoteInput): Distintivo {
  if (o.meeting) return o.meeting;
  if (o.status === "blocked") return "error";
  if (o.stuck) return "esperaLarga";
  if (o.hot) return "contexto";
  return o.timed || "";
}
