import { GlobalRegistrator } from "@happy-dom/global-registrator";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import type { Agente } from "@/components/oficina/logica";
import type { Permiso } from "@/components/permisos/logica";

let React: typeof import("react");
let ReactDOM: typeof import("react-dom/client");
let PanelAgente3D: typeof import("@/components/oficina3d/PanelAgente3D").default;
let useOffice: typeof import("@/components/oficina3d/store").useOffice;

beforeAll(async () => {
  GlobalRegistrator.register({ url: "http://localhost:3100/oficina/3d" });
  (
    globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
  React = await import("react");
  ReactDOM = await import("react-dom/client");
  PanelAgente3D = (await import("@/components/oficina3d/PanelAgente3D"))
    .default;
  useOffice = (await import("@/components/oficina3d/store")).useOffice;
});

afterAll(async () => {
  await GlobalRegistrator.unregister();
});

afterEach(() => {
  document.body.innerHTML = "";
  useOffice.getState().setPanel(null);
});

const AHORA = Date.parse("2026-10-10T18:00:30Z");

function agente(numero: number, extra: Partial<Agente> = {}): Agente {
  return {
    agente: {
      session_id: "sim-3",
      proyecto: "E:/buscapez",
      cuenta: "demo",
    },
    estado: {
      numero,
      nombre: `estado ${numero}`,
      desde: "2026-10-10T18:00:00Z",
    },
    espera: null,
    herramienta_actual: "Read",
    ultimo_evento: { tipo: "pre_tool_use", hora: "2026-10-10T18:00:29Z" },
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

async function montar(a: Agente | undefined): Promise<HTMLElement> {
  const el = document.createElement("div");
  document.body.appendChild(el);
  const raiz = ReactDOM.createRoot(el);
  await React.act(async () => {
    raiz.render(
      React.createElement(PanelAgente3D, {
        agente: a,
        id: "sim-3",
        ahora: AHORA,
        onCerrar: () => useOffice.getState().setPanel(null),
      }),
    );
  });
  return el;
}

describe("clic en un agente de la escena 3D", () => {
  it("abre el panel del agente sobre la escena, sin navegar", () => {
    const antes = window.location.href;
    useOffice.getState().select("sim-3");
    expect(useOffice.getState().panel).toBe("sim-3");
    expect(window.location.href).toBe(antes);
    // a click on an empty desk does nothing
    useOffice.getState().setPanel(null);
    useOffice.getState().select(null);
    expect(useOffice.getState().panel).toBeNull();
  });

  it("el panel de un agente que trabaja muestra su estado y el enlace al detalle", async () => {
    const el = await montar(agente(4));
    expect(el.textContent).toContain("buscapez");
    expect(el.textContent).toContain("4 · estado 4");
    expect(el.textContent).toContain("En este estado 30 s");
    const enlace = el.querySelector("a");
    expect(enlace?.getAttribute("href")).toBe("/oficina?agente=sim-3");
    const cerrar = [...el.querySelectorAll("button")].find(
      (b) => b.textContent === "Cerrar",
    )!;
    useOffice.getState().setPanel("sim-3");
    await React.act(async () => cerrar.click());
    expect(useOffice.getState().panel).toBeNull();
  });

  it("13 con solicitud: los botones de permiso", async () => {
    const permiso: Permiso = {
      id: "abc12345",
      session_id: "sim-3",
      herramienta: "Bash",
      detalle: "git status",
      cuenta: "demo",
      proyecto: "buscapez",
      creada: "2026-10-10T18:00:00Z",
      esperando: true,
      vence: "2026-10-10T18:01:30Z",
      segundos_restantes: 60,
      estado: "pendiente",
      motivo: null,
      dispositivo: null,
      decidida: null,
    };
    const el = await montar(agente(13, { permiso }));
    expect(el.querySelector("pre")?.textContent).toBe("git status");
    expect(el.textContent).toContain("Aprobar");
  });

  it("14: muestra la pregunta pendiente", async () => {
    const el = await montar(
      agente(14, { pregunta_pendiente: "¿Publico la versión nueva?" }),
    );
    expect(el.textContent).toContain("¿Publico la versión nueva?");
  });

  it("si el agente ya no está, lo dice y deja el enlace al detalle", async () => {
    const el = await montar(undefined);
    expect(el.textContent).toContain("Ese agente ya no está en la oficina");
    expect(el.querySelector("a")?.getAttribute("href")).toBe(
      "/oficina?agente=sim-3",
    );
  });
});
