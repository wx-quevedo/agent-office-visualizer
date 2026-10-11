import { GlobalRegistrator } from "@happy-dom/global-registrator";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import type { Consumo } from "@/components/ficha/logica";
import type { Agente } from "@/components/oficina/logica";
import {
  alertaDe,
  armarProyectos,
  etapas,
  promptsDeEtapa,
  quienHace,
  type ProyectoApi,
} from "@/components/donde/logica";

let React: typeof import("react");
let ReactDOM: typeof import("react-dom/client");
let DondeVista: typeof import("@/components/donde/DondeQuedamos").DondeVista;

beforeAll(async () => {
  GlobalRegistrator.register({ url: "http://localhost:3100/donde-quedamos" });
  (
    globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
  React = await import("react");
  ReactDOM = await import("react-dom/client");
  DondeVista = (await import("@/components/donde/DondeQuedamos")).DondeVista;
});

afterAll(async () => {
  await GlobalRegistrator.unregister();
});

afterEach(() => {
  document.body.innerHTML = "";
});

const AHORA = Date.parse("2026-10-11T16:00:00Z");

const VISUALIZADOR: ProyectoApi = {
  carpeta: "E:\\visualizador-agentes",
  maquina: "alienware",
  tiene_project_md: true,
  titulo: "Visualizador de Agentes",
  plan: [
    { nombre: "Arquitectura", estado: "pendiente" },
    { nombre: "Etapa 0, cierre", estado: "hecho" },
    { nombre: "Etapa 1.1", estado: "hecho" },
    { nombre: "Etapa 1, publicar", estado: "hecho" },
    { nombre: "Etapa 2, ver bien", estado: "pendiente" },
    { nombre: "Etapa 3, app iOS", estado: "pendiente" },
    { nombre: "Etapa 4, orquestador", estado: "pendiente" },
  ],
  posicion: "Etapa 2, ver bien",
  siguiente_paso: "Washington actualiza el monitor de la Alienware a la 0.2.1.",
  espera_decision: [
    "Umbrales del detector de atascos",
    "Qué hacer con el disco del VPS",
  ],
  ultimo_commit: {
    hash: "ac740e2",
    mensaje: "feat: esperas específicas, historial, consumo y atascos",
    fecha: "2026-10-11T10:34:06-05:00",
  },
  recibido: "2026-10-11T15:58:00Z",
  ultima_actividad: null,
  prompts: [
    {
      numero: 26,
      nombre: "datos y API",
      estado: "hecho",
      fecha: "2026-10-11",
      commits: ["ac740e2"],
    },
    { numero: 27, nombre: "bocetos", estado: "pendiente", commits: [] },
    { numero: 28, nombre: "ficha y Dónde quedamos", estado: "pendiente" },
    { numero: 29, nombre: "avisos resumidos", estado: "pendiente" },
  ],
  prompts_turnos: [
    {
      numero: 25,
      nombre: "etapa 1.4",
      inicio: "2026-10-10T20:00:00Z",
      duracion_s: 5000,
      commits: [],
      resultado: "completado",
    },
    {
      numero: 28,
      nombre: "Etapa 2.3, ficha",
      inicio: "2026-10-11T15:00:00Z",
      duracion_s: 3720,
      commits: [],
      resultado: "en_curso",
    },
  ],
};

const SIN_MD: ProyectoApi = {
  carpeta: "E:\\vive-demo",
  maquina: "alienware",
  tiene_project_md: false,
  plan: [],
  espera_decision: [],
  ultimo_commit: null,
  ultima_actividad: {
    session_id: "prueba-vb",
    estado: "Inactivo",
    espera: null,
    ultimo_evento: "2026-10-10T23:20:00Z",
    ultimo_turno: {
      numero: 4,
      inicio: "2026-10-10T23:00:00Z",
      fin: "2026-10-10T23:20:00Z",
      duracion_s: 1200,
      pedido: "Validar el correo en el registro",
      herramientas: {},
      total_herramientas: 12,
      archivos_editados: [],
      commits: [],
      errores: 0,
      tokens_salida: 900,
      resultado: "completado",
      pregunta: null,
    },
  },
};

function agente(
  carpeta: string,
  numero: number,
  extra: Partial<Agente> = {},
): Agente {
  return {
    agente: {
      session_id: `prueba-${carpeta}-${numero}`,
      proyecto: carpeta,
      cuenta: "personal",
      maquina: "alienware",
    },
    estado: {
      numero,
      nombre: `estado ${numero}`,
      desde: "2026-10-11T15:00:00Z",
    },
    espera: null,
    herramienta_actual: null,
    ultimo_evento: { tipo: "stop", hora: "2026-10-11T15:59:00Z" },
    subagentes_activos: 0,
    pregunta_pendiente: null,
    cierre: null,
    proceso: null,
    indicadores: {
      herramientas_por_minuto: null,
      tokens_por_minuto: null,
      tokens_totales: null,
      tokens_contexto: null,
      tokens_motivo: null,
      minutos_con_actividad: null,
      contexto_usado_pct: null,
      errores_seguidos: null,
      errores_motivo: null,
    },
    eventos_recientes: [],
    ...extra,
  };
}

const CONSUMO: Consumo = {
  dia: "2026-10-11",
  total: {
    sesiones: 3,
    tokens_salida: 707246,
    segundos_trabajo: 20000,
    segundos_con_agentes: 16500,
  },
  por_sesion: [
    {
      session_id: "x",
      proyecto: "E:\\visualizador-agentes",
      tokens_salida: 120000,
      segundos_trabajo: 4200,
      continuo_s: 0,
    },
  ],
};

async function montar(
  props: Partial<Parameters<typeof DondeVista>[0]>,
): Promise<HTMLElement> {
  const el = document.createElement("div");
  document.body.appendChild(el);
  const raiz = ReactDOM.createRoot(el);
  await React.act(async () => {
    raiz.render(
      React.createElement(DondeVista, {
        proyectos: null,
        elegido: null,
        consumo: CONSUMO,
        ahora: AHORA,
        ...props,
      }),
    );
  });
  return el;
}

function texto(el: HTMLElement): string {
  return (el.textContent ?? "").replace(/\u00a0/g, " ");
}

describe("lógica de Dónde quedamos", () => {
  it("las etapas principales, con la actual marcada", () => {
    const e = etapas(VISUALIZADOR.plan, VISUALIZADOR.posicion);
    expect(e.map((x) => [x.etiqueta, x.nombre, x.estado])).toEqual([
      ["Etapa 0", "Cierre", "hecha"],
      ["Etapa 1", "Publicar", "hecha"],
      ["Etapa 2", "Ver bien", "actual"],
      ["Etapa 3", "App iOS", "pendiente"],
      ["Etapa 4", "Orquestador", "pendiente"],
    ]);
    // without "Etapa N" items, every item counts
    expect(
      etapas(
        [
          { nombre: "Diseño", estado: "hecho" },
          { nombre: "API", estado: "en_curso" },
        ],
        null,
      ).map((x) => x.estado),
    ).toEqual(["hecha", "actual"]);
  });

  it("los prompts de la etapa: los del PROJECT.md con el tiempo de los turnos", () => {
    const p = promptsDeEtapa(VISUALIZADOR);
    expect(p.map((x) => [x.numero, x.estado, x.dato, x.actual])).toEqual([
      [26, "hecho", "ac740e2", false],
      [27, "pendiente", "sin empezar", false],
      [28, "en_curso", "1 h 2 min", true],
      [29, "pendiente", "sin empezar", false],
    ]);
    expect(p[0].nombre).toBe("Datos y API");
    // without a list in the PROJECT.md: the prompts its agents ran
    const solo = promptsDeEtapa({ ...VISUALIZADOR, prompts: [] });
    expect(solo.map((x) => x.numero)).toEqual([25, 28]);
  });

  it("alertas: permiso, atasco, pregunta, decisión y listo", () => {
    const c = "E:\\visualizador-agentes";
    expect(alertaDe(VISUALIZADOR, [agente(c, 13)]).tipo).toBe("permiso");
    expect(
      alertaDe(VISUALIZADOR, [
        agente(c, 4, {
          atasco: {
            tipo: "sin_avance",
            motivo: "x",
            desde: "2026-10-11T15:00:00Z",
            ultimos_intentos: [],
            ultimo_error: null,
          },
        }),
      ]).tipo,
    ).toBe("atasco");
    expect(alertaDe(SIN_MD, [agente(c, 14)]).tipo).toBe("pregunta");
    expect(alertaDe(VISUALIZADOR, []).texto).toBe("Espera tu decisión: 2");
    expect(alertaDe(SIN_MD, []).tipo).toBe("listo");
  });

  it("arma la lista: urgentes primero y carpetas sin reporte del monitor", () => {
    const lista = armarProyectos(
      [SIN_MD, VISUALIZADOR],
      [agente("E:\\vive-demo", 13), agente("E:\\Test\\SkyNest", 4)],
    );
    expect(lista.map((p) => [p.id, p.alerta.tipo])).toEqual([
      ["vive-demo", "permiso"],
      ["visualizador-agentes", "decision"],
      ["skynest", "trabajando"],
    ]);
    expect(lista[2].datos.tiene_project_md).toBe(false);
  });

  it("quién hace lo siguiente", () => {
    expect(quienHace("Washington aprueba los bocetos")).toBe("Quién: tú.");
    expect(quienHace("Prompt 29: avisos resumidos")).toBe("Quién: el agente.");
    expect(quienHace("Vigilar el disco")).toBeNull();
  });
});

describe("vista de Dónde quedamos", () => {
  it("proyecto con PROJECT.md: plan, estás aquí, prompts, tres tarjetas y consumo", async () => {
    const proyectos = armarProyectos([VISUALIZADOR, SIN_MD], []);
    const el = await montar({ proyectos, elegido: "visualizador-agentes" });
    const t = texto(el);
    expect(el.querySelector("h1")?.textContent).toBe("visualizador-agentes");
    expect(t).toContain("Plan por etapas");
    const actual = el.querySelector('[aria-current="step"]');
    expect(actual?.textContent).toContain("Etapa 2");
    expect(t).toContain("Estás aquí");
    expect(t).toContain("Etapa 2 · Ver bien");
    expect(t).toContain("Prompt 28");
    expect(t).toContain("En curso");
    expect(t).toContain("Lo último que se hizo");
    expect(t).toContain("commit ac740e2");
    expect(t).toContain("Lo siguiente");
    expect(t).toContain("Quién: tú.");
    expect(t).toContain("Espera tu decisión · 2");
    expect(t).toContain("Qué hacer con el disco del VPS");
    expect(t).toContain("Hoy: 4 h 35 min de agentes · 707 246 tokens");
    expect(t).toContain("En este proyecto: 1 h 10 min · 120 000 tokens");
    const elegido = el.querySelector('a[aria-current="page"]');
    expect(elegido?.getAttribute("href")).toBe(
      "/donde-quedamos?proyecto=visualizador-agentes",
    );
    expect(t).not.toMatch(/\p{Extended_Pictographic}/u);
  });

  it("proyecto sin PROJECT.md: lo último del agente y el aviso", async () => {
    const proyectos = armarProyectos([VISUALIZADOR, SIN_MD], []);
    const el = await montar({ proyectos, elegido: "vive-demo" });
    const t = texto(el);
    expect(t).toContain("no tiene PROJECT.md");
    expect(t).toContain("Lo último que hizo el agente");
    expect(t).toContain("Validar el correo en el registro");
    expect(t).toContain("Completado");
    expect(t).not.toContain("Plan por etapas");
  });

  it("sin datos: cargando, sin proyectos y aviso de las 8 horas", async () => {
    let el = await montar({ proyectos: null, consumo: null });
    expect(texto(el)).toContain("Cargando…");
    document.body.innerHTML = "";
    el = await montar({ proyectos: [], consumo: null, desdeOficina: true });
    const t = texto(el);
    expect(t).toContain("Todavía no hay proyectos");
    expect(t).toContain("Pasaron más de 8 horas desde tu última visita");
  });
});
