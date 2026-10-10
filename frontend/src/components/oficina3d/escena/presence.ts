import { entornoActivo } from "../entornos/activo";
import { NODES } from "./nav";

// ── Agent "hozirligi" reyestri (ijtimoiy hayot uchun) ────────
// Agentlar bir-birini ko'rishi (yaqinlashib uchrashishi) uchun modul-darajali
// registr. ZUSTAND EMAS — har freym yoziladi/o'qiladi, re-render bo'lmasligi
// kerak. Faqat DEKORATIV hayot: uchrashuv = emoji imo-ishora ().

export interface Presence {
  id: string;
  x: number;
  z: number;
  idle: boolean;
  metAt: number;
}
const reg = new Map<string, Presence>();

/** Har agent o'z joyi + bo'sh holati + uchrashuvга yetgan payti (metAt) bildiradi. */
export function report(
  id: string,
  x: number,
  z: number,
  idle: boolean,
  metAt = 0,
): void {
  const p = reg.get(id);
  if (p) {
    p.x = x;
    p.z = z;
    p.idle = idle;
    p.metAt = metAt;
  } else reg.set(id, { id, x, z, idle, metAt });
}
export function presenceOf(id: string): Presence | undefined {
  return reg.get(id);
}
export function unreport(id: string): void {
  reg.delete(id);
  clearMeeting(id);
}

/** Agent-agent collision: (x,z) boshqa (id emas) agentга rad ichida yaqinmi? */
export function blockedByAgent(
  id: string,
  x: number,
  z: number,
  rad: number,
): boolean {
  const r2 = rad * rad;
  for (const p of reg.values()) {
    if (p.id === id) continue;
    const dx = p.x - x,
      dz = p.z - z;
    if (dx * dx + dz * dz < r2) return true;
  }
  return false;
}

// ── Uchrashuvlar ─────────────────────────────────────────────
// Uchrashuv = umumiy "gather" nav-tuguni + har agentга ALOHIDA joy (side: chap/
// o'ng) → yopishmaydi, orasida masofa bo'ladi. Emote FAQAT ikkovi ham yetganда.
export interface Meet {
  partner: string;
  point: string;
  side: number;
  until: number;
}
const meets = new Map<string, Meet>();
// Band hub'lar — bir hub'ga BIR juft. Ikki juft bir joyni tanlab, bir-birini
// bloklab 30s "qotishi"ning oldini oladi (R5).
const occupiedHubs = new Set<string>();

export function meetingOf(id: string): Meet | null {
  return meets.get(id) ?? null;
}
/** Uchrashuvni tozalaydi — HAR IKKALA tomonни ham (sherikda "osilib" qolgan
 *  yozuv qolmasin, R4) va hub'ni bo'shatadi. */
export function clearMeeting(id: string): void {
  const m = meets.get(id);
  if (!m) return;
  meets.delete(id);
  const pm = meets.get(m.partner);
  if (pm && pm.partner === id) meets.delete(m.partner);
  occupiedHubs.delete(m.point);
}

// Ijtimoiy uchrashuv joylari (xona ichki tugunlari). Katta ofisda tasodifiy
// yaqinlashish bo'lmagani uchun umumiy hub'ga chaqiramiz ("tanaffusга chiqishdi").
// Meeting points come from the active environment.
const socialHubs = (): string[] =>
  entornoActivo().encuentros.filter((h) => NODES[h]);

/** Bo'sh, juftlashmagan sherik izlaydi. Faqat KICHIK id tashabbus qiladi.
 *  Ikkoviga umumiy hub + qarama-qarshi tomon (side ±1) beriladi. */
export function seekMeeting(
  id: string,
  x: number,
  z: number,
  now: number,
): Meet | null {
  const mine = meets.get(id);
  if (mine) return mine;
  const me = reg.get(id);
  if (!me || !me.idle) return null;
  let partner: Presence | null = null;
  for (const p of reg.values()) {
    if (p.id === id || !p.idle || meets.has(p.id)) continue;
    if (!partner || p.id < partner.id) partner = p;
  }
  if (!partner || id > partner.id) return null;
  const mx = (x + partner.x) / 2,
    mz = (z + partner.z) / 2;
  let node = "",
    bd = Infinity;
  for (const h of socialHubs()) {
    if (occupiedHubs.has(h)) continue; // band hub — boshqa juftga qoldiramiz
    const n = NODES[h];
    const d = (n.x - mx) ** 2 + (n.z - mz) ** 2;
    if (d < bd) {
      bd = d;
      node = h;
    }
  }
  if (!node) return null; // barcha hub band — hozircha uchrashuv yo'q
  const until = now + 18; // xavfsizlik timeout'i (yurib borish + ~6s suhbat)
  occupiedHubs.add(node);
  meets.set(id, { partner: partner.id, point: node, side: -1, until });
  meets.set(partner.id, { partner: id, point: node, side: 1, until });
  return meets.get(id)!;
}

// Uchrashuvдаги turish joyi — hub markazidan `side` bo'yicha x-siljish
// (ikkovi ~1.1m masofada yonma-yon; bir-biriga qaraydi).
export const MEET_OFFSET = 0.55;
export function meetSpot(m: Meet): { x: number; z: number } {
  const n = NODES[m.point];
  return { x: n.x + m.side * MEET_OFFSET, z: n.z };
}

/** Sinov/diagnostika uchun — reyestrni tozalaydi. */
export function _reset(): void {
  reg.clear();
  meets.clear();
  occupiedHubs.clear();
}
