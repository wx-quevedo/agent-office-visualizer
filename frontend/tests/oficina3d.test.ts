import { describe, expect, it } from "vitest";
import {
  adaptar,
  asignarPuestos,
  comportamiento,
  contar3d,
  ESPERA_LARGA_MS,
} from "@/components/oficina3d/adaptador";
import { leerDistribucion } from "@/components/oficina3d/distribucion";
import { t } from "@/components/oficina3d/textos";
import type { Agente } from "@/components/oficina/logica";

const T0 = Date.parse("2026-10-10T18:00:00Z");

function agente(
  id: string,
  numero: number,
  extra: Partial<Agente> = {},
  errores = 0,
): Agente {
  return {
    agente: { session_id: id, proyecto: "E:\\vive-demo", cuenta: "demo" },
    estado: {
      numero,
      nombre: `estado ${numero}`,
      desde: new Date(T0).toISOString(),
    },
    espera: null,
    herramienta_actual: null,
    ultimo_evento: { tipo: null, hora: null },
    subagentes_activos: 0,
    pregunta_pendiente: null,
    cierre: null,
    proceso: null,
    indicadores: {
      herramientas_por_minuto: 0,
      tokens_por_minuto: 0,
      tokens_totales: 0,
      tokens_contexto: 0,
      tokens_motivo: null,
      minutos_con_actividad: 0,
      contexto_usado_pct: 40,
      errores_seguidos: errores,
      errores_motivo: null,
    },
    eventos_recientes: [],
    ...extra,
  };
}

describe("21 estados → comportamiento", () => {
  const esperado: Record<number, string | null> = {
    1: "thinking",
    2: "thinking",
    3: "thinking",
    4: "thinking",
    5: "working",
    6: "working",
    7: "thinking",
    8: "working",
    9: "thinking",
    10: "thinking",
    11: "idle",
    12: "idle",
    13: "review",
    14: "review",
    15: "waiting",
    16: "waiting",
    17: "collab",
    18: "idle",
    19: "idle",
    20: "idle",
    21: null,
  };
  for (const [n, status] of Object.entries(esperado)) {
    it(`${n} → ${status ?? "fuera de la escena"}`, () => {
      expect(comportamiento(Number(n), 0)?.status ?? null).toBe(status);
    });
  }

  it("marca permiso (13), pregunta (14), descanso (19) y segundo plano (15, 16)", () => {
    expect(comportamiento(13, 0)).toMatchObject({
      permission: true,
      question: false,
    });
    expect(comportamiento(14, 0)).toMatchObject({
      permission: false,
      question: true,
    });
    expect(comportamiento(19, 0)).toMatchObject({
      status: "idle",
      resting: true,
    });
    expect(comportamiento(18, 0)?.resting).toBe(false);
    expect(comportamiento(15, 0)?.background).toBe(true);
    expect(comportamiento(16, 0)?.background).toBe(true);
  });

  it("errores seguidos ≥ 1 → bloqueado en estados de trabajo; 13, 14 e inactivos no cambian", () => {
    expect(comportamiento(6, 1)?.status).toBe("blocked");
    expect(comportamiento(3, 2)?.status).toBe("blocked");
    expect(comportamiento(13, 3)?.status).toBe("review");
    expect(comportamiento(11, 1)?.status).toBe("idle");
    expect(comportamiento(6, null)?.status).toBe("working");
  });
});

describe("puestos estables", () => {
  it("cada agente conserva su puesto mientras exista; los nuevos toman el libre más bajo", () => {
    const p1 = asignarPuestos({}, ["a", "b", "c"]);
    expect(p1).toEqual({ a: 0, b: 1, c: 2 });
    // b leaves, d arrives: a and c keep their desks, d takes desk 1.
    const p2 = asignarPuestos(p1, ["c", "d", "a"]);
    expect(p2).toEqual({ c: 2, d: 1, a: 0 });
    // Order of the list does not move anybody.
    expect(asignarPuestos(p2, ["a", "c", "d"])).toEqual(p2);
  });

  it("adaptar mantiene el puesto entre lecturas aunque cambie el orden del motor", () => {
    const r1 = adaptar([agente("x", 5), agente("y", 3)], {}, T0);
    const r2 = adaptar(
      [agente("y", 13), agente("x", 11)],
      r1.puestos,
      T0 + 2000,
    );
    const puesto = (r: typeof r1, id: string) =>
      r.vistas.find((v) => v.id === id)?.seatIndex;
    expect(puesto(r2, "x")).toBe(puesto(r1, "x"));
    expect(puesto(r2, "y")).toBe(puesto(r1, "y"));
  });
});

describe("adaptar", () => {
  it("los cerrados (21) no aparecen en la escena ni ocupan puesto", () => {
    const r = adaptar([agente("c", 21), agente("v", 5)], {}, T0);
    expect(r.vistas.map((v) => v.id)).toEqual(["v"]);
    expect(r.puestos).toEqual({ v: 0 });
  });

  it("lleva proyecto, cuenta, estado, pregunta, lo que pide y ayudantes", () => {
    const r = adaptar(
      [
        agente("p", 13, {
          espera: {
            tipo: "tu_permiso",
            evidencia: { herramienta: "Bash", comando: "git push" },
          },
        }),
        agente("q", 14, {
          pregunta_pendiente: "¿Lo subo?",
          subagentes_activos: 2,
        }),
      ],
      {},
      T0 + ESPERA_LARGA_MS,
    );
    const [p, q] = r.vistas;
    expect(p).toMatchObject({
      folderName: "vive-demo",
      cuenta: "demo",
      lePide: "Bash: git push",
      stuck: true,
    });
    expect(q.preguntaPendiente).toBe("¿Lo subo?");
    expect(q.subagents).toHaveLength(2);
    expect(q.inputTokens / q.contextWindow).toBeCloseTo(0.4);
  });

  it("cuenta te esperan, trabajando e inactivos sin los cerrados", () => {
    const lista = [13, 14, 5, 17, 11, 19, 21].map((n, i) => agente(`a${i}`, n));
    expect(contar3d(lista)).toEqual({ espera: 2, trabajando: 2, inactivos: 2 });
  });
});

describe("distribución y textos", () => {
  it("lee la distribución del repo y descarta muebles desconocidos o datos inválidos", () => {
    const d = leerDistribucion({
      version: 1,
      items: [
        { id: "1", type: "plant", x: 1, z: 2, ry: 0 },
        { id: "2", type: "nave-espacial", x: 0, z: 0, ry: 0 },
        { id: "3", type: "sofa", x: "1", z: 0, ry: 0 },
      ],
      floorColor: "#d8c7a8",
      wallColor: "javascript:alert(1)",
    });
    expect(d.items.map((i) => i.id)).toEqual(["1"]);
    expect(d.floorColor).toBe("#d8c7a8");
    expect(d.wallColor).toBeNull();
    expect(leerDistribucion(null).items).toEqual([]);
  });

  it("textos en español sin emojis", () => {
    expect(t("barra.titulo")).toBe("Oficina de agentes");
    expect(t("burbuja.permiso")).toBe("Te pide permiso");
  });
});
