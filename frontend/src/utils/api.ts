/**
 * Requests to the backend of the office: base URL, sign-in redirect and a fetch
 * wrapper with the session cookie and the CSRF header.
 */

/** Backend port used when NEXT_PUBLIC_API_URL is unset. */
export const BACKEND_PORT = process.env.NEXT_PUBLIC_BACKEND_PORT || "8000";

/** Host the page was loaded from (so LAN/Tailscale clients reach the same machine). */
export const BACKEND_HOST =
  typeof window !== "undefined" ? window.location.hostname : "localhost";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || `http://${BACKEND_HOST}:${BACKEND_PORT}`;

/** Path of the sign-in page. */
export const RUTA_ENTRAR = "/entrar";

/**
 * Goes to /entrar and comes back here after signing in. Not from /entrar
 * itself (its own requests answer 401 while there is no session).
 */
export function irAEntrar(): void {
  if (typeof window === "undefined") return;
  const aqui = window.location.pathname + window.location.search;
  if (window.location.pathname.startsWith(RUTA_ENTRAR)) return;
  window.location.replace(`${RUTA_ENTRAR}?volver=${encodeURIComponent(aqui)}`);
}

/**
 * Fetch wrapper for the backend:
 * - sends the session cookie (credentials "include"; VISUALIZADOR_AUTH=activado),
 * - adds X-Visualizador: 1 to requests that change something (the backend asks
 *   for it with the cookie, against CSRF),
 * - on 401 (no session) goes to /entrar.
 * With access off (local) the backend never answers 401: nothing changes.
 */
export async function apiFetch(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  const headers = new Headers(init?.headers);
  const metodo = (init?.method ?? "GET").toUpperCase();
  if (metodo !== "GET" && metodo !== "HEAD") headers.set("X-Visualizador", "1");
  const r = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });
  if (r.status === 401) irAEntrar();
  return r;
}
