import { seatFor } from "./roles";

// ── To'qnashuv (AABB to'siqlar) ──────────────────────────────
// Devor/oyna/mebel — to'rtburchak to'siqlar. Kamera ham personaj ham
// bularga uriladi (arvohdek o'tmaydi). Tez: ~120 to'rtburchak, sof math.

export interface Rect {
  x0: number;
  x1: number;
  z0: number;
  z1: number;
}

const B: Rect[] = [];
const T = 0.16; // devor yarim-qalinligi
function r(x0: number, x1: number, z0: number, z1: number): void {
  B.push({
    x0: Math.min(x0, x1),
    x1: Math.max(x0, x1),
    z0: Math.min(z0, z1),
    z1: Math.max(z0, z1),
  });
}

// ── Perimetr devorlar ──
r(-23, 23, -16.2, -15.8);
r(-23, 23, 15.8, 16.2);
r(-23.2, -22.8, -16, 16);
r(22.8, 23.2, -16, 16);

// ── Xona old devorlari (eshik teshigi bilan) + bo'luvchilar ──
type Room = { x0: number; x1: number; cx: number; door: number };
const top: Room[] = [
  { x0: -23, x1: -9, cx: -16, door: 2.6 },
  { x0: -9, x1: -1, cx: -5, door: 2 },
  { x0: -1, x1: 8, cx: 3.5, door: 2 },
  { x0: 8, x1: 15, cx: 11.5, door: 2 },
  { x0: 15, x1: 23, cx: 19, door: 2 },
];
for (const m of top) {
  r(m.x0, m.cx - m.door / 2, -9.5 - T, -9.5 + T);
  r(m.cx + m.door / 2, m.x1, -9.5 - T, -9.5 + T);
}
for (const x of [-9, -1, 8, 15]) r(x - T, x + T, -16, -9.5);

const bot: Room[] = [
  { x0: -23, x1: -11, cx: -17, door: 2.4 },
  { x0: -11, x1: -3, cx: -7, door: 2 },
  { x0: -3, x1: 7, cx: 2, door: 2 },
  { x0: 7, x1: 15, cx: 11, door: 2 },
  { x0: 15, x1: 23, cx: 19, door: 2 },
];
for (const m of bot) {
  r(m.x0, m.cx - m.door / 2, 9.5 - T, 9.5 + T);
  r(m.cx + m.door / 2, m.x1, 9.5 - T, 9.5 + T);
}
for (const x of [-11, -3, 7, 15]) r(x - T, x + T, 9.5, 16);

// ── Agent stollari — DINAMIK (faqat band o'rindiqlar) ──
// Stol collision'i faqat renderlangan (band) stollar uchun bo'ladi. Aks holda
// bo'sh overflow o'rindiqlari markaziy yo'lakda "fantom devor" hosil qilardi.
// Stol 1.5×0.8; to'siq stol yo'nalishiga (ry) qarab aylanadi.
// Foydalanuvchi joylashtirgan mebel to'siqlari (Layout editor) — dinamik.
let placedRects: Rect[] = [];
export function setPlacedRects(rects: Rect[]): void {
  placedRects = rects;
}

let seatRects: Rect[] = [];
export function setActiveSeats(seatIndexes: number[]): void {
  seatRects = seatIndexes.map((i) => {
    const s = seatFor(i);
    const hx =
      Math.abs(0.75 * Math.cos(s.ry)) + Math.abs(0.4 * Math.sin(s.ry)) + 0.05;
    const hz =
      Math.abs(0.75 * Math.sin(s.ry)) + Math.abs(0.4 * Math.cos(s.ry)) + 0.05;
    return { x0: s.x - hx, x1: s.x + hx, z0: s.z - hz, z1: s.z + hz };
  });
}

// ── Statik mebel (doim bor) ──
// Reception
r(-1.7, 1.7, 7.0, 8.0);
// Server xonasi (rack qatorlari) — orqa qator devorga taqaldi (z=-15.4)
r(-22, -10, -16.0, -14.8);
r(-22, -10, -11.6, -10.4);
// Oshxona — peshtaxta devorga taqaldi (z=-15.5)
r(-7.6, -2.4, -16.0, -14.8);
// Majlis stoli (yuqori)
r(1.9, 5.1, -14.1, -10.9);
// Xojatxona
r(9, 12.6, -16, -13.8);
r(13.2, 15, -16, -14.6);
// glassA stol
r(18, 20, -13.8, -11.8);
// Kutubxona (javonlar + stol) — old qator devorga taqaldi (z=15.68)
r(-22.6, -14.4, 15.4, 15.9);
r(-22.6, -14.4, 10.4, 11.6);
r(-14.8, -12.2, 12, 14);
// Fokus stoli
r(-7.8, -6.2, 14, 15.2);
// Dam olish (divanlar + stol)
r(0.5, 3.5, 14.2, 15.8);
r(4.6, 6.4, 12, 14);
r(1.4, 2.6, 12.4, 13.6);
// glassB stollari
r(8.7, 10.3, 13.8, 15.2);
r(11.7, 13.3, 13.8, 15.2);
// glassC stol
r(18, 20, 12, 14);
// ── Turgan chiroqlar + pol o'simliklari (agent ular ustidan o'tmasin) ──
// Hammasi nav-qirralaridan chetда joylashtirilgan (OfficeDecor), shu bois bu
// kichik to'siqlar yo'l grafini uzmaydi — faqat "arvohdek o'tishни" to'xtatadi.
for (const [x, z] of [
  [-7, 5],
  [7, -5],
] as [number, number][])
  r(x - 0.22, x + 0.22, z - 0.22, z + 0.22); // chiroqlar
for (const [x, z] of [
  [-1.5, 5],
  [1.5, 5],
  [-16, 6],
  [16, 6],
  [-16, -6],
  [16, -6],
] as [number, number][])
  r(x - 0.28, x + 0.28, z - 0.28, z + 0.28); // o'simliklar

/** (x,z) nuqta radius r bilan biror to'siqga tegadimi? (statik mebel + band stollar) */
export function blocked(x: number, z: number, rad: number): boolean {
  for (const b of B) {
    if (x > b.x0 - rad && x < b.x1 + rad && z > b.z0 - rad && z < b.z1 + rad)
      return true;
  }
  for (const b of seatRects) {
    if (x > b.x0 - rad && x < b.x1 + rad && z > b.z0 - rad && z < b.z1 + rad)
      return true;
  }
  for (const b of placedRects) {
    if (x > b.x0 - rad && x < b.x1 + rad && z > b.z0 - rad && z < b.z1 + rad)
      return true;
  }
  return false;
}

/** Harakatni o'qlar bo'yicha alohida qo'llaydi (devor bo'ylab sirg'anadi).
 *  QOCHISH: agar personaj ALLAQACHON to'siq ichida bo'lsa (masalan ustiga
 *  dinamik o'rindiq/mebel to'siqi paydo bo'lgan), har yo'nalish bloklanib
 *  abadiy tiqilib qolardi — shu holda harakatga ruxsat beramiz (chiqib ketsin). */
export function slide(
  x: number,
  z: number,
  dx: number,
  dz: number,
  rad: number,
): { x: number; z: number } {
  if (blocked(x, z, rad)) return { x: x + dx, z: z + dz };
  let nx = x;
  let nz = z;
  if (dx !== 0 && !blocked(x + dx, z, rad)) nx = x + dx;
  if (dz !== 0 && !blocked(nx, z + dz, rad)) nz = z + dz;
  return { x: nx, z: nz };
}
