// Office colour themes (floor and walls), the 9 of Agent Office 3D (MIT) with
// Spanish names, plus the current light one, which stays the default.

export interface Tema {
  key: string;
  nombre: string;
  /** null: the scene's own colour (light theme). */
  floor: string | null;
  wall: string | null;
}

export const TEMA_POR_DEFECTO = "claro";

export const TEMAS: Tema[] = [
  { key: "claro", nombre: "Claro (actual)", floor: null, wall: null },
  { key: "calido", nombre: "Cálido", floor: "#d8c7a8", wall: "#dcd3c2" },
  { key: "fresco", nombre: "Fresco", floor: "#c4cfd8", wall: "#d4d9df" },
  { key: "noche", nombre: "Noche", floor: "#40454e", wall: "#4c525b" },
  { key: "bosque", nombre: "Bosque", floor: "#bcc6ac", wall: "#ced4c3" },
  { key: "rosa", nombre: "Rosa", floor: "#e1cec9", wall: "#e7dad5" },
  { key: "loft", nombre: "Loft", floor: "#c7a880", wall: "#b8a794" },
  { key: "nordico", nombre: "Nórdico", floor: "#e6e4de", wall: "#f1efea" },
  { key: "atardecer", nombre: "Atardecer", floor: "#e0b489", wall: "#d9b6a0" },
  { key: "oceano", nombre: "Océano", floor: "#a9c8cc", wall: "#c2d6d8" },
];

export function temaPorClave(key: string | null | undefined): Tema {
  return TEMAS.find((t) => t.key === key) ?? TEMAS[0];
}
