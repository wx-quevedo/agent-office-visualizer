/**
 * The active environment. The scene modules (roles, collision, nav, the
 * behaviour layer...) read it when they need it; changing it rebuilds the
 * navigation graph (listeners) and the scene remounts with agents placed.
 */

import { CONTROL } from "./control";
import { ORIGINAL } from "./original";
import { PUENTE } from "./puente";
import type { ClaveEntorno, Entorno } from "./tipos";

export const ENTORNOS: Entorno[] = [ORIGINAL, PUENTE, CONTROL];
export const ENTORNO_POR_DEFECTO: ClaveEntorno = "original";

let actual: Entorno = ORIGINAL;
const oyentes = new Set<(e: Entorno) => void>();

export function entornoActivo(): Entorno {
  return actual;
}

export function entornoPorClave(clave: string | null | undefined): Entorno {
  return ENTORNOS.find((e) => e.clave === clave) ?? ORIGINAL;
}

export function esClaveEntorno(clave: unknown): clave is ClaveEntorno {
  return typeof clave === "string" && ENTORNOS.some((e) => e.clave === clave);
}

/** Changes the active environment (no-op if it is already active). */
export function activarEntorno(clave: string | null | undefined): Entorno {
  const e = entornoPorClave(clave);
  if (e !== actual) {
    actual = e;
    for (const f of oyentes) f(e);
  }
  return actual;
}

/** Called when the environment changes (nav.ts rebuilds its graph). */
export function alCambiarEntorno(f: (e: Entorno) => void): () => void {
  oyentes.add(f);
  return () => oyentes.delete(f);
}
