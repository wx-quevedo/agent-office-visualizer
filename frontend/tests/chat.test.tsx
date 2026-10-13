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
import {
  cuerpoAprobar,
  cuerpoRechazar,
  estadoOrden,
  fueEditada,
  historialOrdenes,
  mezclarChat,
  notaChat,
  ordenLarga,
  quienDecidio,
  textoCorto,
  tituloOrden,
  unirMensajes,
  unirOrdenes,
  type Mensaje,
  type Orden,
} from "@/components/proyectos/logica";

let React: typeof import("react");
let ReactDOM: typeof import("react-dom/client");
let ChatVista: typeof import("@/components/proyectos/Chat").ChatVista;
let TarjetaOrden: typeof import("@/components/proyectos/TarjetaOrden").TarjetaOrden;
let DecisionesVista: typeof import("@/components/proyectos/Decisiones").DecisionesVista;
let ListaVista: typeof import("@/components/proyectos/ListaProyectos").ListaVista;

beforeAll(async () => {
  GlobalRegistrator.register({ url: "http://localhost:3100/proyectos" });
  (
    globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
  React = await import("react");
  ReactDOM = await import("react-dom/client");
  ChatVista = (await import("@/components/proyectos/Chat")).ChatVista;
  TarjetaOrden = (await import("@/components/proyectos/TarjetaOrden"))
    .TarjetaOrden;
  DecisionesVista = (await import("@/components/proyectos/Decisiones"))
    .DecisionesVista;
  ListaVista = (await import("@/components/proyectos/ListaProyectos"))
    .ListaVista;
});

afterAll(async () => {
  await GlobalRegistrator.unregister();
});

afterEach(() => {
  vi.restoreAllMocks();
  document.body.innerHTML = "";
});

const AHORA = Date.parse("2026-10-11T16:00:00Z");

function orden(extra: Partial<Orden> = {}): Orden {
  return {
    id: "o1",
    proyecto_id: "p1",
    proyecto: "tienda-web",
    numero: 1,
    agente: "agente",
    texto_propuesto: "Crea la página de inicio con el catálogo.",
    texto_final: null,
    texto: "Crea la página de inicio con el catálogo.",
    editada: false,
    estimado: "10 min",
    dificultad: "media",
    estado: "por_aprobar",
    motivo: null,
    decidido_por: null,
    decidido: null,
    resumen: null,
    creado: "2026-10-11T15:10:00Z",
    actualizado: "2026-10-11T15:10:00Z",
    ...extra,
  };
}

function mensaje(extra: Partial<Mensaje> = {}): Mensaje {
  return {
    id: "m1",
    autor: "washington",
    texto: "Hola",
    creado: "2026-10-11T15:00:00Z",
    ...extra,
  };
}

async function montar(elemento: React.ReactElement): Promise<HTMLElement> {
  const el = document.createElement("div");
  document.body.appendChild(el);
  const raiz = ReactDOM.createRoot(el);
  await React.act(async () => {
    raiz.render(elemento);
  });
  return el;
}

function texto(el: Element): string {
  return (el.textContent ?? "").replace(/ /g, " ");
}

function boton(el: Element, t: string): HTMLButtonElement | undefined {
  return [...el.querySelectorAll("button")].find(
    (b) => (b.textContent ?? "").trim() === t,
  );
}

async function escribir(area: HTMLTextAreaElement, valor: string) {
  const setter = Object.getOwnPropertyDescriptor(
    HTMLTextAreaElement.prototype,
    "value",
  )?.set;
  await React.act(async () => {
    setter?.call(area, valor);
    area.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

function respuesta(body: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

function cuerpoDe(f: { mock: { calls: unknown[][] } }, parte: string): unknown {
  const llamada = f.mock.calls.find((c) => String(c[0]).includes(parte));
  if (!llamada) return undefined;
  const init = llamada[1] as RequestInit | undefined;
  return JSON.parse(String(init?.body));
}

describe("lógica del chat y las órdenes", () => {
  it("mezcla mensajes y órdenes en orden cronológico", () => {
    const items = mezclarChat(
      [
        mensaje({ id: "a", creado: "2026-10-11T15:00:00Z" }),
        mensaje({
          id: "b",
          autor: "orquestador",
          creado: "2026-10-11T15:10:00Z",
        }),
        mensaje({ id: "c", creado: "2026-10-11T15:20:00Z" }),
      ],
      [
        orden({ id: "x", creado: "2026-10-11T15:10:00Z" }),
        orden({ id: "y", numero: 2, creado: "2026-10-11T15:05:00Z" }),
      ],
    );
    expect(items.map((i) => i.id)).toEqual(["m-a", "o-y", "m-b", "o-x", "m-c"]);
    expect(mezclarChat([], [])).toEqual([]);
  });

  it("une lo leído con lo enviado sin repetir", () => {
    const leidos = [mensaje({ id: "1" })];
    const enviados = [mensaje({ id: "1" }), mensaje({ id: "2" })];
    const pendiente = mensaje({ id: "local-1" });
    expect(
      unirMensajes(leidos, enviados, [pendiente]).map((m) => m.id),
    ).toEqual(["1", "2", "local-1"]);

    const vieja = orden({ actualizado: "2026-10-11T15:10:00Z" });
    const aprobada = orden({
      estado: "aprobada",
      actualizado: "2026-10-11T15:11:00Z",
    });
    expect(unirOrdenes([vieja], { o1: aprobada })[0].estado).toBe("aprobada");
    const enCurso = orden({
      estado: "en_curso",
      actualizado: "2026-10-11T15:12:00Z",
    });
    expect(unirOrdenes([enCurso], { o1: aprobada })[0].estado).toBe("en_curso");
  });

  it("textos del estado de la orden y quién decidió", () => {
    expect(estadoOrden("por_aprobar")).toEqual({
      texto: "Por aprobar",
      tono: "morado",
    });
    expect(estadoOrden("aprobada").texto).toBe("Aprobada (en cola)");
    expect(estadoOrden("rechazada").texto).toBe("Rechazada");
    expect(estadoOrden("en_curso").texto).toBe("En curso");
    expect(estadoOrden("terminada")).toEqual({
      texto: "Terminada",
      tono: "verde",
    });
    expect(estadoOrden("fallida")).toEqual({ texto: "Fallida", tono: "rojo" });
    expect(quienDecidio("web")).toBe("Tú desde la web");
    expect(quienDecidio("app")).toBe("Tú desde la app");
    expect(quienDecidio("automatico")).toBe("Automático");
    expect(quienDecidio(null)).toBeNull();
    expect(tituloOrden({ numero: 3, agente: "agente-2" })).toBe(
      "Orden 3 para agente-2",
    );
    expect(fueEditada(orden())).toBe(false);
    expect(fueEditada(orden({ texto_final: "otro" }))).toBe(true);
  });

  it("cuerpo de aprobar con o sin edición, y de rechazar", () => {
    const o = orden();
    expect(cuerpoAprobar(o)).toEqual({ dispositivo: "web" });
    expect(cuerpoAprobar(o, `  ${o.texto_propuesto} `)).toEqual({
      dispositivo: "web",
    });
    expect(cuerpoAprobar(o, "  Hazlo en rojo ")).toEqual({
      texto: "Hazlo en rojo",
      dispositivo: "web",
    });
    expect(cuerpoAprobar(o, "   ")).toEqual({ dispositivo: "web" });
    expect(cuerpoRechazar("  ")).toBeNull();
    expect(cuerpoRechazar(" No hace falta ")).toEqual({
      motivo: "No hace falta",
      dispositivo: "web",
    });
    expect(cuerpoRechazar("x".repeat(600))?.motivo).toHaveLength(500);
  });

  it("texto largo, texto corto, historial y nota del chat", () => {
    expect(ordenLarga("una línea")).toBe(false);
    expect(ordenLarga("1\n2\n3\n4\n5\n6\n7")).toBe(true);
    expect(ordenLarga("x".repeat(500))).toBe(true);
    expect(textoCorto("a\n  b")).toBe("a b");
    expect(textoCorto("x".repeat(200), 10)).toBe(`${"x".repeat(9)}…`);
    const h = historialOrdenes([
      orden({ id: "a", numero: 1, creado: "2026-10-11T15:00:00Z" }),
      orden({ id: "b", numero: 2, creado: "2026-10-11T15:30:00Z" }),
    ]);
    expect(h.map((o) => o.numero)).toEqual([2, 1]);
    expect(notaChat("activo")).toBeNull();
    expect(notaChat("pausado")).toBe(
      "El equipo está pausado: el orquestador leerá tus mensajes cuando lo reanudes.",
    );
    expect(notaChat("detenido")).toContain("El equipo está detenido");
  });
});

describe("tarjeta de orden", () => {
  it("muestra el título corto de la orden debajo de la cabecera", async () => {
    const con = await montar(
      React.createElement(TarjetaOrden, {
        orden: orden({ titulo: "Fase 1 · Prompt 1: base del sitio" }),
        ahora: AHORA,
        cambio: () => {},
      }),
    );
    const cabecera = con.querySelector("header");
    const titulo = cabecera?.nextElementSibling;
    expect(titulo?.textContent).toBe("Fase 1 · Prompt 1: base del sitio");
    // Una orden de antes del Prompt 42 (sin título) se ve como siempre.
    const sin = await montar(
      React.createElement(TarjetaOrden, {
        orden: orden({ titulo: undefined }),
        ahora: AHORA,
        cambio: () => {},
      }),
    );
    expect(texto(sin)).not.toContain("Fase 1");
    expect(sin.querySelector("h3")?.textContent).toBe("Orden 1 para agente");
  });

  it("por aprobar: datos, estado y los tres botones", async () => {
    const el = await montar(
      React.createElement(TarjetaOrden, {
        orden: orden(),
        ahora: AHORA,
        cambio: () => {},
      }),
    );
    const t = texto(el);
    expect(el.querySelector("h3")?.textContent).toBe("Orden 1 para agente");
    expect(t).toContain("Estimado: 10 min");
    expect(t).toContain("Dificultad: media");
    expect(t).toContain("Por aprobar");
    expect(boton(el, "Aprobar")).toBeDefined();
    expect(boton(el, "Editar")).toBeDefined();
    expect(boton(el, "Rechazar con motivo")).toBeDefined();
    expect(boton(el, "Ver la orden completa")).toBeUndefined();
    expect(t).not.toMatch(/\p{Extended_Pictographic}/u);
  });

  it("Aprobar envía dispositivo web y muestra la orden nueva", async () => {
    const cambios: Orden[] = [];
    const f = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() =>
        respuesta(orden({ estado: "aprobada", decidido_por: "web" })),
      );
    const el = await montar(
      React.createElement(TarjetaOrden, {
        orden: orden(),
        ahora: AHORA,
        cambio: (o: Orden) => cambios.push(o),
      }),
    );
    await React.act(async () => boton(el, "Aprobar")!.click());
    expect(String(f.mock.calls[0][0])).toContain("/api/v1/ordenes/o1/aprobar");
    expect(cuerpoDe(f, "/aprobar")).toEqual({ dispositivo: "web" });
    expect(cambios[0].estado).toBe("aprobada");
  });

  it("Editar abre el texto y envía el cambiado", async () => {
    const f = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() => respuesta(orden({ estado: "aprobada" })));
    const el = await montar(
      React.createElement(TarjetaOrden, {
        orden: orden(),
        ahora: AHORA,
        cambio: () => {},
      }),
    );
    await React.act(async () => boton(el, "Editar")!.click());
    const area = el.querySelector("textarea")!;
    expect(area.value).toBe("Crea la página de inicio con el catálogo.");
    expect(document.activeElement).toBe(area);
    expect(boton(el, "Cancelar")).toBeDefined();
    await escribir(area, "Crea solo la cabecera.");
    await React.act(async () => boton(el, "Aprobar con cambios")!.click());
    expect(cuerpoDe(f, "/aprobar")).toEqual({
      texto: "Crea solo la cabecera.",
      dispositivo: "web",
    });
  });

  it("Rechazar exige motivo y lo envía", async () => {
    const f = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() => respuesta(orden({ estado: "rechazada" })));
    const el = await montar(
      React.createElement(TarjetaOrden, {
        orden: orden(),
        ahora: AHORA,
        cambio: () => {},
      }),
    );
    await React.act(async () => boton(el, "Rechazar con motivo")!.click());
    const area = el.querySelector("textarea")!;
    expect(area.getAttribute("aria-required")).toBe("true");
    await React.act(async () => boton(el, "Rechazar")!.click());
    expect(f).not.toHaveBeenCalled();
    expect(texto(el)).toContain("Escribe el motivo del rechazo.");
    expect(area.getAttribute("aria-invalid")).toBe("true");
    await escribir(area, "Primero el diseño");
    await React.act(async () => boton(el, "Rechazar")!.click());
    expect(String(f.mock.calls[0][0])).toContain("/ordenes/o1/rechazar");
    expect(cuerpoDe(f, "/rechazar")).toEqual({
      motivo: "Primero el diseño",
      dispositivo: "web",
    });
  });

  it("muestra el detail del servidor", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      respuesta({ detail: "La orden ya no está por aprobar." }, 409),
    );
    const el = await montar(
      React.createElement(TarjetaOrden, {
        orden: orden(),
        ahora: AHORA,
        cambio: () => {},
      }),
    );
    await React.act(async () => boton(el, "Aprobar")!.click());
    expect(el.querySelector('[role="alert"]')?.textContent).toBe(
      "La orden ya no está por aprobar.",
    );
  });

  it("decidida: quién, motivo, Editada y resultado; sin botones", async () => {
    let el = await montar(
      React.createElement(TarjetaOrden, {
        orden: orden({
          estado: "rechazada",
          decidido_por: "web",
          decidido: "2026-10-11T15:20:00Z",
          motivo: "Primero el diseño",
        }),
        ahora: AHORA,
        cambio: () => {},
      }),
    );
    let t = texto(el);
    expect(t).toContain("Rechazada");
    expect(t).toContain("Decidió: Tú desde la web · hoy");
    expect(t).toContain("Motivo: Primero el diseño");
    expect(boton(el, "Aprobar")).toBeUndefined();
    document.body.innerHTML = "";

    el = await montar(
      React.createElement(TarjetaOrden, {
        orden: orden({
          estado: "terminada",
          decidido_por: "automatico",
          texto_final: "Crea solo la cabecera.",
          texto: "Crea solo la cabecera.",
          editada: true,
          resumen: "Cabecera lista con el logo.",
        }),
        ahora: AHORA,
        cambio: () => {},
      }),
    );
    t = texto(el);
    expect(t).toContain("Terminada");
    expect(t).toContain("Decidió: Automático");
    expect(t).toContain("Editada");
    expect(t).toContain("Resultado: Cabecera lista con el logo.");
  });

  it("orden larga: recortada con Ver la orden completa", async () => {
    const largo = Array.from({ length: 10 }, (_, i) => `Paso ${i + 1}`).join(
      "\n",
    );
    const el = await montar(
      React.createElement(TarjetaOrden, {
        orden: orden({ texto: largo, texto_propuesto: largo }),
        ahora: AHORA,
        cambio: () => {},
      }),
    );
    const b = boton(el, "Ver la orden completa")!;
    expect(b.getAttribute("aria-expanded")).toBe("false");
    await React.act(async () => b.click());
    expect(b.getAttribute("aria-expanded")).toBe("true");
    expect(b.textContent).toBe("Ver menos");
  });
});

describe("chat con el orquestador", () => {
  const chat = {
    mensajes: [
      mensaje({ id: "1", texto: "Arma la tienda" }),
      mensaje({
        id: "2",
        autor: "orquestador" as const,
        texto: "Propongo una orden",
        creado: "2026-10-11T15:05:00Z",
      }),
    ],
    ordenes: [orden({ creado: "2026-10-11T15:06:00Z" })],
  };

  it("burbujas a cada lado y la tarjeta de la orden en su lugar", async () => {
    const el = await montar(
      React.createElement(ChatVista, {
        proyecto: { id: "p1", estado: "activo" },
        chat,
        ahora: AHORA,
      }),
    );
    const log = el.querySelector('[role="log"]')!;
    const items = [...log.children];
    expect(items).toHaveLength(3);
    expect(texto(items[0])).toContain("Tú");
    expect(texto(items[0])).toContain("Arma la tienda");
    expect(texto(items[1])).toContain("Orquestador");
    expect(texto(items[2])).toContain("Orden 1 para agente");
    expect(items[0].className).not.toBe(items[1].className);
    expect(texto(el)).not.toContain("está pausado");
  });

  it("pausado o detenido: avisa que leerá después", async () => {
    const el = await montar(
      React.createElement(ChatVista, {
        proyecto: { id: "p1", estado: "detenido" },
        chat,
        ahora: AHORA,
      }),
    );
    expect(texto(el)).toContain(
      "El equipo está detenido: el orquestador leerá tus mensajes cuando lo reanudes.",
    );
  });

  it("envía con Enter, muestra el mensaje al instante y deshabilita vacío", async () => {
    let resolver: (r: Response) => void = () => {};
    const f = vi.spyOn(globalThis, "fetch").mockImplementation(
      () =>
        new Promise<Response>((r) => {
          resolver = r;
        }),
    );
    const el = await montar(
      React.createElement(ChatVista, {
        proyecto: { id: "p1", estado: "activo" },
        chat,
        ahora: AHORA,
      }),
    );
    const area = el.querySelector<HTMLTextAreaElement>("#chat-mensaje")!;
    expect(boton(el, "Enviar")!.disabled).toBe(true);
    await escribir(area, "Agrega el carrito");
    expect(boton(el, "Enviar")!.disabled).toBe(false);

    // Shift+Enter does not send
    await React.act(async () => {
      area.dispatchEvent(
        new KeyboardEvent("keydown", {
          key: "Enter",
          shiftKey: true,
          bubbles: true,
        }),
      );
    });
    expect(f).not.toHaveBeenCalled();

    await React.act(async () => {
      area.dispatchEvent(
        new KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
      );
    });
    expect(String(f.mock.calls[0][0])).toContain(
      "/api/v1/proyectos-creados/p1/chat",
    );
    expect(cuerpoDe(f, "/chat")).toEqual({ texto: "Agrega el carrito" });
    // optimistic: already in the log, the field is empty and sending
    const log = el.querySelector('[role="log"]')!;
    expect(texto(log)).toContain("Agrega el carrito");
    expect(texto(log)).toContain("Enviando…");
    expect(area.value).toBe("");
    expect(boton(el, "Enviando…")!.disabled).toBe(true);

    await React.act(async () => {
      resolver(
        new Response(
          JSON.stringify(
            mensaje({
              id: "9",
              texto: "Agrega el carrito",
              creado: "2026-10-11T15:30:00Z",
            }),
          ),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      );
    });
    expect(texto(log)).not.toContain("Enviando…");
    expect(texto(log).match(/Agrega el carrito/g)).toHaveLength(1);
  });

  it("si falla, devuelve el texto y muestra el detail", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      respuesta({ detail: "El proyecto todavía no se creó." }, 409),
    );
    const el = await montar(
      React.createElement(ChatVista, {
        proyecto: { id: "p1", estado: "creando" },
        chat: { mensajes: [], ordenes: [] },
        ahora: AHORA,
      }),
    );
    const area = el.querySelector<HTMLTextAreaElement>("#chat-mensaje")!;
    await escribir(area, "Hola");
    await React.act(async () => boton(el, "Enviar")!.click());
    expect(el.querySelector('[role="alert"]')?.textContent).toBe(
      "El proyecto todavía no se creó.",
    );
    expect(area.value).toBe("Hola");
    expect(el.querySelector('[role="log"]')).toBeNull();
  });
});

describe("bloque de Decisiones", () => {
  it("mientras se lee no muestra nada", async () => {
    const el = await montar(
      React.createElement(DecisionesVista, { ordenes: null, ahora: AHORA }),
    );
    expect(el.querySelector("section")).toBeNull();
    expect(texto(el)).toBe("");
  });

  it("sin órdenes por aprobar no se muestra", async () => {
    const el = await montar(
      React.createElement(ListaVista, {
        proyectos: [],
        ordenes: [orden({ estado: "aprobada" })],
        ahora: AHORA,
      }),
    );
    expect(texto(el)).not.toContain("Decisiones");
  });

  it("muestra cada orden con Aprobar, Rechazar y el chat; desaparece al decidir", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockImplementation((url) =>
      String(url).includes("/aprobar")
        ? respuesta(
            orden({
              estado: "aprobada",
              decidido_por: "web",
              actualizado: "2026-10-11T15:59:00Z",
            }),
          )
        : respuesta({}, 404),
    );
    const el = await montar(
      React.createElement(ListaVista, {
        proyectos: [],
        ordenes: [
          orden(),
          orden({
            id: "o2",
            numero: 2,
            agente: "agente-2",
            proyecto: "juego",
            proyecto_id: "p2",
          }),
        ],
        ahora: AHORA,
      }),
    );
    const seccion = el.querySelector(
      'section[aria-labelledby="decisiones-titulo"]',
    )!;
    expect(seccion).not.toBeNull();
    const t = texto(seccion);
    expect(t).toContain("Decisiones");
    expect(t).toContain("tienda-web");
    expect(t).toContain("Orden 2 para agente-2");
    expect(t).toContain("hace 50 min");
    expect(boton(seccion, "Editar")).toBeUndefined();
    const hrefs = [...seccion.querySelectorAll("a")].map((a) =>
      a.getAttribute("href"),
    );
    expect(hrefs).toContain("/proyectos/ver?id=p2&seccion=chat");

    const items = seccion.querySelectorAll("li");
    expect(items).toHaveLength(2);
    // Rechazar asks for the reason first
    await React.act(async () => boton(items[1], "Rechazar")!.click());
    expect(items[1].querySelector("textarea")).not.toBeNull();
    expect(texto(items[1])).toContain("Motivo del rechazo");

    await React.act(async () => boton(items[0], "Aprobar")!.click());
    expect(cuerpoDe(f, "/ordenes/o1/aprobar")).toEqual({ dispositivo: "web" });
    const despues = el.querySelector(
      'section[aria-labelledby="decisiones-titulo"]',
    )!;
    expect(despues.querySelectorAll(":scope > ul > li")).toHaveLength(1);
    expect(texto(despues)).not.toContain("Orden 1 para agente en");
    expect(texto(despues)).toContain("Orden 2 para agente-2");
    expect(texto(el)).toContain("Orden 1 para agente aprobada.");
  });
});

describe("aviso abierto desde Responder (Prompt 43)", () => {
  const chat = {
    mensajes: [
      mensaje({ id: "1", texto: "Arma la tienda" }),
      mensaje({
        id: "2",
        autor: "orquestador" as const,
        texto: "¿Uso Stripe o Mercado Pago?",
        creado: "2026-10-11T15:05:00Z",
      }),
      mensaje({ id: "3", texto: "Otra cosa", creado: "2026-10-11T15:20:00Z" }),
    ],
    ordenes: [orden({ creado: "2026-10-11T15:06:00Z" })],
  };

  it("mensaje: lo resalta un momento y pone el foco en el campo de texto", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    try {
      const el = await montar(
        React.createElement(ChatVista, {
          proyecto: { id: "p1", estado: "activo" },
          chat,
          ahora: AHORA,
          aviso: "mensaje:2",
        }),
      );
      const marcados = el.querySelectorAll("[data-resaltado]");
      expect(marcados).toHaveLength(1);
      expect(marcados[0].getAttribute("data-item")).toBe("m-2");
      expect(texto(marcados[0])).toContain("¿Uso Stripe o Mercado Pago?");
      expect(document.activeElement?.id).toBe("chat-mensaje");
      await React.act(async () => {
        vi.advanceTimersByTime(4000);
      });
      expect(el.querySelectorAll("[data-resaltado]")).toHaveLength(0);
    } finally {
      vi.useRealTimers();
    }
  });

  it("orden: resalta su tarjeta, con Aprobar, Editar y Rechazar", async () => {
    (document.activeElement as HTMLElement | null)?.blur?.();
    const el = await montar(
      React.createElement(ChatVista, {
        proyecto: { id: "p1", estado: "activo" },
        chat,
        ahora: AHORA,
        aviso: "orden:o1",
      }),
    );
    const marcado = el.querySelector("[data-resaltado]")!;
    expect(marcado.getAttribute("data-item")).toBe("o-o1");
    expect(boton(marcado, "Aprobar")).toBeDefined();
    expect(boton(marcado, "Editar")).toBeDefined();
    expect(boton(marcado, "Rechazar con motivo")).toBeDefined();
    expect(document.activeElement?.id).not.toBe("chat-mensaje");
  });

  it("espera a que el mensaje llegue y no resalta nada con un aviso que no está", async () => {
    const el = await montar(
      React.createElement(ChatVista, {
        proyecto: { id: "p1", estado: "activo" },
        chat: null,
        ahora: AHORA,
        aviso: "mensaje:2",
      }),
    );
    expect(el.querySelector("[data-resaltado]")).toBeNull();
    const el2 = await montar(
      React.createElement(ChatVista, {
        proyecto: { id: "p1", estado: "activo" },
        chat,
        ahora: AHORA,
        aviso: "mensaje:99",
      }),
    );
    expect(el2.querySelector("[data-resaltado]")).toBeNull();
  });
});

describe("Decisiones deja fuera los proyectos de prueba (Prompt 43)", () => {
  it("no muestra las órdenes con proyecto_prueba", async () => {
    const el = await montar(
      React.createElement(DecisionesVista, {
        ordenes: [
          orden({ id: "a", proyecto: "tienda-web" }),
          orden({
            id: "b",
            numero: 2,
            proyecto: "prueba-chat",
            proyecto_prueba: true,
          }),
        ],
        ahora: AHORA,
      }),
    );
    expect(texto(el)).toContain(
      "Una orden del orquestador espera tu aprobación.",
    );
    expect(texto(el)).toContain("tienda-web");
    expect(texto(el)).not.toContain("prueba-chat");
    const sola = await montar(
      React.createElement(DecisionesVista, {
        ordenes: [orden({ proyecto_prueba: true })],
        ahora: AHORA,
      }),
    );
    expect(sola.querySelector("section")).toBeNull();
  });
});
