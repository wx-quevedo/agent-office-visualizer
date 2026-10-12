/**
 * Pure logic of the projects created from the office (Prompt 37): types of the
 * API, name validation, the folder that will be created, readable names of
 * model and effort, the state text and colour, and the body of the POST.
 * Prompt 38 adds the chat with the orchestrator and its orders to the code
 * agents (mixing, state texts, who decided, the body of approve/reject).
 * Prompt 39 adds the texts of the auto-approve switch, the estimate and the
 * difficulty of an order.
 * No React, no fetch: tested in tests/proyectos.test.tsx, tests/chat.test.tsx
 * and tests/ajustes.test.tsx.
 */

// -- API (/api/v1/proyectos-creados) ------------------------------------------------

export type Cuenta = "personal" | "demo";
export type Plantilla = "web" | "unity" | "expo" | "vacia";
export type Modelo = "opus" | "sonnet" | "haiku" | "fable";
export type Esfuerzo = "low" | "medium" | "high" | "xhigh" | "max";
export type EstadoProyecto =
  | "creando"
  | "activo"
  | "pausando"
  | "pausado"
  | "reanudando"
  | "deteniendo"
  | "detenido"
  | "error";
export type EstadoMiembro =
  "pendiente" | "activo" | "pausado" | "detenido" | "error";

export interface Miembro {
  id: string;
  rol: "orquestador" | "agente";
  nombre: string;
  modelo: string;
  esfuerzo: string;
  session_id: string | null;
  estado: EstadoMiembro;
  orden: number;
  actualizado: string | null;
  oficina: {
    numero: number;
    nombre: string;
    desde: string | null;
    espera: string | null;
  } | null;
}

export interface Proyecto {
  id: string;
  nombre: string;
  maquina: string;
  cuenta: Cuenta;
  ruta: string;
  plantilla: Plantilla;
  estado: EstadoProyecto;
  auto_aprobar: boolean;
  error: string | null;
  creado: string;
  actualizado: string;
  haciendo: string | null;
  ordenes_por_aprobar: number;
  equipo: Miembro[];
}

export interface Maquina {
  id: string;
  nombre: string;
  sistema: string | null;
  version_monitor: string | null;
  ultima_conexion: string | null;
  encendida: boolean;
  ruta_base: string | null;
  disponible: boolean;
  motivo: string | null;
}

export interface ConfigModelo {
  modelo: Modelo;
  esfuerzo: Esfuerzo;
}

export interface Borrador {
  nombre: string;
  maquina: string;
  cuenta: Cuenta;
  plantilla: Plantilla;
  orquestador: ConfigModelo;
  agentes: ConfigModelo[];
  auto_aprobar: boolean;
}

// -- names ----------------------------------------------------------------------------

export const MODELOS: { valor: Modelo; texto: string }[] = [
  { valor: "opus", texto: "Opus 5.5" },
  { valor: "sonnet", texto: "Sonnet 5.5" },
  { valor: "haiku", texto: "Haiku 5.5" },
  { valor: "fable", texto: "Fable 5.1" },
];

export const ESFUERZOS: { valor: Esfuerzo; texto: string }[] = [
  { valor: "low", texto: "Bajo" },
  { valor: "medium", texto: "Medio" },
  { valor: "high", texto: "Alto" },
  { valor: "xhigh", texto: "Muy alto" },
  { valor: "max", texto: "Máximo" },
];

export const PLANTILLAS: { valor: Plantilla; texto: string }[] = [
  { valor: "web", texto: "Web" },
  { valor: "unity", texto: "Unity" },
  { valor: "expo", texto: "App Expo" },
  { valor: "vacia", texto: "Vacía" },
];

export const CUENTAS: { valor: Cuenta; texto: string }[] = [
  { valor: "personal", texto: "Personal" },
  { valor: "demo", texto: "Demo Org" },
];

export const MAX_AGENTES = 4;

export const ORQUESTADOR_POR_DEFECTO: ConfigModelo = {
  modelo: "opus",
  esfuerzo: "high",
};

export const AGENTE_POR_DEFECTO: ConfigModelo = {
  modelo: "sonnet",
  esfuerzo: "medium",
};

/** "opus" → "Opus 5.5"; an unknown value is shown as it comes. */
export function nombreModelo(valor: string | null | undefined): string {
  if (!valor) return "Modelo sin anotar";
  return MODELOS.find((m) => m.valor === valor)?.texto ?? valor;
}

/** "xhigh" → "Muy alto"; an unknown value is shown as it comes. */
export function nombreEsfuerzo(valor: string | null | undefined): string {
  if (!valor) return "Esfuerzo sin anotar";
  return ESFUERZOS.find((e) => e.valor === valor)?.texto ?? valor;
}

export function nombreCuenta(valor: string | null | undefined): string {
  return CUENTAS.find((c) => c.valor === valor)?.texto ?? valor ?? "";
}

export function nombrePlantilla(valor: string | null | undefined): string {
  return PLANTILLAS.find((p) => p.valor === valor)?.texto ?? valor ?? "";
}

export function nombreRol(rol: Miembro["rol"]): string {
  return rol === "orquestador" ? "Orquestador" : "Agente de código";
}

// -- name validation and folder -------------------------------------------------------

const PATRON_NOMBRE = /^[a-z0-9](?:[a-z0-9-]{0,48}[a-z0-9])?$/;
const RESERVADOS = /^(con|prn|aux|nul|com[0-9]|lpt[0-9])$/;

/** Null when the name is valid; otherwise what is wrong, in one sentence. */
export function errorNombre(nombre: string): string | null {
  if (!nombre) return "Escribe un nombre para el proyecto.";
  if (nombre.length > 50) return "El nombre puede tener hasta 50 caracteres.";
  if (/[A-Z]/.test(nombre)) return "Usa solo minúsculas.";
  if (!/^[a-z0-9-]+$/.test(nombre))
    return "Usa solo letras minúsculas sin tildes, números y guiones.";
  if (!PATRON_NOMBRE.test(nombre))
    return "El nombre no puede empezar ni terminar con un guion.";
  if (RESERVADOS.test(nombre))
    return "Ese nombre está reservado por Windows; elige otro.";
  return null;
}

export function nombreValido(nombre: string): boolean {
  return errorNombre(nombre) === null;
}

/** Windows path ("E:\\x" or with "\\") uses "\\"; otherwise "/". */
export function separadorDe(base: string): "\\" | "/" {
  return /^[A-Za-z]:/.test(base) || base.includes("\\") ? "\\" : "/";
}

/** Folder that will be created: base of the machine + separator + name. */
export function rutaNueva(
  base: string | null | undefined,
  nombre: string,
): string | null {
  if (!base) return null;
  const sep = separadorDe(base);
  const limpia = base.replace(/[\\/]+$/, "");
  // "E:" alone: "E:\name"; "/" alone: "/name".
  return `${limpia}${sep}${nombre}`;
}

// -- state ----------------------------------------------------------------------------

export type Tono = "verde" | "azul" | "gris" | "rojo" | "morado";

export interface EstadoVista {
  texto: string;
  tono: Tono;
}

const ESTADOS: Record<EstadoProyecto, EstadoVista> = {
  creando: { texto: "Creando", tono: "azul" },
  activo: { texto: "Activo", tono: "verde" },
  pausando: { texto: "Pausando", tono: "azul" },
  pausado: { texto: "En pausa", tono: "gris" },
  reanudando: { texto: "Reanudando", tono: "azul" },
  deteniendo: { texto: "Deteniendo", tono: "azul" },
  detenido: { texto: "Detenido", tono: "gris" },
  error: { texto: "Con error", tono: "rojo" },
};

/** Text and colour of the state; orders waiting for approval go first (purple). */
export function estadoDe(
  p: Pick<Proyecto, "estado" | "ordenes_por_aprobar">,
): EstadoVista {
  const n = p.ordenes_por_aprobar ?? 0;
  if (n > 0)
    return {
      texto: `${n} ${n === 1 ? "orden por aprobar" : "órdenes por aprobar"}`,
      tono: "morado",
    };
  return ESTADOS[p.estado] ?? { texto: p.estado, tono: "gris" };
}

const ESTADOS_MIEMBRO: Record<EstadoMiembro, EstadoVista> = {
  pendiente: { texto: "Pendiente", tono: "azul" },
  activo: { texto: "Activo", tono: "verde" },
  pausado: { texto: "En pausa", tono: "gris" },
  detenido: { texto: "Detenido", tono: "gris" },
  error: { texto: "Con error", tono: "rojo" },
};

export function estadoMiembro(estado: EstadoMiembro): EstadoVista {
  return ESTADOS_MIEMBRO[estado] ?? { texto: estado, tono: "gris" };
}

/** What the project is doing, or a text from its state when nothing arrives. */
export function haciendoDe(
  p: Pick<Proyecto, "estado" | "haciendo" | "error">,
): string {
  if (p.estado === "error") return p.error ?? "Hubo un error sin detalle.";
  if (p.haciendo) return p.haciendo;
  switch (p.estado) {
    case "creando":
      return "Creando la carpeta y el equipo…";
    case "pausando":
      return "Pausando el equipo…";
    case "reanudando":
      return "Reanudando el equipo…";
    case "deteniendo":
      return "Deteniendo el equipo…";
    case "pausado":
      return "En pausa";
    case "detenido":
      return "Detenido";
    case "activo":
      // Nadie trabaja: el equipo espera que alguien le escriba.
      return "En espera";
    default:
      return "Sin actividad";
  }
}

/** "Orquestador Opus 5.5 · 2 agentes de código". */
export function resumenEquipo(equipo: Miembro[]): string {
  const orq = equipo.find((m) => m.rol === "orquestador");
  const n = equipo.filter((m) => m.rol === "agente").length;
  const partes: string[] = [];
  if (orq) partes.push(`Orquestador ${nombreModelo(orq.modelo)}`);
  if (n)
    partes.push(`${n} ${n === 1 ? "agente de código" : "agentes de código"}`);
  return partes.join(" · ") || "Sin equipo todavía";
}

/** Which team buttons apply and whether they are enabled. */
export function accionesDe(estado: EstadoProyecto): {
  pausar: boolean;
  reanudar: boolean;
  detener: boolean;
  ocupado: boolean;
} {
  const ocupado =
    estado === "creando" ||
    estado === "pausando" ||
    estado === "reanudando" ||
    estado === "deteniendo";
  return {
    pausar: estado === "activo" || estado === "error",
    reanudar:
      estado === "pausado" || estado === "detenido" || estado === "error",
    detener: estado === "activo" || estado === "pausado" || estado === "error",
    ocupado,
  };
}

/** The member as the office shows it ("Esperando permiso" or the state name). */
export function textoOficina(m: Miembro): string | null {
  if (!m.oficina) return null;
  return m.oficina.espera ?? m.oficina.nombre;
}

// -- POST ----------------------------------------------------------------------------

export function borradorInicial(maquina = ""): Borrador {
  return {
    nombre: "",
    maquina,
    cuenta: "personal",
    plantilla: "vacia",
    orquestador: { ...ORQUESTADOR_POR_DEFECTO },
    agentes: [{ ...AGENTE_POR_DEFECTO }],
    auto_aprobar: false,
  };
}

/** Body of POST /proyectos-creados (name trimmed, between 1 and 4 agents). */
export function cuerpoCrear(b: Borrador): Borrador {
  return {
    nombre: b.nombre.trim(),
    maquina: b.maquina,
    cuenta: b.cuenta,
    plantilla: b.plantilla,
    orquestador: {
      modelo: b.orquestador.modelo,
      esfuerzo: b.orquestador.esfuerzo,
    },
    agentes: b.agentes
      .slice(0, MAX_AGENTES)
      .map((a) => ({ modelo: a.modelo, esfuerzo: a.esfuerzo })),
    auto_aprobar: b.auto_aprobar,
  };
}

/** Whether "Crear proyecto" can be pressed. */
export function puedeCrear(b: Borrador, maquinas: Maquina[] | null): boolean {
  if (!nombreValido(b.nombre.trim())) return false;
  const m = maquinas?.find((x) => x.id === b.maquina);
  return Boolean(m?.disponible) && b.agentes.length >= 1;
}

/** First available machine (to preselect it). */
export function primeraDisponible(maquinas: Maquina[] | null): string {
  return maquinas?.find((m) => m.disponible)?.id ?? "";
}

/** The "detail" of an error response, or a generic sentence. */
export async function detalleError(r: Response): Promise<string> {
  try {
    const j = (await r.json()) as { detail?: unknown };
    if (typeof j.detail === "string" && j.detail) return j.detail;
    if (Array.isArray(j.detail)) {
      const msg = j.detail
        .map((d) =>
          d && typeof d === "object" && "msg" in d ? String(d.msg) : "",
        )
        .filter(Boolean)
        .join(" ");
      if (msg) return msg;
    }
  } catch {
    // not JSON
  }
  return `El servidor respondió ${r.status}.`;
}

export function enlaceProyecto(id: string, seccion?: string): string {
  const q = new URLSearchParams({ id });
  if (seccion) q.set("seccion", seccion);
  return `/proyectos/ver?${q.toString()}`;
}

// -- chat and orders (Prompt 38) -------------------------------------------------------

export type EstadoOrden =
  | "por_aprobar"
  | "aprobada"
  | "rechazada"
  | "en_curso"
  | "terminada"
  | "fallida";

export type Dispositivo = "web" | "app" | "celular" | "pc";

export interface Orden {
  id: string;
  proyecto_id: string;
  proyecto: string;
  numero: number;
  agente: string;
  texto_propuesto: string;
  texto_final: string | null;
  texto: string;
  editada: boolean;
  /** Short title written by the orchestrator, or the first line of the text (Prompt 42). */
  titulo?: string | null;
  estimado: string | null;
  dificultad: string | null;
  estado: EstadoOrden;
  motivo: string | null;
  decidido_por: Dispositivo | "automatico" | null;
  decidido: string | null;
  resumen: string | null;
  creado: string;
  actualizado: string;
}

export interface Mensaje {
  id: string;
  autor: "washington" | "orquestador";
  texto: string;
  creado: string;
}

export interface Chat {
  mensajes: Mensaje[];
  ordenes: Orden[];
}

/** One element of the conversation: a bubble or an order card. */
export type ItemChat =
  | { tipo: "mensaje"; id: string; creado: string; mensaje: Mensaje }
  | { tipo: "orden"; id: string; creado: string; orden: Orden };

export const MAX_MENSAJE = 8000;
export const MAX_MOTIVO = 500;

function tiempo(iso: string): number {
  const t = Date.parse(iso);
  return Number.isNaN(t) ? 0 : t;
}

/**
 * Messages and orders in chronological order by `creado`. Stable: on a tie
 * the message goes first (the orchestrator explains, then proposes).
 */
export function mezclarChat(mensajes: Mensaje[], ordenes: Orden[]): ItemChat[] {
  const items: ItemChat[] = [
    ...mensajes.map((m): ItemChat => ({
      tipo: "mensaje",
      id: `m-${m.id}`,
      creado: m.creado,
      mensaje: m,
    })),
    ...ordenes.map((o): ItemChat => ({
      tipo: "orden",
      id: `o-${o.id}`,
      creado: o.creado,
      orden: o,
    })),
  ];
  return items
    .map((x, i) => ({ x, i }))
    .sort(
      (a, b) =>
        tiempo(a.x.creado) - tiempo(b.x.creado) ||
        (a.x.tipo === b.x.tipo ? 0 : a.x.tipo === "mensaje" ? -1 : 1) ||
        a.i - b.i,
    )
    .map(({ x }) => x);
}

/**
 * The read messages plus the ones sent from here that the read does not bring
 * yet (by id), and the optimistic ones still on their way at the end.
 */
export function unirMensajes(
  leidos: Mensaje[],
  enviados: Mensaje[],
  pendientes: Mensaje[] = [],
): Mensaje[] {
  const ids = new Set(leidos.map((m) => m.id));
  return [...leidos, ...enviados.filter((m) => !ids.has(m.id)), ...pendientes];
}

/** Each read order replaced by the local answer when that one is newer. */
export function unirOrdenes(
  leidas: Orden[],
  locales: Record<string, Orden>,
): Orden[] {
  return leidas.map((o) => {
    const l = locales[o.id];
    return l && tiempo(l.actualizado) >= tiempo(o.actualizado) ? l : o;
  });
}

const ESTADOS_ORDEN: Record<EstadoOrden, EstadoVista> = {
  por_aprobar: { texto: "Por aprobar", tono: "morado" },
  aprobada: { texto: "Aprobada (en cola)", tono: "azul" },
  rechazada: { texto: "Rechazada", tono: "gris" },
  en_curso: { texto: "En curso", tono: "azul" },
  terminada: { texto: "Terminada", tono: "verde" },
  fallida: { texto: "Fallida", tono: "rojo" },
};

export function estadoOrden(estado: EstadoOrden): EstadoVista {
  return ESTADOS_ORDEN[estado] ?? { texto: estado, tono: "gris" };
}

/** "Orden 3 para agente-2". */
export function tituloOrden(o: Pick<Orden, "numero" | "agente">): string {
  return `Orden ${o.numero} para ${o.agente}`;
}

/** Who decided the order, in words (null while nobody did). */
export function quienDecidio(
  por: Orden["decidido_por"] | undefined,
): string | null {
  switch (por) {
    case "web":
      return "Tú desde la web";
    case "app":
      return "Tú desde la app";
    case "celular":
      return "Tú desde el celular";
    case "pc":
      return "Tú desde la PC";
    case "automatico":
      return "Automático";
    default:
      return null;
  }
}

/** Whether the order was edited when approving it. */
export function fueEditada(o: Pick<Orden, "editada" | "texto_final">): boolean {
  return o.editada || o.texto_final !== null;
}

/** Whether the text deserves "Ver la orden completa" (about 6 lines). */
export function ordenLarga(texto: string): boolean {
  return texto.split("\n").length > 6 || texto.length > 420;
}

/** The text in one line, cut at `max` characters (lists and inbox). */
export function textoCorto(texto: string, max = 140): string {
  const limpio = texto.trim().replace(/\s+/g, " ");
  return limpio.length > max
    ? `${limpio.slice(0, max - 1).trimEnd()}…`
    : limpio;
}

/** Body of POST /ordenes/{id}/aprobar: `texto` only when it really changed. */
export function cuerpoAprobar(
  o: Pick<Orden, "texto_propuesto">,
  texto?: string | null,
): { texto?: string; dispositivo: "web" } {
  const t = texto?.trim();
  if (t && t !== o.texto_propuesto.trim())
    return { texto: t, dispositivo: "web" };
  return { dispositivo: "web" };
}

/** Body of POST /ordenes/{id}/rechazar; null when the reason is missing. */
export function cuerpoRechazar(
  motivo: string,
): { motivo: string; dispositivo: "web" } | null {
  const m = motivo.trim();
  if (!m) return null;
  return { motivo: m.slice(0, MAX_MOTIVO), dispositivo: "web" };
}

/** Orders of the project for the history, the newest first. */
export function historialOrdenes(ordenes: Orden[]): Orden[] {
  return [...ordenes].sort(
    (a, b) => tiempo(b.creado) - tiempo(a.creado) || b.numero - a.numero,
  );
}

/** Note over the chat when the team is not running, or null. */
export function notaChat(estado: EstadoProyecto): string | null {
  if (estado === "pausado")
    return "El equipo está pausado: el orquestador leerá tus mensajes cuando lo reanudes.";
  if (estado === "detenido")
    return "El equipo está detenido: el orquestador leerá tus mensajes cuando lo reanudes.";
  return null;
}

/** Number of code agents of the team. */
export function cuantosAgentes(equipo: Miembro[]): number {
  return equipo.filter((m) => m.rol === "agente").length;
}

// -- texts of the switch and the orders (Prompt 39) ---------------------------------

/** What the "Aprobar órdenes automáticamente" switch does in its current state. */
export function textoAuto(activo: boolean): string {
  return activo
    ? "Encendido: las órdenes del orquestador llegan al agente sin pasar por ti."
    : "Apagado: cada orden del orquestador espera tu aprobación.";
}

/** "Estimado: 45 min" (the text of the orchestrator as it comes). */
export function textoEstimado(estimado: string): string {
  return `Estimado: ${estimado.trim()}`;
}

/** "Dificultad: 3 de 10" for 1..10 (also "3/10"); otherwise the text as it comes. */
export function textoDificultad(dificultad: string): string {
  const t = dificultad.trim();
  const m = /^(\d{1,2})(?:\s*\/\s*10)?$/.exec(t);
  const n = m ? Number(m[1]) : NaN;
  if (Number.isInteger(n) && n >= 1 && n <= 10) return `Dificultad: ${n} de 10`;
  return `Dificultad: ${t}`;
}
