/**
 * Pure logic of the agent card (ficha) and of "Dónde quedamos": texts, figures
 * and turns. No React, no fetch: tested in tests/ficha.test.ts.
 */

import type { Agente } from "@/components/oficina/logica";

// -- shapes of the stage 2.1 endpoints ---------------------------------------------

export type Resultado =
  "completado" | "esperando" | "interrumpido" | "error" | "en_curso";

/** One turn of GET /agents/{id}/historial (historial.py). */
export interface Turno {
  numero: number;
  inicio: string;
  fin: string | null;
  duracion_s: number;
  pedido: string | null;
  herramientas: Record<string, number>;
  total_herramientas: number;
  archivos_editados: string[];
  commits: { hora: string; mensaje: string | null }[];
  errores: number;
  tokens_salida: number | null;
  resultado: Resultado | string;
  pregunta: string | null;
}

export interface Historial {
  session_id?: string;
  proyecto?: string | null;
  cuenta?: string | null;
  modelo?: string | null;
  maquina?: string | null;
  pagina: number;
  por_pagina: number;
  total: number;
  paginas: number;
  turnos: Turno[];
}

/** GET /consumo (only the parts the card and "Dónde quedamos" use). */
export interface Consumo {
  dia: string;
  total: {
    sesiones: number;
    tokens_salida: number;
    segundos_trabajo: number;
    segundos_con_agentes: number;
  };
  por_sesion: {
    session_id: string;
    proyecto: string | null;
    tokens_salida: number;
    segundos_trabajo: number;
    continuo_s: number;
  }[];
}

// -- numbers and times ----------------------------------------------------------------

/** 312480 → "312 480" (no-break spaces, as in the mockups). */
export function miles(n: number | null | undefined): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "—";
  return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
}

/** Seconds as "45 s", "2 min 14 s", "1 h 05 min". */
export function tiempoExacto(seg: number | null | undefined): string {
  if (seg === null || seg === undefined || !Number.isFinite(seg)) return "—";
  const s = Math.max(0, Math.floor(seg));
  if (s < 60) return `${s} s`;
  if (s < 3600) {
    const r = s % 60;
    return r
      ? `${Math.floor(s / 60)} min ${String(r).padStart(2, "0")} s`
      : `${s / 60} min`;
  }
  const m = Math.floor((s % 3600) / 60);
  return `${Math.floor(s / 3600)} h ${String(m).padStart(2, "0")} min`;
}

/** Seconds as "34 min", "4 h 35 min" (no seconds). */
export function tiempoCorto(seg: number | null | undefined): string {
  if (seg === null || seg === undefined || !Number.isFinite(seg)) return "—";
  const s = Math.max(0, Math.floor(seg));
  if (s < 60) return `${s} s`;
  if (s < 3600) return `${Math.floor(s / 60)} min`;
  const m = Math.floor((s % 3600) / 60);
  return m ? `${Math.floor(s / 3600)} h ${m} min` : `${Math.floor(s / 3600)} h`;
}

function segundosDesde(
  iso: string | null | undefined,
  ahora: number,
): number | null {
  if (!iso) return null;
  const t = Date.parse(iso);
  return Number.isNaN(t) ? null : Math.max(0, (ahora - t) / 1000);
}

export function haceTiempo(
  iso: string | null | undefined,
  ahora: number,
): string {
  const s = segundosDesde(iso, ahora);
  return s === null ? "—" : `hace ${tiempoCorto(s)}`;
}

/** "09:12" in the browser's time zone. */
export function horaMinuto(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString("es", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

const MESES = [
  "ene",
  "feb",
  "mar",
  "abr",
  "may",
  "jun",
  "jul",
  "ago",
  "sept",
  "oct",
  "nov",
  "dic",
];

/** "hoy 10:36", "ayer 18:20" or "9 oct 18:20" (local days). */
export function cuando(iso: string | null | undefined, ahora: number): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const hoy = new Date(ahora);
  const dia = (x: Date) =>
    new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const dias = Math.round((dia(hoy) - dia(d)) / 86400000);
  const hm = horaMinuto(iso);
  if (dias === 0) return `hoy ${hm}`;
  if (dias === 1) return `ayer ${hm}`;
  return `${d.getDate()} ${MESES[d.getMonth()]} ${hm}`;
}

// -- header -----------------------------------------------------------------------------

export function nombreCarpeta(ruta: string | null | undefined): string {
  if (!ruta) return "Sin proyecto";
  const partes = ruta.split(/[\\/]/).filter(Boolean);
  return partes[partes.length - 1] ?? ruta;
}

/** "SkyNest" → "SK", "vive-demo" → "VB", "visualizador-agentes" → "VA". */
export function iniciales(nombre: string): string {
  const palabras = nombre
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .split(/[\s_\-.]+/)
    .filter((p) => /[\p{L}\p{N}]/u.test(p));
  if (palabras.length >= 2)
    return (palabras[0][0] + palabras[1][0]).toUpperCase();
  const una = (palabras[0] ?? nombre).replace(/[^\p{L}\p{N}]/gu, "");
  return (una.slice(0, 2) || "?").toUpperCase();
}

export function textoCuenta(cuenta: string | null | undefined): string | null {
  if (cuenta === "demo") return "Cuenta Demo Org";
  if (cuenta === "personal") return "Cuenta personal";
  return null;
}

/** "claude-opus-5-5[1m]" → "Opus 5.5"; unknown ids are shown as they come. */
export function nombreModelo(modelo: string | null | undefined): string | null {
  if (!modelo) return null;
  const m =
    /(opus|sonnet|haiku|fable)[-_ ]?(\d+)(?:[-_.](\d{1,2}))?(?!\d)/i.exec(
      modelo,
    );
  if (!m) return modelo;
  const familia = m[1][0].toUpperCase() + m[1].slice(1).toLowerCase();
  return m[3] ? `${familia} ${m[2]}.${m[3]}` : `${familia} ${m[2]}`;
}

export function nombreMaquina(
  maquina: string | null | undefined,
): string | null {
  if (!maquina) return null;
  return maquina[0].toUpperCase() + maquina.slice(1);
}

// -- permission in one clear sentence ------------------------------------------------------

const BORRAR = /\b(?:rm|rmdir|del|rd|remove-item|git\s+clean)\b/i;
const SUBIR = /\bgit\s+push\b/i;
const COMMIT = /\bgit\s+commit\b/i;
const RESET = /\bgit\s+reset\s+--hard\b/i;
const INSTALAR =
  /\b(?:npm|pnpm|yarn|bun)\s+(?:i|install|add)\b|\b(?:pip|uv)\s+(?:install|add|sync)\b/i;
const DESPLEGAR = /\b(?:deploy|desplegar|publish)\b/i;

/** What a permission request asks for, in one sentence (the command goes below). */
export function fraseDePermiso(herramienta: string, detalle: string): string {
  const h = herramienta.toLowerCase();
  const d = detalle ?? "";
  if (h === "bash" || h === "powershell") {
    if (RESET.test(d))
      return "Quiere descartar cambios del repositorio (git reset --hard).";
    if (BORRAR.test(d)) return "Quiere borrar archivos o carpetas.";
    if (SUBIR.test(d))
      return "Quiere subir los cambios al repositorio remoto (git push).";
    if (DESPLEGAR.test(d)) return "Quiere desplegar o publicar.";
    if (COMMIT.test(d)) return "Quiere guardar los cambios en un commit.";
    if (INSTALAR.test(d)) return "Quiere instalar dependencias.";
    return `Quiere ejecutar un comando en ${h === "bash" ? "la terminal" : "PowerShell"}.`;
  }
  if (h === "edit" || h === "multiedit")
    return `Quiere editar ${nombreCarpeta(d.split(/\s/)[0])}.`;
  if (h === "write")
    return `Quiere crear o reemplazar ${nombreCarpeta(d.split(/\s/)[0])}.`;
  if (h === "notebookedit") return "Quiere editar un cuaderno.";
  if (h === "webfetch") return "Quiere abrir una página web.";
  if (h === "websearch") return "Quiere buscar en la web.";
  if (h.startsWith("mcp__")) {
    const [, servidor = "", accion = ""] = herramienta.split("__");
    const s = servidor.replace(/^plugin_[^_]+_/, "");
    return `Quiere usar ${accion || "una herramienta"} de ${s || "un conector"}.`;
  }
  return `Quiere usar ${herramienta}.`;
}

// -- the three figures ----------------------------------------------------------------------

export interface Cifra {
  titulo: string;
  valor: string;
  alerta?: boolean;
}

export function tokensHoy(
  consumo: Consumo | null | undefined,
  sesion: string,
): number | null {
  if (!consumo) return null;
  const s = consumo.por_sesion.find((x) => x.session_id === sesion);
  return s ? s.tokens_salida : 0;
}

/** Continuous work, today's tokens and stuck or errors. */
export function cifras(
  a: Agente,
  tokens: number | null,
  ahora: number,
): Cifra[] {
  const continuo = a.trabajo_continuo_s ?? 0;
  const errores = a.indicadores.errores_seguidos ?? 0;
  const tercera: Cifra = a.atasco
    ? {
        titulo: "Atasco",
        valor: tiempoCorto(segundosDesde(a.atasco.desde, ahora)),
        alerta: true,
      }
    : errores > 0
      ? {
          titulo: "Errores",
          valor: `${errores} ${errores === 1 ? "seguido" : "seguidos"}`,
          alerta: errores >= 3,
        }
      : { titulo: "Atascos", valor: "Ninguno" };
  return [
    {
      titulo: "Trabajo continuo",
      valor: continuo > 0 ? tiempoCorto(continuo) : "—",
    },
    { titulo: "Tokens hoy", valor: miles(tokens) },
    tercera,
  ];
}

// -- "Ahora mismo" --------------------------------------------------------------------------

export interface AhoraMismo {
  texto: string;
  tiempo: string;
  razonable: string | null;
}

export function ahoraMismo(a: Agente, ahora: number): AhoraMismo {
  if (a.cierre) {
    return {
      texto: `Sesión cerrada (${a.cierre.motivo})`,
      tiempo: tiempoExacto(segundosDesde(a.cierre.desde, ahora)),
      razonable: null,
    };
  }
  const e = a.espera_detalle;
  if (e) {
    return {
      texto: e.base,
      tiempo: tiempoExacto(e.segundos),
      razonable:
        e.limite_min !== null && e.limite_min !== undefined
          ? `Tiempo razonable para esto: hasta ${e.limite_min} min`
          : null,
    };
  }
  return {
    texto: a.estado.nombre,
    tiempo: tiempoExacto(segundosDesde(a.estado.desde, ahora)),
    razonable: null,
  };
}

// -- turns ------------------------------------------------------------------------------

export const RESULTADOS: Record<
  string,
  { texto: string; tono: "bien" | "aviso" | "mal" | "info" | "neutro" }
> = {
  completado: { texto: "Completado", tono: "bien" },
  esperando: { texto: "Te esperó", tono: "info" },
  interrumpido: { texto: "Interrumpido", tono: "aviso" },
  error: { texto: "Con error", tono: "mal" },
  en_curso: { texto: "En curso", tono: "neutro" },
};

export function resultado(r: string): {
  texto: string;
  tono: "bien" | "aviso" | "mal" | "info" | "neutro";
} {
  return RESULTADOS[r] ?? { texto: r, tono: "neutro" };
}

export function plural(n: number, uno: string, varios: string): string {
  return `${miles(n)} ${n === 1 ? uno : varios}`;
}

/** "48 herramientas · 3 archivos editados · 1 commit: … · 52 735 tokens". */
export function resumenTurno(t: Turno): string {
  const partes = [plural(t.total_herramientas, "herramienta", "herramientas")];
  const n = t.archivos_editados.length;
  partes.push(
    n
      ? plural(n, "archivo editado", "archivos editados")
      : "sin archivos editados",
  );
  if (t.commits.length) {
    const ultimo = t.commits[t.commits.length - 1].mensaje;
    partes.push(
      t.commits.length === 1
        ? `commit${ultimo ? `: ${ultimo}` : ""}`
        : `${t.commits.length} commits`,
    );
  } else {
    partes.push(t.fin ? "sin commit" : "sin commit todavía");
  }
  if (t.tokens_salida !== null && t.tokens_salida !== undefined) {
    partes.push(`${miles(t.tokens_salida)} tokens`);
  }
  return partes.join(" · ");
}

export function pedidoDe(t: Turno): string {
  return t.pedido ?? "(trabajo sin pedido visible)";
}

/** The current (open) turn and the previous ones, newest first. */
export function separarTurnos(turnos: Turno[]): {
  actual: Turno | null;
  anteriores: Turno[];
} {
  if (!turnos.length) return { actual: null, anteriores: [] };
  return { actual: turnos[0], anteriores: turnos.slice(1) };
}

// -- links ---------------------------------------------------------------------------------

/** Id of a project in /donde-quedamos?proyecto=: its folder name in lower case. */
export function idProyecto(carpeta: string | null | undefined): string {
  return nombreCarpeta(carpeta).toLowerCase();
}

export function enlaceHistorial(sesion: string, pagina = 1): string {
  const q = new URLSearchParams({ agente: sesion });
  if (pagina > 1) q.set("pagina", String(pagina));
  return `/historial?${q.toString()}`;
}

export function enlaceDonde(carpeta: string | null | undefined): string {
  if (!carpeta) return "/donde-quedamos";
  return `/donde-quedamos?proyecto=${encodeURIComponent(idProyecto(carpeta))}`;
}
