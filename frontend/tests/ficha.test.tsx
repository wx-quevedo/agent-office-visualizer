import { GlobalRegistrator } from "@happy-dom/global-registrator";
import {
  afterAll,
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import type { Consumo, Historial, Turno } from "@/components/ficha/logica";
import type { Agente } from "@/components/oficina/logica";
import type { Permiso } from "@/components/permisos/logica";

let React: typeof import("react");
let ReactDOM: typeof import("react-dom/client");
let FichaVista: typeof import("@/components/ficha/FichaAgente").FichaVista;
let useOffice: typeof import("@/components/oficina3d/store").useOffice;

beforeAll(async () => {
  GlobalRegistrator.register({ url: "http://localhost:3100/oficina/3d" });
  (
    globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
  React = await import("react");
  ReactDOM = await import("react-dom/client");
  FichaVista = (await import("@/components/ficha/FichaAgente")).FichaVista;
  useOffice = (await import("@/components/oficina3d/store")).useOffice;
});

afterAll(async () => {
  await GlobalRegistrator.unregister();
});

beforeEach(() => {
  // The permission panel reads its settings: no backend in the tests.
  vi.spyOn(globalThis, "fetch").mockImplementation(() =>
    Promise.reject(new Error("sin red")),
  );
});

afterEach(() => {
  vi.restoreAllMocks();
  document.body.innerHTML = "";
  useOffice.getState().setPanel(null);
});

const AHORA = Date.parse("2026-10-11T15:00:00Z");

function agente(numero: number, extra: Partial<Agente> = {}): Agente {
  return {
    agente: {
      session_id: "prueba-ficha",
      proyecto: "E:\\Test\\SkyNest",
      cuenta: "personal",
      maquina: "alienware",
      modelo: "claude-opus-5-5[1m]",
    },
    estado: {
      numero,
      nombre: `estado ${numero}`,
      desde: "2026-10-11T14:58:00Z",
    },
    espera: null,
    espera_detalle: {
      texto: "Unity: compilando scripts, 2 min",
      base: "Unity: compilando scripts",
      segundos: 134,
      limite_min: 10,
    },
    atasco: null,
    trabajo_continuo_s: 34 * 60,
    herramienta_actual: "Bash",
    ultimo_evento: { tipo: "pre_tool_use", hora: "2026-10-11T14:59:50Z" },
    subagentes_activos: 0,
    pregunta_pendiente: null,
    cierre: null,
    proceso: null,
    indicadores: {
      herramientas_por_minuto: 3,
      tokens_por_minuto: 900,
      tokens_totales: 1000,
      tokens_contexto: 100,
      tokens_motivo: null,
      minutos_con_actividad: 3,
      contexto_usado_pct: 30,
      errores_seguidos: 0,
      errores_motivo: null,
    },
    eventos_recientes: [],
    ...extra,
  };
}

function turno(numero: number, extra: Partial<Turno> = {}): Turno {
  return {
    numero,
    inicio: "2026-10-11T14:00:00Z",
    fin: "2026-10-11T14:30:00Z",
    duracion_s: 1800,
    pedido: `Pedido ${numero}`,
    herramientas: { Bash: 4 },
    total_herramientas: 4,
    archivos_editados: [],
    commits: [],
    errores: 0,
    tokens_salida: 1200,
    resultado: "completado",
    pregunta: null,
    ...extra,
  };
}

const HISTORIAL: Historial = {
  pagina: 1,
  por_pagina: 6,
  total: 3,
  paginas: 1,
  turnos: [
    turno(3, {
      fin: null,
      resultado: "en_curso",
      pedido: "Fase 7A · Prompt 1 · Propuesta del home en VR",
      total_herramientas: 48,
      archivos_editados: ["a.cs", "b.cs", "c.cs"],
      commits: [{ hora: "2026-10-11T14:50:00Z", mensaje: "feat: home" }],
      tokens_salida: 52735,
    }),
    turno(2),
    turno(1, { resultado: "interrumpido", pedido: "Ajustar la economía" }),
  ],
};

const CONSUMO: Consumo = {
  dia: "2026-10-11",
  total: {
    sesiones: 1,
    tokens_salida: 312480,
    segundos_trabajo: 3600,
    segundos_con_agentes: 3600,
  },
  por_sesion: [
    {
      session_id: "prueba-ficha",
      proyecto: "E:\\Test\\SkyNest",
      tokens_salida: 312480,
      segundos_trabajo: 3600,
      continuo_s: 2040,
    },
  ],
};

async function montar(
  a: Agente | undefined,
  opciones: {
    historial?: Historial | null;
    consumo?: Consumo | null;
    onCerrar?: () => void;
  } = {},
): Promise<HTMLElement> {
  const el = document.createElement("div");
  document.body.appendChild(el);
  const raiz = ReactDOM.createRoot(el);
  await React.act(async () => {
    raiz.render(
      React.createElement(FichaVista, {
        agente: a,
        id: "prueba-ficha",
        ahora: AHORA,
        onCerrar: opciones.onCerrar ?? (() => undefined),
        historial:
          opciones.historial === undefined ? HISTORIAL : opciones.historial,
        consumo: opciones.consumo === undefined ? CONSUMO : opciones.consumo,
      }),
    );
  });
  return el;
}

function texto(el: HTMLElement): string {
  return (el.textContent ?? "").replace(/\u00a0/g, " ");
}

describe("ficha del agente", () => {
  it("clic en un agente de la escena abre su ficha sin navegar", () => {
    const antes = window.location.href;
    useOffice.getState().select("prueba-ficha");
    expect(useOffice.getState().panel).toBe("prueba-ficha");
    expect(window.location.href).toBe(antes);
  });

  it("cabecera, ahora mismo, tres cifras y turnos", async () => {
    const el = await montar(agente(4));
    const t = texto(el);
    expect(el.querySelector("h2")?.textContent).toBe("SkyNest");
    expect(t).toContain("E:\\Test\\SkyNest · Alienware");
    expect(t).toContain("Cuenta personal");
    expect(t).toContain("Opus 5.5");
    expect(t).toContain("Unity: compilando scripts");
    expect(t).toContain("2 min 14 s");
    expect(t).toContain("Tiempo razonable para esto: hasta 10 min");
    expect(t).toContain("Trabajo continuo34 min");
    expect(t).toContain("Tokens hoy312 480");
    expect(t).toContain("AtascosNinguno");
    expect(t).toContain("Turno actual · 3");
    expect(t).toContain(
      "48 herramientas · 3 archivos editados · commit: feat: home · 52 735 tokens",
    );
    expect(t).toContain("Ajustar la economía");
    expect(t).toContain("Interrumpido");
    const enlaces = [...el.querySelectorAll("a")].map((a) => [
      a.textContent,
      a.getAttribute("href"),
    ]);
    expect(enlaces).toEqual([
      ["Historial completo", "/historial?agente=prueba-ficha"],
      ["Dónde quedamos", "/donde-quedamos?proyecto=skynest"],
    ]);
    // no emojis anywhere
    expect(t).not.toMatch(/\p{Extended_Pictographic}/u);
  });

  it("permiso pendiente: arriba de todo, con la frase, el comando y los botones", async () => {
    const permiso: Permiso = {
      id: "abc12345",
      session_id: "prueba-ficha",
      herramienta: "PowerShell",
      detalle: "Remove-Item -Recurse Library\\ScriptAssemblies",
      cuenta: "personal",
      proyecto: "SkyNest",
      creada: "2026-10-11T14:59:20Z",
      esperando: true,
      vence: "2026-10-11T15:01:00Z",
      segundos_restantes: 60,
      estado: "pendiente",
      motivo: null,
      dispositivo: null,
      decidida: null,
    };
    const el = await montar(
      agente(13, {
        permiso,
        espera_detalle: {
          texto: "Esperando tu permiso, 40 s",
          base: "Esperando tu permiso",
          segundos: 40,
          limite_min: null,
        },
      }),
    );
    const cuerpo = el.querySelector("aside > div:nth-of-type(2)")!;
    const primero = cuerpo.firstElementChild!;
    expect(primero.textContent).toContain("Te pide permiso · hace 40 s");
    expect(primero.textContent).toContain("Quiere borrar archivos o carpetas.");
    expect(el.querySelector("pre")?.textContent).toBe(
      "Remove-Item -Recurse Library\\ScriptAssemblies",
    );
    const botones = [...el.querySelectorAll("button")].map(
      (b) => b.textContent,
    );
    expect(botones).toContain("Aprobar");
    expect(botones).toContain("Rechazar con motivo");
    // no reasonable time for a wait for you
    expect(texto(el)).not.toContain("Tiempo razonable");
  });

  it("atasco: tarjeta con el motivo, desde cuándo y el último intento", async () => {
    const el = await montar(
      agente(4, {
        atasco: {
          tipo: "error_repetido",
          motivo:
            "Repite el mismo error 3 veces (Bash): falta la variable de entorno",
          desde: "2026-10-11T14:42:00Z",
          ultimos_intentos: ["Bash: npm test", "Bash: npm run build"],
          ultimo_error: "Error: DATABASE_URL no está definida",
        },
        indicadores: { ...agente(4).indicadores, errores_seguidos: 3 },
      }),
    );
    const t = texto(el);
    expect(t).toContain("Parece atascado · 18 min");
    expect(t).toContain("Repite el mismo error 3 veces (Bash)");
    expect(t).toContain("Último intento: Bash: npm run build");
    expect(t).toContain("Último error: Error: DATABASE_URL no está definida");
    expect(t).toContain("Atasco18 min");
    expect(el.querySelector("a")?.textContent).toBe("Ver qué intentó");
  });

  it("pregunta pendiente: la muestra", async () => {
    const el = await montar(
      agente(14, { pregunta_pendiente: "¿Publico la versión nueva?" }),
    );
    const t = texto(el);
    expect(t).toContain("Te pregunta");
    expect(t).toContain("¿Publico la versión nueva?");
  });

  it("sin datos: el agente ya no está y no hay historial ni consumo", async () => {
    const cerrar = vi.fn();
    const el = await montar(undefined, {
      historial: null,
      consumo: null,
      onCerrar: cerrar,
    });
    const t = texto(el);
    expect(t).toContain("Ese agente ya no está en la oficina");
    expect(t).toContain("Cargando el historial…");
    expect(t).not.toContain("Ahora mismo");
    expect(el.querySelector("a")?.getAttribute("href")).toBe(
      "/historial?agente=prueba-ficha",
    );
    const boton = el.querySelector<HTMLButtonElement>(
      'button[aria-label="Cerrar ficha"]',
    )!;
    expect(document.activeElement).toBe(boton);
    await React.act(async () => boton.click());
    expect(cerrar).toHaveBeenCalledTimes(1);
    await React.act(async () => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    });
    expect(cerrar).toHaveBeenCalledTimes(2);
  });

  it("sin consumo ni turnos: guiones y aviso", async () => {
    const el = await montar(
      agente(11, { espera_detalle: null, trabajo_continuo_s: 0 }),
      {
        historial: {
          pagina: 1,
          por_pagina: 6,
          total: 0,
          paginas: 1,
          turnos: [],
        },
        consumo: null,
      },
    );
    const t = texto(el);
    expect(t).toContain("Trabajo continuo—");
    expect(t).toContain("Tokens hoy—");
    expect(t).toContain("Todavía sin turnos registrados.");
    expect(t).toContain("estado 11");
  });
});

describe("ficha con avisos resumidos (etapa 2.4)", () => {
  it("el resumen va primero y el detalle técnico debajo", async () => {
    const permiso: Permiso = {
      id: "abc12345",
      session_id: "prueba-ficha",
      herramienta: "PowerShell",
      detalle: "Remove-Item -Recurse Library\ScriptAssemblies",
      cuenta: "personal",
      proyecto: "SkyNest",
      creada: "2026-10-11T14:59:20Z",
      esperando: true,
      vence: "2026-10-11T15:01:00Z",
      segundos_restantes: 60,
      estado: "pendiente",
      motivo: null,
      dispositivo: null,
      decidida: null,
    };
    const frase =
      "SkyNest quiere borrar una carpeta de compilación de Unity y necesita tu permiso.";
    const el = await montar(
      agente(13, {
        permiso,
        resumenes: {
          permiso: { clave: "k", estado: "listo", texto: frase },
        },
      }),
    );
    const parrafo = [...el.querySelectorAll("p")].find((p) =>
      p.textContent?.includes("SkyNest quiere"),
    );
    expect(parrafo?.textContent).toBe(frase);
    expect(el.textContent).not.toContain("Quiere borrar archivos o carpetas.");
    expect(el.querySelector("pre")?.textContent).toContain("Remove-Item");
  });

  it("pregunta y atasco: frase arriba, texto original debajo", async () => {
    const el = await montar(
      agente(14, {
        pregunta_pendiente: "¿Publico la versión 2.3 en producción?",
        atasco: {
          tipo: "error_repetido",
          motivo: "Repite el mismo error 3 veces (Bash)",
          desde: "2026-10-11T14:42:00Z",
          ultimos_intentos: [],
          ultimo_error: null,
        },
        resumenes: {
          pregunta: {
            clave: "p",
            estado: "listo",
            texto: "SkyNest te pregunta si publica la versión nueva.",
          },
          atasco: { clave: "a", estado: "fallo", texto: null },
        },
      }),
    );
    const t = texto(el);
    expect(t.indexOf("SkyNest te pregunta si publica")).toBeLessThan(
      t.indexOf("¿Publico la versión 2.3"),
    );
    // Atasco sin resumen (falló): el motivo como siempre.
    expect(t).toContain("Repite el mismo error 3 veces (Bash)");
  });
});

describe("permiso sin solicitud registrada (etapa 2.4)", () => {
  it("muestra el resumen y Responde en VS Code", async () => {
    const el = await montar(
      agente(13, {
        permiso: null,
        resumenes: {
          permiso: {
            clave: "k",
            estado: "listo",
            texto: "SkyNest te pregunta cómo sigue con la clave rechazada.",
          },
        },
      }),
    );
    const t = texto(el);
    expect(t).toContain("Te pide permiso");
    expect(t).toContain(
      "SkyNest te pregunta cómo sigue con la clave rechazada.",
    );
    expect(t).toContain("Responde en VS Code.");
  });
});
