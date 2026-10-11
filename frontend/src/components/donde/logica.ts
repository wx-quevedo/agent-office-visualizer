/**
 * Pure logic of "Dónde quedamos" (stage 2.3): the project list with its alert,
 * the plan by stages, the prompts of the current stage and the three cards.
 * No React, no fetch: tested in tests/donde.test.ts.
 */

import {
  cuando,
  idProyecto,
  miles,
  nombreCarpeta,
  tiempoCorto,
  type Consumo,
  type Turno,
} from "@/components/ficha/logica";
import type { Agente } from "@/components/oficina/logica";

// -- GET /api/v1/proyectos -------------------------------------------------------------

export interface ItemPlan {
  nombre: string;
  estado: string;
}

/** Prompts of the current stage written in the PROJECT.md (monitor 0.2.1+). */
export interface PromptPlan {
  numero: number;
  nombre: string;
  estado: string;
  fecha?: string | null;
  commits?: string[];
}

/** Prompts its agents ran ("Prompt N · ..." requests), with time and commits. */
export interface PromptTurnos {
  numero: number;
  nombre: string | null;
  inicio: string;
  duracion_s: number;
  commits: { hora: string; mensaje: string | null }[];
  resultado: string;
  session_id?: string | null;
}

export interface ProyectoApi {
  carpeta: string;
  maquina?: string | null;
  tiene_project_md: boolean;
  titulo?: string | null;
  plan: ItemPlan[];
  posicion?: string | null;
  siguiente_paso?: string | null;
  espera_decision: string[];
  ultimo_commit?: {
    hash: string;
    mensaje: string | null;
    fecha: string | null;
  } | null;
  modificado?: string | null;
  error?: string | null;
  recibido?: string | null;
  ultima_actividad?: {
    session_id: string;
    estado: string;
    espera: string | null;
    ultimo_evento: string | null;
    ultimo_turno: Turno | null;
  } | null;
  prompts?: PromptPlan[];
  prompts_turnos?: PromptTurnos[];
}

// -- projects and alerts ------------------------------------------------------------------

export type Tono = "azul" | "rojo" | "naranja" | "verde" | "gris";

export interface Alerta {
  tipo:
    | "permiso"
    | "atasco"
    | "pregunta"
    | "decision"
    | "trabajando"
    | "listo"
    | "sin_actividad";
  texto: string;
  corto: string;
  tono: Tono;
}

export interface ProyectoVista {
  id: string;
  nombre: string;
  carpeta: string;
  maquina: string | null;
  datos: ProyectoApi;
  agentes: Agente[];
  /** Last known activity (agent event, turn or commit), ISO. */
  ultima: string | null;
  alerta: Alerta;
}

function normal(ruta: string | null | undefined): string {
  return (ruta ?? "").replace(/\\/g, "/").replace(/\/+$/, "").toLowerCase();
}

export function mismaCarpeta(
  a: string | null | undefined,
  b: string | null | undefined,
): boolean {
  if (!a || !b) return false;
  const x = normal(a);
  const y = normal(b);
  // The engine may send only the folder name; the monitor sends the full path.
  return (
    x === y ||
    (!x.includes("/") && y.endsWith(`/${x}`)) ||
    (!y.includes("/") && x.endsWith(`/${y}`))
  );
}

const ESTADOS_TRABAJO = new Set([
  1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 16, 17,
]);

export function alertaDe(p: ProyectoApi, agentes: Agente[]): Alerta {
  const vivos = agentes.filter((a) => a.estado.numero !== 21);
  if (vivos.some((a) => a.estado.numero === 13))
    return {
      tipo: "permiso",
      texto: "Te pide permiso",
      corto: "Permiso",
      tono: "azul",
    };
  if (vivos.some((a) => a.atasco))
    return {
      tipo: "atasco",
      texto: "Parece atascado",
      corto: "Atascado",
      tono: "rojo",
    };
  if (vivos.some((a) => a.estado.numero === 14 || a.pregunta_pendiente))
    return {
      tipo: "pregunta",
      texto: "Te hizo una pregunta",
      corto: "Pregunta",
      tono: "azul",
    };
  const n = p.espera_decision.length;
  if (n > 0)
    return {
      tipo: "decision",
      texto: `Espera tu decisión: ${n}`,
      corto: `Decisión: ${n}`,
      tono: "naranja",
    };
  if (vivos.some((a) => ESTADOS_TRABAJO.has(a.estado.numero)))
    return {
      tipo: "trabajando",
      texto: "Un agente está trabajando",
      corto: "Trabajando",
      tono: "gris",
    };
  if (vivos.length > 0 || p.ultima_actividad || p.ultimo_commit)
    return {
      tipo: "listo",
      texto: "Listo para el siguiente prompt",
      corto: "Listo",
      tono: "verde",
    };
  return {
    tipo: "sin_actividad",
    texto: "Sin actividad reciente",
    corto: "Sin actividad",
    tono: "gris",
  };
}

const URGENCIA: Record<Alerta["tipo"], number> = {
  permiso: 0,
  atasco: 1,
  pregunta: 2,
  decision: 3,
  trabajando: 4,
  listo: 4,
  sin_actividad: 4,
};

function ms(iso: string | null | undefined): number {
  if (!iso) return NaN;
  return Date.parse(iso);
}

function masReciente(...isos: Array<string | null | undefined>): string | null {
  let mejor: string | null = null;
  for (const i of isos) {
    if (i && !Number.isNaN(ms(i)) && (mejor === null || ms(i) > ms(mejor)))
      mejor = i;
  }
  return mejor;
}

/**
 * Projects of the monitor plus folders where an agent works without a report
 * yet (older monitor): those show as "sin PROJECT.md". Urgent ones first
 * (permission, stuck, question, decision), then the most recent.
 */
export function armarProyectos(
  api: ProyectoApi[],
  agentes: Agente[],
): ProyectoVista[] {
  const usados = new Set<string>();
  const salida: ProyectoVista[] = [];
  const ids = new Set<string>();
  const agregar = (datos: ProyectoApi, suyos: Agente[]) => {
    let id = idProyecto(datos.carpeta);
    if (ids.has(id) && datos.maquina)
      id = `${id}-${datos.maquina.toLowerCase()}`;
    ids.add(id);
    const ultima = masReciente(
      ...suyos.map((a) => a.ultimo_evento.hora),
      datos.ultima_actividad?.ultimo_evento,
      datos.ultima_actividad?.ultimo_turno?.inicio,
      datos.ultimo_commit?.fecha,
    );
    salida.push({
      id,
      nombre: nombreCarpeta(datos.carpeta),
      carpeta: datos.carpeta,
      maquina: datos.maquina ?? null,
      datos,
      agentes: suyos,
      ultima,
      alerta: alertaDe(datos, suyos),
    });
  };
  for (const p of api) {
    const suyos = agentes.filter(
      (a) =>
        mismaCarpeta(a.agente.proyecto, p.carpeta) &&
        (!a.agente.maquina || !p.maquina || a.agente.maquina === p.maquina),
    );
    suyos.forEach((a) => usados.add(a.agente.session_id));
    agregar(p, suyos);
  }
  const sueltos = new Map<string, Agente[]>();
  for (const a of agentes) {
    if (usados.has(a.agente.session_id) || !a.agente.proyecto) continue;
    const clave = normal(a.agente.proyecto);
    sueltos.set(clave, [...(sueltos.get(clave) ?? []), a]);
  }
  for (const lista of sueltos.values()) {
    agregar(
      {
        carpeta: lista[0].agente.proyecto ?? "",
        maquina: lista[0].agente.maquina ?? null,
        tiene_project_md: false,
        plan: [],
        espera_decision: [],
      },
      lista,
    );
  }
  return salida.sort(
    (a, b) =>
      URGENCIA[a.alerta.tipo] - URGENCIA[b.alerta.tipo] ||
      (ms(b.ultima) || 0) - (ms(a.ultima) || 0) ||
      a.nombre.localeCompare(b.nombre),
  );
}

// -- plan by stages ---------------------------------------------------------------------------

const ETAPA =
  /^(etapa|fase|phase|stage|sprint|hito|milestone)\s+(\d+)(?:\.(\d+))?\s*[,:.\-–—]?\s*(.*)$/i;

export interface Etapa {
  etiqueta: string;
  /** Number of the stage ("2"), or the position in the plan. */
  corto: string;
  nombre: string;
  estado: "hecha" | "actual" | "pendiente";
}

function mayuscula(t: string): string {
  return t ? t[0].toUpperCase() + t.slice(1) : t;
}

/** Stage blocks: only the main stages ("Etapa 2") when the plan has them. */
export function etapas(
  plan: ItemPlan[],
  posicion: string | null | undefined,
): Etapa[] {
  const conNumero = plan.map((i) => ({ i, m: ETAPA.exec(i.nombre.trim()) }));
  const principales = conNumero.filter((x) => x.m && x.m[3] === undefined);
  const lista = principales.length >= 2 ? principales : conNumero;
  if (!lista.length) return [];

  let actual = -1;
  const pos = posicion ? ETAPA.exec(posicion.trim()) : null;
  if (pos)
    actual = lista.findIndex(
      (x) =>
        x.m &&
        x.m[2] === pos[2] &&
        x.m[1].toLowerCase() === pos[1].toLowerCase(),
    );
  if (actual < 0 && posicion)
    actual = lista.findIndex((x) => x.i.nombre === posicion);
  if (actual < 0) actual = lista.findIndex((x) => x.i.estado === "en_curso");
  if (actual < 0) actual = lista.findIndex((x) => x.i.estado !== "hecho");

  return lista.map(({ i, m }, n) => ({
    etiqueta: m
      ? `${mayuscula(m[1].toLowerCase())} ${m[2]}${m[3] ? `.${m[3]}` : ""}`
      : `Paso ${n + 1}`,
    corto: m ? (m[3] ? `${m[2]}.${m[3]}` : m[2]) : String(n + 1),
    nombre: m ? mayuscula(m[4].trim()) : i.nombre,
    estado:
      n === actual ? "actual" : i.estado === "hecho" ? "hecha" : "pendiente",
  }));
}

// -- prompts of the current stage ----------------------------------------------------------

export type EstadoPrompt =
  "hecho" | "en_curso" | "espera" | "detenido" | "pendiente";

export const ESTADOS_PROMPT: Record<
  EstadoPrompt,
  { texto: string; tono: Tono }
> = {
  hecho: { texto: "Hecho", tono: "verde" },
  en_curso: { texto: "En curso", tono: "azul" },
  espera: { texto: "Te espera", tono: "azul" },
  detenido: { texto: "Se detuvo", tono: "naranja" },
  pendiente: { texto: "Pendiente", tono: "gris" },
};

export interface PromptVista {
  numero: number;
  nombre: string;
  estado: EstadoPrompt;
  dato: string;
  actual: boolean;
}

function estadoDeTurno(resultado: string): EstadoPrompt {
  if (resultado === "completado") return "hecho";
  if (resultado === "esperando") return "espera";
  if (resultado === "en_curso") return "en_curso";
  return "detenido";
}

/**
 * The prompts of the current stage: the ones written in the PROJECT.md, with
 * the time and commits of the turns that ran them. Without a list in the
 * PROJECT.md, the last 4 prompts its agents ran.
 */
export function promptsDeEtapa(p: ProyectoApi): PromptVista[] {
  const plan = p.prompts ?? [];
  let turnos = p.prompts_turnos ?? [];
  let numeros: number[];
  if (plan.length) {
    numeros = plan.map((x) => x.numero);
    const min = Math.min(...numeros);
    const max = Math.max(...numeros);
    turnos = turnos.filter((t) => t.numero >= min && t.numero <= max);
  } else {
    turnos = turnos.slice(-4);
    numeros = turnos.map((t) => t.numero);
  }
  const lista: PromptVista[] = numeros.map((n) => {
    const pp = plan.find((x) => x.numero === n);
    const tt = turnos.find((x) => x.numero === n);
    let estado: EstadoPrompt =
      pp?.estado === "hecho"
        ? "hecho"
        : tt
          ? estadoDeTurno(tt.resultado)
          : pp?.estado === "en_curso"
            ? "en_curso"
            : "pendiente";
    if (pp?.estado === "hecho") estado = "hecho";
    const commit = pp?.commits?.length
      ? pp.commits[pp.commits.length - 1]
      : tt?.commits.length
        ? tt.commits.length === 1
          ? "1 commit"
          : `${tt.commits.length} commits`
        : null;
    const partes = [commit, tt ? tiempoCorto(tt.duracion_s) : null].filter(
      Boolean,
    ) as string[];
    const dato = partes.length
      ? partes.join(" · ")
      : estado === "pendiente"
        ? "sin empezar"
        : (pp?.fecha ?? "sin datos de tiempo");
    return {
      numero: n,
      nombre: mayuscula(pp?.nombre ?? tt?.nombre ?? ""),
      estado,
      dato,
      actual: false,
    };
  });
  const enCurso = lista.findIndex(
    (x) => x.estado === "en_curso" || x.estado === "espera",
  );
  const i =
    enCurso >= 0 ? enCurso : lista.findIndex((x) => x.estado !== "hecho");
  if (i >= 0) lista[i].actual = true;
  return lista;
}

// -- the three cards ---------------------------------------------------------------------------

/** Who must do the next step, from its text (null: the PROJECT.md does not say). */
export function quienHace(texto: string | null | undefined): string | null {
  if (!texto) return null;
  if (
    /\b(washington|t[uú])\b/i.test(texto) ||
    /^(aprobar|aprueba|decidir|decide|revisar|revisa|probar|elegir|elige|confirmar|confirma|ejecutar|ejecuta)\b/i.test(
      texto.trim(),
    )
  )
    return "Quién: tú.";
  if (/\bprompt\s+\d+|\bagente\b|\bclaude\b/i.test(texto))
    return "Quién: el agente.";
  return null;
}

export interface Consumido {
  segundos: number;
  tokens: number;
}

/** Today's work and tokens of the sessions in that project. */
export function consumoDe(
  consumo: Consumo | null,
  carpeta: string,
): Consumido | null {
  if (!consumo) return null;
  const suyas = consumo.por_sesion.filter((s) =>
    mismaCarpeta(s.proyecto, carpeta),
  );
  return {
    segundos: suyas.reduce((n, s) => n + s.segundos_trabajo, 0),
    tokens: suyas.reduce((n, s) => n + s.tokens_salida, 0),
  };
}

/** "Hoy: 4 h 35 min de agentes · 707 246 tokens". */
export function lineaConsumo(consumo: Consumo | null): string | null {
  if (!consumo) return null;
  const base = `Hoy: ${tiempoCorto(consumo.total.segundos_con_agentes)} de agentes · ${miles(consumo.total.tokens_salida)} tokens`;
  const aux = consumo.auxiliar?.total;
  // The summaries' helper, apart: it is not an agent's work.
  if (!aux || aux.llamadas === 0) return base;
  return `${base} · auxiliar: ${miles(aux.tokens_entrada + aux.tokens_salida)} tokens en ${aux.llamadas} ${aux.llamadas === 1 ? "resumen" : "resúmenes"}`;
}

export function textoUltima(p: ProyectoVista, ahora: number): string {
  return p.ultima ? cuando(p.ultima, ahora) : "sin fecha";
}

/** "Etapa 2 · Prompt 27 (en curso)" or "Sin PROJECT.md". */
export function dondeVa(p: ProyectoVista): string {
  if (!p.datos.tiene_project_md) return "Sin PROJECT.md";
  const pr = promptsDeEtapa(p.datos).find((x) => x.actual);
  const pos = p.datos.posicion ?? "Sin posición anotada";
  return pr
    ? `${pos} · Prompt ${pr.numero} (${ESTADOS_PROMPT[pr.estado].texto.toLowerCase()})`
    : pos;
}
