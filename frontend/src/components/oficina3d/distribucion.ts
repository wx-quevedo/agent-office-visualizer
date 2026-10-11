import { create } from "zustand";
import { apiFetch } from "@/utils/api";
import { defMueble, LIMITE_X, LIMITE_Z } from "./muebles";
import {
  ENTORNO_POR_DEFECTO,
  entornoPorClave,
  esClaveEntorno,
} from "./entornos/activo";
import type { ClaveEntorno } from "./entornos/tipos";
import { TEMA_POR_DEFECTO } from "./temas";

// Office layout: furniture placed on top of the fixed building and the colour
// theme. Each copy keeps its own in its data folder, through the backend
// (GET/PUT /api/v1/oficina3d/distribucion); the base is
// frontend/public/oficina3d/distribucion.json (also the fallback when the
// backend does not answer). Same format as the Agent Office 3D layout.

export interface PlacedItem {
  id: string;
  type: string;
  x: number;
  z: number;
  ry: number;
}

/** Furniture and colours of one environment. */
export interface Disposicion {
  items: PlacedItem[];
  floorColor: string | null;
  wallColor: string | null;
  /** Theme key (temas.ts); the colours above are the ones drawn. */
  tema: string | null;
}

/**
 * Saved JSON. The top-level layout is the Original environment's (compatible
 * with files saved before environments existed); `entornos` keeps the layout
 * of every other environment, and `entorno` is the active one (the PC and the
 * iPhone see the same).
 */
export interface Distribucion extends Disposicion {
  version: number;
  entorno: ClaveEntorno;
  entornos: Partial<Record<ClaveEntorno, Disposicion>>;
}

export const RUTA_DISTRIBUCION = "/oficina3d/distribucion.json";
export const URL_DISTRIBUCION = "/api/v1/oficina3d/distribucion";

export const DISPOSICION_VACIA: Disposicion = {
  items: [],
  floorColor: null,
  wallColor: null,
  tema: TEMA_POR_DEFECTO,
};

interface LayoutState extends Disposicion {
  /** Active environment. */
  entorno: ClaveEntorno;
  /** Layout of each environment (the active one is kept in the fields above). */
  guardadas: Partial<Record<ClaveEntorno, Disposicion>>;
  /** Where the layout came from: saved in this copy, the repo base, or nothing yet. */
  origen: "guardada" | "base" | null;
  cargar(d: Distribucion, origen?: "guardada" | "base"): void;
  /** Switches the environment; each one keeps its own furniture and theme. */
  cambiarEntorno(clave: ClaveEntorno): void;
}

function activaDe(s: Disposicion): Disposicion {
  return {
    items: s.items,
    floorColor: s.floorColor,
    wallColor: s.wallColor,
    tema: s.tema,
  };
}

export const useLayout = create<LayoutState>()((set, get) => ({
  ...DISPOSICION_VACIA,
  entorno: ENTORNO_POR_DEFECTO,
  guardadas: {},
  origen: null,
  cargar: (d, origen) => {
    const guardadas: Partial<Record<ClaveEntorno, Disposicion>> = {
      ...d.entornos,
      original: activaDe(d),
    };
    const activa = guardadas[d.entorno] ?? DISPOSICION_VACIA;
    set({
      ...activa,
      entorno: d.entorno,
      guardadas,
      origen: origen ?? get().origen,
    });
  },
  cambiarEntorno: (clave) => {
    const s = get();
    if (clave === s.entorno) return;
    const guardadas = { ...s.guardadas, [s.entorno]: activaDe(s) };
    set({
      ...(guardadas[clave] ?? DISPOSICION_VACIA),
      entorno: clave,
      guardadas,
    });
  },
}));

function componer(
  entorno: ClaveEntorno,
  todas: Partial<Record<ClaveEntorno, Disposicion>>,
): Distribucion {
  const { original, ...otras } = todas;
  return {
    version: 1,
    ...(original ?? DISPOSICION_VACIA),
    entorno,
    entornos: otras,
  };
}

/** Whole layout (all environments) as saved/exported. */
export function distribucionActual(): Distribucion {
  return distribucionCon({});
}

/** Whole layout with a change applied to the active environment (editor). */
export function distribucionCon(cambio: Partial<Disposicion>): Distribucion {
  const s = useLayout.getState();
  return componer(s.entorno, {
    ...s.guardadas,
    [s.entorno]: { ...activaDe(s), ...cambio },
  });
}

const color = (v: unknown): string | null =>
  typeof v === "string" && /^#[0-9a-f]{6}$/i.test(v) ? v : null;

/**
 * Validates the JSON (only JSON.parse data, never code): unknown furniture,
 * pieces outside the office and bad values are dropped; repeated ids too.
 */
function leerDisposicion(
  raw: unknown,
  limites: { x: number; z: number },
): Disposicion {
  const o = (raw && typeof raw === "object" ? raw : {}) as Record<
    string,
    unknown
  >;
  const items = Array.isArray(o.items) ? o.items : [];
  const vistos = new Set<string>();
  return {
    items: items.filter((it): it is PlacedItem => {
      if (!it || typeof it !== "object") return false;
      const m = it as PlacedItem;
      const ok =
        typeof m.id === "string" &&
        /^[A-Za-z0-9_-]{1,64}$/.test(m.id) &&
        typeof m.type === "string" &&
        defMueble(m.type) !== undefined &&
        [m.x, m.z, m.ry].every(
          (n) => typeof n === "number" && Number.isFinite(n),
        ) &&
        Math.abs(m.x) <= Math.min(LIMITE_X, limites.x) &&
        Math.abs(m.z) <= Math.min(LIMITE_Z, limites.z) &&
        Math.abs(m.ry) <= 7 &&
        !vistos.has(m.id);
      if (ok) vistos.add(m.id);
      return ok;
    }),
    floorColor: color(o.floorColor),
    wallColor: color(o.wallColor),
    tema:
      typeof o.tema === "string" && /^[a-z]{1,32}$/.test(o.tema)
        ? o.tema
        : TEMA_POR_DEFECTO,
  };
}

/**
 * Validates the JSON (only JSON.parse data, never code): unknown furniture,
 * pieces outside the office and bad values are dropped; repeated ids too;
 * unknown environments are ignored.
 */
export function leerDistribucion(raw: unknown): Distribucion {
  const o = (raw && typeof raw === "object" ? raw : {}) as Record<
    string,
    unknown
  >;
  const mapa = (
    o.entornos && typeof o.entornos === "object" ? o.entornos : {}
  ) as Record<string, unknown>;
  const entornos: Partial<Record<ClaveEntorno, Disposicion>> = {};
  for (const [clave, d] of Object.entries(mapa)) {
    if (esClaveEntorno(clave) && clave !== "original") {
      entornos[clave] = leerDisposicion(d, entornoPorClave(clave).limites);
    }
  }
  return {
    version: typeof o.version === "number" ? o.version : 1,
    ...leerDisposicion(o, entornoPorClave("original").limites),
    entorno: esClaveEntorno(o.entorno) ? o.entorno : ENTORNO_POR_DEFECTO,
    entornos,
  };
}

/** Layout of this copy from the backend; the repo base if it does not answer. */
export async function cargarDistribucion(): Promise<void> {
  try {
    const r = await apiFetch(URL_DISTRIBUCION, { cache: "no-store" });
    if (r.ok) {
      const body = (await r.json()) as {
        origen?: string;
        distribucion?: unknown;
      };
      useLayout
        .getState()
        .cargar(
          leerDistribucion(body.distribucion),
          body.origen === "guardada" ? "guardada" : "base",
        );
      return;
    }
  } catch {
    // backend not available: try the base file of the repo
  }
  try {
    const r = await fetch(RUTA_DISTRIBUCION, { cache: "no-store" });
    if (r.ok)
      useLayout.getState().cargar(leerDistribucion(await r.json()), "base");
  } catch {
    // no layout file: the default office is used
  }
}

/** Saves the layout in this copy. Returns an error message, or null when saved. */
export async function guardarDistribucion(
  d: Distribucion,
): Promise<string | null> {
  try {
    const r = await apiFetch(URL_DISTRIBUCION, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(d),
    });
    if (r.ok) return null;
    const body = (await r.json().catch(() => null)) as {
      detail?: unknown;
    } | null;
    const detalle = Array.isArray(body?.detail)
      ? body.detail.join("; ")
      : String(body?.detail ?? "");
    return `El servidor no aceptó la distribución (HTTP ${r.status}). ${detalle}`.trim();
  } catch (e) {
    return `No se pudo guardar: ${e instanceof Error ? e.message : String(e)}`;
  }
}

/** Downloads the layout as a JSON file (to take it to the other copy). */
export function exportarDistribucion(d: Distribucion): void {
  const blob = new Blob([JSON.stringify(d, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "distribucion-oficina.json";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
