/**
 * SubagentCountBadge
 *
 * Pixel-style counter of active subagents (SubagentStart without its
 * SubagentStop), drawn over the main agent instead of separate characters.
 * Square corners, hard border and a hard drop shadow keep it in the pixel
 * look; colors match the existing Command Center subagent badge.
 * Renders nothing when the count is 0.
 */

"use client";

import { memo, useCallback, type ReactNode } from "react";
import type { Graphics } from "pixi.js";

const BADGE_H = 24;
const DIGIT_W = 12;
const PAD_X = 8;
const BORDER = 2;
const SHADOW = 2;

const BG_COLOR = 0x111827;
const ACCENT_COLOR = 0xf59e0b;

/** Badge width for a given count (grows with the number of digits). */
export function subagentBadgeWidth(count: number): number {
  return String(count).length * DIGIT_W + PAD_X * 2;
}

interface SubagentCountBadgeProps {
  count: number;
  /** Badge center X. */
  x: number;
  /** Badge center Y. */
  y: number;
  /** Draw scale (matches the 2x main agent so the number stays legible). */
  scale?: number;
}

function SubagentCountBadgeComponent({
  count,
  x,
  y,
  scale = 1,
}: SubagentCountBadgeProps): ReactNode {
  const w = subagentBadgeWidth(count);

  const draw = useCallback(
    (g: Graphics) => {
      g.clear();
      // Hard drop shadow (no blur).
      g.rect(-w / 2 + SHADOW, -BADGE_H / 2 + SHADOW, w, BADGE_H);
      g.fill({ color: 0x000000, alpha: 0.6 });
      // Border then body: two filled rects instead of a stroke keeps edges
      // on whole pixels.
      g.rect(-w / 2, -BADGE_H / 2, w, BADGE_H);
      g.fill({ color: ACCENT_COLOR });
      g.rect(
        -w / 2 + BORDER,
        -BADGE_H / 2 + BORDER,
        w - BORDER * 2,
        BADGE_H - BORDER * 2,
      );
      g.fill({ color: BG_COLOR });
    },
    [w],
  );

  if (count <= 0) return null;

  return (
    <pixiContainer x={Math.round(x)} y={Math.round(y)} scale={scale}>
      <pixiGraphics draw={draw} />
      {/* Text rendered at 2x and scaled down for sharpness */}
      <pixiContainer y={1} scale={0.5}>
        <pixiText
          text={String(count)}
          anchor={0.5}
          resolution={2 * scale}
          style={{
            fontFamily: "monospace",
            fontSize: 36,
            fill: ACCENT_COLOR,
            fontWeight: "bold",
          }}
        />
      </pixiContainer>
    </pixiContainer>
  );
}

export const SubagentCountBadge = memo(SubagentCountBadgeComponent);

/** Badge height at scale 1, for callers that stack it above other labels. */
export const SUBAGENT_BADGE_HEIGHT = BADGE_H;
