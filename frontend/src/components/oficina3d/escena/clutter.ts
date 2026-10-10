// ── Stol tartibsizligi ───────────────────────────────────────
// Ish qilgan sari stol to'lib boradi: qog'oz, ikkinchi krujka, stiker, g'ijimlangan
// qog'oz. Bu O'YLAB TOPILGAN bezak emas — manba HAQIQIY: agentning tool
// chaqiruvlari soni (`toolCalls`). Sessiya boshida stol toza, uzoq ishlagandan
// keyin to'lib ketadi — bir qarashda "kim ko'p ishlagan"i ko'rinadi.

/** Har daraja uchun kerakli tool chaqiruvlari soni. */
export const CLUTTER_TIERS = [5, 15, 30, 55] as const;
export const MAX_CLUTTER = CLUTTER_TIERS.length;

/** Tool chaqiruvlari → tartibsizlik darajasi (0 = toza stol … 4 = to'lib ketgan). */
export function clutterLevel(toolCalls: number): number {
  let n = 0;
  for (const t of CLUTTER_TIERS) if (toolCalls >= t) n++;
  return n;
}
