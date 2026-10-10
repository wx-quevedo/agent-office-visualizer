import { create } from "zustand";
import { furnitureDef } from "./escena/furniture";

// Office layout (furniture placed on top of the fixed building) loaded from
// the repo: frontend/public/oficina3d/distribucion.json. The furniture editor
// of Agent Office 3D is not ported yet; its save format is the same.

export interface PlacedItem {
  id: string;
  type: string;
  x: number;
  z: number;
  ry: number;
}

export interface Distribucion {
  version: number;
  items: PlacedItem[];
  floorColor: string | null;
  wallColor: string | null;
}

export const RUTA_DISTRIBUCION = "/oficina3d/distribucion.json";

interface LayoutState {
  items: PlacedItem[];
  floorColor: string | null;
  wallColor: string | null;
  cargar(d: Distribucion): void;
}

export const useLayout = create<LayoutState>()((set) => ({
  items: [],
  floorColor: null,
  wallColor: null,
  cargar: (d) =>
    set({ items: d.items, floorColor: d.floorColor, wallColor: d.wallColor }),
}));

const color = (v: unknown): string | null =>
  typeof v === "string" && /^#[0-9a-f]{6}$/i.test(v) ? v : null;

/** Validates the JSON (only JSON.parse data, never code); unknown furniture is dropped. */
export function leerDistribucion(raw: unknown): Distribucion {
  const o = (raw && typeof raw === "object" ? raw : {}) as Record<
    string,
    unknown
  >;
  const items = Array.isArray(o.items) ? o.items : [];
  return {
    version: typeof o.version === "number" ? o.version : 1,
    items: items
      .filter(
        (it): it is PlacedItem =>
          !!it &&
          typeof it === "object" &&
          typeof (it as PlacedItem).id === "string" &&
          typeof (it as PlacedItem).type === "string" &&
          [
            (it as PlacedItem).x,
            (it as PlacedItem).z,
            (it as PlacedItem).ry,
          ].every((n) => typeof n === "number" && Number.isFinite(n)),
      )
      .filter((it) => furnitureDef(it.type) !== undefined),
    floorColor: color(o.floorColor),
    wallColor: color(o.wallColor),
  };
}

export async function cargarDistribucion(): Promise<void> {
  try {
    const r = await fetch(RUTA_DISTRIBUCION, { cache: "no-store" });
    if (!r.ok) return;
    useLayout.getState().cargar(leerDistribucion(await r.json()));
  } catch {
    // no layout file: the default office is used
  }
}
