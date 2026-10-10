/**
 * Environment "Cabinas por proyecto": a central corridor (left to right) with
 * glass cabins on both sides, one per active project (up to 6), each with
 * its project name over the door. Your desk is in the middle of the corridor.
 * Projects that do not get a cabin share the "Cabina general" (top left);
 * past it, extra desks along the walls. Break room at the back right, entrance
 * at the bottom right corner. An agent waiting for you walks to the door of
 * its cabin and faces your desk.
 */

import {
  caja,
  grafoCuadricula,
  huellaPieza,
  mirarHacia,
  paredes,
  type Agrupacion,
  type Entorno,
  type Pieza,
  type Puesto,
  type PuntoFila,
  type PuntoSofa,
  type Rect,
  type WP,
} from "./tipos";

const ANCHO = 50;
const FONDO = 30;
/** Half width of the corridor (z from -2.5 to 2.5). */
export const PASILLO = 2.5;
const PUERTA_CABINA = 0.8; // half width of a cabin door

export interface Cabina {
  /** Centre x and side: -1 above the corridor (back), +1 below. */
  cx: number;
  lado: -1 | 1;
  /** Half width and far wall (|z|). */
  hw: number;
  fondo: number;
  /** Desks inside the cabin. */
  capacidad: number;
}

/** Dedicated cabins 0-5 (centre ones first), then the general cabin (6). */
export const CABINAS: Cabina[] = [
  { cx: 0, lado: -1, hw: 4.6, fondo: 11, capacidad: 8 },
  { cx: 0, lado: 1, hw: 4.6, fondo: 11, capacidad: 8 },
  { cx: -10, lado: -1, hw: 4.6, fondo: 11, capacidad: 8 },
  { cx: -10, lado: 1, hw: 4.6, fondo: 11, capacidad: 8 },
  { cx: 10, lado: -1, hw: 4.6, fondo: 11, capacidad: 8 },
  { cx: 10, lado: 1, hw: 4.6, fondo: 11, capacidad: 8 },
  { cx: -20, lado: -1, hw: 4.6, fondo: 14.5, capacidad: 12 },
];
export const CABINAS_PROPIAS = 6;
export const CABINA_GENERAL = 6;
const EN_CABINAS = CABINAS_PROPIAS * 8; // 48 seats in the dedicated cabins
/** Desk columns inside a cabin, centre first. */
const COLUMNAS = [-0.95, 0.95, -2.85, 2.85];

function enCabina(c: Cabina, k: number): Puesto {
  const fila = Math.floor(k / 4);
  return {
    x: c.cx + COLUMNAS[k % 4],
    z: c.lado * (5 + fila * 3),
    // The agent faces the corridor (your desk).
    ry: c.lado > 0 ? 0 : Math.PI,
  };
}

/** Extra desks when the general cabin is full: bottom left, along the walls, then the lobby. */
function extra(m: number): Puesto {
  if (m < 12)
    return {
      x: [-22.4, -20, -17.6][m % 3],
      z: 5 + Math.floor(m / 3) * 2.6,
      ry: 0,
    };
  m -= 12;
  if (m < 11) return { x: -13 + m * 2.6, z: 12.6, ry: 0 };
  m -= 11;
  if (m < 11) return { x: -13 + m * 2.6, z: -12.6, ry: Math.PI };
  m -= 11;
  return {
    x: [17, 19.6, 22.2][m % 3],
    z: 4.5 + Math.floor(m / 3) * 2.5,
    ry: 0,
  };
}
/** Fixed desks the paths avoid (cabins, general cabin and the extra desks). */
const PUESTOS_FIJOS = EN_CABINAS + 12 + 43;

function puesto(i: number): Puesto {
  if (i < EN_CABINAS) return enCabina(CABINAS[Math.floor(i / 8)], i % 8);
  const k = i - EN_CABINAS;
  if (k < 12) return enCabina(CABINAS[CABINA_GENERAL], k);
  return extra(k - 12);
}

export const TU_PUESTO_CABINAS: Puesto = { x: 0, z: 0, ry: 0 };

/** Where an agent waiting for you stands: in the corridor at the door of its cabin. */
function puertaCabina(g: number, orden: number): PuntoFila {
  const c = CABINAS[Math.min(g, CABINA_GENERAL)];
  const paso = Math.floor((orden + 1) / 2) * 0.85;
  const dx = orden % 2 === 1 ? paso : -paso;
  const z = c.lado * (orden < 9 ? 1.9 : 1.1);
  const x = c.cx + Math.max(-3.4, Math.min(3.4, dx));
  return { x, z, ry: mirarHacia(x, z, TU_PUESTO_CABINAS.x, 0) };
}

const AGRUPACION: Agrupacion = {
  grupoDe: (i) =>
    i < EN_CABINAS
      ? { g: Math.floor(i / 8), k: i % 8 }
      : { g: CABINA_GENERAL, k: i - EN_CABINAS },
  asiento: (g, k) => (g < CABINAS_PROPIAS ? g * 8 + k : EN_CABINAS + k),
  capacidad: (g) => (g === CABINA_GENERAL ? Infinity : 8),
  grupos: CABINAS.length,
  generalFijo: CABINA_GENERAL,
  umbralPropio: 1,
  reservaGeneral: 0,
  puerta: puertaCabina,
};

/** Desks drawn: from 2 up to the last used one in each cabin with agents. */
function puestosVisibles(ocupados: number[]): number[] {
  const max = new Map<number, number>();
  for (const i of ocupados) {
    const { g, k } = AGRUPACION.grupoDe(i);
    if (k >= CABINAS[g].capacidad) continue; // extra desk: drawn on its own
    max.set(g, Math.max(max.get(g) ?? 0, k));
  }
  const out: number[] = [];
  for (const [g, m] of max)
    for (let k = 0; k <= Math.max(1, m); k++)
      out.push(AGRUPACION.asiento(g, k));
  return out;
}

// Break room at the back right: two sofas, a coffee table, plants.
const SOFA_A = { x: 20.5, z: -13.9 }; // against the back wall, facing the room
const SOFA_B = { x: 24.0, z: -9.5 }; // against the right wall, facing left
const MESA = { x: 21.3, z: -11.0 };
const ASIENTOS: PuntoSofa[] = [
  ...[-0.55, 0.55].map((dx) => ({
    x: SOFA_A.x + dx,
    z: SOFA_A.z + 0.1,
    ry: Math.PI,
    ax: SOFA_A.x + dx,
    az: SOFA_A.z + 1.2,
  })),
  ...[-0.55, 0.55].map((dz) => ({
    x: SOFA_B.x - 0.1,
    z: SOFA_B.z + dz,
    ry: Math.PI / 2,
    ax: SOFA_B.x - 1.2,
    az: SOFA_B.z + dz,
  })),
];
const CERCA: PuntoSofa[] = [
  [18.4, -10.6],
  [19.0, -8.4],
  [21.2, -7.6],
  [18.2, -12.4],
  [22.6, -6.8],
  [17.6, -6.4],
].map(([x, z]) => ({
  x,
  z,
  ry: mirarHacia(x, z, MESA.x, MESA.z),
  ax: x,
  az: z,
}));

const DECORACION: Pieza[] = [
  // break room
  {
    tipo: "alfombra",
    x: 21.2,
    z: -10.6,
    ancho: 6.2,
    fondo: 6.4,
    color: "#8a6e5a",
  },
  { tipo: "sofa", x: SOFA_A.x, z: SOFA_A.z, color: "#4a5568" },
  {
    tipo: "sofa",
    x: SOFA_B.x,
    z: SOFA_B.z,
    ry: -Math.PI / 2,
    color: "#556070",
  },
  { tipo: "mesaCafe", x: MESA.x, z: MESA.z },
  { tipo: "lampara", x: 24.2, z: -14.2 },
  { tipo: "plantaGrande", x: 17.0, z: -14.1 },
  { tipo: "planta", x: 24.2, z: -4.2 },
  { tipo: "librero", x: 17.4, z: -3.4, ry: Math.PI },
  // lobby at the entrance (bottom right)
  { tipo: "plantaGrande", x: 24.1, z: 2.9 },
  { tipo: "banca", x: 19.6, z: 14.4, ry: Math.PI },
  { tipo: "planta", x: 16.8, z: 14.4 },
  { tipo: "lampara", x: 24.2, z: 10.9 },
  // corridor ends and corners
  { tipo: "plantaGrande", x: -24.1, z: -1.9 },
  { tipo: "plantaGrande", x: -24.1, z: 1.9 },
  { tipo: "planta", x: 15.4, z: -2.0 },
  { tipo: "planta", x: 15.4, z: 2.0 },
  { tipo: "planta", x: -24.2, z: 14.3 },
  // walls
  { tipo: "cuadro", x: -24.8, z: 9.0, ry: Math.PI / 2, color: "#3a7bc8" },
  { tipo: "cuadro", x: 24.8, z: 6.5, ry: -Math.PI / 2, color: "#c85a3c" },
  { tipo: "cuadro", x: 20.5, z: -14.85, color: "#5aa06a" },
  { tipo: "reloj", x: 24.8, z: -6.0, ry: -Math.PI / 2 },
];

/** Glass walls of every cabin, with the door gap on the corridor side. */
function paredesCabinas(): Rect[] {
  const r: Rect[] = [];
  const t = 0.05;
  for (const c of CABINAS) {
    const zp = c.lado * PASILLO;
    const zf = c.lado * c.fondo;
    const [z0, z1] = [Math.min(zp, zf), Math.max(zp, zf)];
    r.push({
      x0: c.cx - c.hw,
      x1: c.cx - PUERTA_CABINA,
      z0: zp - t,
      z1: zp + t,
    });
    r.push({
      x0: c.cx + PUERTA_CABINA,
      x1: c.cx + c.hw,
      z0: zp - t,
      z1: zp + t,
    });
    r.push({ x0: c.cx - c.hw, x1: c.cx + c.hw, z0: zf - t, z1: zf + t });
    for (const x of [c.cx - c.hw, c.cx + c.hw])
      r.push({ x0: x - t, x1: x + t, z0, z1 });
  }
  return r;
}

function choques(): Rect[] {
  const r: Rect[] = paredes(ANCHO, FONDO);
  r.push(caja(TU_PUESTO_CABINAS.x, TU_PUESTO_CABINAS.z, 1.05, 0.5));
  r.push(...paredesCabinas());
  for (const p of DECORACION) {
    const h = huellaPieza(p);
    if (h) r.push(h);
  }
  return r;
}

const ENTRADA: WP = { x: 23.7, z: 13 };

export const CABINAS_ENTORNO: Entorno = {
  clave: "cabinas",
  nombre: "Cabinas por proyecto",
  tamano: { ancho: ANCHO, fondo: FONDO },
  zoom: 19,
  puestosBase: 0,
  puesto,
  tuPuesto: TU_PUESTO_CABINAS,
  placaNombre: false,
  resaltarEspera: false,
  descanso: { asientos: ASIENTOS, cerca: CERCA, pasillo: null, nodo: "sala" },
  puerta: { x: 24.6, z: 13 },
  entrada: ENTRADA,
  mostrador: null,
  choques: choques(),
  grafo: (bloqueado) =>
    grafoCuadricula(
      bloqueado,
      Array.from({ length: PUESTOS_FIJOS }, (_, i) => puesto(i)),
      ANCHO / 2 - 1,
      FONDO / 2 - 1,
      1,
      {
        sala: { x: 20, z: -9 },
        entrada: ENTRADA,
        encuentro1: { x: -6, z: 0 },
        encuentro2: { x: 6, z: 0 },
        encuentro3: { x: 18.5, z: -5 },
        rincon1: { x: -20, z: 1 },
        rincon2: { x: 20, z: 1 },
        rincon3: { x: 21, z: 12 },
      },
    ),
  encuentros: ["encuentro1", "encuentro2", "encuentro3", "sala"],
  paseo: {
    descanso: ["sala"],
    destinos: [
      "sala",
      "encuentro1",
      "encuentro2",
      "encuentro3",
      "rincon1",
      "rincon2",
      "rincon3",
    ],
  },
  limites: { x: ANCHO / 2 - 0.5, z: FONDO / 2 - 0.5 },
  agrupacion: AGRUPACION,
  puestosGrafo: PUESTOS_FIJOS,
  puestosVisibles,
  decoracion: DECORACION,
  pisoCentral: { x0: -ANCHO / 2, x1: ANCHO / 2, z0: -PASILLO, z1: PASILLO },
};
