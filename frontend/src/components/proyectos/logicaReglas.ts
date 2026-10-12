/**
 * Pure logic of the house rules and the safe commands (Prompt 39): types of
 * the API (/reglas, /comandos and /proyectos-creados/{id}/reglas), readable
 * names of the rule types, the bodies of the POST/PATCH and the local copy of
 * a list after a change (shown at once, before the next read).
 * No React, no fetch: tested in tests/ajustes.test.tsx.
 */

export type TipoRegla =
  | "idioma"
  | "interfaz"
  | "git"
  | "documentacion"
  | "ordenes"
  | "entrega"
  | "herramientas"
  | "pruebas"
  | "otra";

export interface Regla {
  id: string;
  texto: string;
  tipo: TipoRegla;
  activa_por_defecto: boolean;
  orden: number;
}

export interface ReglaProyecto extends Regla {
  /** The effective value in that project. */
  activa: boolean;
  /** True when the project changed it from the global value. */
  ajustada: boolean;
}

export interface Comando {
  id: string;
  comando: string;
  activo_por_defecto: boolean;
  orden: number;
}

export interface ComandoProyecto extends Comando {
  activo: boolean;
  ajustado: boolean;
}

/** GET /reglas. */
export interface ListaReglas {
  reglas: Regla[];
  tipos: TipoRegla[];
}

/** GET /comandos. */
export interface ListaComandos {
  comandos: Comando[];
}

/** GET (and the POSTs) of /proyectos-creados/{id}/reglas. */
export interface ReglasDeProyecto {
  reglas: ReglaProyecto[];
  comandos: ComandoProyecto[];
}

export const MAX_REGLA = 500;
export const MAX_COMANDO = 80;

export const TIPOS_REGLA: { valor: TipoRegla; texto: string }[] = [
  { valor: "idioma", texto: "Idioma" },
  { valor: "interfaz", texto: "Interfaz" },
  { valor: "git", texto: "Git" },
  { valor: "documentacion", texto: "Documentación" },
  { valor: "ordenes", texto: "Órdenes" },
  { valor: "entrega", texto: "Entrega" },
  { valor: "herramientas", texto: "Herramientas" },
  { valor: "pruebas", texto: "Pruebas" },
  { valor: "otra", texto: "Otra" },
];

/** "documentacion" → "Documentación"; an unknown type is shown as it comes. */
export function nombreTipo(tipo: string): string {
  return TIPOS_REGLA.find((t) => t.valor === tipo)?.texto ?? tipo;
}

/** The types for the select: the ones of the server (known first) or all. */
export function opcionesTipo(
  tipos: string[] | null | undefined,
): { valor: string; texto: string }[] {
  if (!tipos || tipos.length === 0) return TIPOS_REGLA;
  return tipos.map((t) => ({ valor: t, texto: nombreTipo(t) }));
}

/** Body of POST /reglas, or null when the text is empty. */
export function cuerpoRegla(
  texto: string,
  tipo: string,
  activa = true,
): { texto: string; tipo: string; activa_por_defecto: boolean } | null {
  const t = texto.trim();
  if (!t) return null;
  return { texto: t.slice(0, MAX_REGLA), tipo, activa_por_defecto: activa };
}

/** Body of PATCH /reglas/{id} with only what changed (null: nothing changed). */
export function cambiosRegla(
  r: Pick<Regla, "texto" | "tipo">,
  texto: string,
  tipo: string,
): { texto?: string; tipo?: string } | null {
  const t = texto.trim().slice(0, MAX_REGLA);
  const c: { texto?: string; tipo?: string } = {};
  if (t && t !== r.texto) c.texto = t;
  if (tipo !== r.tipo) c.tipo = tipo;
  return Object.keys(c).length ? c : null;
}

/** Body of POST /comandos, or null when the text is empty. */
export function cuerpoComando(
  comando: string,
  activo = true,
): { comando: string; activo_por_defecto: boolean } | null {
  const c = comando.trim().replace(/\s+/g, " ");
  if (!c) return null;
  return { comando: c, activo_por_defecto: activo };
}

/** The list with `x` replaced (same id) or added, sorted by `orden`. */
export function ponerEnLista<T extends { id: string; orden: number }>(
  lista: T[],
  x: T,
): T[] {
  const otra = lista.some((y) => y.id === x.id)
    ? lista.map((y) => (y.id === x.id ? x : y))
    : [...lista, x];
  return otra
    .map((y, i) => ({ y, i }))
    .sort((a, b) => a.y.orden - b.y.orden || a.i - b.i)
    .map(({ y }) => y);
}

/** The list without the element `id`. */
export function quitarDeLista<T extends { id: string }>(
  lista: T[],
  id: string,
): T[] {
  return lista.filter((y) => y.id !== id);
}
