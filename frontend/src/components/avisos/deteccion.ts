/**
 * Alert detection, pure logic (no React, no browser APIs).
 *
 * Compares the previous and the new state of each agent on every observation
 * and returns the alerts to give. Tested in tests/avisos.test.ts.
 *
 * Rules:
 * - The first observation only records the current states (no alerts on load).
 * - A change alerts only if the new state holds for `estabilidadMs` (3 s).
 * - Cooldown of `enfriamientoMs` (30 s) per agent and alert type.
 * - While an agent stays in 13 or 14, a reminder every N minutes.
 * - Sessions whose id starts with "prueba-" never alert.
 * - Stage 2.4: an agent that starts looking stuck alerts once per stuck
 *   episode, and every alert uses the one-sentence summary of the helper
 *   agent when it is ready (EsperaResumenes waits for it up to 8 s).
 */

import {
  loQuePide,
  nombreProyecto,
  recortar,
  type Agente,
} from "@/components/oficina/logica";

/** Where the permission (13) can be answered: the office while the hook waits for it. */
export function dondeResponder(a: Agente): string {
  const p = a.permiso;
  return p && p.estado === "pendiente" && p.esperando
    ? "Puedes responder desde la oficina."
    : "Responde en VS Code.";
}

export type TipoAviso =
  "permiso" | "pregunta" | "termino" | "cerrado" | "atasco";

export interface ConfigAvisos {
  /** Master switch ("Activar avisos"). */
  activos: boolean;
  eventos: {
    permiso: boolean;
    pregunta: boolean;
    termino: boolean;
    recordatorio: boolean;
    cerrado: boolean;
    atasco: boolean;
  };
  /** Minutes between reminders while in 13/14; 0 = never. */
  recordatorioMin: 0 | 2 | 5 | 10;
  /** Read the tool and command of a permission. */
  leerPermiso: boolean;
  /** Read the pending question. */
  leerPregunta: boolean;
  /** "Terminó" also shows a Windows notification (voice only by default). */
  notificarTermino: boolean;
  /** Show the notification even when the tab is visible and focused. */
  notificarConFoco: boolean;
  /** voiceURI of the chosen voice; null = automatic (es-MX, es-US, es-*). */
  voz: string | null;
  velocidad: number;
  volumen: number;
  sonido: boolean;
}

export const CONFIG_INICIAL: ConfigAvisos = {
  activos: false,
  eventos: {
    permiso: true,
    pregunta: true,
    termino: true,
    recordatorio: true,
    cerrado: false,
    atasco: true,
  },
  recordatorioMin: 5,
  leerPermiso: true,
  leerPregunta: true,
  notificarTermino: false,
  notificarConFoco: true,
  voz: null,
  velocidad: 1,
  volumen: 1,
  sonido: true,
};

export interface Aviso {
  tipo: TipoAviso;
  sessionId: string;
  recordatorio: boolean;
  /** Spoken text. */
  voz: string;
  /** Notification title and body. */
  titulo: string;
  cuerpo: string;
  /** One notification per agent: a reminder replaces the previous one. */
  tag: string;
  /** Whether to show a Windows notification (voice is always given). */
  notificar: boolean;
  /** The helper agent is still writing its summary (stage 2.4). */
  esperaResumen: boolean;
}

/** Summary of the helper agent for this alert, when ready. */
export function resumenListo(a: Agente, tipo: TipoAviso): string | null {
  if (tipo === "cerrado") return null;
  const r = a.resumenes?.[tipo];
  return r && r.estado === "listo" && r.texto ? r.texto : null;
}

function resumenPendiente(a: Agente, tipo: TipoAviso): boolean {
  if (tipo === "cerrado") return false;
  return a.resumenes?.[tipo]?.estado === "pendiente";
}

export const ESTABILIDAD_MS = 3000;
export const ENFRIAMIENTO_MS = 30000;
export const PREFIJO_PRUEBA = "prueba-";

const CUENTAS: Record<string, string> = { personal: "personal", demo: "Demo Org" };

export function cuentaLegible(cuenta: string | null): string {
  if (!cuenta) return "desconocida";
  return CUENTAS[cuenta] ?? cuenta;
}

/**
 * Project folder name. When another agent shares the project, the Demo Org one
 * says ", cuenta Demo Org"; the personal account is never named.
 */
export function nombreAviso(a: Agente, todos: Agente[]): string {
  const p = nombreProyecto(a);
  const repetido = todos.some(
    (o) =>
      o.agente.session_id !== a.agente.session_id && nombreProyecto(o) === p,
  );
  return repetido && a.agente.cuenta === "demo" ? `${p}, cuenta Demo Org` : p;
}

/** Removes a match but keeps the punctuation that closed the sentence. */
function quitarConservandoPuntuacion(_m: string, ...g: unknown[]): string {
  const final = g[0];
  return ` ${typeof final === "string" ? final : ""}`;
}

/**
 * Text that is pleasant to hear: no code blocks, inline code, URLs or long
 * paths; whitespace collapsed; cut to `max` characters.
 */
export function textoParaLeer(texto: string, max: number): string {
  const limpio = texto
    .replace(/```[\s\S]*?(```|$)/g, " ")
    .replace(/`[^`]*`/g, " ")
    .replace(
      /\bhttps?:\/\/\S*?([.,;:!?)]*)(?=\s|$)/gi,
      quitarConservandoPuntuacion,
    )
    .replace(/\bwww\.\S*?([.,;:!?)]*)(?=\s|$)/gi, quitarConservandoPuntuacion)
    .replace(
      /(?:[A-Za-z]:)?(?:[\\/][^\s\\/]+?){2,}[\\/]?([.,;:!?)]*)(?=\s|$)/g,
      quitarConservandoPuntuacion,
    )
    .replace(/[*_#>|]+/g, " ")
    .replace(/\s+/g, " ")
    .replace(/\s+([.,;:?!])/g, "$1")
    .trim();
  return recortar(limpio, max);
}

function tipoPara(a: Agente): TipoAviso | null {
  const n = a.estado.numero;
  if (n === 13) return "permiso";
  if (n === 14) return "pregunta";
  if (n === 11 && !a.pregunta_pendiente) return "termino";
  if (n === 21 && a.pregunta_pendiente) return "cerrado";
  return null;
}

function habilitado(tipo: TipoAviso, c: ConfigAvisos): boolean {
  return c.eventos[tipo];
}

export function construirAviso(
  tipo: TipoAviso,
  a: Agente,
  todos: Agente[],
  config: ConfigAvisos,
  recordatorio = false,
): Aviso {
  const quien = nombreAviso(a, todos);
  // Only the Demo Org account is named; the personal one has no mark.
  const cuenta = a.agente.cuenta === "demo" ? "Cuenta Demo Org" : "";
  const base = {
    tipo,
    sessionId: a.agente.session_id,
    recordatorio,
    tag: `agente-${a.agente.session_id}`,
    notificar: tipo !== "termino" || config.notificarTermino,
  };
  const prefijo = recordatorio ? "Sigue esperando: " : "";
  // Stage 2.4: the helper agent's sentence replaces the technical text in the
  // voice and leads the notification; the technical detail stays below it.
  const resumen = resumenListo(a, tipo);
  const conResumen = {
    ...base,
    esperaResumen: !resumen && resumenPendiente(a, tipo),
  };
  if (tipo === "permiso") {
    const pide = loQuePide(a)?.texto ?? "";
    const titulo = `${quien} te pide permiso`;
    const leido =
      config.leerPermiso && pide ? `. ${textoParaLeer(pide, 120)}` : "";
    const donde = dondeResponder(a);
    return {
      ...conResumen,
      titulo: prefijo + titulo,
      voz: resumen
        ? `${prefijo}${resumen} ${donde}`
        : `${prefijo}${titulo}${leido}. ${donde}`,
      cuerpo: [resumen, recortar(pide, 120), donde, cuenta]
        .filter(Boolean)
        .join("\n"),
    };
  }
  if (tipo === "pregunta") {
    const q = a.pregunta_pendiente ?? "";
    const titulo = `${quien} te hizo una pregunta`;
    const leido = config.leerPregunta && q ? `. ${textoParaLeer(q, 200)}` : "";
    return {
      ...conResumen,
      titulo: prefijo + titulo,
      voz: resumen ? `${prefijo}${resumen}` : `${prefijo}${titulo}${leido}`,
      cuerpo: [resumen, recortar(q, 200), cuenta].filter(Boolean).join("\n"),
    };
  }
  if (tipo === "termino") {
    const titulo = `${quien} terminó`;
    return {
      ...conResumen,
      titulo,
      voz: resumen ?? titulo,
      cuerpo: [resumen, cuenta].filter(Boolean).join("\n"),
    };
  }
  if (tipo === "atasco") {
    const motivo = a.atasco?.motivo ?? "";
    const titulo = `${quien} parece atascado`;
    return {
      ...conResumen,
      titulo,
      voz: resumen ?? `${titulo}. ${textoParaLeer(motivo, 120)}`,
      cuerpo: [resumen, recortar(motivo, 160), cuenta]
        .filter(Boolean)
        .join("\n"),
    };
  }
  const q = a.pregunta_pendiente ?? "";
  const titulo = `${quien} se cerró con una pregunta pendiente`;
  return {
    ...base,
    esperaResumen: false,
    titulo,
    voz: titulo,
    cuerpo: [recortar(q, 200), cuenta].filter(Boolean).join("\n"),
  };
}

interface Registro {
  /** Last state that held long enough (null: agent seen for the first time). */
  estable: number | null;
  candidato: { numero: number; desde: number } | null;
  /** Last time each alert type was given (cooldown). */
  ultimo: Partial<Record<TipoAviso, number>>;
  /** Base time of the next reminder. */
  baseRecordatorio: number;
  /** Stuck episode already seen (type and start), to alert once per episode. */
  atasco: string | null;
}

function claveAtasco(a: Agente): string | null {
  return a.atasco ? `${a.atasco.tipo}:${a.atasco.desde}` : null;
}

export class DetectorAvisos {
  private registros = new Map<string, Registro>();
  private iniciado = false;

  constructor(
    private readonly estabilidadMs = ESTABILIDAD_MS,
    private readonly enfriamientoMs = ENFRIAMIENTO_MS,
  ) {}

  /** Forget everything: the next observation is again "the load". */
  reiniciar(): void {
    this.registros.clear();
    this.iniciado = false;
  }

  observar(agentes: Agente[], ahora: number, config: ConfigAvisos): Aviso[] {
    const reales = agentes.filter(
      (a) => !a.agente.session_id.startsWith(PREFIJO_PRUEBA),
    );
    if (!this.iniciado) {
      // Page load: record the current states, alert nothing. Agents already
      // waiting get their first reminder one interval from now.
      for (const a of reales) {
        this.registros.set(a.agente.session_id, {
          estable: a.estado.numero,
          candidato: null,
          ultimo: {},
          baseRecordatorio: ahora,
          atasco: claveAtasco(a),
        });
      }
      this.iniciado = true;
      return [];
    }

    const avisos: Aviso[] = [];
    const vistos = new Set<string>();
    for (const a of reales) {
      const id = a.agente.session_id;
      vistos.add(id);
      let r = this.registros.get(id);
      if (!r) {
        r = {
          estable: null,
          candidato: null,
          ultimo: {},
          baseRecordatorio: ahora,
          atasco: null,
        };
        this.registros.set(id, r);
      }

      // A new stuck episode alerts once (the state itself may not change).
      const atasco = claveAtasco(a);
      if (atasco !== r.atasco) {
        r.atasco = atasco;
        if (atasco && config.activos && config.eventos.atasco) {
          const previo = r.ultimo.atasco;
          if (previo === undefined || ahora - previo >= this.enfriamientoMs) {
            avisos.push(construirAviso("atasco", a, reales, config));
            r.ultimo.atasco = ahora;
          }
        }
      }
      const n = a.estado.numero;
      if (n === r.estable) {
        r.candidato = null; // back to the stable state: a flicker, no alert
      } else if (!r.candidato || r.candidato.numero !== n) {
        r.candidato = { numero: n, desde: ahora };
      }

      if (r.candidato && ahora - r.candidato.desde >= this.estabilidadMs) {
        r.estable = n;
        r.candidato = null;
        r.baseRecordatorio = ahora;
        const tipo = tipoPara(a);
        if (tipo && config.activos && habilitado(tipo, config)) {
          const previo = r.ultimo[tipo];
          if (previo === undefined || ahora - previo >= this.enfriamientoMs) {
            avisos.push(construirAviso(tipo, a, reales, config));
            r.ultimo[tipo] = ahora;
          }
        }
        continue;
      }

      // Reminder while the stable state is a wait for the user.
      const esperaTi = r.estable === 13 || r.estable === 14;
      const intervalo = config.recordatorioMin * 60000;
      if (
        !r.candidato &&
        esperaTi &&
        config.activos &&
        config.eventos.recordatorio &&
        intervalo > 0 &&
        ahora - r.baseRecordatorio >= intervalo
      ) {
        r.baseRecordatorio = ahora;
        const tipo = tipoPara(a);
        if (tipo && habilitado(tipo, config)) {
          avisos.push(construirAviso(tipo, a, reales, config, true));
          r.ultimo[tipo] = ahora;
        }
      }
    }
    for (const id of [...this.registros.keys()]) {
      if (!vistos.has(id)) this.registros.delete(id);
    }
    return avisos;
  }
}

/** Longest wait for the helper agent's summary (stage 2.4). */
export const ESPERA_RESUMEN_MS = 8000;

interface Pendiente {
  aviso: Aviso;
  desde: number;
}

/**
 * Alerts waiting for the helper agent's sentence. An alert is given as soon as
 * its summary is ready, or with the technical text when the summary failed,
 * the summaries are off, the agent left, or `ESPERA_RESUMEN_MS` passed: an
 * alert is never held longer than that.
 */
export class EsperaResumenes {
  private pendientes: Pendiente[] = [];

  constructor(private readonly esperaMs = ESPERA_RESUMEN_MS) {}

  get enEspera(): number {
    return this.pendientes.length;
  }

  agregar(aviso: Aviso, ahora: number): void {
    this.pendientes.push({ aviso, desde: ahora });
  }

  listos(agentes: Agente[], ahora: number, config: ConfigAvisos): Aviso[] {
    const salida: Aviso[] = [];
    const quedan: Pendiente[] = [];
    for (const p of this.pendientes) {
      const { aviso } = p;
      const a = agentes.find((x) => x.agente.session_id === aviso.sessionId);
      if (a && resumenListo(a, aviso.tipo)) {
        salida.push(
          construirAviso(aviso.tipo, a, agentes, config, aviso.recordatorio),
        );
      } else if (
        a &&
        resumenPendiente(a, aviso.tipo) &&
        ahora - p.desde < this.esperaMs
      ) {
        quedan.push(p);
      } else {
        salida.push(aviso);
      }
    }
    this.pendientes = quedan;
    return salida;
  }

  vaciar(): void {
    this.pendientes = [];
  }
}

/**
 * Speech queue: items are spoken one after the other, never cut. The speaker
 * is injected (speechSynthesis in the browser, a fake in tests) and must call
 * `fin` when the item ends.
 */
export class ColaVoz<T> {
  private pendientes: T[] = [];
  private ocupado = false;

  constructor(private readonly hablar: (item: T, fin: () => void) => void) {}

  encolar(item: T): void {
    this.pendientes.push(item);
    this.siguiente();
  }

  vaciar(): void {
    this.pendientes = [];
    this.ocupado = false;
  }

  get enCola(): number {
    return this.pendientes.length;
  }

  get hablando(): boolean {
    return this.ocupado;
  }

  private siguiente(): void {
    if (this.ocupado) return;
    const item = this.pendientes.shift();
    if (item === undefined) return;
    this.ocupado = true;
    let terminado = false;
    this.hablar(item, () => {
      if (terminado) return; // a speaker may report the end twice
      terminado = true;
      this.ocupado = false;
      this.siguiente();
    });
  }
}

export interface VozDisponible {
  name: string;
  lang: string;
  voiceURI: string;
}

/** Spanish voices; the chosen one, else es-MX, es-US, es-419, then any es-*. */
export function vocesEspanol<V extends VozDisponible>(voces: V[]): V[] {
  return voces.filter((v) =>
    v.lang.toLowerCase().replace("_", "-").startsWith("es"),
  );
}

export function elegirVoz<V extends VozDisponible>(
  voces: V[],
  preferida: string | null,
): V | null {
  const es = vocesEspanol(voces);
  if (preferida) {
    const v = es.find((x) => x.voiceURI === preferida);
    if (v) return v;
  }
  const norm = (l: string) => l.toLowerCase().replace("_", "-");
  for (const pref of ["es-mx", "es-us", "es-419"]) {
    const v = es.find((x) => norm(x.lang) === pref);
    if (v) return v;
  }
  return es[0] ?? null;
}
