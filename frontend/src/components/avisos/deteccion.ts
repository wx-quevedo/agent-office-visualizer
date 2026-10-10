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
 */

import {
  loQuePide,
  nombreProyecto,
  recortar,
  type Agente,
} from "@/components/oficina/logica";

export type TipoAviso = "permiso" | "pregunta" | "termino" | "cerrado";

export interface ConfigAvisos {
  /** Master switch ("Activar avisos"). */
  activos: boolean;
  eventos: {
    permiso: boolean;
    pregunta: boolean;
    termino: boolean;
    recordatorio: boolean;
    cerrado: boolean;
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
}

export const ESTABILIDAD_MS = 3000;
export const ENFRIAMIENTO_MS = 30000;
export const PREFIJO_PRUEBA = "prueba-";

const CUENTAS: Record<string, string> = { personal: "personal", demo: "Demo Org" };

export function cuentaLegible(cuenta: string | null): string {
  if (!cuenta) return "desconocida";
  return CUENTAS[cuenta] ?? cuenta;
}

/** Project folder name; with the account when another agent shares the project. */
export function nombreAviso(a: Agente, todos: Agente[]): string {
  const p = nombreProyecto(a);
  const repetido = todos.some(
    (o) =>
      o.agente.session_id !== a.agente.session_id && nombreProyecto(o) === p,
  );
  return repetido ? `${p}, cuenta ${cuentaLegible(a.agente.cuenta)}` : p;
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
  const cuenta = `Cuenta ${cuentaLegible(a.agente.cuenta)}`;
  const base = {
    tipo,
    sessionId: a.agente.session_id,
    recordatorio,
    tag: `agente-${a.agente.session_id}`,
    notificar: tipo !== "termino" || config.notificarTermino,
  };
  const prefijo = recordatorio ? "Sigue esperando: " : "";
  if (tipo === "permiso") {
    const pide = loQuePide(a)?.texto ?? "";
    const titulo = `${quien} te pide permiso`;
    const leido =
      config.leerPermiso && pide ? `. ${textoParaLeer(pide, 120)}` : "";
    return {
      ...base,
      titulo: prefijo + titulo,
      voz: `${prefijo}${titulo}${leido}`,
      cuerpo: [recortar(pide, 120), cuenta].filter(Boolean).join("\n"),
    };
  }
  if (tipo === "pregunta") {
    const q = a.pregunta_pendiente ?? "";
    const titulo = `${quien} te hizo una pregunta`;
    const leido = config.leerPregunta && q ? `. ${textoParaLeer(q, 200)}` : "";
    return {
      ...base,
      titulo: prefijo + titulo,
      voz: `${prefijo}${titulo}${leido}`,
      cuerpo: [recortar(q, 200), cuenta].filter(Boolean).join("\n"),
    };
  }
  if (tipo === "termino") {
    const titulo = `${quien} terminó`;
    return { ...base, titulo, voz: titulo, cuerpo: cuenta };
  }
  const q = a.pregunta_pendiente ?? "";
  const titulo = `${quien} se cerró con una pregunta pendiente`;
  return {
    ...base,
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
        };
        this.registros.set(id, r);
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
