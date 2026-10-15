import { describe, expect, it } from "vitest";
import {
  cuando,
  fraseDePermiso,
  iniciales,
  miles,
  nombreModelo,
  resumenTurno,
  tiempoExacto,
  type Turno,
} from "@/components/ficha/logica";

describe("textos de la ficha", () => {
  it("tiempos y miles como en los bocetos", () => {
    expect(tiempoExacto(45)).toBe("45 s");
    expect(tiempoExacto(134)).toBe("2 min 14 s");
    expect(tiempoExacto(65)).toBe("1 min 05 s");
    expect(tiempoExacto(120)).toBe("2 min");
    expect(tiempoExacto(3900)).toBe("1 h 05 min");
    expect(tiempoExacto(null)).toBe("—");
    expect(miles(312480)).toBe("312\u00a0480");
    expect(miles(980)).toBe("980");
    expect(miles(null)).toBe("—");
  });

  it("iniciales, modelo y fechas", () => {
    expect(iniciales("SkyNest")).toBe("SN");
    expect(iniciales("vive-demo")).toBe("VD");
    expect(iniciales("buscapez")).toBe("BU");
    expect(nombreModelo("claude-opus-5-5[1m]")).toBe("Opus 5.5");
    expect(nombreModelo("claude-sonnet-4-5-20250929")).toBe("Sonnet 4.5");
    expect(nombreModelo("otro")).toBe("otro");
    const ahora = new Date(2026, 9, 11, 15, 0).getTime();
    expect(cuando(new Date(2026, 9, 11, 10, 36).toISOString(), ahora)).toBe(
      "hoy 10:36",
    );
    expect(cuando(new Date(2026, 9, 10, 18, 20).toISOString(), ahora)).toBe(
      "ayer 18:20",
    );
    expect(cuando(new Date(2026, 9, 2, 8, 5).toISOString(), ahora)).toBe(
      "2 oct 08:05",
    );
  });

  it("el permiso en una frase clara", () => {
    expect(fraseDePermiso("Bash", "git push origin main")).toContain(
      "git push",
    );
    expect(fraseDePermiso("Bash", "rm -rf build")).toBe(
      "Quiere borrar archivos o carpetas.",
    );
    expect(fraseDePermiso("Bash", "ls")).toBe(
      "Quiere ejecutar un comando en la terminal.",
    );
    expect(fraseDePermiso("Edit", "E:/x/app.ts")).toBe("Quiere editar app.ts.");
    expect(fraseDePermiso("mcp__plugin_unity_unity__manage_scene", "{}")).toBe(
      "Quiere usar manage_scene de unity.",
    );
  });

  it("resumen del turno", () => {
    const t: Turno = {
      numero: 1,
      inicio: "2026-10-11T14:00:00Z",
      fin: null,
      duracion_s: 60,
      pedido: null,
      herramientas: { Read: 1 },
      total_herramientas: 1,
      archivos_editados: [],
      commits: [],
      errores: 0,
      tokens_salida: null,
      resultado: "en_curso",
      pregunta: null,
    };
    expect(resumenTurno(t)).toBe(
      "1 herramienta · sin archivos editados · sin commit todavía",
    );
  });
});
