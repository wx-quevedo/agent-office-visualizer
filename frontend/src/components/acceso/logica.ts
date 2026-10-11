/**
 * Sign-in (VISUALIZADOR_AUTH=activado): state of this browser and where to go
 * back after signing in. Tested in tests/acceso.test.ts.
 */

import { API_BASE, apiFetch } from "@/utils/api";

export interface EstadoAcceso {
  modo: "activado" | "desactivado";
  sesion: boolean;
  expira: string | null;
}

/**
 * Only a path of this site (never another host): no open redirect. Parsed as
 * the browser would (it drops tabs and new lines, so "/	/evil.com" would
 * become "//evil.com"): the result must keep this origin.
 */
export function destinoSeguro(volver: string | null): string {
  if (!volver || !volver.startsWith("/")) return "/oficina";
  const base =
    typeof window !== "undefined" ? window.location.origin : "http://localhost";
  let u: URL;
  try {
    u = new URL(volver, base);
  } catch {
    return "/oficina";
  }
  if (u.origin !== new URL(base).origin) return "/oficina";
  if (u.pathname.startsWith("/entrar")) return "/oficina";
  return u.pathname + u.search + u.hash;
}

/** Mode and session of this browser (null if the backend does not answer). */
export async function leerEstadoAcceso(): Promise<EstadoAcceso | null> {
  try {
    const r = await fetch(`${API_BASE}/api/v1/auth/estado`, {
      credentials: "include",
      cache: "no-store",
    });
    return r.ok ? ((await r.json()) as EstadoAcceso) : null;
  } catch {
    return null;
  }
}

/** Without a session (access on) a page must go to /entrar. */
export function debeEntrar(e: EstadoAcceso | null, ruta: string): boolean {
  return (
    !!e && e.modo === "activado" && !e.sesion && !ruta.startsWith("/entrar")
  );
}

/** Closes this session and goes to /entrar. */
export async function salir(): Promise<void> {
  try {
    await apiFetch("/api/v1/auth/salir", { method: "POST" });
  } finally {
    window.location.replace("/entrar");
  }
}
