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

let api: typeof import("@/utils/api");
let acceso: typeof import("@/components/acceso/logica");

beforeAll(async () => {
  GlobalRegistrator.register({
    url: "http://localhost:3100/oficina/3d?zoom=40",
  });
  api = await import("@/utils/api");
  acceso = await import("@/components/acceso/logica");
});

afterAll(async () => {
  await GlobalRegistrator.unregister();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("volver después de entrar", () => {
  it.each([
    ["/oficina/3d?zoom=40", "/oficina/3d?zoom=40"],
    ["/oficina?agente=abc", "/oficina?agente=abc"],
    [null, "/oficina"],
    ["", "/oficina"],
    ["https://otro.example/robar", "/oficina"],
    ["//otro.example/robar", "/oficina"],
    ["/\\otro.example", "/oficina"],
    // the browser drops tabs and new lines: "/\t/x" would become "//x"
    ["/\t/otro.example", "/oficina"],
    ["/\n/otro.example", "/oficina"],
    ["/%09/otro.example", "/%09/otro.example"],
    ["/entrar", "/oficina"],
    ["oficina", "/oficina"],
  ])("%s -> %s", (volver, esperado) => {
    expect(acceso.destinoSeguro(volver)).toBe(esperado);
  });
});

describe("cuándo ir a /entrar", () => {
  it("solo con el modo activado y sin sesión, fuera de /entrar", () => {
    const sin = { modo: "activado" as const, sesion: false, expira: null };
    expect(acceso.debeEntrar(sin, "/oficina")).toBe(true);
    expect(acceso.debeEntrar(sin, "/entrar")).toBe(false);
    expect(acceso.debeEntrar({ ...sin, sesion: true }, "/oficina")).toBe(false);
    expect(acceso.debeEntrar({ ...sin, modo: "desactivado" }, "/oficina")).toBe(
      false,
    );
    expect(acceso.debeEntrar(null, "/oficina")).toBe(false); // backend off
  });
});

describe("apiFetch", () => {
  it("manda la cookie y el encabezado contra CSRF en los cambios", async () => {
    const f = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response("{}", { status: 200 }));
    await api.apiFetch("/api/v1/permisos/config", {
      method: "PUT",
      body: "{}",
    });
    const [, init] = f.mock.calls[0];
    expect(init?.credentials).toBe("include");
    expect(new Headers(init?.headers).get("X-Visualizador")).toBe("1");
    await api.apiFetch("/api/v1/agents/state");
    const [, get] = f.mock.calls[1];
    expect(get?.credentials).toBe("include");
    expect(new Headers(get?.headers).get("X-Visualizador")).toBeNull();
  });

  it("sin sesión (401) va a /entrar y vuelve a esta página", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("{}", { status: 401 }),
    );
    const replace = vi
      .spyOn(window.location, "replace")
      .mockImplementation(() => undefined);
    await api.apiFetch("/api/v1/agents/state");
    expect(replace).toHaveBeenCalledWith(
      "/entrar?volver=%2Foficina%2F3d%3Fzoom%3D40",
    );
  });

  it("con el modo desactivado (sin 401) no redirige", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("{}", { status: 200 }),
    );
    const replace = vi
      .spyOn(window.location, "replace")
      .mockImplementation(() => undefined);
    await api.apiFetch("/api/v1/agents/state");
    expect(replace).not.toHaveBeenCalled();
  });
});
