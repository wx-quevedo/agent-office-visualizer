// Placeable furniture: types, names and sizes (no three.js; the drawings are
// in escena/furniture.tsx). The backend accepts the same types
// (backend/app/api/routes/oficina3d.py, TIPOS_MUEBLE).

export interface DefMueble {
  type: string;
  label: string;
  /** Base half sizes (at ry = 0), for the collision box. */
  hx: number;
  hz: number;
}

export const MUEBLES: DefMueble[] = [
  { type: "plant", label: "Planta", hx: 0.3, hz: 0.3 },
  { type: "desk", label: "Escritorio", hx: 0.72, hz: 0.42 },
  { type: "sofa", label: "Sofá", hx: 1.12, hz: 0.48 },
  { type: "coffee", label: "Mesa de centro", hx: 0.56, hz: 0.32 },
  { type: "meeting", label: "Mesa de reuniones", hx: 1.1, hz: 1.1 },
  { type: "shelf", label: "Librero", hx: 0.62, hz: 0.2 },
  { type: "lamp", label: "Lámpara", hx: 0.24, hz: 0.24 },
];

const POR_TIPO: Record<string, DefMueble> = Object.fromEntries(
  MUEBLES.map((m) => [m.type, m]),
);

export function defMueble(type: string): DefMueble | undefined {
  return POR_TIPO[type];
}

/** Rotated box half sizes of a placed piece (collision and path checks). */
export function huella(type: string, ry: number): { hx: number; hz: number } {
  const d = defMueble(type);
  if (!d) return { hx: 0.3, hz: 0.3 };
  const c = Math.abs(Math.cos(ry));
  const s = Math.abs(Math.sin(ry));
  return { hx: d.hx * c + d.hz * s + 0.05, hz: d.hx * s + d.hz * c + 0.05 };
}

/** Office limits for placed pieces (inside the outer walls). */
export const LIMITE_X = 22.5;
export const LIMITE_Z = 15.5;
