import { describe, expect, it, vi } from "vitest";
import { avisarApp, esModoApp } from "@/components/oficina3d/modoApp";

describe("modo app de la oficina 3D", () => {
  it("solo con ?app=ios", () => {
    expect(esModoApp(new URLSearchParams("app=ios"))).toBe(true);
    expect(esModoApp(new URLSearchParams("app=android"))).toBe(false);
    expect(esModoApp(new URLSearchParams(""))).toBe(false);
  });

  it("avisa a la app por el manejador de WebKit", () => {
    const postMessage = vi.fn();
    const w = { webkit: { messageHandlers: { oficina: { postMessage } } } };
    expect(avisarApp({ tipo: "agente", id: "abc" }, w)).toBe(true);
    expect(postMessage).toHaveBeenCalledWith({ tipo: "agente", id: "abc" });
  });

  it("sin app que escuche no falla", () => {
    expect(avisarApp({ tipo: "agente", id: "abc" }, {})).toBe(false);
    const roto = {
      webkit: {
        messageHandlers: {
          oficina: {
            postMessage: () => {
              throw new Error("x");
            },
          },
        },
      },
    };
    expect(avisarApp({ tipo: "lista" }, roto)).toBe(false);
  });
});
