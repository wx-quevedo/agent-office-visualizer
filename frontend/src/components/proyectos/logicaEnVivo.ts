/**
 * Live state of the chat (Prompt 45): the orchestrator read the message and is
 * answering, with the text as it is written. Pure logic (tested without a
 * browser); the hook is useChatEnVivo.ts and the view is Chat.tsx.
 */

import type { EnVivo, Mensaje } from "./logica";

/** Body of `/chat/en-vivo` and `data` of each `chat` event of `/chat/eventos`. */
export interface ChatEnVivo {
  version: string;
  en_vivo: EnVivo;
  recientes: Mensaje[];
}

/** Consecutive EventSource errors without a message before polling instead. */
export const MAX_ERRORES_SSE = 3;

/** Poll interval of `/chat/en-vivo` when EventSource is not usable. */
export const CONSULTA_MS = 1000;

/** Route of the Server-Sent Events of the chat of a project. */
export function rutaEventos(id: string): string {
  return `/api/v1/proyectos-creados/${encodeURIComponent(id)}/chat/eventos`;
}

/** Route of the light JSON of the live state of the chat. */
export function rutaEnVivo(id: string): string {
  return `/api/v1/proyectos-creados/${encodeURIComponent(id)}/chat/en-vivo`;
}

const ESTADOS_EN_VIVO = new Set(["libre", "leido", "respondiendo"]);

function texto(v: unknown): string | null {
  return typeof v === "string" ? v : null;
}

/** A message of `recientes` (null when it lacks id, autor, texto or creado). */
function leerMensaje(v: unknown): Mensaje | null {
  if (!v || typeof v !== "object") return null;
  const o = v as Record<string, unknown>;
  const id = texto(o.id);
  const t = texto(o.texto);
  const creado = texto(o.creado);
  if (
    !id ||
    t === null ||
    !creado ||
    (o.autor !== "washington" && o.autor !== "orquestador")
  )
    return null;
  const m: Mensaje = { id, autor: o.autor, texto: t, creado };
  if (
    o.estado === null ||
    o.estado === "enviado" ||
    o.estado === "leido" ||
    o.estado === "respondiendo"
  )
    m.estado = o.estado;
  if (o.leido === null || typeof o.leido === "string") m.leido = o.leido;
  return m;
}

/** `en_vivo` of the server (null when it is not one). */
export function leerEnVivo(v: unknown): EnVivo | null {
  if (!v || typeof v !== "object") return null;
  const o = v as Record<string, unknown>;
  if (typeof o.estado !== "string" || !ESTADOS_EN_VIVO.has(o.estado))
    return null;
  return {
    estado: o.estado as EnVivo["estado"],
    parcial: texto(o.parcial) ?? "",
    mensaje_id: texto(o.mensaje_id),
    desde: texto(o.desde),
    actualizado: texto(o.actualizado),
  };
}

/**
 * The JSON of `/chat/en-vivo` (or the `data` of an event, already parsed or
 * as text). Null when it does not have the expected shape.
 */
export function leerChatEnVivo(v: unknown): ChatEnVivo | null {
  let datos = v;
  if (typeof v === "string") {
    try {
      datos = JSON.parse(v);
    } catch {
      return null;
    }
  }
  if (!datos || typeof datos !== "object") return null;
  const o = datos as Record<string, unknown>;
  const enVivo = leerEnVivo(o.en_vivo);
  if (!enVivo) return null;
  const recientes = Array.isArray(o.recientes)
    ? o.recientes.map(leerMensaje).filter((m): m is Mensaje => m !== null)
    : [];
  return { version: texto(o.version) ?? "", en_vivo: enVivo, recientes };
}

/**
 * The read messages with the recent ones of the live state: each recent one
 * replaces the read one with its id (fresher `estado`) and the new ones go at
 * the end (mezclarChat sorts them by `creado`).
 */
export function unirRecientes(
  leidos: Mensaje[],
  recientes: Mensaje[] | null | undefined,
): Mensaje[] {
  if (!recientes || recientes.length === 0) return leidos;
  const porId = new Map(recientes.map((m) => [m.id, m]));
  const unidos = leidos.map((m) => porId.get(m.id) ?? m);
  const ids = new Set(leidos.map((m) => m.id));
  return [...unidos, ...recientes.filter((m) => !ids.has(m.id))];
}

/** Mark under one of Washington's bubbles, next to the time. */
export type Marca = "Enviando…" | "Enviado" | "Leído";

/** "Enviando…" while it is sent, then "Enviado" and "Leído"; null for the orchestrator. */
export function marcaMensaje(m: Mensaje, pendiente = false): Marca | null {
  if (m.autor !== "washington") return null;
  if (pendiente) return "Enviando…";
  if (m.estado === "leido" || m.estado === "respondiendo" || m.leido)
    return "Leído";
  return "Enviado";
}

/** What the live bubble of the orchestrator shows (null: no bubble). */
export type BurbujaEnVivo =
  { tipo: "puntos" } | { tipo: "texto"; texto: string };

function tiempo(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const t = Date.parse(iso);
  return Number.isNaN(t) ? null : t;
}

/**
 * The live bubble: three dots while the orchestrator answers without text yet,
 * the partial text once there is some. None when it is free, or when an
 * orchestrator message newer than the last change of the live state is already
 * in the list (the final answer arrived before the live state said "libre").
 */
export function burbujaEnVivo(
  enVivo: EnVivo | null | undefined,
  mensajes: Mensaje[] = [],
): BurbujaEnVivo | null {
  if (!enVivo || enVivo.estado !== "respondiendo") return null;
  const cambio = tiempo(enVivo.actualizado) ?? tiempo(enVivo.desde);
  if (cambio !== null) {
    const llego = mensajes.some((m) => {
      if (m.autor !== "orquestador") return false;
      const t = tiempo(m.creado);
      return t !== null && t >= cambio;
    });
    if (llego) return null;
  }
  return enVivo.parcial
    ? { tipo: "texto", texto: enVivo.parcial }
    : { tipo: "puntos" };
}

/** Connection state of the hook: EventSource, or polling after failing. */
export interface Conexion {
  modo: "sse" | "consulta";
  errores: number;
}

export function conexionInicial(hayEventSource: boolean): Conexion {
  return { modo: hayEventSource ? "sse" : "consulta", errores: 0 };
}

/**
 * Next connection state. A message resets the errors; an error adds one, and
 * after MAX_ERRORES_SSE in a row (or when EventSource closed for good, which
 * it does on an HTTP error) the hook polls instead. Polling stays.
 */
export function siguienteConexion(
  c: Conexion,
  evento: "mensaje" | "error" | "cerrado",
): Conexion {
  if (c.modo === "consulta") return c;
  if (evento === "mensaje") return c.errores === 0 ? c : { ...c, errores: 0 };
  const errores = c.errores + 1;
  if (evento === "cerrado" || errores >= MAX_ERRORES_SSE)
    return { modo: "consulta", errores };
  return { modo: "sse", errores };
}
