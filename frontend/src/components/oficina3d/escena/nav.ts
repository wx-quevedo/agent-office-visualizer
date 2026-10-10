// ── Ofis navigatsiyasi (waypoint grafi, katta ofis) ─────────
// Markaziy grid + har xonaning eshik/ich nuqtasi. Agentlar bo'sh turganda
// shular orasida yuradi (eshiklardan xonalarga kiradi).

import { blocked } from "./collision";

export interface WP {
  x: number;
  z: number;
}

export const NODES: Record<string, WP> = {};
/** Graf qirralari — sinov (nav-validatsiya) uchun ham eksport qilinadi. */
export const EDGES: [string, string][] = [];

// Markaziy grid (ochiq yo'laklar — agent stollari x=±5.5, z=-3.2/0/3.2 va
// yon stollar x=±13 dan chetda: qatorlar ular orasidagi yo'laklarda).
const CX = [-17, -9, 0, 9, 17];
const CZ = [-6.5, -1.8, 1.8, 6.5];
const grid: string[][] = [];
/** Faqat markaziy grid tugunlari. (DIQQAT: "glassA_d" ham "g" bilan boshlanadi —
 *  shuning uchun startsWith("g") ISHLATMAYMIZ, aniq ro'yxat yuritamiz.) */
const GRID_KEYS: string[] = [];
CX.forEach((x, i) => {
  grid[i] = [];
  CZ.forEach((z, j) => {
    const k = `g${i}_${j}`;
    NODES[k] = { x, z };
    grid[i][j] = k;
    GRID_KEYS.push(k);
  });
});
for (let i = 0; i < CX.length; i++) {
  for (let j = 0; j < CZ.length; j++) {
    if (i + 1 < CX.length) EDGES.push([grid[i][j], grid[i + 1][j]]);
    if (j + 1 < CZ.length) EDGES.push([grid[i][j], grid[i][j + 1]]);
  }
}

// Xonalar: [kalit, markaz-x, tomon]
const ROOMS: [string, number, "top" | "bottom"][] = [
  ["server", -16, "top"],
  ["kitchen", -5, "top"],
  ["meeting", 3.5, "top"],
  ["bathroom", 11.5, "top"],
  ["glassA", 19, "top"],
  ["library", -17, "bottom"],
  ["focus", -7, "bottom"],
  ["lounge", 2, "bottom"],
  ["glassB", 11, "bottom"],
  ["glassC", 19, "bottom"],
];
/** Ikki nuqta orasidagi to'g'ri kesma to'siqsizmi? (agent radiusidan kengroq
 *  zaxira bilan — qirra tanlashda ishonchli bo'lsin). */
function clearPath(
  ax: number,
  az: number,
  bx: number,
  bz: number,
  rad = 0.22,
): boolean {
  const d = Math.hypot(bx - ax, bz - az);
  const steps = Math.max(2, Math.ceil(d / 0.1));
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    if (blocked(ax + (bx - ax) * t, az + (bz - az) * t, rad)) return false;
  }
  return true;
}

for (const [key, cx, side] of ROOMS) {
  const doorZ = side === "top" ? -9.0 : 9.0;
  const inward = side === "top" ? -1 : 1;
  // Ichki tugun: eshikdan ichkariga YURIB, birinchi to'siqgacha eng chuqur bo'sh
  // nuqta. Shunda door→interior kesmasi HAR DOIM to'siqsiz — agent xonaga kirib
  // qolmaydi va bemalol chiqadi. (Avval: qat'iy z=±12.5 → server/kutubxona
  // rack/javon qatorlari ortida qolib ketardi.)
  let iz = doorZ;
  for (let z = doorZ; Math.abs(z - doorZ) <= 6.5; z += inward * 0.25) {
    if (blocked(cx, z, 0.32)) break;
    iz = z;
  }
  NODES[`${key}_d`] = { x: cx, z: doorZ };
  NODES[`${key}_i`] = { x: cx, z: iz };
  EDGES.push([`${key}_d`, `${key}_i`]);
  // Eshikni eng yaqin TO'SIQSIZ grid tuguniga ulaymiz — masofa emas, haqiqiy
  // yo'l muhim (masalan lounge eshigi resepshn stoli ortida qolmasin).
  const near = [...GRID_KEYS].sort((a, b) => {
    const A = NODES[a],
      B = NODES[b];
    return (
      (A.x - cx) ** 2 +
      (A.z - doorZ) ** 2 -
      ((B.x - cx) ** 2 + (B.z - doorZ) ** 2)
    );
  });
  const best =
    near.find((gk) => clearPath(cx, doorZ, NODES[gk].x, NODES[gk].z)) ??
    near[0];
  EDGES.push([`${key}_d`, best]);
}

const ADJ: Record<string, string[]> = {};
for (const k of Object.keys(NODES)) ADJ[k] = [];
for (const [a, b] of EDGES) {
  ADJ[a].push(b);
  ADJ[b].push(a);
}
const KEYS = Object.keys(NODES);

export function nearestNode(x: number, z: number): string {
  let best = KEYS[0];
  let bd = Infinity;
  for (const k of KEYS) {
    const n = NODES[k];
    const d = (n.x - x) ** 2 + (n.z - z) ** 2;
    if (d < bd) {
      bd = d;
      best = k;
    }
  }
  return best;
}

export function pathBetween(from: string, to: string): WP[] {
  if (from === to) return [NODES[to]];
  const prev: Record<string, string | null> = { [from]: null };
  const q = [from];
  while (q.length) {
    const cur = q.shift()!;
    if (cur === to) break;
    for (const n of ADJ[cur]) {
      if (!(n in prev)) {
        prev[n] = cur;
        q.push(n);
      }
    }
  }
  // Yetib bo'lmasa — BO'SH yo'l. (Avval maqsad nuqtasini qaytarardi → agent
  // to'g'ri chiziqda devorga qarab yurib tiqilib qolardi.)
  if (!(to in prev)) return [];
  const out: WP[] = [];
  let c: string | null = to;
  while (c) {
    out.unshift(NODES[c]);
    c = prev[c];
  }
  return out;
}

export function randomNodeKey(): string {
  return KEYS[Math.floor(Math.random() * KEYS.length)];
}

// ── Kontekstli (smart) idle manzillari ──────────────────────
// Bo'sh turgan agent tasodifiy nuqtaga emas — rolига mos xonaga boradi
// (tadqiqotchi kutubxonaga, backend serverga, hamma oshxonaga tanaffusga...).
// Bu ofisni "tirik" ko'rsatadi: har kim maqsad bilan yuradi.

const ROLE_ROOMS: Record<string, string[]> = {
  research: ["library_i", "focus_i", "kitchen_i"],
  docs: ["library_i", "focus_i", "lounge_i"],
  frontend: ["kitchen_i", "lounge_i", "meeting_i"],
  backend: ["server_i", "kitchen_i", "lounge_i"],
  data: ["focus_i", "library_i", "kitchen_i"],
  qa: ["meeting_i", "lounge_i", "kitchen_i"],
};

// Ishdan keyingi birinchi "tanaffus" xonalari (oshxona/lounge).
const BREAK_ROOMS = ["kitchen_i", "lounge_i"];

// Barcha xona ichki nuqtalari (rol noma'lum bo'lsa — istalgan xona).
const ALL_ROOMS = ROOMS.map(([k]) => `${k}_i`);

/** Ishni tugatgach birinchi idle safar — tanaffusga (oshxona/lounge). */
export function breakRoom(): string {
  return BREAK_ROOMS[Math.floor(Math.random() * BREAK_ROOMS.length)];
}

/** Rolига mos idle manzil. 25% holatda umumiy tasodif — tabiiy ko'rinsin. */
export function idleDestination(role: string | undefined): string {
  if (Math.random() < 0.25) return randomNodeKey();
  const rooms = (role && ROLE_ROOMS[role]) || ALL_ROOMS;
  return rooms[Math.floor(Math.random() * rooms.length)];
}
