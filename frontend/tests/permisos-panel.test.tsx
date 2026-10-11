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
import type { Permiso } from "@/components/permisos/logica";

let React: typeof import("react");
let ReactDOM: typeof import("react-dom/client");
let PanelPermiso: typeof import("@/components/permisos/PanelPermiso").default;

beforeAll(async () => {
  GlobalRegistrator.register({ url: "http://localhost:3100/oficina" });
  (
    globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
  React = await import("react");
  ReactDOM = await import("react-dom/client");
  PanelPermiso = (await import("@/components/permisos/PanelPermiso")).default;
});

afterAll(async () => {
  await GlobalRegistrator.unregister();
});

afterEach(() => {
  vi.restoreAllMocks();
  document.body.innerHTML = "";
});

const AHORA = Date.parse("2026-10-10T18:00:05Z");

function permiso(extra: Partial<Permiso> = {}): Permiso {
  return {
    id: "abc12345",
    session_id: "prueba-1",
    herramienta: "Bash",
    detalle: "git push origin main",
    cuenta: "personal",
    proyecto: "demo",
    creada: "2026-10-10T18:00:00Z",
    esperando: true,
    vence: "2026-10-10T18:01:30Z",
    segundos_restantes: 90,
    estado: "pendiente",
    motivo: null,
    dispositivo: null,
    decidida: null,
    ...extra,
  };
}

async function montar(p: Permiso): Promise<HTMLElement> {
  const el = document.createElement("div");
  document.body.appendChild(el);
  const raiz = ReactDOM.createRoot(el);
  await React.act(async () => {
    raiz.render(
      React.createElement(PanelPermiso, { permiso: p, ahora: AHORA }),
    );
  });
  return el;
}

function boton(el: HTMLElement, texto: string): HTMLButtonElement {
  const b = [...el.querySelectorAll("button")].find(
    (x) => x.textContent?.trim() === texto,
  );
  if (!b) throw new Error(`sin botón ${texto}: ${el.textContent}`);
  return b as HTMLButtonElement;
}

function respuesta(body: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

describe("panel de permiso", () => {
  it("muestra el comando completo, el tiempo y los botones", async () => {
    Object.defineProperty(window, "innerWidth", {
      value: 1440,
      configurable: true,
    });
    vi.spyOn(globalThis, "fetch").mockImplementation(() => respuesta({}, 404));
    const el = await montar(permiso());
    expect(el.querySelector("pre")?.textContent).toBe("git push origin main");
    expect(el.textContent).toContain("Quedan 1:25");
    expect(boton(el, "Aprobar")).toBeTruthy();
    expect(boton(el, "Rechazar")).toBeTruthy();
  });

  it("aprobar en la PC envía la decisión sin confirmación", async () => {
    Object.defineProperty(window, "innerWidth", {
      value: 1440,
      configurable: true,
    });
    const f = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((url) =>
        String(url).includes("/decision")
          ? respuesta(permiso({ estado: "aprobada", dispositivo: "pc" }))
          : respuesta({}, 404),
      );
    const el = await montar(permiso());
    await React.act(async () => boton(el, "Aprobar").click());
    const llamada = f.mock.calls.find(([u]) => String(u).includes("/decision"));
    expect(llamada).toBeTruthy();
    expect(JSON.parse(String(llamada![1]!.body))).toEqual({
      decision: "aprobar",
      motivo: null,
      dispositivo: "pc",
    });
    expect(el.textContent).toContain("Aprobado desde la PC.");
    expect(el.textContent).not.toContain("Rechazar");
  });

  it("en el celular, un git push pide confirmación antes de aprobar", async () => {
    Object.defineProperty(window, "innerWidth", {
      value: 390,
      configurable: true,
    });
    const f = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((url) =>
        String(url).includes("/decision")
          ? respuesta(permiso({ estado: "aprobada", dispositivo: "celular" }))
          : respuesta({}, 404),
      );
    const el = await montar(permiso());
    await React.act(async () => boton(el, "Aprobar").click());
    expect(el.textContent).toContain("Este comando borra o sube algo");
    expect(f.mock.calls.some(([u]) => String(u).includes("/decision"))).toBe(
      false,
    );
    await React.act(async () => boton(el, "Sí, aprobar").click());
    const llamada = f.mock.calls.find(([u]) => String(u).includes("/decision"));
    expect(JSON.parse(String(llamada![1]!.body)).dispositivo).toBe("celular");
  });

  it("rechazar con motivo", async () => {
    Object.defineProperty(window, "innerWidth", {
      value: 1440,
      configurable: true,
    });
    const f = vi.spyOn(globalThis, "fetch").mockImplementation((url) =>
      String(url).includes("/decision")
        ? respuesta(
            permiso({
              estado: "rechazada",
              dispositivo: "pc",
              motivo: "Usa la rama de prueba",
            }),
          )
        : respuesta({}, 404),
    );
    const el = await montar(permiso());
    await React.act(async () => boton(el, "Rechazar").click());
    const input = el.querySelector("input") as HTMLInputElement;
    await React.act(async () => {
      const set = Object.getOwnPropertyDescriptor(
        HTMLInputElement.prototype,
        "value",
      )!.set!;
      set.call(input, "Usa la rama de prueba");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await React.act(async () => boton(el, "Enviar rechazo").click());
    const llamada = f.mock.calls.find(([u]) => String(u).includes("/decision"));
    expect(JSON.parse(String(llamada![1]!.body))).toMatchObject({
      decision: "rechazar",
      motivo: "Usa la rama de prueba",
    });
    expect(el.textContent).toContain(
      "Rechazado desde la PC: Usa la rama de prueba",
    );
  });

  it("muestra el error claro de una solicitud vencida", async () => {
    Object.defineProperty(window, "innerWidth", {
      value: 1440,
      configurable: true,
    });
    vi.spyOn(globalThis, "fetch").mockImplementation((url) =>
      String(url).includes("/decision")
        ? respuesta(
            { detail: "Se agotó el tiempo de espera: responde en VS Code." },
            410,
          )
        : respuesta({}, 404),
    );
    const el = await montar(permiso());
    await React.act(async () => boton(el, "Aprobar").click());
    expect(el.textContent).toContain("Se agotó el tiempo de espera");
  });

  it("sin espera de la oficina: Responde en VS Code, sin botones", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => respuesta({}, 404));
    const el = await montar(permiso({ esperando: false, vence: null }));
    expect(el.textContent).toContain("Responde en VS Code.");
    expect(el.querySelectorAll("button").length).toBe(0);
  });
});
