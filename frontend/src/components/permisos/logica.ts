/**
 * Permission requests answered from the office (state 13). Pure logic and the
 * calls to the backend (/api/v1/permisos), tested in tests/permisos.test.ts.
 */

import { API_BASE } from "@/utils/api";

export type EstadoPermiso =
  "pendiente" | "aprobada" | "rechazada" | "vencida" | "resuelta_fuera";

/** Request of an agent (field `permiso` of each agent in /agents/state). */
export interface Permiso {
  id: string;
  session_id: string;
  herramienta: string;
  detalle: string;
  cuenta: string | null;
  proyecto: string | null;
  creada: string;
  /** The hook waits for the office (policy and presence) and it is not decided yet. */
  esperando: boolean;
  vence: string | null;
  segundos_restantes: number;
  estado: EstadoPermiso;
  motivo: string | null;
  dispositivo: string | null;
  decidida: string | null;
}

export type Politica = "solo_en_el_celular" | "siempre" | "nunca";

export interface ConfigPermisos {
  politica: Politica;
  espera_seg: number;
  confirmar: string[];
  limites?: { espera_min: number; espera_max: number };
}

export const POLITICAS: Array<{ id: Politica; nombre: string; ayuda: string }> =
  [
    {
      id: "solo_en_el_celular",
      nombre: "Solo cuando estoy en el celular",
      ayuda:
        "Espera tu respuesta en la oficina solo si la tienes abierta en el celular y no en la PC. Si no la tienes abierta en ningún lado, o la tienes en la PC, responde VS Code como siempre. Si cierras la oficina en el celular mientras espera, deja de esperar.",
    },
    {
      id: "siempre",
      nombre: "Siempre",
      ayuda:
        "Siempre espera tu respuesta en la oficina, hasta el tiempo límite, aunque nadie la tenga abierta.",
    },
    {
      id: "nunca",
      nombre: "Nunca",
      ayuda: "Solo muestra la solicitud; se responde en VS Code.",
    },
  ];

export const CONFIG_POR_DEFECTO: ConfigPermisos = {
  politica: "solo_en_el_celular",
  espera_seg: 90,
  confirmar: [
    "rm",
    "rmdir",
    "del",
    "rd",
    "Remove-Item",
    "git push",
    "git reset --hard",
    "git clean",
    "deploy",
    "publish",
    "drop",
    "truncate",
    "format",
  ],
};

/** The office can still decide this request. */
export function sePuedeDecidir(p: Permiso | null | undefined): p is Permiso {
  return !!p && p.estado === "pendiente" && p.esperando;
}

/** Seconds left of the wait, from the backend expiry and the client clock. */
export function segundosRestantes(p: Permiso, ahora: number): number {
  if (!p.vence) return 0;
  return Math.max(0, Math.ceil((Date.parse(p.vence) - ahora) / 1000));
}

/** 85 -> "1:25". */
export function textoRestante(seg: number): string {
  const m = Math.floor(seg / 60);
  const s = seg % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

/**
 * The command deletes or uploads something: one of its parts (split by
 * ;, &&, ||, |, line breaks, parentheses) starts with a listed command
 * (also after sudo), or a single-word entry appears as a word of a part
 * ("npm run deploy"). Case-insensitive (Remove-Item, DEL).
 */
export function pideConfirmacion(
  herramienta: string,
  detalle: string,
  lista: string[],
): boolean {
  if (!/^(bash|powershell)$/i.test(herramienta)) return false;
  const partes = detalle
    .toLowerCase()
    .split(/\|\||&&|;|\||\r?\n|\(|\)|`|\$\(/)
    .map((p) => p.trim().replace(/^(sudo|exec|call)\s+/, ""))
    .filter(Boolean);
  for (const entrada of lista) {
    const c = entrada.trim().toLowerCase();
    if (!c) continue;
    for (const parte of partes) {
      if (parte === c || parte.startsWith(c + " ")) return true;
      if (!c.includes(" ") && parte.split(/\s+/).includes(c)) return true;
    }
  }
  return false;
}

/** Text when the office cannot answer this request. */
export function textoSinBotones(p: Permiso): string {
  if (p.estado === "aprobada")
    return `Aprobado desde ${p.dispositivo === "celular" ? "el celular" : "la PC"}.`;
  if (p.estado === "rechazada")
    return `Rechazado desde ${p.dispositivo === "celular" ? "el celular" : "la PC"}${p.motivo ? `: ${p.motivo}` : "."}`;
  if (p.estado === "resuelta_fuera") return "Ya se respondió en VS Code.";
  return "Responde en VS Code.";
}

// -- backend -----------------------------------------------------------------------

export interface ResultadoDecision {
  ok: boolean;
  permiso?: Permiso;
  error?: string;
}

export async function decidirPermiso(
  id: string,
  decision: "aprobar" | "rechazar",
  motivo: string | null,
  dispositivo: "pc" | "celular",
): Promise<ResultadoDecision> {
  try {
    const r = await fetch(
      `${API_BASE}/api/v1/permisos/solicitudes/${encodeURIComponent(id)}/decision`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          decision,
          motivo: motivo?.trim() || null,
          dispositivo,
        }),
      },
    );
    const body = (await r.json().catch(() => null)) as
      (Permiso & { detail?: unknown }) | null;
    if (!r.ok) {
      const detalle =
        body && typeof body.detail === "string"
          ? body.detail
          : `No se pudo enviar (HTTP ${r.status}).`;
      return { ok: false, error: detalle };
    }
    return { ok: true, permiso: body ?? undefined };
  } catch {
    return { ok: false, error: "No hay conexión con la oficina." };
  }
}

export async function leerConfigPermisos(): Promise<ConfigPermisos | null> {
  try {
    const r = await fetch(`${API_BASE}/api/v1/permisos/config`, {
      cache: "no-store",
    });
    if (!r.ok) return null;
    return (await r.json()) as ConfigPermisos;
  } catch {
    return null;
  }
}

export async function guardarConfigPermisos(
  c: ConfigPermisos,
): Promise<{ ok: boolean; config?: ConfigPermisos; error?: string }> {
  try {
    const r = await fetch(`${API_BASE}/api/v1/permisos/config`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        politica: c.politica,
        espera_seg: c.espera_seg,
        confirmar: c.confirmar,
      }),
    });
    const body = (await r.json().catch(() => null)) as
      (ConfigPermisos & { detail?: unknown }) | null;
    if (!r.ok)
      return {
        ok: false,
        error:
          body && typeof body.detail === "string"
            ? body.detail
            : `No se pudo guardar (HTTP ${r.status}).`,
      };
    return { ok: true, config: body ?? undefined };
  } catch {
    return { ok: false, error: "No hay conexión con la oficina." };
  }
}
