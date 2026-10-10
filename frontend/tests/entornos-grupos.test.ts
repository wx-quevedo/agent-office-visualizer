import { afterEach, describe, expect, it } from "vitest";
import { adaptar, estadoInicial } from "@/components/oficina3d/adaptador";
import { activarEntorno } from "@/components/oficina3d/entornos/activo";
import {
  CABINA_GENERAL,
  CABINAS,
  PASILLO,
} from "@/components/oficina3d/entornos/cabinas";
import { asignarPorProyecto } from "@/components/oficina3d/entornos/grupos";
import { GRUPO_GENERAL } from "@/components/oficina3d/entornos/tipos";
import type { Agente } from "@/components/oficina/logica";

afterEach(() => {
  activarEntorno("original");
});

const T = Date.parse("2026-10-10T18:00:00Z");

function agente(
  id: string,
  proyecto: string,
  numero = 6,
  haceSeg = 30,
): Agente {
  return {
    agente: { session_id: id, proyecto: `E:\\${proyecto}`, cuenta: "personal" },
    estado: {
      numero,
      nombre: `estado ${numero}`,
      desde: new Date(T - haceSeg * 1000).toISOString(),
    },
    espera: null,
    herramienta_actual: null,
    ultimo_evento: { tipo: null, hora: null },
    subagentes_activos: 0,
    pregunta_pendiente: numero === 14 ? "¿Sigo?" : null,
    cierre: null,
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
  };
}

describe("Cabinas por proyecto: asignación", () => {
  it("una cabina por proyecto; un agente nuevo de un proyecto con cabina se sienta en ella", () => {
    const e = activarEntorno("cabinas");
    const agr = e.agrupacion!;
    const r1 = adaptar(
      [agente("a1", "alfa"), agente("b1", "beta"), agente("a2", "alfa")],
      estadoInicial(),
      T,
    );
    const g = (r: typeof r1, id: string) =>
      agr.grupoDe(r.vistas.find((v) => v.id === id)!.seatIndex).g;
    expect(g(r1, "a1")).toBe(g(r1, "a2"));
    expect(g(r1, "a1")).not.toBe(g(r1, "b1"));
    expect(r1.estado.grupos[g(r1, "a1")]).toBe("alfa");
    expect(r1.estado.grupos[g(r1, "b1")]).toBe("beta");
    // A new agent of alfa joins its cabin; nobody else moves.
    const r2 = adaptar(
      [
        agente("a1", "alfa"),
        agente("b1", "beta"),
        agente("a2", "alfa"),
        agente("a3", "alfa"),
      ],
      r1.estado,
      T + 2000,
    );
    expect(g(r2, "a3")).toBe(g(r1, "a1"));
    for (const id of ["a1", "b1", "a2"])
      expect(r2.vistas.find((v) => v.id === id)!.seatIndex).toBe(
        r1.vistas.find((v) => v.id === id)!.seatIndex,
      );
  });

  it("máximo 6 cabinas: los proyectos que no alcanzan comparten la Cabina general", () => {
    const e = activarEntorno("cabinas");
    const agr = e.agrupacion!;
    const lista = Array.from({ length: 8 }, (_, i) => ({
      id: `s${i}`,
      proyecto: `p${i}`,
    }));
    const r = asignarPorProyecto({}, lista, {}, agr);
    const grupos = lista.map(({ id }) => agr.grupoDe(r.puestos[id]).g);
    expect(new Set(grupos.slice(0, 6)).size).toBe(6);
    expect(grupos.slice(0, 6).every((g) => g < CABINA_GENERAL)).toBe(true);
    expect(grupos[6]).toBe(CABINA_GENERAL);
    expect(grupos[7]).toBe(CABINA_GENERAL);
    expect(r.duenos[CABINA_GENERAL]).toBe(GRUPO_GENERAL);
  });

  it("la asignación es estable mientras el proyecto tenga agentes; la cabina se libera al irse todos", () => {
    const agr = activarEntorno("cabinas").agrupacion!;
    const r1 = asignarPorProyecto(
      {},
      [
        { id: "a", proyecto: "alfa" },
        { id: "b", proyecto: "beta" },
      ],
      {},
      agr,
    );
    const gBeta = agr.grupoDe(r1.puestos.b).g;
    // alfa leaves: beta keeps its cabin; a new project takes the free one.
    const r2 = asignarPorProyecto(
      r1.puestos,
      [
        { id: "b", proyecto: "beta" },
        { id: "c", proyecto: "gama" },
      ],
      r1.duenos,
      agr,
    );
    expect(r2.puestos.b).toBe(r1.puestos.b);
    expect(r2.duenos[gBeta]).toBe("beta");
    expect(agr.grupoDe(r2.puestos.c).g).toBe(agr.grupoDe(r1.puestos.a).g);
    expect(r2.duenos[agr.grupoDe(r2.puestos.c).g]).toBe("gama");
  });

  it("40 agentes: puestos distintos, de cualquier mezcla de proyectos", () => {
    const e = activarEntorno("cabinas");
    for (const proyectos of [1, 4, 10, 40]) {
      const lista = Array.from({ length: 40 }, (_, i) => ({
        id: `s${i}`,
        proyecto: `p${i % proyectos}`,
      }));
      const r = asignarPorProyecto({}, lista, {}, e.agrupacion!);
      const puestos = Object.values(r.puestos);
      expect(new Set(puestos).size).toBe(40);
      expect(Math.max(...puestos)).toBeLessThan(103); // fixed desks (tested without overlap)
    }
  });

  it("13 y 14 caminan a la puerta de su cabina mirando a tu puesto; al dejar de esperar vuelven", () => {
    const e = activarEntorno("cabinas");
    const agr = e.agrupacion!;
    const r1 = adaptar(
      [
        agente("a1", "alfa", 13, 200),
        agente("a2", "alfa", 14, 50),
        agente("b1", "beta", 6),
      ],
      estadoInicial(),
      T,
    );
    const v = (r: typeof r1, id: string) => r.vistas.find((x) => x.id === id)!;
    const g = agr.grupoDe(v(r1, "a1").seatIndex).g;
    const cab = CABINAS[g];
    expect(v(r1, "a1")).toMatchObject({
      destino: "fila",
      fila: agr.puerta!(g, 0),
    });
    expect(v(r1, "a2").fila).toEqual(agr.puerta!(g, 1));
    expect(v(r1, "b1")).toMatchObject({ destino: "escritorio", fila: null });
    const f = v(r1, "a1").fila!;
    // In the corridor, in front of the door of its cabin...
    expect(Math.abs(f.z)).toBeLessThan(PASILLO);
    expect(Math.sign(f.z)).toBe(cab.lado);
    expect(Math.abs(f.x - cab.cx)).toBeLessThan(1);
    // ...facing your desk.
    const hacia = { x: e.tuPuesto.x - f.x, z: e.tuPuesto.z - f.z };
    const mira = { x: -Math.sin(f.ry), z: -Math.cos(f.ry) };
    expect(hacia.x * mira.x + hacia.z * mira.z).toBeGreaterThan(0);
    // Stops waiting: back to its desk, same seat; the other one moves up.
    const r2 = adaptar(
      [
        agente("a1", "alfa", 6, 1),
        agente("a2", "alfa", 14, 52),
        agente("b1", "beta", 6),
      ],
      r1.estado,
      T + 2000,
    );
    expect(v(r2, "a1")).toMatchObject({ destino: "escritorio", fila: null });
    expect(v(r2, "a1").seatIndex).toBe(v(r1, "a1").seatIndex);
    expect(v(r2, "a2").fila).toEqual(agr.puerta!(g, 0));
  });
});

describe("Estudio con jardín: asignación por islas", () => {
  it("proyectos con un solo agente comparten la Isla general; los de varios tienen su isla", () => {
    const e = activarEntorno("estudio");
    const agr = e.agrupacion!;
    const r = adaptar(
      [
        agente("a1", "alfa"),
        agente("a2", "alfa"),
        agente("b1", "beta"),
        agente("c1", "gama"),
      ],
      estadoInicial(),
      T,
    );
    const g = (id: string) =>
      agr.grupoDe(r.vistas.find((v) => v.id === id)!.seatIndex).g;
    expect(g("a1")).toBe(g("a2"));
    expect(r.estado.grupos[g("a1")]).toBe("alfa");
    expect(g("b1")).toBe(g("c1"));
    expect(r.estado.grupos[g("b1")]).toBe(GRUPO_GENERAL);
  });

  it("se agregan islas cuando hace falta y nadie se cambia de puesto", () => {
    const agr = activarEntorno("estudio").agrupacion!;
    const lista = Array.from({ length: 6 }, (_, i) => ({
      id: `a${i}`,
      proyecto: "alfa",
    }));
    const r1 = asignarPorProyecto({}, lista, {}, agr);
    const islas = new Set(lista.map(({ id }) => agr.grupoDe(r1.puestos[id]).g));
    expect(islas.size).toBe(2); // 6 agents, 4 per island
    for (const g of islas) expect(r1.duenos[g]).toBe("alfa");
    const r2 = asignarPorProyecto(
      r1.puestos,
      [...lista, { id: "b0", proyecto: "beta" }],
      r1.duenos,
      agr,
    );
    for (const { id } of lista) expect(r2.puestos[id]).toBe(r1.puestos[id]);
    expect(r2.duenos[agr.grupoDe(r2.puestos.b0).g]).toBe(GRUPO_GENERAL);
  });

  it("40 agentes: puestos distintos en las islas", () => {
    const e = activarEntorno("estudio");
    for (const proyectos of [1, 5, 20, 40]) {
      const lista = Array.from({ length: 40 }, (_, i) => ({
        id: `s${i}`,
        proyecto: `p${i % proyectos}`,
      }));
      const r = asignarPorProyecto({}, lista, {}, e.agrupacion!);
      const puestos = Object.values(r.puestos);
      expect(new Set(puestos).size).toBe(40);
      expect(Math.max(...puestos)).toBeLessThan(84);
    }
  });

  it("quien te espera se queda en su escritorio, iluminado y girado hacia ti", () => {
    const e = activarEntorno("estudio");
    const r = adaptar([agente("a1", "alfa", 13)], estadoInicial(), T);
    expect(r.vistas[0]).toMatchObject({
      destino: "escritorio",
      fila: null,
      permission: true,
    });
    expect(e.resaltarEspera).toBe(true);
    expect(e.girarHaciaTi).toBe(true);
  });
});
