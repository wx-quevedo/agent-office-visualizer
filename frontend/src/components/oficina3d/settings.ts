import { create } from "zustand";

// Scene settings (adapted from Agent Office 3D, MIT). Not persisted for now:
// /oficina/3d has no settings panel yet. Quality is chosen on mount from the
// screen width (phones: low, no shadows).

export type Quality = "high" | "low";

/** Quality → pixel density. Fewer pixels = the biggest GPU win. */
export function dprFor(q: Quality): number {
  return q === "low" ? 0.7 : 1;
}
/** Quality → shadow map refreshed every N frames. */
export function shadowEvery(q: Quality): number {
  return q === "low" ? 12 : 4;
}

function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export interface SettingsValues {
  /** Small idle animations and plant sway (PixelPerson, OfficeDecor). */
  reducedMotion: boolean;
  /** Pixel density and shadow refresh. */
  quality: Quality;
  /** Shadows (off on phones). */
  shadows: boolean;
  /** Label over each agent (AgentAvatar). */
  showLabels: boolean;
  /** Idle agents walk around the office (AgentAvatar). */
  wander: boolean;
  /** Idle agents meet each other (AgentAvatar + presence). */
  social: boolean;
}

interface SettingsState extends SettingsValues {
  set(values: Partial<SettingsValues>): void;
}

export const useSettings = create<SettingsState>()((set) => ({
  reducedMotion: prefersReducedMotion(),
  quality: "high",
  shadows: true,
  showLabels: true,
  wander: true,
  social: true,
  set: (values) => set(values),
}));
