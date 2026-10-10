/**
 * Environment "Puente de mando": a wide room; your desk at the bottom centre
 * and the agents' desks on arcs of 140° around it, every agent facing you
 * (its monitor between you and it, screen towards the agent). A big screen on
 * the back wall, a break corner at the top right, the entrance at a bottom
 * corner. When an agent waits for you its desk lights up.
 */

import {
  caja,
  grafoCuadricula,
  paredes,
  ryHacia,
  type Entorno,
  type Puesto,
  type PuntoSofa,
  type Rect,
  type WP,
} from "./tipos";

const ANCHO = 36;
const FONDO = 28;
/** Centre of the arcs: your chair. */
export const CENTRO_PUENTE: WP = { x: 0, z: 8.7 };
const ARCO = (140 * Math.PI) / 180;

/** Arcs: radius and number of desks (the first one holds 10). */
export const ARCOS = [
  { radio: 7, cupo: 10 },
  { radio: 10, cupo: 14 },
  { radio: 13, cupo: 18 },
  { radio: 16, cupo: 22 },
];

function enArco(radio: number, cupo: number, k: number): Puesto {
  const a = -ARCO / 2 + (cupo === 1 ? ARCO / 2 : (ARCO * k) / (cupo - 1));
  const x = CENTRO_PUENTE.x + radio * Math.sin(a);
  const z = CENTRO_PUENTE.z - radio * Math.cos(a);
  // Monitor towards you: the agent sits on the outer side, facing you.
  return { x, z, ry: ryHacia(x, z, CENTRO_PUENTE.x, CENTRO_PUENTE.z) };
}

/** Desk i: fills the first arc, then a second one behind, and so on. */
function puesto(i: number): Puesto {
  let resto = i;
  for (const { radio, cupo } of ARCOS) {
    if (resto < cupo) return enArco(radio, cupo, resto);
    resto -= cupo;
  }
  // Very many agents: rows along the back wall.
  const col = resto % 12;
  const fila = Math.floor(resto / 12);
  return { x: -13.2 + col * 2.4, z: -11.2 + fila * 1.6, ry: Math.PI };
}

export const TU_PUESTO_PUENTE: Puesto = { x: 0, z: 8.0, ry: 0 };

// Break corner (top right): sofa A against the back wall facing the room,
// sofa B against the right wall facing left, coffee table in between.
const SOFA_A = { x: 12.6, z: -12.6 };
const SOFA_B = { x: 16.5, z: -9.6 };
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
const MESA_CENTRO = { x: 13.6, z: -10.4 };
const CERCA: PuntoSofa[] = [
  [11.0, -9.4],
  [12.2, -8.4],
  [13.8, -8.2],
  [10.4, -11.0],
  [15.0, -7.6],
  [10.8, -7.8],
].map(([x, z]) => ({
  x,
  z,
  ry: ryHacia(x, z, MESA_CENTRO.x, MESA_CENTRO.z),
  ax: x,
  az: z,
}));

const PLANTAS: WP[] = [
  { x: -16.8, z: -12.8 },
  { x: -16.8, z: 12.8 },
  { x: 16.8, z: 12.8 },
  { x: 9.4, z: -12.9 },
];

function choques(): Rect[] {
  const r: Rect[] = paredes(ANCHO, FONDO);
  r.push(caja(TU_PUESTO_PUENTE.x, TU_PUESTO_PUENTE.z, 1.05, 0.5));
  r.push(caja(SOFA_A.x, SOFA_A.z, 1.15, 0.5));
  r.push(caja(SOFA_B.x, SOFA_B.z, 0.5, 1.15));
  r.push(caja(MESA_CENTRO.x, MESA_CENTRO.z, 0.6, 0.35));
  for (const p of PLANTAS) r.push(caja(p.x, p.z, 0.28, 0.28));
  return r;
}

export const PUENTE: Entorno = {
  clave: "puente",
  nombre: "Puente de mando",
  tamano: { ancho: ANCHO, fondo: FONDO },
  zoom: 24,
  puestosBase: ARCOS[0].cupo,
  puesto,
  tuPuesto: TU_PUESTO_PUENTE,
  placaNombre: true,
  resaltarEspera: true,
  descanso: { asientos: ASIENTOS, cerca: CERCA, pasillo: null, nodo: "sala" },
  puerta: { x: -17.6, z: 11 },
  entrada: { x: -16.3, z: 11 },
  mostrador: null,
  choques: choques(),
  grafo: (bloqueado, base) =>
    grafoCuadricula(bloqueado, base, ANCHO / 2 - 1, FONDO / 2 - 1, 1, {
      sala: { x: 12.2, z: -9.6 },
      entrada: { x: -16.3, z: 11 },
      encuentro1: { x: -11, z: -9.5 },
      encuentro2: { x: -3, z: -11.5 },
      encuentro3: { x: 6, z: -11.5 },
      rincon1: { x: -15, z: -4 },
      rincon2: { x: 15, z: 4 },
      rincon3: { x: -12, z: 12 },
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
      "rincon3",
    ],
  },
  limites: { x: ANCHO / 2 - 0.5, z: FONDO / 2 - 0.5 },
};
