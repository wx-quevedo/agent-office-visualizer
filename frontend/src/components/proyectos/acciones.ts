"use client";

/**
 * Requests that change something in the projects (Prompt 38): a POST with a
 * JSON body that answers the new object or rejects with the "detail" of the
 * server, and a clock for the "hace cuánto" texts.
 */

import { useEffect, useState } from "react";
import { apiFetch } from "@/utils/api";
import { detalleError } from "./logica";

/** POST `ruta` with `cuerpo` (when given); resolves with the JSON answer. */
export async function enviarJson<T>(
  ruta: string,
  cuerpo?: unknown,
): Promise<T> {
  let r: Response;
  try {
    r = await apiFetch(ruta, {
      method: "POST",
      ...(cuerpo === undefined
        ? {}
        : {
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(cuerpo),
          }),
    });
  } catch {
    throw new Error("No se pudo conectar con el servidor; intenta de nuevo.");
  }
  if (!r.ok) throw new Error(await detalleError(r));
  return (await r.json()) as T;
}

/** The message of a rejected promise, for the screen. */
export function mensajeDe(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

/** Now, refreshed every `cadaMs` (for "hace 3 min" and "hoy 15:32"). */
export function useAhora(cadaMs = 30000): number {
  const [ahora, setAhora] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setAhora(Date.now()), cadaMs);
    return () => clearInterval(id);
  }, [cadaMs]);
  return ahora;
}
