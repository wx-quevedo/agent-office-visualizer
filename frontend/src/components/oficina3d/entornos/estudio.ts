/**
 * Environment "Estudio abierto con jardín": a long window along the back wall,
 * islands of shared tables (4 desks each, 2 on each side) with a hanging sign
 * with the project name, your desk next to the window on the left, and a big
 * indoor garden (lawn, trees, sofas, benches) for the breaks: the warmest of
 * the environments. Projects with a single agent share the "Isla general";
 * islands are added when needed. An agent waiting for you stays seated, its
 * desk and chair light up blue and it turns towards your desk.
 */

import {
  caja,
  grafoCuadricula,
  huellaPieza,
  mirarHacia,
  paredes,
  ryHacia,
  type Agrupacion,
  type Entorno,
  type Pieza,
  type Puesto,
  type PuntoSofa,
  type Rect,
  type WP,
} from "./tipos";

const ANCHO = 44;
const FONDO = 34;

/** Island centres, in order of use (the first 3 are always drawn). */
export const ISLAS: WP[] = [
  { x: -3, z: -10 },
  { x: 3, z: -10 },
  { x: -9, z: -10 },
  { x: -3, z: -4.5 },
  { x: 3, z: -4.5 },
  { x: -9, z: -4.5 },
  { x: 9, z: -10 },
  { x: 9, z: -4.5 },
  { x: -3, z: 1 },
  { x: 3, z: 1 },
  { x: -9, z: 1 },
  { x: 9, z: 1 },
  { x: 15, z: -10 },
  { x: 15, z: -4.5 },
  { x: 15, z: 1 },
  { x: -15, z: -4.5 },
  { x: -15, z: 1 },
];
const POR_ISLA = 4;
const EN_ISLAS = ISLAS.length * POR_ISLA;
/** Desks of an island: two facing the window side, two facing the garden side. */
const LUGARES: Array<[number, number, number]> = [
  [-0.8, 0.46, 0],
  [0.8, 0.46, 0],
  [-0.8, -0.46, Math.PI],
  [0.8, -0.46, Math.PI],
];

/** Extra desks past all the islands (many agents): two columns on the left. */
function extra(m: number): Puesto {
  const col = Math.floor(m / 8);
  return { x: col === 0 ? -19 : -21, z: -9 + (m % 8) * 1.7, ry: Math.PI / 2 };
}

function puesto(i: number): Puesto {
  if (i >= EN_ISLAS) return extra(i - EN_ISLAS);
  const c = ISLAS[Math.floor(i / POR_ISLA)];
  const [dx, dz, ry] = LUGARES[i % POR_ISLA];
  return { x: c.x + dx, z: c.z + dz, ry };
}

/** Your desk next to the window, at the left of the islands, facing them. */
export const TU_PUESTO_ESTUDIO: Puesto = {
  x: -16.5,
  z: -12.5,
  ry: ryHacia(-16.5, -12.5, -15.5, -12.5),
};

const AGRUPACION: Agrupacion = {
  grupoDe: (i) => ({
    g: Math.floor(i / POR_ISLA),
    k: i % POR_ISLA,
  }),
  asiento: (g, k) => g * POR_ISLA + k,
  capacidad: () => POR_ISLA,
  grupos: ISLAS.length,
  generalFijo: null,
  umbralPropio: 2,
  reservaGeneral: 3,
  puerta: null,
};

/** Every island with agents is drawn complete (4 desks). */
function puestosVisibles(ocupados: number[]): number[] {
  const islas = new Set(
    ocupados.filter((i) => i < EN_ISLAS).map((i) => Math.floor(i / POR_ISLA)),
  );
  return [...islas].flatMap((g) =>
    Array.from({ length: POR_ISLA }, (_, k) => g * POR_ISLA + k),
  );
}

// Garden (bottom): lawn, two sofas around a coffee table, benches, trees.
export const JARDIN: Rect = { x0: -16, x1: 20.5, z0: 5.5, z1: 16.4 };
const SOFA_A = { x: 2, z: 15.6 }; // against the front wall, facing the garden
const SOFA_B = { x: 2, z: 11.0 }; // facing sofa A
const MESA = { x: 2, z: 13.3 };
const ASIENTOS: PuntoSofa[] = [
  ...[-0.55, 0.55].map((dx) => ({
    x: SOFA_A.x + dx,
    z: SOFA_A.z - 0.1,
    ry: 0,
    ax: SOFA_A.x + dx,
    az: SOFA_A.z - 1.2,
  })),
  ...[-0.55, 0.55].map((dx) => ({
    x: SOFA_B.x + dx,
    z: SOFA_B.z + 0.1,
    ry: Math.PI,
    ax: SOFA_B.x + dx,
    az: SOFA_B.z + 1.2,
  })),
];
const CERCA: PuntoSofa[] = [
  [-0.6, 13.3],
  [4.6, 13.3],
  [-1.4, 9.4],
  [5.4, 9.4],
  [7.4, 12.2],
  [-3.6, 11.6],
  [8.4, 14.6],
  [-4.4, 14.6],
].map(([x, z]) => ({
  x,
  z,
  ry: mirarHacia(x, z, MESA.x, MESA.z),
  ax: x,
  az: z,
}));

const DECORACION: Pieza[] = [
  // garden
  {
    tipo: "cesped",
    x: (JARDIN.x0 + JARDIN.x1) / 2,
    z: (JARDIN.z0 + JARDIN.z1) / 2,
    ancho: JARDIN.x1 - JARDIN.x0,
    fondo: JARDIN.z1 - JARDIN.z0,
  },
  {
    tipo: "alfombra",
    x: MESA.x,
    z: MESA.z,
    ancho: 5.2,
    fondo: 6.0,
    color: "#b07a52",
  },
  { tipo: "sofa", x: SOFA_A.x, z: SOFA_A.z, ry: Math.PI, color: "#7a5a44" },
  { tipo: "sofa", x: SOFA_B.x, z: SOFA_B.z, color: "#8a6a50" },
  { tipo: "mesaCafe", x: MESA.x, z: MESA.z },
  { tipo: "banca", x: -8, z: 12.5, ry: Math.PI / 2 },
  { tipo: "banca", x: 12, z: 12.5, ry: -Math.PI / 2 },
  { tipo: "banca", x: 2, z: 7.4 },
  { tipo: "arbol", x: -13, z: 8.5 },
  { tipo: "arbol", x: -12, z: 14.6, escala: 1.2 },
  { tipo: "arbol", x: 17.5, z: 8.5, escala: 1.1 },
  { tipo: "arbol", x: 18, z: 14.6 },
  { tipo: "arbol", x: 9.5, z: 15.3, escala: 0.9 },
  { tipo: "arbusto", x: -5, z: 15.6 },
  { tipo: "arbusto", x: 14.6, z: 15.6, escala: 0.9 },
  { tipo: "arbusto", x: -15, z: 11.6, escala: 0.8 },
  { tipo: "arbusto", x: 19.6, z: 11.6, escala: 0.8 },
  { tipo: "plantaGrande", x: -9.6, z: 6.4 },
  { tipo: "plantaGrande", x: 14.6, z: 6.4 },
  { tipo: "planta", x: 6, z: 6.3 },
  { tipo: "planta", x: -2, z: 6.3 },
  { tipo: "lampara", x: 5.2, z: 16.1 },
  { tipo: "lampara", x: -1.2, z: 16.1 },
  // planters under the window
  { tipo: "macetero", x: -6, z: -16.3, ancho: 4.4, fondo: 0.6 },
  { tipo: "macetero", x: 6, z: -16.3, ancho: 4.4, fondo: 0.6 },
  { tipo: "macetero", x: 16, z: -16.3, ancho: 4.4, fondo: 0.6 },
  // your corner and the walls
  { tipo: "lampara", x: -21.2, z: -16.2 },
  { tipo: "plantaGrande", x: -14.2, z: -16.0 },
  { tipo: "librero", x: -21.6, z: -10.4, ry: Math.PI / 2 },
  { tipo: "librero", x: -21.6, z: -11.7, ry: Math.PI / 2 },
  { tipo: "cafeteria", x: 21.3, z: -6, ry: -Math.PI / 2 },
  { tipo: "plantaGrande", x: 21.2, z: -10.6 },
  { tipo: "plantaGrande", x: 21.2, z: -1.4 },
  { tipo: "planta", x: -21.2, z: 16.2 },
  { tipo: "planta", x: -21.2, z: 4.6 },
  { tipo: "cuadro", x: -21.85, z: -5, ry: Math.PI / 2, color: "#d9895b" },
  { tipo: "cuadro", x: 21.85, z: 2.6, ry: -Math.PI / 2, color: "#5aa06a" },
  { tipo: "reloj", x: -21.85, z: 1.5, ry: Math.PI / 2 },
];

function choques(): Rect[] {
  const r: Rect[] = paredes(ANCHO, FONDO);
  r.push(caja(TU_PUESTO_ESTUDIO.x, TU_PUESTO_ESTUDIO.z, 0.5, 1.05));
  for (const p of DECORACION) {
    const h = huellaPieza(p);
    if (h) r.push(h);
  }
  return r;
}

const ENTRADA: WP = { x: -20.7, z: 13.6 };

export const ESTUDIO: Entorno = {
  clave: "estudio",
  nombre: "Estudio abierto con jardín",
  tamano: { ancho: ANCHO, fondo: FONDO },
  zoom: 19,
  puestosBase: 3 * POR_ISLA,
  puesto,
  tuPuesto: TU_PUESTO_ESTUDIO,
  placaNombre: false,
  resaltarEspera: true,
  descanso: { asientos: ASIENTOS, cerca: CERCA, pasillo: null, nodo: "jardin" },
  puerta: { x: -21.6, z: 13.6 },
  entrada: ENTRADA,
  mostrador: null,
  choques: choques(),
  grafo: (bloqueado) =>
    grafoCuadricula(
      bloqueado,
      Array.from({ length: EN_ISLAS }, (_, i) => puesto(i)),
      ANCHO / 2 - 1,
      FONDO / 2 - 1,
      1,
      {
        jardin: { x: 2, z: 9.0 },
        entrada: ENTRADA,
        encuentro1: { x: 12, z: -14 },
        encuentro2: { x: -6, z: -14 },
        encuentro3: { x: 18.5, z: -6 },
        rincon1: { x: -12, z: 4 },
        rincon2: { x: 9, z: 9.5 },
        rincon3: { x: -6, z: 9.5 },
      },
    ),
  encuentros: ["encuentro1", "encuentro2", "encuentro3", "jardin"],
  paseo: {
    descanso: ["jardin", "rincon2", "rincon3"],
    destinos: [
      "jardin",
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
  puestosGrafo: EN_ISLAS,
  puestosVisibles,
  girarHaciaTi: true,
  decoracion: DECORACION,
  pisoCentral: { x0: -18, x1: 18, z0: -13, z1: 3.4 },
};
