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
  cambiosRegla,
  cuerpoComando,
  cuerpoRegla,
  nombreTipo,
  opcionesTipo,
  ponerEnLista,
  quitarDeLista,
  TIPOS_REGLA,
  type Comando,
  type Regla,
  type ReglasDeProyecto,
} from "@/components/proyectos/logicaReglas";
import {
  textoAuto,
  textoDificultad,
  textoEstimado,
  type Orden,
  type Proyecto,
} from "@/components/proyectos/logica";

let React: typeof import("react");
let ReactDOM: typeof import("react-dom/client");
let Ajustes: typeof import("@/components/proyectos/Ajustes").default;
let ReglasProyectoVista: typeof import("@/components/proyectos/Reglas").ReglasProyectoVista;
let EquipoVista: typeof import("@/components/proyectos/VerProyecto").EquipoVista;
let TarjetaOrden: typeof import("@/components/proyectos/TarjetaOrden").TarjetaOrden;
let ListaVista: typeof import("@/components/proyectos/ListaProyectos").ListaVista;

const raices: import("react-dom/client").Root[] = [];

beforeAll(async () => {
  GlobalRegistrator.register({ url: "http://localhost:3100/ajustes" });
  (
    globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
  React = await import("react");
  ReactDOM = await import("react-dom/client");
  Ajustes = (await import("@/components/proyectos/Ajustes")).default;
  ReglasProyectoVista = (await import("@/components/proyectos/Reglas"))
    .ReglasProyectoVista;
  EquipoVista = (await import("@/components/proyectos/VerProyecto"))
    .EquipoVista;
  TarjetaOrden = (await import("@/components/proyectos/TarjetaOrden"))
    .TarjetaOrden;
  ListaVista = (await import("@/components/proyectos/ListaProyectos"))
    .ListaVista;
});

afterAll(async () => {
  await GlobalRegistrator.unregister();
});

afterEach(async () => {
  await React.act(async () => {
    for (const r of raices.splice(0)) r.unmount();
  });
  vi.restoreAllMocks();
  document.body.innerHTML = "";
});

async function montar(elemento: React.ReactElement): Promise<HTMLElement> {
  const el = document.createElement("div");
  document.body.appendChild(el);
  const raiz = ReactDOM.createRoot(el);
  raices.push(raiz);
  await React.act(async () => {
    raiz.render(elemento);
  });
  await esperar();
  return el;
}

/** Lets the pending fetches and their answers reach the screen. */
async function esperar() {
  for (let i = 0; i < 3; i++)
    await React.act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
}

function texto(el: Element): string {
  return (el.textContent ?? "").replace(/\u00a0/g, " ");
}

function boton(el: Element, t: string): HTMLButtonElement | undefined {
  return [...el.querySelectorAll("button")].find(
    (b) => (b.textContent ?? "").trim() === t,
  );
}

async function clic(b: HTMLElement | undefined) {
  expect(b).toBeDefined();
  await React.act(async () => b!.click());
  await esperar();
}

/** Types into a controlled input or textarea (React listens to the setter). */
async function escribir(
  campo: HTMLInputElement | HTMLTextAreaElement,
  valor: string,
) {
  const proto =
    campo instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
  await React.act(async () => {
    setter?.call(campo, valor);
    campo.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

async function elegir(select: HTMLSelectElement, valor: string) {
  await React.act(async () => {
    select.value = valor;
    select.dispatchEvent(new Event("change", { bubbles: true }));
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

function regla(extra: Partial<Regla> = {}): Regla {
  return {
    id: "idioma",
    texto: "Escribe la interfaz en español latino neutro.",
    tipo: "idioma",
    activa_por_defecto: true,
    orden: 0,
    ...extra,
  };
}

function comando(extra: Partial<Comando> = {}): Comando {
  return {
    id: "c1",
    comando: "git status",
    activo_por_defecto: true,
    orden: 0,
    ...extra,
  };
}

interface Pedido {
  metodo: string;
  ruta: string;
  cuerpo: unknown;
}

/**
 * A small fake of /reglas and /comandos: answers like the server and keeps
 * every request that changes something. `rechazo` answers POST /comandos.
 */
function servidor(rechazo?: { status: number; detail: string }) {
  const pedidos: Pedido[] = [];
  let reglas: Regla[] = [
    regla(),
    regla({
      id: "autoskills",
      texto: "Usa las skills del proyecto.",
      tipo: "herramientas",
      activa_por_defecto: false,
      orden: 1,
    }),
  ];
  let comandos: Comando[] = [
    comando(),
    comando({ id: "c2", comando: "npm run build", orden: 1 }),
  ];
  const f = vi.spyOn(globalThis, "fetch").mockImplementation((url, init) => {
    const ruta = new URL(String(url)).pathname.replace("/api/v1", "");
    const metodo = (init?.method ?? "GET").toUpperCase();
    const cuerpo = init?.body ? JSON.parse(String(init.body)) : undefined;
    if (metodo !== "GET") pedidos.push({ metodo, ruta, cuerpo });
    const [, lista, id] = ruta.split("/");
    if (lista === "reglas") {
      if (metodo === "GET")
        return respuesta({ reglas, tipos: TIPOS_REGLA.map((t) => t.valor) });
      if (metodo === "POST") {
        const nueva = regla({ id: "abc123", orden: 9, ...cuerpo });
        reglas = [...reglas, nueva];
        return respuesta(nueva, 201);
      }
      if (metodo === "PATCH") {
        reglas = reglas.map((r) => (r.id === id ? { ...r, ...cuerpo } : r));
        return respuesta(reglas.find((r) => r.id === id));
      }
      if (metodo === "DELETE") {
        reglas = reglas.filter((r) => r.id !== id);
        return respuesta({ ok: true });
      }
    }
    if (lista === "comandos") {
      if (metodo === "GET") return respuesta({ comandos });
      if (metodo === "POST") {
        if (rechazo)
          return respuesta({ detail: rechazo.detail }, rechazo.status);
        const nuevo = comando({ id: "c9", orden: 9, ...cuerpo });
        comandos = [...comandos, nuevo];
        return respuesta(nuevo, 201);
      }
      if (metodo === "PATCH") {
        comandos = comandos.map((c) => (c.id === id ? { ...c, ...cuerpo } : c));
        return respuesta(comandos.find((c) => c.id === id));
      }
      if (metodo === "DELETE") {
        comandos = comandos.filter((c) => c.id !== id);
        return respuesta({ ok: true });
      }
    }
    return respuesta({ detail: "No existe." }, 404);
  });
  return { f, pedidos };
}

function seccion(el: HTMLElement, titulo: string): HTMLElement {
  const h = [...el.querySelectorAll("h2, h3")].find(
    (x) => x.textContent === titulo,
  );
  expect(h).toBeDefined();
  return h!.closest("section") as HTMLElement;
}

describe("lógica de reglas, comandos y textos de las órdenes", () => {
  it("nombres legibles de los tipos", () => {
    expect(nombreTipo("idioma")).toBe("Idioma");
    expect(nombreTipo("documentacion")).toBe("Documentación");
    expect(nombreTipo("ordenes")).toBe("Órdenes");
    expect(nombreTipo("herramientas")).toBe("Herramientas");
    expect(nombreTipo("nuevo")).toBe("nuevo");
    expect(TIPOS_REGLA).toHaveLength(9);
    expect(opcionesTipo(null)).toBe(TIPOS_REGLA);
    expect(opcionesTipo(["git", "otra"])).toEqual([
      { valor: "git", texto: "Git" },
      { valor: "otra", texto: "Otra" },
    ]);
  });

  it("cuerpos de agregar y editar", () => {
    expect(cuerpoRegla("  ", "otra")).toBeNull();
    expect(cuerpoRegla(" Usa git ", "git")).toEqual({
      texto: "Usa git",
      tipo: "git",
      activa_por_defecto: true,
    });
    expect(cuerpoRegla("x".repeat(600), "otra", false)?.texto).toHaveLength(
      500,
    );
    const r = regla();
    expect(cambiosRegla(r, r.texto, r.tipo)).toBeNull();
    expect(cambiosRegla(r, ` ${r.texto} `, r.tipo)).toBeNull();
    expect(cambiosRegla(r, "Otro texto", r.tipo)).toEqual({
      texto: "Otro texto",
    });
    expect(cambiosRegla(r, r.texto, "git")).toEqual({ tipo: "git" });
    expect(cuerpoComando("  ")).toBeNull();
    expect(cuerpoComando("  npm   run  build ")).toEqual({
      comando: "npm run build",
      activo_por_defecto: true,
    });
  });

  it("la copia local de una lista después de un cambio", () => {
    const a = comando({ id: "a", orden: 0 });
    const b = comando({ id: "b", orden: 1 });
    expect(ponerEnLista([b], a).map((x) => x.id)).toEqual(["a", "b"]);
    const b2 = { ...b, comando: "ls" };
    expect(ponerEnLista([a, b], b2)).toEqual([a, b2]);
    expect(quitarDeLista([a, b], "a")).toEqual([b]);
  });

  it("el texto del interruptor automático según el estado", () => {
    expect(textoAuto(true)).toBe(
      "Encendido: las órdenes del orquestador llegan al agente sin pasar por ti.",
    );
    expect(textoAuto(false)).toBe(
      "Apagado: cada orden del orquestador espera tu aprobación.",
    );
  });

  it("estimado y dificultad de una orden", () => {
    expect(textoEstimado("45 min")).toBe("Estimado: 45 min");
    expect(textoEstimado("1 h 30 min")).toBe("Estimado: 1 h 30 min");
    expect(textoDificultad("3")).toBe("Dificultad: 3 de 10");
    expect(textoDificultad(" 10 ")).toBe("Dificultad: 10 de 10");
    expect(textoDificultad("1")).toBe("Dificultad: 1 de 10");
    expect(textoDificultad("3/10")).toBe("Dificultad: 3 de 10");
    expect(textoDificultad("7 / 10")).toBe("Dificultad: 7 de 10");
    expect(textoDificultad("0")).toBe("Dificultad: 0");
    expect(textoDificultad("11")).toBe("Dificultad: 11");
    expect(textoDificultad("3.5")).toBe("Dificultad: 3.5");
    expect(textoDificultad("media")).toBe("Dificultad: media");
  });
});

describe("Ajustes: reglas de la casa", () => {
  it("lista las reglas con su tipo, su interruptor, la ayuda y los enlaces", async () => {
    servidor();
    const el = await montar(React.createElement(Ajustes));
    expect(el.querySelector("h1")?.textContent).toBe("Ajustes");
    const enlaces = [...el.querySelectorAll("a")].map((a) => [
      a.textContent,
      a.getAttribute("href"),
    ]);
    expect(enlaces).toContainEqual(["Volver a Proyectos", "/proyectos"]);
    expect(enlaces).toContainEqual(["Ir a la oficina", "/oficina/3d"]);

    const sec = seccion(el, "Reglas de la casa");
    expect(texto(sec)).toContain(
      "Se escriben en el CLAUDE.md de cada proyecto. Cada proyecto puede apagar las que no le sirvan.",
    );
    const filas = sec.querySelectorAll("ul > li");
    expect(filas).toHaveLength(2);
    expect(texto(filas[0])).toContain("Idioma");
    expect(texto(filas[0])).toContain(
      "Escribe la interfaz en español latino neutro.",
    );
    expect(texto(filas[1])).toContain("Herramientas");
    const sw = filas[1].querySelector<HTMLButtonElement>('[role="switch"]')!;
    expect(sw.getAttribute("aria-checked")).toBe("false");
    // the switch is named by "Activa por defecto" and the text of the rule
    const nombres = sw
      .getAttribute("aria-labelledby")!
      .split(" ")
      .map((i) => document.getElementById(i)?.textContent);
    expect(nombres).toEqual([
      "Activa por defecto",
      "Usa las skills del proyecto.",
    ]);
    expect(texto(el)).not.toMatch(/\p{Extended_Pictographic}/u);
  });

  it("el interruptor cambia activa_por_defecto con PATCH", async () => {
    const { pedidos } = servidor();
    const el = await montar(React.createElement(Ajustes));
    const fila = seccion(el, "Reglas de la casa").querySelectorAll(
      "ul > li",
    )[0];
    await clic(fila.querySelector<HTMLButtonElement>('[role="switch"]')!);
    expect(pedidos).toEqual([
      {
        metodo: "PATCH",
        ruta: "/reglas/idioma",
        cuerpo: { activa_por_defecto: false },
      },
    ]);
    const sw = seccion(el, "Reglas de la casa")
      .querySelectorAll("ul > li")[0]
      .querySelector('[role="switch"]')!;
    expect(sw.getAttribute("aria-checked")).toBe("false");
  });

  it("agrega una regla con texto, tipo y activa por defecto", async () => {
    const { pedidos } = servidor();
    const el = await montar(React.createElement(Ajustes));
    const sec = seccion(el, "Reglas de la casa");
    const agregar = boton(sec, "Agregar regla")!;
    expect(agregar.disabled).toBe(true);
    const form = agregar.closest("form")!;
    await escribir(form.querySelector("textarea")!, "  Corre las pruebas.  ");
    await elegir(form.querySelector("select")!, "pruebas");
    // "Activa por defecto" starts on; turn it off
    const sw = form.querySelector<HTMLButtonElement>('[role="switch"]')!;
    expect(sw.getAttribute("aria-checked")).toBe("true");
    await clic(sw);
    expect(sw.getAttribute("aria-checked")).toBe("false");
    await clic(agregar);
    expect(pedidos).toEqual([
      {
        metodo: "POST",
        ruta: "/reglas",
        cuerpo: {
          texto: "Corre las pruebas.",
          tipo: "pruebas",
          activa_por_defecto: false,
        },
      },
    ]);
    const filas = seccion(el, "Reglas de la casa").querySelectorAll("ul > li");
    expect(filas).toHaveLength(3);
    expect(texto(filas[2])).toContain("Pruebas");
    expect(texto(filas[2])).toContain("Corre las pruebas.");
    expect(form.querySelector("textarea")!.value).toBe("");
  });

  it("edita el texto y el tipo en el lugar; Cancelar no envía nada", async () => {
    const { pedidos } = servidor();
    const el = await montar(React.createElement(Ajustes));
    const fila = () =>
      seccion(el, "Reglas de la casa").querySelectorAll("ul > li")[0];
    await clic(boton(fila(), "Editar"));
    const area = fila().querySelector("textarea")!;
    expect(area.value).toBe("Escribe la interfaz en español latino neutro.");
    await escribir(area, "Otro texto");
    await clic(boton(fila(), "Cancelar"));
    expect(pedidos).toEqual([]);
    expect(texto(fila())).toContain(
      "Escribe la interfaz en español latino neutro.",
    );

    await clic(boton(fila(), "Editar"));
    await escribir(fila().querySelector("textarea")!, "Español neutro.");
    await elegir(fila().querySelector("select")!, "interfaz");
    await clic(boton(fila(), "Guardar"));
    expect(pedidos).toEqual([
      {
        metodo: "PATCH",
        ruta: "/reglas/idioma",
        cuerpo: { texto: "Español neutro.", tipo: "interfaz" },
      },
    ]);
    expect(fila().querySelector("textarea")).toBeNull();
    expect(texto(fila())).toContain("Español neutro.");
    expect(texto(fila())).toContain("Interfaz");
  });

  it("borra con confirmación en el diálogo", async () => {
    const { pedidos } = servidor();
    const el = await montar(React.createElement(Ajustes));
    const sec = () => seccion(el, "Reglas de la casa");
    await clic(boton(sec().querySelectorAll("ul > li")[1], "Borrar"));
    let dialogo = el.querySelector<HTMLElement>('[role="alertdialog"]')!;
    expect(texto(dialogo)).toContain("¿Borrar la regla?");
    expect(document.activeElement?.textContent).toBe("Cancelar");
    await clic(boton(dialogo, "Cancelar"));
    expect(el.querySelector('[role="alertdialog"]')).toBeNull();
    expect(pedidos).toEqual([]);

    await clic(boton(sec().querySelectorAll("ul > li")[1], "Borrar"));
    dialogo = el.querySelector<HTMLElement>('[role="alertdialog"]')!;
    await clic(boton(dialogo, "Borrar"));
    expect(pedidos).toEqual([
      { metodo: "DELETE", ruta: "/reglas/autoskills", cuerpo: undefined },
    ]);
    expect(sec().querySelectorAll("ul > li")).toHaveLength(1);
    expect(texto(sec())).not.toContain("Usa las skills del proyecto.");
  });
});

describe("Ajustes: comandos seguros", () => {
  it("lista, agrega y borra con confirmación", async () => {
    const { pedidos } = servidor();
    const el = await montar(React.createElement(Ajustes));
    const sec = () => seccion(el, "Comandos seguros");
    expect(texto(sec())).toContain(
      "Los agentes de código los corren sin pedirte permiso. Todo lo demás sigue pidiéndolo.",
    );
    expect(sec().querySelectorAll("ul > li")).toHaveLength(2);
    expect(texto(sec())).toContain("git status");

    const input = sec().querySelector<HTMLInputElement>('input[type="text"]')!;
    await escribir(input, " npm test ");
    await clic(boton(sec(), "Agregar comando"));
    expect(pedidos[0]).toEqual({
      metodo: "POST",
      ruta: "/comandos",
      cuerpo: { comando: "npm test", activo_por_defecto: true },
    });
    expect(sec().querySelectorAll("ul > li")).toHaveLength(3);
    expect(input.value).toBe("");

    await clic(
      sec()
        .querySelectorAll("ul > li")[0]
        .querySelector<HTMLButtonElement>('[role="switch"]')!,
    );
    expect(pedidos[1]).toEqual({
      metodo: "PATCH",
      ruta: "/comandos/c1",
      cuerpo: { activo_por_defecto: false },
    });

    await clic(boton(sec().querySelectorAll("ul > li")[1], "Borrar"));
    const dialogo = el.querySelector<HTMLElement>('[role="alertdialog"]')!;
    expect(texto(dialogo)).toContain("npm run build");
    await clic(boton(dialogo, "Borrar"));
    expect(pedidos[2]).toEqual({
      metodo: "DELETE",
      ruta: "/comandos/c2",
      cuerpo: undefined,
    });
    expect(texto(sec())).not.toContain("npm run build");
  });

  it("muestra el detail del 422", async () => {
    servidor({ status: 422, detail: "El comando no puede tener ;." });
    const el = await montar(React.createElement(Ajustes));
    const sec = seccion(el, "Comandos seguros");
    const input = sec.querySelector<HTMLInputElement>('input[type="text"]')!;
    await escribir(input, "ls; rm -rf x");
    await clic(boton(sec, "Agregar comando"));
    expect(sec.querySelector('[role="alert"]')?.textContent).toBe(
      "El comando no puede tener ;.",
    );
    expect(input.getAttribute("aria-invalid")).toBe("true");
    expect(input.value).toBe("ls; rm -rf x");
    expect(sec.querySelectorAll("ul > li")).toHaveLength(2);
  });

  it("muestra el detail del 409", async () => {
    servidor({ status: 409, detail: "Ese comando ya está en la lista." });
    const el = await montar(React.createElement(Ajustes));
    const sec = seccion(el, "Comandos seguros");
    await escribir(
      sec.querySelector<HTMLInputElement>('input[type="text"]')!,
      "git status",
    );
    await clic(boton(sec, "Agregar comando"));
    expect(sec.querySelector('[role="alert"]')?.textContent).toBe(
      "Ese comando ya está en la lista.",
    );
  });
});

// -- project ----------------------------------------------------------------------

function deProyecto(): ReglasDeProyecto {
  return {
    reglas: [
      {
        ...regla(),
        activa: true,
        ajustada: false,
      },
      {
        ...regla({
          id: "autoskills",
          texto: "Usa las skills del proyecto.",
          tipo: "herramientas",
          orden: 1,
        }),
        activa: false,
        ajustada: true,
      },
    ],
    comandos: [
      { ...comando(), activo: true, ajustado: false },
      {
        ...comando({ id: "c2", comando: "npm run build", orden: 1 }),
        activo: false,
        ajustado: true,
      },
    ],
  };
}

function proyecto(extra: Partial<Proyecto> = {}): Proyecto {
  return {
    id: "p1",
    nombre: "tienda-web",
    maquina: "alienware",
    cuenta: "personal",
    ruta: "E:\\proyectos\\tienda-web",
    plantilla: "web",
    estado: "activo",
    auto_aprobar: false,
    error: null,
    creado: "2026-10-11T15:00:00Z",
    actualizado: "2026-10-11T15:00:00Z",
    haciendo: null,
    ordenes_por_aprobar: 0,
    equipo: [],
    ...extra,
  };
}

function orden(extra: Partial<Orden> = {}): Orden {
  return {
    id: "o1",
    proyecto_id: "p1",
    proyecto: "tienda-web",
    numero: 1,
    agente: "agente-1",
    texto_propuesto: "Crea la cabecera.",
    texto_final: null,
    texto: "Crea la cabecera.",
    editada: false,
    estimado: "45 min",
    dificultad: "3",
    estado: "por_aprobar",
    motivo: null,
    decidido_por: null,
    decidido: null,
    resumen: null,
    creado: "2026-10-11T15:00:00Z",
    actualizado: "2026-10-11T15:00:00Z",
    ...extra,
  };
}

describe("reglas y comandos de un proyecto (Equipo)", () => {
  it("cada regla y comando con su interruptor y la marca de ajustada", async () => {
    const cambios: [string, string, boolean][] = [];
    const el = await montar(
      React.createElement(ReglasProyectoVista, {
        datos: deProyecto(),
        cambiarRegla: async (id: string, v: boolean) => {
          cambios.push(["regla", id, v]);
        },
        cambiarComando: async (id: string, v: boolean) => {
          cambios.push(["comando", id, v]);
        },
      }),
    );
    const reglas = seccion(el, "Reglas de la casa");
    const filas = reglas.querySelectorAll("li");
    expect(filas).toHaveLength(2);
    expect(texto(filas[0])).toContain("Idioma");
    expect(texto(filas[0])).not.toContain("Ajustada en este proyecto");
    expect(texto(filas[1])).toContain("Ajustada en este proyecto");
    const sw0 = filas[0].querySelector<HTMLButtonElement>('[role="switch"]')!;
    const sw1 = filas[1].querySelector<HTMLButtonElement>('[role="switch"]')!;
    expect(sw0.getAttribute("aria-checked")).toBe("true");
    expect(sw1.getAttribute("aria-checked")).toBe("false");
    expect(
      document.getElementById(sw1.getAttribute("aria-describedby")!)
        ?.textContent,
    ).toBe("Ajustada en este proyecto");
    await clic(sw0);
    await clic(sw1);

    const coms = seccion(el, "Comandos seguros");
    const fc = coms.querySelectorAll("li");
    expect(texto(fc[0])).toContain("git status");
    expect(texto(fc[1])).toContain("Ajustado en este proyecto");
    await clic(fc[1].querySelector<HTMLButtonElement>('[role="switch"]')!);
    expect(cambios).toEqual([
      ["regla", "idioma", false],
      ["regla", "autoskills", true],
      ["comando", "c2", true],
    ]);
    const enlace = [...el.querySelectorAll("a")].find(
      (a) => a.textContent === "Editar la lista global en Ajustes",
    );
    expect(enlace?.getAttribute("href")).toBe("/ajustes");
  });

  it("muestra el error si el servidor rechaza el cambio", async () => {
    const el = await montar(
      React.createElement(ReglasProyectoVista, {
        datos: deProyecto(),
        cambiarRegla: async () => {
          throw new Error("El proyecto no existe.");
        },
        cambiarComando: async () => {},
      }),
    );
    const sw = el.querySelector<HTMLButtonElement>('[role="switch"]')!;
    await clic(sw);
    expect(el.querySelector('[role="alert"]')?.textContent).toBe(
      "El proyecto no existe.",
    );
    expect(sw.getAttribute("aria-checked")).toBe("true");
  });

  it("Equipo muestra las reglas y el texto del interruptor encendido", async () => {
    const el = await montar(
      React.createElement(EquipoVista, {
        proyecto: proyecto({ auto_aprobar: true }),
        accion: async () => {},
        reglas: deProyecto(),
        ordenes: [orden({ dificultad: "8/10", estimado: "1 h 30 min" })],
      }),
    );
    const sw = el.querySelector<HTMLButtonElement>('[role="switch"]')!;
    expect(sw.getAttribute("aria-checked")).toBe("true");
    expect(texto(el)).toContain(
      "Encendido: las órdenes del orquestador llegan al agente sin pasar por ti.",
    );
    expect(texto(el)).not.toContain("Apagado:");
    expect(texto(el)).toContain("Reglas de la casa");
    expect(texto(el)).toContain("Comandos seguros");
    expect(texto(el)).toContain("Ajustada en este proyecto");
    // the history shows estimate and difficulty
    expect(texto(el)).toContain("Estimado: 1 h 30 min · Dificultad: 8 de 10");
  });

  it("Equipo sin las reglas todavía: Cargando", async () => {
    const el = await montar(
      React.createElement(EquipoVista, {
        proyecto: proyecto(),
        accion: async () => {},
      }),
    );
    expect(texto(seccion(el, "Reglas de la casa"))).toContain("Cargando…");
  });
});

describe("tarjeta de orden y lista de proyectos", () => {
  it("la tarjeta dice Estimado y Dificultad 3 de 10", async () => {
    const el = await montar(
      React.createElement(TarjetaOrden, {
        orden: orden(),
        ahora: Date.parse("2026-10-11T16:00:00Z"),
        cambio: () => {},
      }),
    );
    expect(texto(el)).toContain("Estimado: 45 min");
    expect(texto(el)).toContain("Dificultad: 3 de 10");
  });

  it("Proyectos tiene el enlace a Ajustes", async () => {
    const el = await montar(React.createElement(ListaVista, { proyectos: [] }));
    const a = [...el.querySelectorAll("a")].find(
      (x) => x.textContent === "Ajustes",
    );
    expect(a?.getAttribute("href")).toBe("/ajustes");
  });
});
