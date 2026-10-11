/**
 * App mode of /oficina/3d (stage 3, iOS app): with ?app=ios the page is shown
 * inside the app's WKWebView. The app draws its own header, tab bar and agent
 * card, so the page hides its bar and tells the app which agent was tapped
 * through the WebKit message handler "oficina". Tested in tests/oficina3d-app.test.ts.
 */

export const PARAM_APP = "app";
export const VALOR_IOS = "ios";
export const MANEJADOR = "oficina";

export type MensajeApp = { tipo: "agente"; id: string } | { tipo: "lista" };

interface ManejadorWebKit {
  postMessage(m: unknown): void;
}

interface VentanaConWebKit {
  webkit?: { messageHandlers?: Record<string, ManejadorWebKit | undefined> };
}

/** The page runs inside the iOS app (?app=ios). */
export function esModoApp(params: { get(k: string): string | null }): boolean {
  return params.get(PARAM_APP) === VALOR_IOS;
}

/** Sends a message to the app; false when there is no app listening. */
export function avisarApp(m: MensajeApp, w: unknown = globalThis): boolean {
  const h = (w as VentanaConWebKit).webkit?.messageHandlers?.[MANEJADOR];
  if (!h) return false;
  try {
    h.postMessage(m);
    return true;
  } catch {
    return false;
  }
}
