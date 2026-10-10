import { describe, expect, it } from "vitest";
import {
  agruparPorProyecto,
  agruparPorUrgencia,
  cerradoVisible,
  contar,
  dispositivo,
  grupoDe,
  loQuePide,
  minutosParaDesaparecer,
  textoPresencia,
  type Agente,
} from "@/components/oficina/logica";

const AHORA = Date.parse("2026-10-10T18:00:00Z");

function min(antes: number): string {
  return new Date(AHORA - antes * 60000).toISOString();
}

function agente(
  id: string,
  numero: number,
  hace: number,
  extra: Partial<Agente> & { proyecto?: string } = {},
): Agente {
  const { proyecto, ...resto } = extra;
  return {
    agente: {
      session_id: id,
      proyecto: proyecto ?? "E:\\Test\\demo",
      cuenta: "personal",
    },
    estado: { numero, nombre: `estado ${numero}`, desde: min(hace) },
    espera: null,
    herramienta_actual: null,
    ultimo_evento: { tipo: null, hora: null },
    subagentes_activos: 0,
    pregunta_pendiente: null,
    cierre:
      numero === 21 ? { motivo: "proceso_terminado", desde: min(hace) } : null,
    proceso: null,
    indicadores: {
      herramientas_por_minuto: 0,
      tokens_por_minuto: 0,
      tokens_totales: 0,
      tokens_contexto: 0,
      tokens_motivo: null,
      minutos_con_actividad: 0,
      contexto_usado_pct: 0,
      errores_seguidos: 0,
      errores_motivo: null,
    },
    eventos_recientes: [],
    ...resto,
  };
}

describe("grupos por estado", () => {
  it("13 y 14 te esperan; 21 cerrado; 11 y 18-20 inactivos; el resto trabaja", () => {
    expect([13, 14].map(grupoDe)).toEqual(["espera", "espera"]);
    expect(grupoDe(21)).toBe("cerrados");
    expect([11, 18, 19, 20].map(grupoDe)).toEqual(Array(4).fill("inactivos"));
    const trabajo = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 16, 17];
    expect(trabajo.map(grupoDe)).toEqual(
      Array(trabajo.length).fill("trabajando"),
    );
  });

  it("los contadores separan inactivos (11, 18) de descansando (19, 20)", () => {
    const c = contar([
      agente("a", 13, 1),
      agente("b", 5, 1),
      agente("c", 11, 1),
      agente("d", 18, 1),
      agente("e", 19, 1),
      agente("f", 21, 1),
    ]);
    expect(c).toEqual({
      espera: 1,
      trabajando: 1,
      inactivos: 2,
      descansando: 1,
      cerrados: 1,
    });
  });
});

describe("vista por urgencia", () => {
  it("ordena por tiempo en el estado: el que más lleva esperando primero", () => {
    const g = agruparPorUrgencia(
      [
        agente("nuevo", 14, 2),
        agente("viejo", 13, 30),
        agente("medio", 14, 10),
      ],
      AHORA,
    );
    expect(g.espera.map((a) => a.agente.session_id)).toEqual([
      "viejo",
      "medio",
      "nuevo",
    ]);
  });

  it("reparte cada agente en su sección", () => {
    const g = agruparPorUrgencia(
      [
        agente("w", 6, 1),
        agente("p", 15, 3),
        agente("i", 11, 5),
        agente("x", 21, 5),
      ],
      AHORA,
    );
    expect(g.trabajando.map((a) => a.agente.session_id)).toEqual(["p", "w"]);
    expect(g.inactivos).toHaveLength(1);
    expect(g.cerrados).toHaveLength(1);
    expect(g.espera).toHaveLength(0);
  });
});

describe("regla de cerrados", () => {
  it("sin pregunta pendiente se muestra 1 h desde el cierre y luego desaparece", () => {
    const reciente = agente("r", 21, 45);
    const viejo = agente("v", 21, 61);
    expect(cerradoVisible(reciente, AHORA)).toBe(true);
    expect(minutosParaDesaparecer(reciente, AHORA)).toBe(15);
    expect(cerradoVisible(viejo, AHORA)).toBe(false);
    expect(agruparPorUrgencia([reciente, viejo], AHORA).cerrados).toEqual([
      reciente,
    ]);
  });

  it("con pregunta pendiente se queda hasta que la sesión se reabra", () => {
    const conPregunta = agente("q", 21, 600, {
      pregunta_pendiente: "¿Lo subo?",
    });
    expect(cerradoVisible(conPregunta, AHORA)).toBe(true);
    expect(minutosParaDesaparecer(conPregunta, AHORA)).toBeNull();
    // Reopened: it leaves state 21 and is shown in its new section.
    const reabierta = {
      ...conPregunta,
      estado: { ...conPregunta.estado, numero: 20 },
    };
    expect(agruparPorUrgencia([reabierta], AHORA).inactivos).toHaveLength(1);
  });

  it("usa la hora del cierre, no la del estado", () => {
    const a = agente("c", 21, 5, {
      cierre: { motivo: "sin_pid_antiguo", desde: min(70) },
    });
    expect(cerradoVisible(a, AHORA)).toBe(false);
  });
});

describe("vista por proyecto", () => {
  it("una sala por carpeta; primero las que te esperan, luego las que trabajan, luego el resto", () => {
    const salas = agruparPorProyecto(
      [
        agente("a1", 11, 5, { proyecto: "E:\\Test\\alfa" }),
        agente("b1", 5, 5, { proyecto: "C:/xampp/htdocs/beta" }),
        agente("c1", 21, 5, { proyecto: "E:\\Test\\gamma" }),
        agente("c2", 14, 1, { proyecto: "E:\\Test\\gamma" }),
        agente("d1", 19, 5, { proyecto: "E:\\Test\\delta" }),
      ],
      AHORA,
    );
    expect(salas.map((s) => s.proyecto)).toEqual([
      "gamma",
      "beta",
      "alfa",
      "delta",
    ]);
    expect(salas[0].resumen).toBe("1 te espera · 1 cerrado");
    // Inside a room: waiting first, closed last.
    expect(salas[0].agentes.map((a) => a.agente.session_id)).toEqual([
      "c2",
      "c1",
    ]);
  });

  it("una sala con solo cerrados vencidos no aparece", () => {
    const salas = agruparPorProyecto(
      [agente("z", 21, 90, { proyecto: "E:\\x\\vieja" })],
      AHORA,
    );
    expect(salas).toEqual([]);
  });

  it("resume en plural", () => {
    const salas = agruparPorProyecto(
      [agente("a", 5, 1), agente("b", 6, 2), agente("c", 14, 1)],
      AHORA,
    );
    expect(salas[0].resumen).toBe("1 te espera · 2 trabajando");
  });
});

describe("textos", () => {
  it("lo que pide un permiso: herramienta y comando", () => {
    const a = agente("p", 13, 1, {
      espera: {
        tipo: "tu_permiso",
        evidencia: { herramienta: "Bash", comando: "git push" },
      },
    });
    expect(loQuePide(a)).toEqual({
      titulo: "Lo que pide",
      texto: "Bash: git push",
    });
    const q = agente("q", 14, 1, { pregunta_pendiente: "¿Sigo?" });
    expect(loQuePide(q)).toEqual({
      titulo: "Pregunta pendiente",
      texto: "¿Sigo?",
    });
  });

  it("presencia por dispositivo", () => {
    const base = {
      motivo: "",
      navegadores_conectados: 1,
      ultimo_encargo: null,
      desconectado_desde: null,
    };
    expect(
      textoPresencia({ ...base, estado: "conectado", dispositivos: ["pc"] }),
    ).toBe("Estás presente (PC)");
    expect(
      textoPresencia({
        ...base,
        estado: "conectado",
        dispositivos: ["celular"],
      }),
    ).toBe("Estás presente (celular)");
    expect(
      textoPresencia({ ...base, estado: "desconectado", dispositivos: [] }),
    ).toBe("Desconectado");
  });

  it("celular por ancho o por user agent", () => {
    expect(dispositivo(390, "Mozilla/5.0 (Windows NT 10.0)")).toBe("celular");
    expect(dispositivo(1440, "Mozilla/5.0 (Linux; Android 14) Mobile")).toBe(
      "celular",
    );
    expect(dispositivo(1440, "Mozilla/5.0 (Windows NT 10.0)")).toBe("pc");
  });
});
