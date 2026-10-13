/**
 * Alerts of the orchestrators that can be answered (Prompt 43), pure logic:
 * the API type, the link of "Responder", which cards show on each page, the
 * texts of the card and the voice, and the keys already alerted (one alert
 * per key, kept in localStorage by AvisosOrquestador).
 * No React, no fetch: tested in tests/avisos-orquestador.test.tsx.
 */

import { textoCorto, type Orden } from "@/components/proyectos/logica";
import { textoParaLeer } from "./deteccion";

/** GET /api/v1/avisos-orquestador, one per question or order waiting for you. */
export interface AvisoOrquestador {
  /** "orden:<id>" or "mensaje:<id>". */
  clave: string;
  tipo: "orden" | "pregunta";
  proyecto_id: string;
  /** Name of the project. */
  proyecto: string;
  maquina: string;
  cuenta: string;
  /** The question, or "Orden N para agente: <titulo>". */
  texto: string;
  /** ISO. */
  desde: string;
  hace_s: number;
  mensaje_id: string | null;
  orden: Orden | null;
}

export interface RespuestaAvisos {
  avisos: AvisoOrquestador[];
}

export const RUTA_AVISOS_ORQUESTADOR = "/api/v1/avisos-orquestador";
export const LECTURA_AVISOS_MS = 5000;
/** localStorage key of the keys already alerted. */
export const CLAVE_AVISADAS = "oficina-avisos-orquestador";
/** Only the latest keys are kept. */
export const MAX_AVISADAS = 200;

export type AccionAviso = "ignorar" | "esperar";

/** POST route of Ignorar or Esperar. */
export function rutaAccion(accion: AccionAviso): string {
  return `${RUTA_AVISOS_ORQUESTADOR}/${accion}`;
}

/** /proyectos/ver?id=<id>&seccion=chat&aviso=<clave>: where "Responder" goes. */
export function enlaceResponder(
  a: Pick<AvisoOrquestador, "proyecto_id" | "clave">,
): string {
  const q = new URLSearchParams({
    id: a.proyecto_id,
    seccion: "chat",
    aviso: a.clave,
  });
  return `/proyectos/ver?${q.toString()}`;
}

/** What the `aviso` of the URL points to in the chat, or null. */
export function objetivoAviso(
  aviso: string | null | undefined,
): { tipo: "mensaje" | "orden"; id: string } | null {
  if (!aviso) return null;
  const m = /^(mensaje|orden):(.+)$/.exec(aviso);
  if (!m) return null;
  return { tipo: m[1] as "mensaje" | "orden", id: m[2] };
}

/**
 * Cards to show: not the ones answered here (Ignorar or Esperar) and, on the
 * page of a project, not the ones of that project (its chat is right there and
 * the cards would cover the text field).
 */
export function avisosVisibles(
  avisos: AvisoOrquestador[],
  quitadas: ReadonlySet<string>,
  proyectoActual?: string | null,
): AvisoOrquestador[] {
  return avisos.filter(
    (a) =>
      !quitadas.has(a.clave) &&
      !(proyectoActual && a.proyecto_id === proyectoActual),
  );
}

/** "te hizo una pregunta" or "propone una orden". */
export function textoTipo(tipo: AvisoOrquestador["tipo"]): string {
  return tipo === "orden" ? "propone una orden" : "te hizo una pregunta";
}

/** Card text: the question or the order in one line, cut. */
export function textoTarjeta(a: Pick<AvisoOrquestador, "texto">): string {
  return textoCorto(a.texto, 180);
}

/** "hace 5 s", "hace 3 min", "hace 2 h", "hace 1 d". */
export function haceCuanto(segundos: number): string {
  const s = Math.max(0, Math.floor(Number.isFinite(segundos) ? segundos : 0));
  if (s < 60) return `hace ${s} s`;
  if (s < 3600) return `hace ${Math.floor(s / 60)} min`;
  if (s < 86400) return `hace ${Math.floor(s / 3600)} h`;
  return `hace ${Math.floor(s / 86400)} d`;
}

/** Seconds since the alert, now (the server's hace_s ages between reads). */
export function segundosDesde(
  a: Pick<AvisoOrquestador, "desde" | "hace_s">,
  ahora: number,
): number {
  const t = Date.parse(a.desde);
  if (Number.isNaN(t)) return a.hace_s;
  return Math.max(0, (ahora - t) / 1000);
}

/** Title of the notification: "tienda-web: el orquestador te hizo una pregunta". */
export function tituloAviso(
  a: Pick<AvisoOrquestador, "proyecto" | "tipo">,
): string {
  return `${a.proyecto}: el orquestador ${textoTipo(a.tipo)}`;
}

/** Spoken text: the title and the question or order, without code or paths. */
export function vozAviso(
  a: Pick<AvisoOrquestador, "proyecto" | "tipo" | "texto">,
): string {
  const leido = textoParaLeer(a.texto, 200);
  return leido ? `${tituloAviso(a)}. ${leido}` : tituloAviso(a);
}

/**
 * Keys of one read against the ones already alerted. On the first read of the
 * page nothing is alerted (the keys are only recorded, as DetectorAvisos does
 * on load); afterwards every key not alerted before is alerted once. The list
 * keeps the latest `MAX_AVISADAS` keys.
 */
export function revisarClaves(
  claves: string[],
  avisadas: string[],
  primera: boolean,
): { nuevas: string[]; avisadas: string[] } {
  const ya = new Set(avisadas);
  const sinVer = [...new Set(claves)].filter((c) => !ya.has(c));
  const todas = [...avisadas, ...sinVer];
  return {
    nuevas: primera ? [] : sinVer,
    avisadas: todas.slice(Math.max(0, todas.length - MAX_AVISADAS)),
  };
}

/** Keys already alerted, from localStorage (empty when blocked or broken). */
export function leerAvisadas(
  almacen: Pick<Storage, "getItem"> | null,
): string[] {
  try {
    const raw = almacen?.getItem(CLAVE_AVISADAS);
    if (!raw) return [];
    const v: unknown = JSON.parse(raw);
    return Array.isArray(v)
      ? v.filter((x): x is string => typeof x === "string")
      : [];
  } catch {
    return [];
  }
}

export function guardarAvisadas(
  almacen: Pick<Storage, "setItem"> | null,
  avisadas: string[],
): void {
  try {
    almacen?.setItem(
      CLAVE_AVISADAS,
      JSON.stringify(avisadas.slice(-MAX_AVISADAS)),
    );
  } catch {
    // private window or blocked storage: alerts are deduplicated in memory only
  }
}
