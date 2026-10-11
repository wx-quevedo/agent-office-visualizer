"use client";

/**
 * Permission settings of this copy (policy, wait, commands that ask for
 * confirmation), read from the backend once per minute and shared by every
 * panel of the page.
 */

import { useEffect, useSyncExternalStore } from "react";
import {
  CONFIG_POR_DEFECTO,
  leerConfigPermisos,
  type ConfigPermisos,
} from "./logica";

let actual: ConfigPermisos = CONFIG_POR_DEFECTO;
let ultimaLectura = 0;
const oyentes = new Set<() => void>();

function suscribir(f: () => void): () => void {
  oyentes.add(f);
  return () => oyentes.delete(f);
}

export function fijarConfigPermisos(c: ConfigPermisos): void {
  actual = c;
  oyentes.forEach((f) => f());
}

export async function recargarConfigPermisos(): Promise<ConfigPermisos> {
  ultimaLectura = Date.now();
  const c = await leerConfigPermisos();
  if (c) fijarConfigPermisos(c);
  return actual;
}

export function useConfigPermisos(): ConfigPermisos {
  useEffect(() => {
    if (Date.now() - ultimaLectura > 60000) void recargarConfigPermisos();
  }, []);
  return useSyncExternalStore(
    suscribir,
    () => actual,
    () => CONFIG_POR_DEFECTO,
  );
}
