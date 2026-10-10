/**
 * Pure logic of /oficina: grouping by urgency, rooms by project, ordering and
 * the rule for closed agents. No React, no fetch: tested in tests/oficina.test.ts.
 */

export interface Espera {
  tipo: string;
  evidencia: Record<string, unknown> | null;
}

export interface EventoReciente {
  hora: string;
  tipo: string;
  agente: string | null;
  herramienta: string | null;
  detalle: string | null;
}

export interface Indicadores {
  herramientas_por_minuto: number | null;
  tokens_por_minuto: number | null;
  tokens_totales: number | null;
  tokens_contexto: number | null;
  tokens_motivo: string | null;
  minutos_con_actividad: number | null;
  contexto_usado_pct: number | null;
  errores_seguidos: number | null;
  errores_motivo: string | null;
}

export interface Agente {
  agente: {
    session_id: string;
    proyecto: string | null;
    cuenta: string | null;
  };
  estado: { numero: number; nombre: string; desde: string };
  espera: Espera | null;
  herramienta_actual: string | null;
  ultimo_evento: { tipo: string | null; hora: string | null };
  subagentes_activos: number;
  pregunta_pendiente: string | null;
  cierre: { motivo: string; desde: string } | null;
  proceso: { pid: number; creado: number | null } | null;
  indicadores: Indicadores;
  eventos_recientes: EventoReciente[];
}

export interface Presencia {
  estado: string;
  motivo: string;
  navegadores_conectados: number;
  dispositivos?: string[];
  ultimo_encargo: string | null;
  desconectado_desde: string | null;
}

export interface Estado {
  generado: string;
  presencia: Presencia;
  agentes: Agente[];
}

export type Grupo = "espera" | "trabajando" | "inactivos" | "cerrados";

/** Sections of the urgency view, in display order. */
export const GRUPOS: Array<{ id: Grupo; titulo: string }> = [
  { id: "espera", titulo: "Te esperan" },
  { id: "trabajando", titulo: "Trabajando" },
  { id: "inactivos", titulo: "Inactivos y en la sala de descanso" },
  { id: "cerrados", titulo: "Cerrados" },
];

/** A closed agent without a pending question stays visible this long. */
export const CERRADO_VISIBLE_MS = 60 * 60 * 1000;

/** States 13 and 14: waiting for the user (permission or answer). */
export function grupoDe(numero: number): Grupo {
  if (numero === 13 || numero === 14) return "espera";
  if (numero === 21) return "cerrados";
  if (numero === 11 || numero >= 18) return "inactivos";
  return "trabajando"; // 1-10, 12, 15, 16, 17
}

export type Contador =
  "espera" | "trabajando" | "inactivos" | "descansando" | "cerrados";

export const CONTADORES: Array<{ id: Contador; titulo: string }> = [
  { id: "espera", titulo: "Te esperan" },
  { id: "trabajando", titulo: "Trabajando" },
  { id: "inactivos", titulo: "Inactivos" },
  { id: "descansando", titulo: "Descansando" },
  { id: "cerrados", titulo: "Cerrados" },
];

/** Header counters: the "inactivos" section split into idle (11, 18) and resting (19, 20). */
export function contadorDe(numero: number): Contador {
  if (numero === 19 || numero === 20) return "descansando";
  return grupoDe(numero);
}

export function contar(agentes: Agente[]): Record<Contador, number> {
  const c: Record<Contador, number> = {
    espera: 0,
    trabajando: 0,
    inactivos: 0,
    descansando: 0,
    cerrados: 0,
  };
  for (const a of agentes) c[contadorDe(a.estado.numero)] += 1;
  return c;
}

function ms(iso: string | null | undefined): number {
  if (!iso) return NaN;
  return Date.parse(iso);
}

/**
 * Closed agents: with a pending question they stay until the session reopens
 * (it then leaves state 21); without one they are shown for 1 h after closing.
 */
export function cerradoVisible(a: Agente, ahora: number): boolean {
  if (a.estado.numero !== 21) return true;
  if (a.pregunta_pendiente) return true;
  const desde = ms(a.cierre?.desde ?? a.estado.desde);
  if (Number.isNaN(desde)) return true;
  return ahora - desde < CERRADO_VISIBLE_MS;
}

/** Minutes left before a closed agent without a question disappears. */
export function minutosParaDesaparecer(
  a: Agente,
  ahora: number,
): number | null {
  if (a.estado.numero !== 21 || a.pregunta_pendiente) return null;
  const desde = ms(a.cierre?.desde ?? a.estado.desde);
  if (Number.isNaN(desde)) return null;
  return Math.max(0, Math.ceil((desde + CERRADO_VISIBLE_MS - ahora) / 60000));
}

export function visibles(agentes: Agente[], ahora: number): Agente[] {
  return agentes.filter((a) => cerradoVisible(a, ahora));
}

/** Longest time in the current state first; ties by session id for stability. */
export function porTiempoEnEstado(a: Agente, b: Agente): number {
  const d = ms(a.estado.desde) - ms(b.estado.desde);
  if (d !== 0 && !Number.isNaN(d)) return d;
  return a.agente.session_id.localeCompare(b.agente.session_id);
}

export function agruparPorUrgencia(
  agentes: Agente[],
  ahora: number,
): Record<Grupo, Agente[]> {
  const g: Record<Grupo, Agente[]> = {
    espera: [],
    trabajando: [],
    inactivos: [],
    cerrados: [],
  };
  for (const a of visibles(agentes, ahora)) g[grupoDe(a.estado.numero)].push(a);
  for (const k of Object.keys(g) as Grupo[]) g[k].sort(porTiempoEnEstado);
  return g;
}

/** Folder name of the project (the engine already sends the last path part). */
export function nombreProyecto(a: Agente): string {
  const p = a.agente.proyecto;
  if (!p) return "Sin proyecto";
  const partes = p.split(/[\\/]/).filter(Boolean);
  return partes[partes.length - 1] ?? p;
}

export interface Sala {
  proyecto: string;
  agentes: Agente[];
  resumen: string;
}

const ORDEN_GRUPO: Record<Grupo, number> = {
  espera: 0,
  trabajando: 1,
  inactivos: 2,
  cerrados: 3,
};

const ETIQUETAS: Record<Grupo, [string, string]> = {
  espera: ["te espera", "te esperan"],
  trabajando: ["trabajando", "trabajando"],
  inactivos: ["inactivo", "inactivos"],
  cerrados: ["cerrado", "cerrados"],
};

export function resumenSala(agentes: Agente[]): string {
  const n: Record<Grupo, number> = {
    espera: 0,
    trabajando: 0,
    inactivos: 0,
    cerrados: 0,
  };
  for (const a of agentes) n[grupoDe(a.estado.numero)] += 1;
  return GRUPOS.filter((g) => n[g.id] > 0)
    .map((g) => `${n[g.id]} ${ETIQUETAS[g.id][n[g.id] === 1 ? 0 : 1]}`)
    .join(" · ");
}

/**
 * One room per project. Rooms with agents waiting for you first, then rooms
 * with agents working, then the rest; ties by project name. Inside a room,
 * agents follow the urgency order (waiting, working, idle, closed) and then
 * the time in their state.
 */
export function agruparPorProyecto(agentes: Agente[], ahora: number): Sala[] {
  const mapa = new Map<string, Agente[]>();
  for (const a of visibles(agentes, ahora)) {
    const p = nombreProyecto(a);
    const lista = mapa.get(p) ?? [];
    lista.push(a);
    mapa.set(p, lista);
  }
  const salas: Sala[] = [...mapa.entries()].map(([proyecto, lista]) => ({
    proyecto,
    agentes: [...lista].sort(
      (a, b) =>
        ORDEN_GRUPO[grupoDe(a.estado.numero)] -
          ORDEN_GRUPO[grupoDe(b.estado.numero)] || porTiempoEnEstado(a, b),
    ),
    resumen: resumenSala(lista),
  }));
  const rango = (s: Sala) =>
    Math.min(...s.agentes.map((a) => ORDEN_GRUPO[grupoDe(a.estado.numero)]));
  const nivel = (s: Sala) => Math.min(rango(s), 2); // idle and closed rooms rank together
  return salas.sort(
    (a, b) => nivel(a) - nivel(b) || a.proyecto.localeCompare(b.proyecto),
  );
}

// -- text helpers -------------------------------------------------------------

export function duracion(
  desdeIso: string | null | undefined,
  ahora: number,
): string {
  const d = ms(desdeIso);
  if (Number.isNaN(d)) return "—";
  const s = Math.max(0, (ahora - d) / 1000);
  if (s < 60) return `${Math.round(s)} s`;
  if (s < 3600) return `${Math.floor(s / 60)} min`;
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return m ? `${h} h ${m} min` : `${h} h`;
}

export function hace(
  desdeIso: string | null | undefined,
  ahora: number,
): string {
  const t = duracion(desdeIso, ahora);
  return t === "—" ? t : `hace ${t}`;
}

export function sesionCorta(id: string): string {
  return id.slice(0, 8);
}

export function recortar(texto: string, max: number): string {
  const t = texto.replace(/\s+/g, " ").trim();
  return t.length > max ? `${t.slice(0, max - 1)}…` : t;
}

/** "permiso" or "respuesta" for the waiting label of states 13 and 14. */
export function tipoEspera(a: Agente): string {
  return a.estado.numero === 13 ? "permiso" : "respuesta";
}

/** What a permission asks for (tool and command), or the pending question. */
export function loQuePide(a: Agente): { titulo: string; texto: string } | null {
  if (a.estado.numero === 13) {
    const ev = a.espera?.evidencia ?? {};
    const herr =
      typeof ev.herramienta === "string"
        ? ev.herramienta
        : a.herramienta_actual;
    const cmd = typeof ev.comando === "string" ? ev.comando : null;
    const texto = [herr, cmd].filter(Boolean).join(": ");
    return { titulo: "Lo que pide", texto: texto || "Permiso sin detalle" };
  }
  if (a.pregunta_pendiente)
    return { titulo: "Pregunta pendiente", texto: a.pregunta_pendiente };
  return null;
}

/** Current file, command or tool of a working agent. */
export function detalleActual(a: Agente): string {
  const ev = a.espera?.evidencia;
  if (
    ev &&
    (typeof ev.herramienta === "string" || typeof ev.comando === "string")
  ) {
    return [ev.herramienta, ev.comando]
      .filter((x) => typeof x === "string" && x)
      .join(": ");
  }
  if (a.herramienta_actual) {
    const e = a.eventos_recientes.find(
      (x) =>
        x.tipo === "pre_tool_use" && x.herramienta === a.herramienta_actual,
    );
    return e?.detalle
      ? `${a.herramienta_actual}: ${e.detalle}`
      : a.herramienta_actual;
  }
  const ultimo = a.eventos_recientes.find((x) => x.detalle);
  return ultimo?.detalle ?? a.estado.nombre;
}

export function numero(n: number | null | undefined, sufijo = ""): string {
  if (n === null || n === undefined) return "—";
  return `${n.toLocaleString("es")}${sufijo}`;
}

/** Effort bar: share of a reference of 3 000 output tokens per minute. */
export const ESFUERZO_REFERENCIA = 3000;

export function esfuerzo(a: Agente): number {
  const t = a.indicadores.tokens_por_minuto;
  if (!t || t <= 0) return 0;
  return Math.min(1, t / ESFUERZO_REFERENCIA);
}

export function textoPresencia(p: Presencia | undefined): string {
  if (!p || p.estado !== "conectado") return "Desconectado";
  const d = p.dispositivos ?? [];
  const cel = d.includes("celular");
  const pc = d.includes("pc") || d.includes("navegador") || d.length === 0;
  if (cel && pc) return "Estás presente (PC y celular)";
  return cel ? "Estás presente (celular)" : "Estás presente (PC)";
}

export function dispositivo(
  ancho: number,
  userAgent: string,
): "pc" | "celular" {
  if (ancho < 700) return "celular";
  return /Mobi|Android|iPhone|iPad/i.test(userAgent) ? "celular" : "pc";
}
