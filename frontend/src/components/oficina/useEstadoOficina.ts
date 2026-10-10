"use client";

/**
 * Shared by /oficina and /oficina/3d: the engine state every 2 s and the
 * presence heartbeat (an open page counts as the user being present).
 */

import { useEffect, useState } from "react";
import { API_BASE } from "@/utils/api";
import { dispositivo, type Estado } from "./logica";

const REFRESCO_MS = 2000;
const LATIDO_MS = 30000;

export interface EstadoOficina {
  datos: Estado | null;
  error: string | null;
  /** Time of the last successful read (ms). */
  recibido: number | null;
  /** Client clock, updated on every read. */
  ahora: number;
}

/** GET /api/v1/agents/state every 2 s (at most), one request at a time. */
export function useEstadoOficina(): EstadoOficina {
  const [datos, setDatos] = useState<Estado | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recibido, setRecibido] = useState<number | null>(null);
  const [ahora, setAhora] = useState(() => Date.now());

  useEffect(() => {
    let vivo = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const cargar = async () => {
      try {
        const r = await fetch(`${API_BASE}/api/v1/agents/state`, {
          cache: "no-store",
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const d = (await r.json()) as Estado;
        if (!vivo) return;
        setDatos(d);
        setError(null);
        setRecibido(Date.now());
      } catch (e) {
        if (vivo) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (vivo) {
          setAhora(Date.now());
          timer = setTimeout(cargar, REFRESCO_MS);
        }
      }
    };
    void cargar();
    return () => {
      vivo = false;
      if (timer) clearTimeout(timer);
    };
  }, []);

  return { datos, error, recibido, ahora };
}

function nuevoCliente(): string {
  try {
    return crypto.randomUUID();
  } catch {
    return `oficina-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  }
}

/** POST /api/v1/agents/presence on open and every 30 s (PC or phone). */
export function useLatidoPresencia(): void {
  useEffect(() => {
    const cliente = nuevoCliente();
    const latir = () => {
      const cuerpo = JSON.stringify({
        cliente,
        dispositivo: dispositivo(window.innerWidth, navigator.userAgent),
      });
      void fetch(`${API_BASE}/api/v1/agents/presence`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: cuerpo,
      }).catch(() => undefined);
    };
    latir();
    const id = setInterval(latir, LATIDO_MS);
    return () => clearInterval(id);
  }, []);
}
