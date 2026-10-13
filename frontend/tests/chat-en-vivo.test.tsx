import { GlobalRegistrator } from "@happy-dom/global-registrator";
import {
  afterAll,
  afterEach,
  beforeAll,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import type { Chat, EnVivo, Mensaje } from "@/components/proyectos/logica";
import {
  CONSULTA_MS,
  burbujaEnVivo,
  conexionInicial,
  leerChatEnVivo,
  marcaMensaje,
  siguienteConexion,
  unirRecientes,
} from "@/components/proyectos/logicaEnVivo";

let React: typeof import("react");
let ReactDOM: typeof import("react-dom/client");
let ChatVista: typeof import("@/components/proyectos/Chat").ChatVista;
let useChatEnVivo: typeof import("@/components/proyectos/useChatEnVivo").useChatEnVivo;

beforeAll(async () => {
  GlobalRegistrator.register({ url: "http://localhost:3100/proyectos" });
  (
    globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
  React = await import("react");
  ReactDOM = await import("react-dom/client");
  ChatVista = (await import("@/components/proyectos/Chat")).ChatVista;
  useChatEnVivo = (await import("@/components/proyectos/useChatEnVivo"))
    .useChatEnVivo;
});

afterAll(async () => {
  await GlobalRegistrator.unregister();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
  document.body.innerHTML = "";
});

const AHORA = Date.parse("2026-10-11T16:00:00Z");

function mensaje(extra: Partial<Mensaje> = {}): Mensaje {
  return {
    id: "m1",
    autor: "washington",
    texto: "Hola",
    creado: "2026-10-11T15:00:00Z",
    estado: "enviado",
    leido: null,
    ...extra,
  };
}

function enVivo(extra: Partial<EnVivo> = {}): EnVivo {
  return {
    estado: "respondiendo",
    parcial: "",
    mensaje_id: "1",
    desde: "2026-10-11T15:00:05Z",
    actualizado: "2026-10-11T15:00:05Z",
    ...extra,
  };
}

const LIBRE: EnVivo = {
  estado: "libre",
  parcial: "",
  mensaje_id: null,
  desde: null,
  actualizado: null,
};

async function montar(elemento: React.ReactElement) {
  const el = document.createElement("div");
  document.body.appendChild(el);
  const raiz = ReactDOM.createRoot(el);
  await React.act(async () => {
    raiz.render(elemento);
  });
  return {
    el,
    raiz,
    volver: async (otro: React.ReactElement) => {
      await React.act(async () => {
        raiz.render(otro);
      });
    },
  };
}

function texto(el: Element): string {
  return (el.textContent ?? "").replace(/ /g, " ");
}

function respuesta(body: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

describe("lógica del chat en vivo", () => {
  it("une los recientes por id: reemplaza el estado y agrega los nuevos", () => {
    const leidos = [
      mensaje({ id: "1" }),
      mensaje({ id: "2", autor: "orquestador", estado: null }),
    ];
    const recientes = [
      mensaje({ id: "1", estado: "leido", leido: "2026-10-11T15:00:03Z" }),
      mensaje({
        id: "3",
        autor: "orquestador",
        texto: "Listo",
        estado: null,
        creado: "2026-10-11T15:01:00Z",
      }),
    ];
    const r = unirRecientes(leidos, recientes);
    expect(r.map((m) => m.id)).toEqual(["1", "2", "3"]);
    expect(r[0].estado).toBe("leido");
    expect(unirRecientes(leidos, [])).toBe(leidos);
    expect(unirRecientes(leidos, undefined)).toBe(leidos);
  });

  it("marca Enviando…, Enviado y Leído; nada para el orquestador", () => {
    expect(marcaMensaje(mensaje(), true)).toBe("Enviando…");
    expect(marcaMensaje(mensaje())).toBe("Enviado");
    expect(marcaMensaje(mensaje({ estado: undefined }))).toBe("Enviado");
    expect(marcaMensaje(mensaje({ estado: "leido" }))).toBe("Leído");
    expect(marcaMensaje(mensaje({ estado: "respondiendo" }))).toBe("Leído");
    expect(
      marcaMensaje(mensaje({ autor: "orquestador", estado: null })),
    ).toBeNull();
  });

  it("burbuja en vivo: puntos, texto, nada si está libre o ya llegó el final", () => {
    expect(burbujaEnVivo(null)).toBeNull();
    expect(burbujaEnVivo(LIBRE)).toBeNull();
    expect(burbujaEnVivo(enVivo({ estado: "leido" }))).toBeNull();
    expect(burbujaEnVivo(enVivo())).toEqual({ tipo: "puntos" });
    expect(burbujaEnVivo(enVivo({ parcial: "Voy" }))).toEqual({
      tipo: "texto",
      texto: "Voy",
    });
    const viejo = mensaje({
      id: "0",
      autor: "orquestador",
      estado: null,
      creado: "2026-10-11T14:00:00Z",
    });
    expect(burbujaEnVivo(enVivo({ parcial: "Voy" }), [viejo])).not.toBeNull();
    const final = { ...viejo, creado: "2026-10-11T15:00:09Z" };
    expect(burbujaEnVivo(enVivo({ parcial: "Voy" }), [final])).toBeNull();
  });

  it("lee el JSON del servidor (objeto o texto) y descarta lo que no sirve", () => {
    const d = leerChatEnVivo(
      JSON.stringify({
        version: "7",
        en_vivo: enVivo({ parcial: "Hola" }),
        recientes: [mensaje({ estado: "leido" }), { id: 3 }],
      }),
    );
    expect(d?.version).toBe("7");
    expect(d?.en_vivo.parcial).toBe("Hola");
    expect(d?.recientes).toHaveLength(1);
    expect(d?.recientes[0].estado).toBe("leido");
    expect(leerChatEnVivo("no es json")).toBeNull();
    expect(leerChatEnVivo({ en_vivo: { estado: "otro" } })).toBeNull();
  });

  it("pasa a consultar tras 3 errores seguidos sin mensaje o si se cierra", () => {
    let c = conexionInicial(true);
    c = siguienteConexion(c, "error");
    c = siguienteConexion(c, "error");
    c = siguienteConexion(c, "mensaje");
    expect(c).toEqual({ modo: "sse", errores: 0 });
    c = siguienteConexion(c, "error");
    c = siguienteConexion(c, "error");
    expect(c.modo).toBe("sse");
    c = siguienteConexion(c, "error");
    expect(c.modo).toBe("consulta");
    expect(siguienteConexion(c, "mensaje").modo).toBe("consulta");
    expect(siguienteConexion(conexionInicial(true), "cerrado").modo).toBe(
      "consulta",
    );
    expect(conexionInicial(false).modo).toBe("consulta");
  });
});

describe("chat con la respuesta en vivo", () => {
  const base: Chat = {
    mensajes: [mensaje({ id: "1", texto: "Arma la tienda" })],
    ordenes: [],
  };

  function vista(extra: Record<string, unknown> = {}) {
    return React.createElement(ChatVista, {
      proyecto: { id: "p1", estado: "activo" },
      chat: base,
      ahora: AHORA,
      ...extra,
    });
  }

  it("marca Enviado y luego Leído con los recientes", async () => {
    const { el, volver } = await montar(vista());
    const log = el.querySelector('[role="log"]')!;
    expect(log.querySelector("[data-marca]")?.textContent).toBe("Enviado");
    await volver(
      vista({
        enVivo: enVivo({ estado: "leido" }),
        recientes: [
          mensaje({
            id: "1",
            texto: "Arma la tienda",
            estado: "leido",
            leido: "2026-10-11T15:00:03Z",
          }),
        ],
      }),
    );
    expect(log.querySelector("[data-marca]")?.textContent).toBe("Leído");
    expect(texto(log).match(/Arma la tienda/g)).toHaveLength(1);
    expect(log.querySelector("[data-en-vivo]")).toBeNull();
  });

  it("respondiendo sin texto: burbuja del orquestador con tres puntos", async () => {
    const { el } = await montar(vista({ enVivo: enVivo() }));
    const log = el.querySelector('[role="log"]')!;
    const vivo = log.querySelector("[data-en-vivo]")!;
    expect(vivo).toBe(log.lastElementChild);
    expect(vivo.getAttribute("data-en-vivo")).toBe("puntos");
    expect(
      vivo.querySelector('[aria-label="El orquestador está escribiendo"]'),
    ).not.toBeNull();
    expect(texto(vivo)).toContain("Orquestador");
  });

  it("el en_vivo leído con el chat también sirve, y con la lista vacía", async () => {
    const { el } = await montar(
      vista({ chat: { mensajes: [], ordenes: [], en_vivo: enVivo() } }),
    );
    expect(texto(el)).not.toContain("Todavía no hay mensajes");
    expect(el.querySelector('[role="log"] [data-en-vivo]')).not.toBeNull();
  });

  it("con parcial muestra el texto y Escribiendo…; el final lo reemplaza sin duplicar", async () => {
    const parcial = "Propongo **dos** órdenes";
    const { el, volver } = await montar(
      vista({ enVivo: enVivo({ parcial }), recientes: [] }),
    );
    const log = el.querySelector('[role="log"]')!;
    const vivo = log.querySelector("[data-en-vivo]")!;
    expect(vivo.getAttribute("data-en-vivo")).toBe("texto");
    expect(vivo.querySelector("strong")?.textContent).toBe("dos");
    expect(texto(vivo)).toContain("Escribiendo…");
    const clase = vivo.className;

    const final = mensaje({
      id: "2",
      autor: "orquestador",
      texto: "Propongo **dos** órdenes y listo",
      estado: null,
      creado: "2026-10-11T15:00:20Z",
    });
    await volver(vista({ enVivo: LIBRE, recientes: [final] }));
    expect(log.querySelector("[data-en-vivo]")).toBeNull();
    expect(texto(log).match(/Propongo/g)).toHaveLength(1);
    expect(texto(log)).not.toContain("Escribiendo…");
    const ultimo = log.lastElementChild!;
    expect(ultimo.className).toBe(clase);
    expect(ultimo.querySelector("strong")?.textContent).toBe("dos");
    expect(ultimo.querySelector("time")).not.toBeNull();
  });

  it("sin duplicar aunque el final llegue antes de que el estado diga libre", async () => {
    const final = mensaje({
      id: "2",
      autor: "orquestador",
      texto: "Respuesta final",
      estado: null,
      creado: "2026-10-11T15:00:20Z",
    });
    const { el } = await montar(
      vista({
        enVivo: enVivo({
          parcial: "Respuesta",
          actualizado: "2026-10-11T15:00:19Z",
        }),
        chat: { ...base, mensajes: [...base.mensajes, final] },
      }),
    );
    expect(el.querySelector("[data-en-vivo]")).toBeNull();
    expect(texto(el).match(/Respuesta/g)).toHaveLength(1);
  });
});

/** EventSource that the test drives by hand. */
class FuenteFalsa {
  static creadas: FuenteFalsa[] = [];
  url: string;
  opciones: EventSourceInit | undefined;
  readyState = 0;
  onerror: (() => void) | null = null;
  cerrada = false;
  oyentes: ((e: MessageEvent) => void)[] = [];
  constructor(url: string, opciones?: EventSourceInit) {
    this.url = url;
    this.opciones = opciones;
    FuenteFalsa.creadas.push(this);
  }
  addEventListener(tipo: string, f: (e: MessageEvent) => void) {
    if (tipo === "chat") this.oyentes.push(f);
  }
  close() {
    this.cerrada = true;
    this.readyState = 2;
  }
  emitir(datos: unknown) {
    this.readyState = 1;
    for (const f of this.oyentes)
      f(new MessageEvent("chat", { data: JSON.stringify(datos) }));
  }
  fallar() {
    this.readyState = 0;
    this.onerror?.();
  }
}

describe("hook del chat en vivo", () => {
  function Sonda({ id }: { id: string | null }) {
    const d = useChatEnVivo(id);
    return React.createElement(
      "p",
      { id: "sonda" },
      `${d.enVivo?.estado ?? "-"}|${d.enVivo?.parcial ?? ""}|${d.recientes.length}`,
    );
  }

  function sonda(el: Element): string {
    return el.querySelector("#sonda")?.textContent ?? "";
  }

  it("escucha /chat/eventos con cookie y entrega en_vivo y recientes", async () => {
    FuenteFalsa.creadas = [];
    vi.stubGlobal("EventSource", FuenteFalsa);
    const f = vi.spyOn(globalThis, "fetch");
    const { el, volver } = await montar(
      React.createElement(Sonda, { id: "p1" }),
    );
    expect(FuenteFalsa.creadas).toHaveLength(1);
    const fuente = FuenteFalsa.creadas[0];
    expect(fuente.url).toMatch(
      /\/api\/v1\/proyectos-creados\/p1\/chat\/eventos$/,
    );
    expect(fuente.opciones).toEqual({ withCredentials: true });
    expect(sonda(el)).toBe("-||0");
    await React.act(async () => {
      fuente.emitir({
        version: "1",
        en_vivo: enVivo({ parcial: "Hola" }),
        recientes: [mensaje()],
      });
    });
    expect(sonda(el)).toBe("respondiendo|Hola|1");
    // Two errors are reconnections: still listening, no polling.
    await React.act(async () => {
      fuente.fallar();
      fuente.fallar();
    });
    expect(fuente.cerrada).toBe(false);
    expect(f).not.toHaveBeenCalled();
    // Another project: the old source is closed and a new one opened.
    await volver(React.createElement(Sonda, { id: "p2" }));
    expect(fuente.cerrada).toBe(true);
    expect(FuenteFalsa.creadas).toHaveLength(2);
    expect(sonda(el)).toBe("-||0");
    await volver(React.createElement(Sonda, { id: null }));
    expect(FuenteFalsa.creadas[1].cerrada).toBe(true);
  });

  it("tras 3 errores sin mensaje consulta /chat/en-vivo cada 1 s", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    FuenteFalsa.creadas = [];
    vi.stubGlobal("EventSource", FuenteFalsa);
    let n = 0;
    const f = vi.spyOn(globalThis, "fetch").mockImplementation(() => {
      n += 1;
      return respuesta({
        version: String(n),
        en_vivo: enVivo({ parcial: `parte ${n}` }),
        recientes: [],
      });
    });
    const { el, raiz } = await montar(React.createElement(Sonda, { id: "p1" }));
    const fuente = FuenteFalsa.creadas[0];
    await React.act(async () => {
      fuente.fallar();
      fuente.fallar();
    });
    expect(f).not.toHaveBeenCalled();
    await React.act(async () => {
      fuente.fallar();
    });
    expect(fuente.cerrada).toBe(true);
    expect(f).toHaveBeenCalledTimes(1);
    expect(String(f.mock.calls[0][0])).toMatch(
      /\/api\/v1\/proyectos-creados\/p1\/chat\/en-vivo$/,
    );
    expect((f.mock.calls[0][1] as RequestInit).credentials).toBe("include");
    expect(sonda(el)).toBe("respondiendo|parte 1|0");

    await React.act(async () => {
      await vi.advanceTimersByTimeAsync(CONSULTA_MS);
    });
    expect(f).toHaveBeenCalledTimes(2);
    expect(sonda(el)).toBe("respondiendo|parte 2|0");

    // On unmount the polling stops.
    await React.act(async () => raiz.unmount());
    await React.act(async () => {
      await vi.advanceTimersByTimeAsync(CONSULTA_MS * 3);
    });
    expect(f).toHaveBeenCalledTimes(2);
  });

  it("sin EventSource consulta desde el principio", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    vi.stubGlobal("EventSource", undefined);
    const f = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() =>
        respuesta({ version: "1", en_vivo: LIBRE, recientes: [mensaje()] }),
      );
    const { el, raiz } = await montar(React.createElement(Sonda, { id: "p1" }));
    expect(f).toHaveBeenCalledTimes(1);
    expect(sonda(el)).toBe("libre||1");
    await React.act(async () => {
      await vi.advanceTimersByTimeAsync(CONSULTA_MS);
    });
    expect(f).toHaveBeenCalledTimes(2);
    await React.act(async () => raiz.unmount());
  });
});
