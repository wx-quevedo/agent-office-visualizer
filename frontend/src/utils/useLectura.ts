"use client";

/**
 * Reads a JSON endpoint now and every `cadaMs` (null route: nothing). Keeps the
 * last good data while a later read fails; the data is reset when the route
 * changes (another agent or another page of the history).
 */

import { useEffect, useState } from "react";
import { apiFetch } from "./api";

export interface Lectura<T> {
  datos: T | null;
  error: string | null;
}

export function useLectura<T>(ruta: string | null, cadaMs = 10000): Lectura<T> {
  const [estado, setEstado] = useState<Lectura<T> & { ruta: string | null }>({
    datos: null,
    error: null,
    ruta,
  });
  useEffect(() => {
    if (!ruta) return;
    let vivo = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const cargar = async () => {
      try {
        const r = await apiFetch(ruta, { cache: "no-store" });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const j = (await r.json()) as T;
        if (vivo) setEstado({ datos: j, error: null, ruta });
      } catch (e) {
        if (vivo)
          setEstado((v) => ({
            datos: v.ruta === ruta ? v.datos : null,
            error: e instanceof Error ? e.message : String(e),
            ruta,
          }));
      } finally {
        if (vivo) timer = setTimeout(cargar, cadaMs);
      }
    };
    void cargar();
    return () => {
      vivo = false;
      if (timer) clearTimeout(timer);
    };
  }, [ruta, cadaMs]);
  if (!ruta || estado.ruta !== ruta) return { datos: null, error: null };
  return { datos: estado.datos, error: estado.error };
}
