// ── Rol presetlari + Pixel Agents personaj palitralari ───────
// Pixel Agents 6 personajini (JIK-A-4 Metro City) chuqur o'rganib,
// har birini voxel/blokli chibi 3D personaj sifatida qayta yaratamiz.

export type HairStyle =
  "short" | "long" | "afro" | "curly" | "medium" | "spiky";
export type Accessory = "glasses" | "headphones" | "cap" | "beanie" | null;

export interface CharSkin {
  label: string;
  skin: string;
  hair: string;
  hairStyle: HairStyle;
  top: string;
  bottom: string;
  shoes: string;
  /** Aksessuar (per-agent xilma-xillik uchun) — ko'zoynak/naushnik/shляпа. */
  accessory?: Accessory;
}

// 6 pixel personaj → 6 rol. Ranglar sprite'lardan olingan.
export const ROLE_PRESETS: Record<string, CharSkin> = {
  // char_1 — sarg'ish uzun soch, qora libos
  research: {
    label: "Investigación",
    skin: "#efc4a2",
    hair: "#d7a24c",
    hairStyle: "long",
    top: "#20222a",
    bottom: "#26282f",
    shoes: "#3a2c1e",
  },
  // char_0 — qisqa jigarrang soch, ko'k/oq ko'ylak, navy shim
  frontend: {
    label: "Frontend",
    skin: "#e8b58f",
    hair: "#6b4a2f",
    hairStyle: "short",
    top: "#c3d0e0",
    bottom: "#2f3a52",
    shoes: "#20242c",
  },
  // char_2 — qora afro, to'q teri, to'q-sariq libos
  backend: {
    label: "Backend",
    skin: "#6e4a34",
    hair: "#141414",
    hairStyle: "afro",
    top: "#cf5a28",
    bottom: "#d5722a",
    shoes: "#eaeaea",
  },
  // char_5 — qora tikanli soch, qizil ko'ylak
  qa: {
    label: "Revisión",
    skin: "#e8b58f",
    hair: "#1a1a1a",
    hairStyle: "spiky",
    top: "#c0392b",
    bottom: "#26282f",
    shoes: "#eaeaea",
  },
  // char_3 — oq/kumush jingalak soch, oq/krem libos (olim)
  docs: {
    label: "Documentación",
    skin: "#d9a884",
    hair: "#e3e4e6",
    hairStyle: "curly",
    top: "#eceae4",
    bottom: "#c9c4b6",
    shoes: "#7a5a3a",
  },
  // char_4 — jigarrang o'rta soch, oq ko'ylak, teal shim
  data: {
    label: "Datos",
    skin: "#e8b58f",
    hair: "#5a3f28",
    hairStyle: "medium",
    top: "#eceae4",
    bottom: "#2b6b6e",
    shoes: "#20242c",
  },
};

const PALETTE = Object.values(ROLE_PRESETS);

export function presetFor(
  role: string | undefined,
  seatIndex: number,
): CharSkin {
  if (role && ROLE_PRESETS[role]) return ROLE_PRESETS[role];
  return PALETTE[seatIndex % PALETTE.length];
}

// Rol KALITI (i18n uchun) — aniqlanган rol yoki seat-fallback kaliti.
const ROLE_KEYS = Object.keys(ROLE_PRESETS);
export function roleKeyFor(
  role: string | undefined,
  seatIndex: number,
): string {
  if (role && ROLE_PRESETS[role]) return role;
  return ROLE_KEYS[seatIndex % ROLE_KEYS.length];
}

// Har ROLning IMZO aksessuari — rol bir qarashda tanilsin (siluetdan). Har
// rolда 4 variant: birinchisi ustuvor (rol identifikatori), qolganlari id
// bo'yicha xilma-xillik (bir xil rolli 2 agent aynan bir xil bo'lmasin).
//   Tadqiqot/Hujjatlar — olim → ko'zoynak · Backend/Ma'lumot — koder → naushnik
//   QA — tester → kepka · Frontend — erkin uslub.
const ROLE_ACCESSORY: Record<string, Accessory[]> = {
  research: ["glasses", "glasses", "beanie", null],
  frontend: [null, "beanie", "headphones", null],
  backend: ["headphones", "headphones", "cap", "beanie"],
  qa: ["cap", "cap", "glasses", "headphones"],
  docs: ["glasses", "glasses", "glasses", "beanie"],
  data: ["headphones", "glasses", "headphones", "cap"],
};

// Rol "energiyasi" — bo'sh vaqtдagi jonlilik (atrofga qarash chastotasi). Olimlar
// (Tadqiqot/Hujjatlar) xotirjam, Frontend/QA faolroq. Faqat mavjud animatsiyani
// shkalalaydi (PixelPerson).
const ROLE_ENERGY: Record<string, number> = {
  research: 0.75,
  docs: 0.75,
  backend: 0.95,
  data: 0.95,
  frontend: 1.3,
  qa: 1.25,
};
export function energyFor(role: string | undefined, seatIndex: number): number {
  return ROLE_ENERGY[roleKeyFor(role, seatIndex)] ?? 1;
}

/** Kichik rang siljishi (och/to'q) — bir xil rolli agentlarni ajratish uchun. */
function shade(hex: string, amt: number): string {
  const n = parseInt(hex.slice(1), 16);
  const cl = (v: number) => Math.max(0, Math.min(255, v));
  const r = cl(((n >> 16) & 255) + amt);
  const g = cl(((n >> 8) & 255) + amt);
  const b = cl((n & 255) + amt);
  return "#" + ((1 << 24) | (r << 16) | (g << 8) | b).toString(16).slice(1);
}

/** Agent uchun personaj ko'rinishi (rol preseti + id bo'yicha variatsiya). */
/** Stable small number from a session id (variation of accessory and colours). */
function hashId(id: string): number {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
  return h;
}

export function characterFor(
  role: string | undefined,
  seatIndex: number,
  sessionId: string,
): CharSkin {
  const id = hashId(sessionId);
  const base = presetFor(role, seatIndex);
  // Rol imzo aksessuari — id bo'yicha 4 variantdan biri (rol identifikatori
  // ustuvor, lekin bir xil rolli agentlar ozgina farqlansin).
  const set = ROLE_ACCESSORY[roleKeyFor(role, seatIndex)] ?? [null];
  const accessory = set[id % set.length];
  const d = ((id * 37) % 5) - 2; // -2..+2
  return {
    ...base,
    accessory,
    hair: shade(base.hair, d * 8),
    top: shade(base.top, d * 6),
  };
}

export interface Seat {
  x: number;
  z: number;
  ry: number;
}

// Ish joylari — hamma markazga qaraydi.
//  • 1-6: asosiy ikki ustun (chap/o'ng, x=±5.5).
//  • 7-10: markazdagi qo'shimcha stollar (x=±13) — ofis to'ladi (Variant B).
export const SEATS: Seat[] = [
  { x: -5.5, z: -3.2, ry: -Math.PI / 2 },
  { x: -5.5, z: 0, ry: -Math.PI / 2 },
  { x: -5.5, z: 3.2, ry: -Math.PI / 2 },
  { x: 5.5, z: -3.2, ry: Math.PI / 2 },
  { x: 5.5, z: 0, ry: Math.PI / 2 },
  { x: 5.5, z: 3.2, ry: Math.PI / 2 },
  // Qo'shimcha stollar (avval "bo'sh stol" edi — endi overflow agentlar shu yerda)
  { x: -13, z: -3, ry: -Math.PI / 2 },
  { x: -13, z: 3, ry: -Math.PI / 2 },
  { x: 13, z: -3, ry: Math.PI / 2 },
  { x: 13, z: 3, ry: Math.PI / 2 },
];

/** O'rindiq soni — dinamik (SEATS uzunligidan). */
export const SEAT_COUNT = SEATS.length;

/** Indeks bo'yicha o'rindiq. SEATS'dan tashqari (juda ko'p agent) — ustma-ust
 *  bo'lmasin uchun markaziy ochiq maydonda neat qator generatsiya qilinadi. */
export function seatFor(index: number): Seat {
  if (index >= 0 && index < SEATS.length) return SEATS[index];
  const o = index - SEATS.length;
  const cols = 5;
  const col = o % cols;
  const row = Math.floor(o / cols);
  return { x: -4.4 + col * 2.2, z: -5.2 - row * 2.0, ry: Math.PI };
}

/** Personaj o'tirish nuqtasi (stul markazi, yo'nalishga mos) — Workstation
 *  stuli bilan bir xil formula: (0.72·sin(ry), 0.72·cos(ry)) siljish. */
export function sitPoint(seat: Seat): { x: number; z: number } {
  return {
    x: seat.x + 0.72 * Math.sin(seat.ry),
    z: seat.z + 0.72 * Math.cos(seat.ry),
  };
}

export const STATUS_COLOR: Record<string, string> = {
  idle: "#8e8e93",
  thinking: "#5e9bff",
  working: "#30d158",
  review: "#ff9f0a",
  blocked: "#ff453a",
  collab: "#ffd60a",
  waiting: "#a2a6ad",
};

// Standart kontekst oynasi (model aniqlanmasa — token health-bar uchun).
export const MAX_CONTEXT_TOKENS = 200000;

export function tokenBar(
  input: number,
  contextWindow: number = MAX_CONTEXT_TOKENS,
): { pct: number; color: string } {
  const win = contextWindow > 0 ? contextWindow : MAX_CONTEXT_TOKENS;
  const pct = Math.min(1, input / win);
  const color =
    pct < 0.6
      ? "#30d158"
      : pct < 0.8
        ? "#ffd60a"
        : pct < 0.95
          ? "#ff9f0a"
          : "#ff453a";
  return { pct, color };
}
