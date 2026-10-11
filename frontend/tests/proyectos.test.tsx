import { GlobalRegistrator } from "@happy-dom/global-registrator";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  accionesDe,
  borradorInicial,
  cuerpoCrear,
  errorNombre,
  estadoDe,
  haciendoDe,
  nombreEsfuerzo,
  nombreModelo,
  nombreValido,
  puedeCrear,
  resumenEquipo,
  rutaNueva,
  type Borrador,
  type Maquina,
  type Miembro,
  type Proyecto,
} from "@/components/proyectos/logica";

let React: typeof import("react");
let ReactDOM: typeof import("react-dom/client");
let ListaVista: typeof import("@/components/proyectos/ListaProyectos").ListaVista;
let FormularioNuevo: typeof import("@/components/proyectos/NuevoProyecto").FormularioNuevo;
let EquipoVista: typeof import("@/components/proyectos/VerProyecto").EquipoVista;
let ProyectoVista: typeof import("@/components/proyectos/VerProyecto").ProyectoVista;
let DondeVista: typeof import("@/components/donde/DondeQuedamos").DondeVista;
let armarProyectos: typeof import("@/components/donde/logica").armarProyectos;

beforeAll(async () => {
  GlobalRegistrator.register({ url: "http://localhost:3100/proyectos" });
  (
    globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
  React = await import("react");
  ReactDOM = await import("react-dom/client");
  ListaVista = (await import("@/components/proyectos/ListaProyectos"))
    .ListaVista;
  FormularioNuevo = (await import("@/components/proyectos/NuevoProyecto"))
    .FormularioNuevo;
  const ver = await import("@/components/proyectos/VerProyecto");
  EquipoVista = ver.EquipoVista;
  ProyectoVista = ver.ProyectoVista;
  DondeVista = (await import("@/components/donde/DondeQuedamos")).DondeVista;
  armarProyectos = (await import("@/components/donde/logica")).armarProyectos;
});

afterAll(async () => {
  await GlobalRegistrator.unregister();
});

afterEach(() => {
  document.body.innerHTML = "";
});

function miembro(extra: Partial<Miembro> = {}): Miembro {
  return {
    id: "m1",
    rol: "orquestador",
    nombre: "Orquestador",
    modelo: "opus",
    esfuerzo: "high",
    session_id: "ses-orq",
    estado: "activo",
    orden: 0,
    actualizado: "2026-10-11T15:00:00Z",
    oficina: null,
    ...extra,
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
    equipo: [
      miembro({
        oficina: {
          numero: 4,
          nombre: "Trabajando",
          desde: "2026-10-11T15:00:00Z",
          espera: null,
        },
      }),
      miembro({
        id: "m2",
        rol: "agente",
        nombre: "Agente 1",
        modelo: "sonnet",
        esfuerzo: "medium",
        session_id: "ses-a1",
        orden: 1,
        oficina: {
          numero: 13,
          nombre: "Permiso",
          desde: null,
          espera: "Esperando tu permiso",
        },
      }),
    ],
    ...extra,
  };
}

const MAQUINAS: Maquina[] = [
  {
    id: "alienware",
    nombre: "Alienware",
    sistema: "windows",
    version_monitor: "0.3.0",
    ultima_conexion: "2026-10-11T15:59:00Z",
    encendida: true,
    ruta_base: "E:\\proyectos",
    disponible: true,
    motivo: null,
  },
  {
    id: "mac",
    nombre: "MacBook",
    sistema: "darwin",
    version_monitor: "0.3.0",
    ultima_conexion: "2026-10-10T10:00:00Z",
    encendida: false,
    ruta_base: "/Users/w/proyectos",
    disponible: false,
    motivo: "Apagada desde ayer",
  },
];

async function montar(elemento: React.ReactElement): Promise<HTMLElement> {
  const el = document.createElement("div");
  document.body.appendChild(el);
  const raiz = ReactDOM.createRoot(el);
  await React.act(async () => {
    raiz.render(elemento);
  });
  return el;
}

function texto(el: HTMLElement): string {
  return (el.textContent ?? "").replace(/\u00a0/g, " ");
}

/** Types into a controlled input (React listens to the native setter). */
async function escribir(input: HTMLInputElement, valor: string) {
  const setter = Object.getOwnPropertyDescriptor(
    HTMLInputElement.prototype,
    "value",
  )?.set;
  await React.act(async () => {
    setter?.call(input, valor);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

function botonCon(el: HTMLElement, t: string): HTMLButtonElement | undefined {
  return [...el.querySelectorAll("button")].find((b) =>
    (b.textContent ?? "").includes(t),
  );
}

describe("lógica de proyectos", () => {
  it("valida el nombre como el servidor", () => {
    for (const ok of ["a", "mi-proyecto", "app2", "a".repeat(50), "con-tienda"])
      expect(nombreValido(ok)).toBe(true);
    expect(errorNombre("")).toMatch(/Escribe/);
    expect(errorNombre("Mi")).toMatch(/minúsculas/);
    expect(errorNombre("año")).toMatch(/sin tildes/);
    expect(errorNombre("mi proyecto")).not.toBeNull();
    expect(errorNombre("-mal")).toMatch(/guion/);
    expect(errorNombre("mal-")).toMatch(/guion/);
    expect(errorNombre("a".repeat(51))).toMatch(/50/);
    for (const r of ["con", "prn", "aux", "nul", "com1", "lpt9"])
      expect(errorNombre(r)).toMatch(/reservado/);
  });

  it("la ruta que se va a crear usa el separador de la máquina", () => {
    expect(rutaNueva("E:\\proyectos", "web")).toBe("E:\\proyectos\\web");
    expect(rutaNueva("E:\\proyectos\\", "web")).toBe("E:\\proyectos\\web");
    expect(rutaNueva("E:", "web")).toBe("E:\\web");
    expect(rutaNueva("\\\\nas\\c", "web")).toBe("\\\\nas\\c\\web");
    expect(rutaNueva("/Users/w/proyectos/", "web")).toBe(
      "/Users/w/proyectos/web",
    );
    expect(rutaNueva(null, "web")).toBeNull();
  });

  it("nombres legibles de modelo y esfuerzo", () => {
    expect(nombreModelo("opus")).toBe("Opus 5.5");
    expect(nombreModelo("sonnet")).toBe("Sonnet 5.5");
    expect(nombreModelo("haiku")).toBe("Haiku 5.5");
    expect(nombreModelo("fable")).toBe("Fable 5.1");
    expect(nombreModelo("otro")).toBe("otro");
    expect(nombreEsfuerzo("low")).toBe("Bajo");
    expect(nombreEsfuerzo("medium")).toBe("Medio");
    expect(nombreEsfuerzo("high")).toBe("Alto");
    expect(nombreEsfuerzo("xhigh")).toBe("Muy alto");
    expect(nombreEsfuerzo("max")).toBe("Máximo");
  });

  it("texto y color del estado, con el morado de las órdenes", () => {
    const e = (estado: Proyecto["estado"], n = 0) =>
      estadoDe({ estado, ordenes_por_aprobar: n });
    expect(e("activo")).toEqual({ texto: "Activo", tono: "verde" });
    expect(e("creando").tono).toBe("azul");
    expect(e("pausando").tono).toBe("azul");
    expect(e("reanudando").tono).toBe("azul");
    expect(e("pausado")).toEqual({ texto: "En pausa", tono: "gris" });
    expect(e("error").tono).toBe("rojo");
    expect(e("activo", 1)).toEqual({
      texto: "1 orden por aprobar",
      tono: "morado",
    });
    expect(e("activo", 3).texto).toBe("3 órdenes por aprobar");
  });

  it("qué está haciendo y el resumen del equipo", () => {
    const h = (x: Partial<Proyecto>) => haciendoDe(proyecto(x));
    expect(h({ haciendo: "Agente 1: Editando" })).toBe("Agente 1: Editando");
    expect(h({ estado: "creando" })).toBe("Creando la carpeta y el equipo…");
    expect(h({ estado: "pausado" })).toBe("En pausa");
    expect(h({ estado: "activo" })).toBe("En espera");
    expect(h({ estado: "error", error: "Falló git init", haciendo: "x" })).toBe(
      "Falló git init",
    );
    expect(resumenEquipo(proyecto().equipo)).toBe(
      "Orquestador Opus 5.5 · 1 agente de código",
    );
    const dos = [...proyecto().equipo, miembro({ id: "m3", rol: "agente" })];
    expect(resumenEquipo(dos)).toBe(
      "Orquestador Opus 5.5 · 2 agentes de código",
    );
  });

  it("botones del equipo según el estado", () => {
    expect(accionesDe("activo")).toEqual({
      pausar: true,
      reanudar: false,
      ocupado: false,
    });
    expect(accionesDe("pausado")).toMatchObject({
      pausar: false,
      reanudar: true,
    });
    expect(accionesDe("error")).toMatchObject({ pausar: true, reanudar: true });
    expect(accionesDe("creando").ocupado).toBe(true);
  });

  it("arma el cuerpo del POST con los valores por defecto", () => {
    const b: Borrador = {
      ...borradorInicial("alienware"),
      nombre: " tienda-web ",
    };
    expect(cuerpoCrear(b)).toEqual({
      nombre: "tienda-web",
      maquina: "alienware",
      cuenta: "personal",
      plantilla: "vacia",
      orquestador: { modelo: "opus", esfuerzo: "high" },
      agentes: [{ modelo: "sonnet", esfuerzo: "medium" }],
      auto_aprobar: false,
    });
    const cinco = { ...b, agentes: Array(5).fill(b.agentes[0]) };
    expect(cuerpoCrear(cinco).agentes).toHaveLength(4);
    expect(puedeCrear(b, MAQUINAS)).toBe(true);
    expect(puedeCrear({ ...b, maquina: "mac" }, MAQUINAS)).toBe(false);
    expect(puedeCrear({ ...b, nombre: "Mal" }, MAQUINAS)).toBe(false);
  });
});

describe("lista de proyectos", () => {
  it("muestra cuenta, máquina, qué hace, equipo y estado", async () => {
    const el = await montar(
      React.createElement(ListaVista, {
        proyectos: [
          proyecto(),
          proyecto({
            id: "p2",
            nombre: "juego",
            cuenta: "demo",
            estado: "creando",
          }),
          proyecto({ id: "p3", nombre: "app", ordenes_por_aprobar: 2 }),
        ],
        maquinas: MAQUINAS,
      }),
    );
    const t = texto(el);
    expect(el.querySelector("h1")?.textContent).toBe("Proyectos");
    expect(t).toContain(
      "Personal · Alienware · Orquestador Opus 5.5 · 1 agente de código",
    );
    expect(t).toContain("Demo Org");
    expect(t).toContain("Creando la carpeta y el equipo…");
    expect(t).toContain("2 órdenes por aprobar");
    const enlaces = [...el.querySelectorAll("a")].map((a) =>
      a.getAttribute("href"),
    );
    expect(enlaces).toContain("/proyectos/nuevo");
    expect(enlaces).toContain("/oficina/3d");
    expect(enlaces).toContain("/proyectos/ver?id=p2");
    expect(t).not.toMatch(/\p{Extended_Pictographic}/u);
  });

  it("vacía: invita a crear el primero", async () => {
    const el = await montar(React.createElement(ListaVista, { proyectos: [] }));
    expect(texto(el)).toContain("Todavía no creaste ningún proyecto");
  });
});

describe("formulario de nuevo proyecto", () => {
  it("máquina apagada no elegible, nombre inválido deshabilita, agentes", async () => {
    const enviados: Borrador[] = [];
    const el = await montar(
      React.createElement(FormularioNuevo, {
        maquinas: MAQUINAS,
        crear: async (b: Borrador) => {
          enviados.push(b);
        },
      }),
    );
    const radios = [
      ...el.querySelectorAll<HTMLInputElement>('input[name="maquina"]'),
    ];
    expect(radios.map((r) => [r.value, r.disabled, r.checked])).toEqual([
      ["alienware", false, true],
      ["mac", true, false],
    ]);
    expect(texto(el)).toContain("Apagada desde ayer");
    expect(texto(el)).toContain("Encendida");
    const crear = botonCon(el, "Crear proyecto")!;
    expect(crear.disabled).toBe(true);

    const nombre = el.querySelector<HTMLInputElement>("input:not([type])")!;
    await escribir(nombre, "Mal");
    expect(crear.disabled).toBe(true);
    expect(texto(el)).toContain("Usa solo minúsculas.");
    await escribir(nombre, "tienda-web");
    expect(crear.disabled).toBe(false);
    expect(texto(el)).toContain("Se va a crear: E:\\proyectos\\tienda-web");

    // agents: add up to 4, remove one
    const agregar = () => botonCon(el, "Agregar otro agente de código");
    for (let i = 0; i < 3; i++) await React.act(async () => agregar()!.click());
    expect(agregar()).toBeUndefined();
    expect(texto(el)).toContain("Agente de código 4");
    const quitar = [...el.querySelectorAll("button")].filter(
      (b) => b.textContent === "Quitar",
    );
    expect(quitar).toHaveLength(3);
    await React.act(async () => quitar[0].click());
    expect(texto(el)).not.toContain("Agente de código 4");
    expect(agregar()).toBeDefined();

    // the switch and the note
    const sw = el.querySelector<HTMLButtonElement>('[role="switch"]')!;
    expect(sw.getAttribute("aria-checked")).toBe("false");
    expect(texto(el)).toContain(
      "Todavía sin efecto: llega con las órdenes del orquestador.",
    );

    await React.act(async () => crear.click());
    expect(enviados).toHaveLength(1);
    expect(enviados[0].nombre).toBe("tienda-web");
    expect(enviados[0].agentes).toHaveLength(3);
    expect(enviados[0].orquestador).toEqual({
      modelo: "opus",
      esfuerzo: "high",
    });
  });

  it("muestra el detail del servidor", async () => {
    const el = await montar(
      React.createElement(FormularioNuevo, {
        maquinas: MAQUINAS,
        crear: async () => {
          throw new Error("Ya existe una carpeta con ese nombre.");
        },
      }),
    );
    await escribir(
      el.querySelector<HTMLInputElement>("input:not([type])")!,
      "tienda",
    );
    await React.act(async () => botonCon(el, "Crear proyecto")!.click());
    expect(el.querySelector('[role="alert"]')?.textContent).toBe(
      "Ya existe una carpeta con ese nombre.",
    );
  });

  it("sin máquina disponible no se puede crear", async () => {
    const el = await montar(
      React.createElement(FormularioNuevo, {
        maquinas: [MAQUINAS[1]],
        crear: async () => {},
      }),
    );
    await escribir(
      el.querySelector<HTMLInputElement>("input:not([type])")!,
      "tienda",
    );
    expect(botonCon(el, "Crear proyecto")!.disabled).toBe(true);
    expect(texto(el)).toContain("Ninguna máquina está disponible ahora.");
  });
});

describe("equipo del proyecto", () => {
  const sin = async () => {};

  it("activo: pausar, miembros legibles y enlace a la oficina", async () => {
    const el = await montar(
      React.createElement(EquipoVista, { proyecto: proyecto(), accion: sin }),
    );
    const t = texto(el);
    expect(botonCon(el, "Pausar el equipo")?.disabled).toBe(false);
    expect(botonCon(el, "Reanudar")).toBeUndefined();
    expect(t).toContain("Orquestador");
    expect(t).toContain("Agente de código");
    expect(t).toContain("Opus 5.5 · esfuerzo alto");
    expect(t).toContain("Sonnet 5.5 · esfuerzo medio");
    expect(t).toContain("En la oficina: Trabajando");
    expect(t).toContain("En la oficina: Esperando tu permiso");
    const hrefs = [...el.querySelectorAll("a")].map((a) =>
      a.getAttribute("href"),
    );
    expect(hrefs).toContain("/oficina/3d?agente=ses-a1");
  });

  it("pausado: reanudar; error: ambos y el mensaje; ocupado: deshabilitados", async () => {
    let el = await montar(
      React.createElement(EquipoVista, {
        proyecto: proyecto({ estado: "pausado" }),
        accion: sin,
      }),
    );
    expect(botonCon(el, "Pausar el equipo")).toBeUndefined();
    expect(botonCon(el, "Reanudar")?.disabled).toBe(false);
    document.body.innerHTML = "";

    el = await montar(
      React.createElement(EquipoVista, {
        proyecto: proyecto({
          estado: "error",
          error: "El monitor no respondió",
        }),
        accion: sin,
      }),
    );
    expect(botonCon(el, "Pausar el equipo")).toBeDefined();
    expect(botonCon(el, "Reanudar")).toBeDefined();
    expect(texto(el)).toContain("El monitor no respondió");
    document.body.innerHTML = "";

    el = await montar(
      React.createElement(EquipoVista, {
        proyecto: proyecto({ estado: "pausando" }),
        accion: sin,
      }),
    );
    expect(texto(el)).toContain("Pausando el equipo…");
    expect(botonCon(el, "Pausar el equipo")).toBeUndefined();
    expect(botonCon(el, "Reanudar")).toBeUndefined();
  });

  it("muestra el detail si pausar falla", async () => {
    const el = await montar(
      React.createElement(EquipoVista, {
        proyecto: proyecto(),
        accion: async () => {
          throw new Error("El proyecto ya se está pausando.");
        },
      }),
    );
    await React.act(async () => botonCon(el, "Pausar el equipo")!.click());
    expect(el.querySelector('[role="alert"]')?.textContent).toBe(
      "El proyecto ya se está pausando.",
    );
  });
});

describe("página del proyecto", () => {
  it("encabezado, pestañas y aviso del chat", async () => {
    const el = await montar(
      React.createElement(ProyectoVista, {
        proyecto: proyecto(),
        seccion: "chat",
        maquinas: MAQUINAS,
        accion: async () => {},
      }),
    );
    const t = texto(el);
    expect(el.querySelector("h1")?.textContent).toBe("tienda-web");
    expect(t).toContain("E:\\proyectos\\tienda-web");
    expect(t).toContain("Alienware");
    expect(t).toContain("El chat con el orquestador llega en el Prompt 38.");
    const actual = el.querySelector('a[aria-current="page"]');
    expect(actual?.textContent).toBe("Chat");
    expect(actual?.getAttribute("href")).toBe(
      "/proyectos/ver?id=p1&seccion=chat",
    );
  });

  it("Dónde quedamos fijo: sin lista lateral y aviso sin datos", async () => {
    let el = await montar(
      React.createElement(DondeVista, {
        proyectos: [],
        elegido: "tienda-web",
        consumo: null,
        ahora: Date.parse("2026-10-11T16:00:00Z"),
        fijo: true,
      }),
    );
    expect(texto(el)).toContain("Todavía no hay datos de este proyecto");
    expect(el.querySelector('nav[aria-label="Proyectos"]')).toBeNull();
    document.body.innerHTML = "";

    const proyectos = armarProyectos(
      [
        {
          carpeta: "E:\\proyectos\\Tienda-Web",
          tiene_project_md: false,
          plan: [],
          espera_decision: [],
        },
        {
          carpeta: "E:\\otro",
          tiene_project_md: false,
          plan: [],
          espera_decision: [],
        },
      ],
      [],
    );
    el = await montar(
      React.createElement(DondeVista, {
        proyectos,
        elegido: "tienda-web",
        consumo: null,
        ahora: Date.parse("2026-10-11T16:00:00Z"),
        fijo: true,
      }),
    );
    expect(texto(el)).toContain("no tiene PROJECT.md");
    expect(el.querySelector('nav[aria-label="Proyectos"]')).toBeNull();
    expect(el.querySelector("h1")).toBeNull();
    expect(texto(el)).not.toContain("Ir a la oficina");
  });
});
