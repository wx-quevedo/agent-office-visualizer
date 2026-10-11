/**
 * Pure logic of the projects created from the office (Prompt 37): types of the
 * API, name validation, the folder that will be created, readable names of
 * model and effort, the state text and colour, and the body of the POST.
 * No React, no fetch: tested in tests/proyectos.test.tsx.
 */

// -- API (/api/v1/proyectos-creados) ------------------------------------------------

export type Cuenta = "personal" | "demo";
export type Plantilla = "web" | "unity" | "expo" | "vacia";
export type Modelo = "opus" | "sonnet" | "haiku" | "fable";
export type Esfuerzo = "low" | "medium" | "high" | "xhigh" | "max";
export type EstadoProyecto =
  "creando" | "activo" | "pausando" | "pausado" | "reanudando" | "error";
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
    case "pausado":
      return "En pausa";
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
  ocupado: boolean;
} {
  const ocupado =
    estado === "creando" || estado === "pausando" || estado === "reanudando";
  return {
    pausar: estado === "activo" || estado === "error",
    reanudar: estado === "pausado" || estado === "error",
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
