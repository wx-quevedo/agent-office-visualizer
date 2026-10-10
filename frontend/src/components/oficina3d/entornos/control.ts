/**
 * Environment "Sala de control con mostrador": a big screen on the front
 * wall, your desk in front of it facing the room, then a long low counter,
 * then the agents' desks in rows of 5 facing you (rows are added towards the
 * back). The break room is at the back; the entrance at a back corner.
 * An agent waiting for you (13, 14) walks to the counter and queues in front
 * of your desk: the one waiting longest is first (closest to you).
 */

import {
  caja,
  grafoCuadricula,
  huellaPieza,
  mirarHacia,
  paredes,
  type Entorno,
  type Pieza,
  type Puesto,
  type PuntoFila,
  type PuntoSofa,
  type Rect,
  type WP,
} from "./tipos";

const ANCHO = 32;
const FONDO = 32;

export const TU_PUESTO_CONTROL: Puesto = { x: 0, z: -12.5, ry: Math.PI };

/** Counter between your desk and the agents (x -6..6). */
export const MOSTRADOR: Rect = { x0: -6, x1: 6, z0: -8.85, z1: -8.15 };
/** Queue: the first spot faces your desk across the counter. */
const FILA_Z0 = -7.5;
const FILA_PASO = 0.9;
export const LARGO_FILA = 5;

/**
 * Queue spot i: up to 5 in a line from the counter back towards the room;
 * with more, the queue folds along the counter (alternating right and left).
 */
function fila(i: number): PuntoFila {
  if (i < LARGO_FILA) return { x: 0, z: FILA_Z0 + i * FILA_PASO, ry: 0 };
  const k = i - LARGO_FILA;
  const lado = k % 2 === 0 ? 1 : -1;
  const paso = Math.floor(k / 2) + 1;
  const x = Math.max(-5.5, Math.min(5.5, lado * paso * 0.95));
  return { x, z: FILA_Z0, ry: 0 };
}

const COLUMNAS = [-6, -3, 0, 3, 6];
const FILA_ESCRITORIOS_Z0 = -1.5;
const SEPARACION_FILAS = 3.5;
const FILAS_CENTRALES = 4;

/**
 * Desk i: rows of 5 facing you (2 rows are drawn from the start; up to 4 rows
 * towards the back), then two side columns on each side, then two short rows
 * at the back right (next to the break room). Never overlapping.
 */
function puesto(i: number): Puesto {
  const enCentro = COLUMNAS.length * FILAS_CENTRALES;
  if (i < enCentro) {
    const fila = Math.floor(i / COLUMNAS.length);
    return {
      x: COLUMNAS[i % COLUMNAS.length],
      z: FILA_ESCRITORIOS_Z0 + fila * SEPARACION_FILAS,
      ry: 0,
    };
  }
  const k = i - enCentro;
  if (k < 16) {
    // side columns: x = ±11.5 first, then ±14.2; 4 desks each
    const lado = k % 2 === 0 ? -1 : 1;
    const columna = Math.floor(k / 8);
    const fila = Math.floor((k % 8) / 2);
    return {
      x: lado * (columna === 0 ? 11.5 : 14.2),
      z: FILA_ESCRITORIOS_Z0 + fila * SEPARACION_FILAS,
      ry: 0,
    };
  }
  const m = k - 16;
  return { x: 3 + (m % 4) * 2.6, z: 12.0 + Math.floor(m / 4) * 2.0, ry: 0 };
}

// Break room at the back (left): two sofas against the back wall facing the
// room, a coffee table and plants.
const SOFAS: WP[] = [
  { x: -10.4, z: 15.0 },
  { x: -6.8, z: 15.0 },
];
const ASIENTOS: PuntoSofa[] = SOFAS.flatMap((s) =>
  [0.55, -0.55].map((dx) => ({
    x: s.x + dx,
    z: s.z - 0.1,
    ry: 0,
    ax: s.x + dx,
    az: s.z - 1.2,
  })),
);
const MESA_CAFE = { x: -8.6, z: 12.4 };
const CERCA: PuntoSofa[] = [
  [-11.6, 12.0],
  [-5.4, 12.0],
  [-12.8, 13.4],
  [-4.4, 13.4],
  [-8.6, 10.9],
  [-10.4, 10.8],
  [-6.8, 10.8],
].map(([x, z]) => ({
  x,
  z,
  ry: mirarHacia(x, z, MESA_CAFE.x, MESA_CAFE.z),
  ax: x,
  az: z,
}));

const PLANTAS: WP[] = [
  { x: -14.8, z: 14.8 },
  { x: -3.4, z: 15.0 },
  { x: -14.8, z: -14.8 },
  { x: 14.8, z: -14.8 },
];

/** More decoration (data): bookshelves, meeting corner, whiteboard, rugs, lamps. */
const DECORACION: Pieza[] = [
  {
    tipo: "alfombra",
    x: 0,
    z: -12.6,
    ancho: 5.4,
    fondo: 3.2,
    color: "#9aa6b8",
  },
  { tipo: "librero", x: -13.2, z: -15.55 },
  { tipo: "librero", x: -11.9, z: -15.55 },
  { tipo: "lampara", x: -9.6, z: -15.2 },
  { tipo: "mesaReuniones", x: 11.6, z: -12.4 },
  { tipo: "pizarra", x: 15.7, z: -8.2, ry: -Math.PI / 2 },
  { tipo: "plantaGrande", x: -15.2, z: -6 },
  { tipo: "plantaGrande", x: 15.2, z: -4.6 },
  { tipo: "lampara", x: -15.2, z: -8.2 },
  { tipo: "planta", x: 6.9, z: -15.3 },
  { tipo: "planta", x: -6.9, z: -15.3 },
  { tipo: "cuadro", x: 15.85, z: 4.5, ry: -Math.PI / 2, color: "#d9895b" },
  { tipo: "cuadro", x: -15.85, z: -10.5, ry: Math.PI / 2, color: "#5aa06a" },
];

function choques(): Rect[] {
  const r: Rect[] = paredes(ANCHO, FONDO);
  r.push(caja(TU_PUESTO_CONTROL.x, TU_PUESTO_CONTROL.z, 1.05, 0.5));
  r.push(MOSTRADOR);
  for (const s of SOFAS) r.push(caja(s.x, s.z, 1.15, 0.5));
  r.push(caja(MESA_CAFE.x, MESA_CAFE.z, 0.6, 0.35));
  for (const p of PLANTAS) r.push(caja(p.x, p.z, 0.28, 0.28));
  for (const p of DECORACION) {
    const h = huellaPieza(p);
    if (h) r.push(h);
  }
  return r;
}

export const CONTROL: Entorno = {
  clave: "control",
  nombre: "Sala de control con mostrador",
  tamano: { ancho: ANCHO, fondo: FONDO },
  zoom: 22,
  puestosBase: COLUMNAS.length * 2,
  puesto,
  tuPuesto: TU_PUESTO_CONTROL,
  placaNombre: true,
  resaltarEspera: false,
  descanso: { asientos: ASIENTOS, cerca: CERCA, pasillo: null, nodo: "sala" },
  puerta: { x: 15.6, z: 13.5 },
  entrada: { x: 14.3, z: 13.5 },
  mostrador: { rect: MOSTRADOR, fila },
  choques: choques(),
  grafo: (bloqueado, base) =>
    grafoCuadricula(bloqueado, base, ANCHO / 2 - 1, FONDO / 2 - 1, 1, {
      sala: { x: -8.6, z: 11.0 },
      entrada: { x: 14.3, z: 13.5 },
      encuentro1: { x: 10.5, z: 10.5 },
      encuentro2: { x: -13.5, z: -4 },
      encuentro3: { x: 13.5, z: -4 },
      rincon1: { x: 8.5, z: -12 },
      rincon2: { x: -8.5, z: -12 },
    }),
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
    ],
  },
  limites: { x: ANCHO / 2 - 0.5, z: FONDO / 2 - 0.5 },
  decoracion: DECORACION,
};
