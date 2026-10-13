"use client";

/**
 * useAvisos(agentes): spoken alerts and Windows notifications for agent state
 * changes. Independent from the view: /oficina uses it now and the 3D scene
 * (/oficina/3d) will use it later. Detection lives in deteccion.ts.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { Agente } from "@/components/oficina/logica";
import { apiFetch } from "@/utils/api";
import {
  CONFIG_INICIAL,
  ColaVoz,
  DetectorAvisos,
  EsperaResumenes,
  elegirVoz,
  vocesEspanol,
  type Aviso,
  type ConfigAvisos,
} from "./deteccion";

const CLAVE_CONFIG = "oficina-avisos";
const REVISION_MS = 1000;

export type PermisoNotificaciones =
  "default" | "granted" | "denied" | "no-disponible";

function leerConfig(): ConfigAvisos {
  try {
    const raw = window.localStorage.getItem(CLAVE_CONFIG);
    if (!raw) return CONFIG_INICIAL;
    const c = JSON.parse(raw) as Partial<ConfigAvisos>;
    return {
      ...CONFIG_INICIAL,
      ...c,
      eventos: { ...CONFIG_INICIAL.eventos, ...(c.eventos ?? {}) },
    };
  } catch {
    return CONFIG_INICIAL;
  }
}

function guardarConfig(c: ConfigAvisos): void {
  try {
    window.localStorage.setItem(CLAVE_CONFIG, JSON.stringify(c));
  } catch {
    // private window or blocked storage: settings last until the tab closes
  }
}

function permisoActual(): PermisoNotificaciones {
  if (typeof window === "undefined" || !("Notification" in window))
    return "no-disponible";
  return Notification.permission;
}

// -- short sound (Web Audio, no files) -------------------------------------------

let contextoAudio: AudioContext | null = null;

function audio(): AudioContext | null {
  try {
    if (!contextoAudio) {
      const Ctor =
        window.AudioContext ??
        (window as unknown as { webkitAudioContext?: typeof AudioContext })
          .webkitAudioContext;
      if (!Ctor) return null;
      contextoAudio = new Ctor();
    }
    return contextoAudio;
  } catch {
    return null;
  }
}

/** Two rising tones, ~0.3 s. Calls `fin` when done. */
function tocarSonido(volumen: number, fin: () => void): void {
  const ctx = audio();
  if (!ctx) {
    fin();
    return;
  }
  try {
    const t0 = ctx.currentTime + 0.02;
    [660, 880].forEach((f, i) => {
      const osc = ctx.createOscillator();
      const g = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = f;
      const ini = t0 + i * 0.15;
      g.gain.setValueAtTime(0.0001, ini);
      g.gain.exponentialRampToValueAtTime(
        Math.max(0.0002, 0.2 * volumen),
        ini + 0.02,
      );
      g.gain.exponentialRampToValueAtTime(0.0001, ini + 0.13);
      osc.connect(g).connect(ctx.destination);
      osc.start(ini);
      osc.stop(ini + 0.14);
    });
  } catch {
    // audio not available: go on with the voice
  }
  setTimeout(fin, 380);
}

// -- speech queue (one per page: alerts never talk over each other) ---------------

interface ItemVoz {
  texto: string;
  sonido: boolean;
}

/** Settings and voices used by the queue; updated by the hook. */
let configVoz: ConfigAvisos = CONFIG_INICIAL;
let vocesActuales: SpeechSynthesisVoice[] = [];

function hablarItem(item: ItemVoz, fin: () => void): void {
  const c = configVoz;
  const decir = () => {
    const synth =
      typeof window !== "undefined" ? window.speechSynthesis : undefined;
    if (!synth) {
      fin();
      return;
    }
    const u = new SpeechSynthesisUtterance(item.texto);
    const voz = elegirVoz(vocesActuales, c.voz);
    if (voz) {
      u.voice = voz;
      u.lang = voz.lang;
    } else {
      u.lang = "es-MX";
    }
    u.rate = c.velocidad;
    u.volume = c.volumen;
    // Safety net: some browsers never fire onend.
    const tope = setTimeout(fin, 4000 + item.texto.length * 120);
    u.onend = () => {
      clearTimeout(tope);
      fin();
    };
    u.onerror = () => {
      clearTimeout(tope);
      fin();
    };
    synth.speak(u);
  };
  if (item.sonido) tocarSonido(c.volumen, decir);
  else decir();
}

const colaVoz = new ColaVoz<ItemVoz>(hablarItem);

// -- alerts from outside the agent detector (Prompt 43) ----------------------------

export interface AvisoExterno {
  voz: string;
  titulo: string;
  cuerpo: string;
  /** One notification per alert key. */
  tag: string;
  /** Click on the Windows notification. */
  alHacerClic: () => void;
}

/**
 * Voice and Windows notification of an alert that does not come from the
 * agent detector (the orchestrators' questions and orders, AvisosOrquestador).
 * Uses the saved settings of "Avisos": nothing while they are off, and the
 * notification only with the permission granted. Works on pages without
 * useAvisos (/proyectos): it reads the settings and voices itself.
 */
export function darAvisoExterno(aviso: AvisoExterno): void {
  if (typeof window === "undefined") return;
  const c = leerConfig();
  if (!c.activos) return;
  configVoz = c;
  if (vocesActuales.length === 0) {
    try {
      vocesActuales = window.speechSynthesis?.getVoices() ?? [];
    } catch {
      vocesActuales = [];
    }
  }
  colaVoz.encolar({ texto: aviso.voz, sonido: c.sonido });
  if (permisoActual() !== "granted") return;
  const conFoco = document.visibilityState === "visible" && document.hasFocus();
  if (conFoco && !c.notificarConFoco) return;
  try {
    const opciones: NotificationOptions & { renotify?: boolean } = {
      body: aviso.cuerpo,
      tag: aviso.tag,
    };
    const n = new Notification(aviso.titulo, opciones);
    n.onclick = () => {
      window.focus();
      aviso.alHacerClic();
      n.close();
    };
  } catch {
    // some browsers only allow notifications from a service worker
  }
}

// -- hook ---------------------------------------------------------------------------

export interface ApiAvisos {
  config: ConfigAvisos;
  cambiar: (cambio: Partial<ConfigAvisos>) => void;
  cambiarEvento: (
    evento: keyof ConfigAvisos["eventos"],
    valor: boolean,
  ) => void;
  /** Click on "Activar avisos": asks for notifications and unlocks audio. */
  activar: () => Promise<void>;
  desactivar: () => void;
  probarVoz: () => void;
  probarAviso: () => void;
  permiso: PermisoNotificaciones;
  /** The browser lets the page speak (needs a click after each load). */
  audioListo: boolean;
  /** Notifications need localhost or https. */
  contextoSeguro: boolean;
  voces: SpeechSynthesisVoice[];
  vozElegida: SpeechSynthesisVoice | null;
  vozDisponible: boolean;
  /** Summaries by the helper agent (server setting; null while unknown). */
  resumenes: boolean | null;
  cambiarResumenes: (activos: boolean) => void;
}

const RUTA_CONFIG_AVISOS = "/api/v1/avisos/config";

interface Opciones {
  /** Opens the agent detail when a notification is clicked. */
  abrirAgente: (sessionId: string) => void;
}

export function useAvisos(
  agentes: Agente[] | null,
  { abrirAgente }: Opciones,
): ApiAvisos {
  const [config, setConfig] = useState<ConfigAvisos>(CONFIG_INICIAL);
  const [permiso, setPermiso] = useState<PermisoNotificaciones>("default");
  const [audioListo, setAudioListo] = useState(false);
  const [voces, setVoces] = useState<SpeechSynthesisVoice[]>([]);
  const [contextoSeguro, setContextoSeguro] = useState(true);

  const configRef = useRef(config);
  const agentesRef = useRef(agentes);
  const abrirRef = useRef(abrirAgente);
  const detector = useRef(new DetectorAvisos());
  const espera = useRef(new EsperaResumenes());
  const [resumenes, setResumenes] = useState<boolean | null>(null);

  useEffect(() => {
    configRef.current = config;
    configVoz = config;
  }, [config]);
  useEffect(() => {
    agentesRef.current = agentes;
  }, [agentes]);
  useEffect(() => {
    abrirRef.current = abrirAgente;
  }, [abrirAgente]);

  // Settings and browser capabilities (browser only).
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reading browser state once on mount
    setConfig(leerConfig());
    setPermiso(permisoActual());
    setContextoSeguro(window.isSecureContext);
    const synth = window.speechSynthesis;
    if (!synth) return;
    const cargar = () => {
      const v = synth.getVoices();
      vocesActuales = v;
      setVoces(vocesEspanol(v));
    };
    cargar();
    synth.addEventListener("voiceschanged", cargar);
    return () => synth.removeEventListener("voiceschanged", cargar);
  }, []);

  // Browsers only let a page speak after a user gesture: the first click
  // anywhere unlocks speech and Web Audio for this load.
  useEffect(() => {
    if (audioListo) return;
    const desbloquear = () => {
      try {
        void audio()?.resume();
        const u = new SpeechSynthesisUtterance(" ");
        u.volume = 0;
        window.speechSynthesis?.speak(u);
      } catch {
        // nothing to unlock
      }
      setAudioListo(true);
    };
    window.addEventListener("pointerdown", desbloquear, { once: true });
    window.addEventListener("keydown", desbloquear, { once: true });
    return () => {
      window.removeEventListener("pointerdown", desbloquear);
      window.removeEventListener("keydown", desbloquear);
    };
  }, [audioListo]);

  const notificar = useCallback((aviso: Aviso) => {
    const c = configRef.current;
    if (!aviso.notificar || permisoActual() !== "granted") return;
    const conFoco =
      document.visibilityState === "visible" && document.hasFocus();
    if (conFoco && !c.notificarConFoco) return;
    try {
      const opciones: NotificationOptions & { renotify?: boolean } = {
        body: aviso.cuerpo,
        tag: aviso.tag,
        renotify: true,
      };
      const n = new Notification(aviso.titulo, opciones);
      n.onclick = () => {
        window.focus();
        abrirRef.current(aviso.sessionId);
        n.close();
      };
    } catch {
      // some browsers only allow notifications from a service worker
    }
  }, []);

  const dar = useCallback(
    (aviso: Aviso) => {
      colaVoz.encolar({
        texto: aviso.voz,
        sonido: configRef.current.sonido,
      });
      notificar(aviso);
    },
    [notificar],
  );

  // Check every second (the 3 s rule needs a clock, not only new data).
  // An alert whose summary is still being written waits for it (at most
  // ESPERA_RESUMEN_MS); the others are given right away.
  useEffect(() => {
    const id = setInterval(() => {
      const lista = agentesRef.current;
      if (!lista) return;
      const ahora = Date.now();
      for (const aviso of detector.current.observar(
        lista,
        ahora,
        configRef.current,
      )) {
        if (aviso.esperaResumen) espera.current.agregar(aviso, ahora);
        else dar(aviso);
      }
      for (const aviso of espera.current.listos(
        lista,
        ahora,
        configRef.current,
      )) {
        dar(aviso);
      }
    }, REVISION_MS);
    return () => clearInterval(id);
  }, [dar]);

  // Summaries switch: a server setting (the monitors read it too).
  useEffect(() => {
    let vivo = true;
    apiFetch(RUTA_CONFIG_AVISOS)
      .then((r) => (r.ok ? r.json() : null))
      .then((d: { resumenes?: boolean } | null) => {
        if (vivo && d && typeof d.resumenes === "boolean")
          setResumenes(d.resumenes);
      })
      .catch(() => undefined);
    return () => {
      vivo = false;
    };
  }, []);

  const cambiarResumenes = useCallback((activos: boolean) => {
    setResumenes(activos);
    apiFetch(RUTA_CONFIG_AVISOS, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resumenes: activos }),
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((d: { resumenes?: boolean } | null) => {
        if (d && typeof d.resumenes === "boolean") setResumenes(d.resumenes);
      })
      .catch(() => setResumenes(!activos));
  }, []);

  const cambiar = useCallback((cambio: Partial<ConfigAvisos>) => {
    setConfig((prev) => {
      const next = { ...prev, ...cambio };
      guardarConfig(next);
      return next;
    });
  }, []);

  const cambiarEvento = useCallback(
    (evento: keyof ConfigAvisos["eventos"], valor: boolean) => {
      setConfig((prev) => {
        const next = { ...prev, eventos: { ...prev.eventos, [evento]: valor } };
        guardarConfig(next);
        return next;
      });
    },
    [],
  );

  const activar = useCallback(async () => {
    try {
      void audio()?.resume();
    } catch {
      // no Web Audio
    }
    setAudioListo(true);
    if ("Notification" in window && Notification.permission === "default") {
      try {
        await Notification.requestPermission();
      } catch {
        // old callback-only API or blocked
      }
    }
    setPermiso(permisoActual());
    cambiar({ activos: true });
  }, [cambiar]);

  const desactivar = useCallback(() => {
    espera.current.vaciar();
    colaVoz.vaciar();
    window.speechSynthesis?.cancel();
    cambiar({ activos: false });
  }, [cambiar]);

  const probarVoz = useCallback(() => {
    colaVoz.encolar({
      texto: "Así suenan los avisos de la oficina de agentes.",
      sonido: configRef.current.sonido,
    });
  }, []);

  const probarAviso = useCallback(() => {
    dar({
      tipo: "permiso",
      sessionId: "",
      recordatorio: false,
      voz: "visualizador-agentes te pide permiso. Bash: git status",
      titulo: "visualizador-agentes te pide permiso",
      cuerpo: "Bash: git status\nAviso de prueba",
      tag: "aviso-de-prueba",
      notificar: true,
      esperaResumen: false,
    });
  }, [dar]);

  return {
    config,
    cambiar,
    cambiarEvento,
    activar,
    desactivar,
    probarVoz,
    probarAviso,
    permiso,
    audioListo,
    contextoSeguro,
    voces,
    vozElegida: elegirVoz(voces, config.voz),
    vozDisponible: typeof window !== "undefined" && "speechSynthesis" in window,
    resumenes,
    cambiarResumenes,
  };
}
