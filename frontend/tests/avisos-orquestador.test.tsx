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
import {
  CLAVE_AVISADAS,
  MAX_AVISADAS,
  avisosVisibles,
  enlaceResponder,
  guardarAvisadas,
  haceCuanto,
  leerAvisadas,
  objetivoAviso,
  revisarClaves,
  rutaAccion,
  textoTipo,
  tituloAviso,
  vozAviso,
  type AvisoOrquestador,
} from "@/components/avisos/logicaOrquestador";
import type { Orden } from "@/components/proyectos/logica";

let React: typeof import("react");
let ReactDOM: typeof import("react-dom/client");
let AvisosOrquestador: typeof import("@/components/avisos/AvisosOrquestador").default;

beforeAll(async () => {
  GlobalRegistrator.register({ url: "http://localhost:3100/oficina" });
  (
    globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
  React = await import("react");
  ReactDOM = await import("react-dom/client");
  AvisosOrquestador = (await import("@/components/avisos/AvisosOrquestador"))
    .default;
});

afterAll(async () => {
  await GlobalRegistrator.unregister();
});

beforeEach(() => {
  window.localStorage.clear();
});

const raices: import("react-dom/client").Root[] = [];

afterEach(async () => {
  for (const r of raices.splice(0))
    await React.act(async () => {
      r.unmount();
    });
  vi.restoreAllMocks();
  document.body.innerHTML = "";
});

function orden(extra: Partial<Orden> = {}): Orden {
  return {
    id: "o1",
    proyecto_id: "p2",
    proyecto: "juego",
    numero: 3,
    agente: "agente-1",
    texto_propuesto: "Arma el nivel 2.",
    texto_final: null,
    texto: "Arma el nivel 2.",
    editada: false,
    titulo: "Nivel 2",
    estimado: null,
    dificultad: null,
    estado: "por_aprobar",
    motivo: null,
    decidido_por: null,
    decidido: null,
    resumen: null,
    creado: "2026-10-12T15:00:00Z",
    actualizado: "2026-10-12T15:00:00Z",
    ...extra,
  };
}

function aviso(extra: Partial<AvisoOrquestador> = {}): AvisoOrquestador {
  return {
    clave: "mensaje:m1",
    tipo: "pregunta",
    proyecto_id: "p1",
    proyecto: "tienda-web",
    maquina: "alienware",
    cuenta: "personal",
    texto: "¿Uso Stripe o Mercado Pago para el cobro?",
    desde: new Date(Date.now() - 120_000).toISOString(),
    hace_s: 120,
    mensaje_id: "m1",
    orden: null,
    ...extra,
  };
}

const ORDEN = aviso({
  clave: "orden:o1",
  tipo: "orden",
  proyecto_id: "p2",
  proyecto: "juego",
  texto: "Orden 3 para agente-1: Nivel 2",
  mensaje_id: null,
  orden: orden(),
});

function respuesta(body: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

/**
 * fetch with the reads of GET /avisos-orquestador taken from `lecturas` (the
 * last one repeats) and POST ignorar/esperar answered with `estadoPost`.
 */
function servidor(lecturas: AvisoOrquestador[][], estadoPost = 200) {
  let i = 0;
  return vi.spyOn(globalThis, "fetch").mockImplementation((url, init) => {
    const u = String(url);
    if (init?.method === "POST") {
      const cuerpo = JSON.parse(String(init.body)) as { clave: string };
      return respuesta(
        {
          clave: cuerpo.clave,
          estado: u.endsWith("/ignorar") ? "ignorado" : "en_espera",
        },
        estadoPost,
      );
    }
    if (u.includes("/api/v1/avisos-orquestador")) {
      const avisos = lecturas[Math.min(i, lecturas.length - 1)];
      i += 1;
      return respuesta({ avisos });
    }
    return respuesta({}, 404);
  });
}

async function montar(elemento: React.ReactElement): Promise<HTMLElement> {
  const el = document.createElement("div");
  document.body.appendChild(el);
  const raiz = ReactDOM.createRoot(el);
  raices.push(raiz);
  await React.act(async () => {
    raiz.render(elemento);
  });
  return el;
}

/** Lets reads every `CADA` ms happen (real timers). */
async function esperar(ms: number) {
  await React.act(() => new Promise<void>((r) => setTimeout(r, ms)));
}

const CADA = 15;

function boton(el: Element, t: string): HTMLButtonElement | undefined {
  return [...el.querySelectorAll("button")].find((b) =>
    (b.textContent ?? "").startsWith(t),
  );
}

function texto(el: Element): string {
  return (el.textContent ?? "").replace(/\u00a0/g, " ");
}

describe("lógica de los avisos de los orquestadores", () => {
  it("Responder arma la URL del chat con la clave codificada", () => {
    expect(enlaceResponder(aviso())).toBe(
      "/proyectos/ver?id=p1&seccion=chat&aviso=mensaje%3Am1",
    );
    expect(enlaceResponder(ORDEN)).toBe(
      "/proyectos/ver?id=p2&seccion=chat&aviso=orden%3Ao1",
    );
    const raro = enlaceResponder(
      aviso({ proyecto_id: "p 1", clave: "mensaje:a&b=c" }),
    );
    const q = new URLSearchParams(raro.split("?")[1]);
    expect(q.get("id")).toBe("p 1");
    expect(q.get("aviso")).toBe("mensaje:a&b=c");
    expect(rutaAccion("ignorar")).toBe("/api/v1/avisos-orquestador/ignorar");
    expect(rutaAccion("esperar")).toBe("/api/v1/avisos-orquestador/esperar");
  });

  it("lee el destino del aviso de la URL", () => {
    expect(objetivoAviso("mensaje:m1")).toEqual({ tipo: "mensaje", id: "m1" });
    expect(objetivoAviso("orden:o-7")).toEqual({ tipo: "orden", id: "o-7" });
    expect(objetivoAviso("otra:1")).toBeNull();
    expect(objetivoAviso("mensaje:")).toBeNull();
    expect(objetivoAviso(null)).toBeNull();
  });

  it("en la página de un proyecto no muestra sus avisos; tampoco los quitados", () => {
    const lista = [aviso(), ORDEN];
    expect(avisosVisibles(lista, new Set()).length).toBe(2);
    expect(avisosVisibles(lista, new Set(), "p1").map((a) => a.clave)).toEqual([
      "orden:o1",
    ]);
    expect(
      avisosVisibles(lista, new Set(["orden:o1"]), null).map((a) => a.clave),
    ).toEqual(["mensaje:m1"]);
  });

  it("una vez por clave: la primera lectura solo registra", () => {
    const r1 = revisarClaves(["a", "b"], [], true);
    expect(r1).toEqual({ nuevas: [], avisadas: ["a", "b"] });
    const r2 = revisarClaves(["a", "b", "c"], r1.avisadas, false);
    expect(r2).toEqual({ nuevas: ["c"], avisadas: ["a", "b", "c"] });
    expect(revisarClaves(["a", "b", "c"], r2.avisadas, false).nuevas).toEqual(
      [],
    );
    // the list keeps the latest 200
    const muchas = Array.from({ length: MAX_AVISADAS }, (_, i) => `k${i}`);
    const r3 = revisarClaves(["nueva"], muchas, false);
    expect(r3.avisadas).toHaveLength(MAX_AVISADAS);
    expect(r3.avisadas[0]).toBe("k1");
    expect(r3.avisadas.at(-1)).toBe("nueva");
  });

  it("guarda y lee las claves avisadas, sin romperse con el almacén bloqueado", () => {
    const datos = new Map<string, string>();
    const st = {
      getItem: (k: string) => datos.get(k) ?? null,
      setItem: (k: string, v: string) => void datos.set(k, v),
    };
    guardarAvisadas(st, ["a", "b"]);
    expect(JSON.parse(datos.get(CLAVE_AVISADAS)!)).toEqual(["a", "b"]);
    expect(leerAvisadas(st)).toEqual(["a", "b"]);
    datos.set(CLAVE_AVISADAS, "{roto");
    expect(leerAvisadas(st)).toEqual([]);
    const bloqueado = {
      getItem: () => {
        throw new Error("bloqueado");
      },
      setItem: () => {
        throw new Error("bloqueado");
      },
    };
    expect(leerAvisadas(bloqueado)).toEqual([]);
    expect(() => guardarAvisadas(bloqueado, ["a"])).not.toThrow();
    expect(leerAvisadas(null)).toEqual([]);
  });

  it("textos de la tarjeta, la notificación y la voz", () => {
    expect(textoTipo("pregunta")).toBe("te hizo una pregunta");
    expect(textoTipo("orden")).toBe("propone una orden");
    expect(tituloAviso(aviso())).toBe(
      "tienda-web: el orquestador te hizo una pregunta",
    );
    expect(
      vozAviso(
        aviso({ texto: "¿Borro `node_modules` en E:/proyectos/web/x?" }),
      ),
    ).toBe("tienda-web: el orquestador te hizo una pregunta. ¿Borro en?");
    expect(haceCuanto(5)).toBe("hace 5 s");
    expect(haceCuanto(180)).toBe("hace 3 min");
    expect(haceCuanto(7200)).toBe("hace 2 h");
    expect(haceCuanto(90000)).toBe("hace 1 d");
    expect(haceCuanto(-3)).toBe("hace 0 s");
  });
});

describe("tarjetas de avisos de los orquestadores", () => {
  it("muestra pregunta y orden con sus tres botones y Responder lleva al chat", async () => {
    servidor([[aviso(), ORDEN]]);
    const el = await montar(
      React.createElement(AvisosOrquestador, { dar: vi.fn(), cadaMs: CADA }),
    );
    await esperar(5);
    const tarjetas = el.querySelectorAll("li");
    expect(tarjetas).toHaveLength(2);
    const t = texto(el);
    expect(t).toContain("tienda-web");
    expect(t).toContain("El orquestador te hizo una pregunta");
    expect(t).toContain("¿Uso Stripe o Mercado Pago para el cobro?");
    expect(t).toContain("hace 2 min");
    expect(t).toContain("El orquestador propone una orden");
    expect(t).toContain("Orden 3 para agente-1: Nivel 2");
    const responder = [...el.querySelectorAll("a")].map((a) =>
      a.getAttribute("href"),
    );
    expect(responder).toEqual([
      "/proyectos/ver?id=p1&seccion=chat&aviso=mensaje%3Am1",
      "/proyectos/ver?id=p2&seccion=chat&aviso=orden%3Ao1",
    ]);
    expect(boton(tarjetas[0], "Ignorar")).toBeDefined();
    expect(boton(tarjetas[0], "Esperar")).toBeDefined();
    expect(
      el.querySelector('section[aria-label="Avisos de los orquestadores"]'),
    ).not.toBeNull();
    expect(t).not.toMatch(/\p{Extended_Pictographic}/u);
  });

  it("sin avisos no muestra nada", async () => {
    servidor([[]]);
    const el = await montar(
      React.createElement(AvisosOrquestador, { dar: vi.fn(), cadaMs: CADA }),
    );
    await esperar(5);
    expect(el.innerHTML).toBe("");
  });

  it("en la página del proyecto no muestra sus avisos", async () => {
    servidor([[aviso(), ORDEN]]);
    const el = await montar(
      React.createElement(AvisosOrquestador, {
        dar: vi.fn(),
        cadaMs: CADA,
        proyectoActual: "p1",
      }),
    );
    await esperar(5);
    expect(el.querySelectorAll("li")).toHaveLength(1);
    expect(texto(el)).not.toContain("tienda-web");
    expect(texto(el)).toContain("juego");
  });

  it("Ignorar llama a la ruta y la tarjeta se va al instante", async () => {
    const f = servidor([[aviso(), ORDEN]]);
    const el = await montar(
      React.createElement(AvisosOrquestador, { dar: vi.fn(), cadaMs: 10_000 }),
    );
    await esperar(5);
    await React.act(async () => boton(el, "Ignorar")!.click());
    expect(texto(el)).not.toContain("tienda-web");
    expect(el.querySelectorAll("li")).toHaveLength(1);
    const post = f.mock.calls.find((c) => c[1]?.method === "POST")!;
    expect(String(post[0])).toMatch(/\/api\/v1\/avisos-orquestador\/ignorar$/);
    expect(JSON.parse(String(post[1]!.body))).toEqual({ clave: "mensaje:m1" });
    expect(new Headers(post[1]!.headers).get("X-Visualizador")).toBe("1");
  });

  it("Esperar llama a la ruta y la tarjeta se va al instante", async () => {
    const f = servidor([[aviso(), ORDEN]]);
    const el = await montar(
      React.createElement(AvisosOrquestador, { dar: vi.fn(), cadaMs: 10_000 }),
    );
    await esperar(5);
    const segunda = el.querySelectorAll("li")[1];
    await React.act(async () => boton(segunda, "Esperar")!.click());
    expect(texto(el)).not.toContain("juego");
    expect(el.querySelectorAll("li")).toHaveLength(1);
    const post = f.mock.calls.find((c) => c[1]?.method === "POST")!;
    expect(String(post[0])).toMatch(/\/api\/v1\/avisos-orquestador\/esperar$/);
    expect(JSON.parse(String(post[1]!.body))).toEqual({ clave: "orden:o1" });
  });

  it("si Ignorar falla, la tarjeta vuelve y se explica", async () => {
    servidor([[aviso()]], 500);
    const el = await montar(
      React.createElement(AvisosOrquestador, { dar: vi.fn(), cadaMs: 10_000 }),
    );
    await esperar(5);
    await React.act(async () => boton(el, "Ignorar")!.click());
    await esperar(5);
    expect(el.querySelectorAll("li")).toHaveLength(1);
    expect(el.querySelector('[role="alert"]')?.textContent).toContain(
      "No se pudo ignorar el aviso de tienda-web",
    );
    await React.act(async () => boton(el, "Cerrar")!.click());
    expect(el.querySelector('[role="alert"]')).toBeNull();
  });

  it("un aviso por clave: no se repite en cada lectura ni tras recargar", async () => {
    const dar = vi.fn();
    servidor([[aviso()], [aviso(), ORDEN]]);
    const el = await montar(
      React.createElement(AvisosOrquestador, { dar, cadaMs: CADA }),
    );
    await esperar(5);
    // the first read only records what was there
    expect(dar).not.toHaveBeenCalled();
    await esperar(CADA * 6);
    expect(dar).toHaveBeenCalledTimes(1);
    expect(dar.mock.calls[0][0].clave).toBe("orden:o1");
    expect(el.querySelectorAll("li")).toHaveLength(2);
    expect(JSON.parse(window.localStorage.getItem(CLAVE_AVISADAS)!)).toEqual([
      "mensaje:m1",
      "orden:o1",
    ]);

    // reload: the order is gone for a moment and comes back; not alerted again
    for (const r of raices.splice(0))
      await React.act(async () => {
        r.unmount();
      });
    vi.restoreAllMocks();
    const dar2 = vi.fn();
    servidor([[aviso()], [aviso(), ORDEN]]);
    await montar(
      React.createElement(AvisosOrquestador, { dar: dar2, cadaMs: CADA }),
    );
    await esperar(CADA * 6);
    expect(dar2).not.toHaveBeenCalled();
  });

  it("clic en la notificación: lo mismo que Responder", async () => {
    const dar = vi.fn();
    const irA = vi.fn();
    servidor([[], [aviso()]]);
    await montar(
      React.createElement(AvisosOrquestador, { dar, irA, cadaMs: CADA }),
    );
    await esperar(CADA * 4);
    expect(dar).toHaveBeenCalledTimes(1);
    const abrir = dar.mock.calls[0][1] as () => void;
    abrir();
    expect(irA).toHaveBeenCalledWith(
      "/proyectos/ver?id=p1&seccion=chat&aviso=mensaje%3Am1",
    );
  });

  it("oculta: no muestra tarjetas pero sigue avisando", async () => {
    const dar = vi.fn();
    servidor([[], [aviso()]]);
    const el = await montar(
      React.createElement(AvisosOrquestador, {
        dar,
        cadaMs: CADA,
        oculta: true,
      }),
    );
    await esperar(CADA * 4);
    expect(el.innerHTML).toBe("");
    expect(dar).toHaveBeenCalledTimes(1);
  });
});
