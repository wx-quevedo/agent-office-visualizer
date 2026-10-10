/**
 * Shared store constants and helpers (ARC-005).
 * Used by bossSlice, bubbleSlice, agentSlice, and the gameStore reset variants.
 */
import type { Position } from "@/types";
import { BOSS_POSITION as BOSS_ANCHOR } from "@/constants/positions";
import type { BubbleState, BossAnimationState } from "./types";

export const BOSS_POSITION: Position = BOSS_ANCHOR;

export const createEmptyBubbleState = (): BubbleState => ({
  content: null,
  displayStartTime: null,
  queue: [],
});

export const initialBossState: BossAnimationState = {
  backendState: "idle",
  position: BOSS_POSITION,
  bubble: createEmptyBubbleState(),
  inUseBy: null,
  currentTask: null,
  isTyping: false,
};
