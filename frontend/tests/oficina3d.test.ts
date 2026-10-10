import { describe, expect, it } from "vitest";
import {
  adaptar,
  asignarPuestos,
  contar3d,
  ESPERA_LARGA_MS,
  estadoInicial,
  type EstadoAdaptador,
} from "@/components/oficina3d/adaptador";
import {
  ASIENTOS_SOFA,
  asignarDescanso,
  comportamiento,
  etiqueta,
} from "@/components/oficina3d/comportamiento";
import { leerDistribucion } from "@/components/oficina3d/distribucion";
import { t } from "@/components/oficina3d/textos";
import type { Agente } from "@/components/oficina/logica";

const T0 = Date.parse("2026-10-10T18:00:00Z");
const MIN = 60_000;

function agente(
  id: string,
  numero: number,
  extra: Partial<Agente> = {},
  errores = 0,
): Agente {
  return {
    agente: { session_id: id, proyecto: "E:\\vive-demo", cuenta: "personal" },
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
    cierre:
      numero === 21
        ? { motivo: "proceso_terminado", desde: new Date(T0).toISOString() }
        : null,
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

/** Runs several reads in a row, carrying the adapter memory. */
function lecturas(listas: Agente[][], salidos: Set<string> = new Set()) {
  let estado: EstadoAdaptador = estadoInicial();
  return listas.map((lista, i) => {
    const r = adaptar(lista, estado, T0 + i * 2000, salidos);
    estado = r.estado;
    return r;
  });
}

describe("21 estados → comportamiento", () => {
  const esperado: Record<number, [string, string, string] | null> = {
    1: ["thinking", "escritorio", "pensar"],
    2: ["thinking", "escritorio", "pensar"],
    3: ["thinking", "escritorio", "pensar"],
    4: ["thinking", "escritorio", "pensar"],
    5: ["working", "escritorio", "teclear"],
    6: ["working", "escritorio", "teclear"],
    7: ["thinking", "escritorio", "pensar"],
    8: ["working", "escritorio", "teclear"],
    9: ["thinking", "escritorio", "pensar"],
    10: ["thinking", "escritorio", "pensar"],
    11: ["idle", "pasear", "libre"],
    12: ["idle", "salida", "libre"],
    13: ["review", "escritorio", "brazoAlzado"],
    14: ["review", "escritorio", "mirarCamara"],
    15: ["waiting", "escritorio", "quieto"],
    16: ["waiting", "escritorio", "quieto"],
    17: ["collab", "escritorio", "teclear"],
    18: ["idle", "pasear", "libre"],
    19: ["idle", "sofa", "libre"],
    20: ["idle", "escritorio", "libre"],
    21: null,
  };
  for (const [n, e] of Object.entries(esperado)) {
    it(`${n} → ${e ? e.join(" / ") : "fuera de la escena"}`, () => {
      const c = comportamiento(Number(n), 0);
      expect(c ? [c.status, c.destino, c.pose] : null).toEqual(e);
    });
  }

  it("13 pide permiso y 14 pregunta; 15 reloj y 16 barra sobre el monitor", () => {
    expect(comportamiento(13, 0)?.espera).toBe("permiso");
    expect(comportamiento(14, 0)?.espera).toBe("pregunta");
    expect(comportamiento(15, 0)?.monitor).toBe("reloj");
    expect(comportamiento(16, 0)?.monitor).toBe("progreso");
    expect(comportamiento(6, 0)?.monitor).toBeNull();
  });

  it("errores seguidos ≥ 1 → con errores solo en estados de trabajo", () => {
    expect(comportamiento(6, 1)?.status).toBe("blocked");
    expect(comportamiento(16, 2)?.status).toBe("blocked");
    expect(comportamiento(13, 3)?.status).toBe("review");
    expect(comportamiento(11, 1)?.status).toBe("idle");
  });
});

describe("etiquetas", () => {
  it("libre: solo el proyecto, sin 'Inactivo'", () => {
    for (const n of [1, 11, 12, 18, 19, 20]) {
      expect(etiqueta("vive-demo", n, 0, "personal")).toEqual({
        proyecto: "vive-demo",
        actividad: null,
        espera: null,
        errores: false,
        demo: false,
      });
    }
  });

  it("trabajando: proyecto y actividad corta", () => {
    const act = (n: number) => etiqueta("p", n, 0, null).actividad;
    expect([4, 5, 6, 7, 9, 15, 16, 17].map(act)).toEqual([
      "Leyendo",
      "Escribiendo",
      "Terminal",
      "Web",
      "Planificando",
      "Esperando un programa",
      "Subiendo",
      "Con subagentes",
    ]);
  });

  it("te espera: 'Te pide permiso' o 'Te preguntó' y sin actividad", () => {
    expect(etiqueta("p", 13, 0, null)).toMatchObject({
      espera: "Te pide permiso",
      actividad: null,
    });
    expect(etiqueta("p", 14, 0, null)).toMatchObject({
      espera: "Te preguntó",
      actividad: null,
    });
  });

  it("con errores en trabajo; isotipo solo para la cuenta Demo Org", () => {
    expect(etiqueta("p", 6, 1, "personal").errores).toBe(true);
    expect(etiqueta("p", 18, 1, "personal").errores).toBe(false);
    expect(etiqueta("p", 6, 0, "demo").demo).toBe(true);
    expect(etiqueta("p", 6, 0, "personal").demo).toBe(false);
  });

  it("los textos de la escena no dicen 'Inactivo' ni 'personal'", () => {
    const todos = [
      "barra.libres",
      "barra.teEsperan",
      "barra.trabajando",
      "distintivo.conErrores",
      "nota.cerrado",
    ] as const;
    for (const k of todos) expect(t(k)).not.toMatch(/inactiv|personal/i);
  });
});

describe("puestos estables", () => {
  it("cada agente conserva su puesto mientras exista; los nuevos toman el libre más bajo", () => {
    const p1 = asignarPuestos({}, ["a", "b", "c"]);
    expect(p1).toEqual({ a: 0, b: 1, c: 2 });
    const p2 = asignarPuestos(p1, ["c", "d", "a"]);
    expect(p2).toEqual({ c: 2, d: 1, a: 0 });
    expect(asignarPuestos(p2, ["a", "c", "d"])).toEqual(p2);
  });

  it("adaptar mantiene el puesto entre lecturas aunque cambie el orden del motor", () => {
    const [r1, r2] = lecturas([
      [agente("x", 5), agente("y", 3)],
      [agente("y", 13), agente("x", 11)],
    ]);
    const puesto = (r: typeof r1, id: string) =>
      r.vistas.find((v) => v.id === id)?.seatIndex;
    expect(puesto(r2, "x")).toBe(puesto(r1, "x"));
    expect(puesto(r2, "y")).toBe(puesto(r1, "y"));
  });
});

describe("llegada y salida", () => {
  it("al cargar la página nadie camina desde la puerta; los que aparecen después sí", () => {
    const [r1, r2] = lecturas([
      [agente("a", 1), agente("b", 6)],
      [agente("a", 2), agente("b", 6), agente("c", 1)],
    ]);
    expect(r1.vistas.map((v) => [v.id, v.origen])).toEqual([
      ["a", "lugar"],
      ["b", "lugar"],
    ]);
    expect(r2.vistas.find((v) => v.id === "c")?.origen).toBe("puerta");
    expect(r2.vistas.find((v) => v.id === "a")?.origen).toBe("lugar");
  });

  it("12 camina a la puerta; cuando sale ya no se dibuja", () => {
    const [r1, r2] = lecturas([[agente("a", 6)], [agente("a", 12)]]);
    expect(r1.vistas[0].destino).toBe("escritorio");
    expect(r2.vistas[0].destino).toBe("salida");
    const [, r3] = lecturas(
      [[agente("a", 6)], [agente("a", 12)]],
      new Set(["a"]),
    );
    expect(r3.vistas).toEqual([]);
  });

  it("un agente que se cierra (21) estando en escena camina a la puerta antes de desaparecer", () => {
    const [, r2] = lecturas([[agente("a", 6)], [agente("a", 21)]]);
    expect(r2.vistas.map((v) => [v.id, v.destino])).toEqual([["a", "salida"]]);
    expect(r2.cerrados).toEqual([]); // no note while walking out
  });

  it("un cerrado que ya estaba cerrado al cargar no aparece en escena", () => {
    const [r1] = lecturas([[agente("a", 21)]]);
    expect(r1.vistas).toEqual([]);
  });

  it("al reabrirse después de salir vuelve a entrar por la puerta", () => {
    let estado = estadoInicial();
    const salidos = new Set<string>();
    const r1 = adaptar([agente("a", 6)], estado, T0, salidos);
    estado = r1.estado;
    const r2 = adaptar([agente("a", 21)], estado, T0 + 2000, salidos);
    estado = r2.estado;
    salidos.add("a"); // the character reached the door
    const r3 = adaptar([agente("a", 21)], estado, T0 + 4000, salidos);
    estado = r3.estado;
    expect(r3.vistas).toEqual([]);
    const r4 = adaptar([agente("a", 20)], estado, T0 + 6000, salidos);
    expect(r4.vistas[0]).toMatchObject({
      origen: "puerta",
      destino: "escritorio",
    });
    expect(r4.reentradas).toEqual(["a"]);
  });
});

describe("escritorios de los cerrados (21)", () => {
  const conPregunta = (desdeMin: number) =>
    agente("q", 21, {
      pregunta_pendiente: "¿Lo subo a producción?",
      cierre: {
        motivo: "proceso_terminado",
        desde: new Date(T0 - desdeMin * MIN).toISOString(),
      },
    });
  const sinPregunta = (desdeMin: number) =>
    agente("s", 21, {
      cierre: {
        motivo: "proceso_terminado",
        desde: new Date(T0 - desdeMin * MIN).toISOString(),
      },
    });

  it("con pregunta pendiente: el escritorio muestra la nota (sin límite de tiempo)", () => {
    const [r] = lecturas([[conPregunta(600)]]);
    expect(r.cerrados).toEqual([
      {
        seatIndex: 0,
        sessionId: "q",
        proyecto: "vive-demo",
        cuenta: "personal",
        pregunta: "¿Lo subo a producción?",
      },
    ]);
  });

  it("sin pregunta: el escritorio queda vacío y reservado una hora; después se libera", () => {
    const [antes] = lecturas([[sinPregunta(30), agente("n", 6)]]);
    expect(antes.cerrados).toMatchObject([
      { sessionId: "s", pregunta: null, seatIndex: 0 },
    ]);
    expect(antes.vistas[0].seatIndex).toBe(1); // the new agent does not take the kept desk
    const [despues] = lecturas([[sinPregunta(61), agente("n", 6)]]);
    expect(despues.cerrados).toEqual([]);
    expect(despues.vistas[0].seatIndex).toBe(0); // desk freed
  });
});

describe("sofá de la sala de descanso", () => {
  it("los primeros se sientan en el sofá; si hay más agentes que lugares, los demás quedan de pie cerca", () => {
    const n = ASIENTOS_SOFA.length + 2;
    const ids = Array.from({ length: n }, (_, i) => ({
      id: `a${i}`,
      seatIndex: i,
    }));
    const l = asignarDescanso(ids);
    const sofa = Object.values(l).filter((x) => x.tipo === "sofa");
    const cerca = Object.values(l).filter((x) => x.tipo === "cerca");
    expect(sofa).toHaveLength(ASIENTOS_SOFA.length);
    expect(cerca).toHaveLength(2);
    expect(new Set(sofa.map((x) => x.indice)).size).toBe(ASIENTOS_SOFA.length);
    expect(l.a0).toEqual({ tipo: "sofa", indice: 0 });
    expect(l[`a${n - 1}`].tipo).toBe("cerca");
  });

  it("adaptar da a cada agente que descansa (19) su lugar; al pasar a 20 vuelve al escritorio", () => {
    const lista = Array.from({ length: 6 }, (_, i) => agente(`r${i}`, 19));
    const [r1, r2] = lecturas([lista, [agente("r0", 20), ...lista.slice(1)]]);
    expect(r1.vistas.filter((v) => v.descanso?.tipo === "sofa")).toHaveLength(
      4,
    );
    expect(r1.vistas.filter((v) => v.descanso?.tipo === "cerca")).toHaveLength(
      2,
    );
    const r0 = r2.vistas.find((v) => v.id === "r0");
    expect(r0).toMatchObject({ destino: "escritorio", descanso: null });
  });
});

describe("adaptar", () => {
  it("lleva etiqueta, pregunta, lo que pide, espera larga y ayudantes", () => {
    const [r] = lecturas([
      [
        agente("p", 13, {
          espera: {
            tipo: "tu_permiso",
            evidencia: { herramienta: "Bash", comando: "git push" },
          },
          estado: {
            numero: 13,
            nombre: "Te espera: permiso",
            desde: new Date(T0 - ESPERA_LARGA_MS).toISOString(),
          },
          agente: {
            session_id: "p",
            proyecto: "E:\\vive-demo",
            cuenta: "demo",
          },
        }),
        agente("q", 14, {
          pregunta_pendiente: "¿Lo subo?",
          subagentes_activos: 2,
        }),
      ],
    ]);
    const [p, q] = r.vistas;
    expect(p).toMatchObject({
      lePide: "Bash: git push",
      stuck: true,
      pose: "brazoAlzado",
    });
    expect(p.etiqueta).toMatchObject({ espera: "Te pide permiso", demo: true });
    expect(q).toMatchObject({
      preguntaPendiente: "¿Lo subo?",
      pose: "mirarCamara",
    });
    expect(q.subagents).toHaveLength(2);
  });

  it("cuenta te esperan, trabajando y libres sin los cerrados", () => {
    const lista = [13, 14, 5, 17, 11, 19, 21].map((n, i) => agente(`a${i}`, n));
    expect(contar3d(lista)).toEqual({ espera: 2, trabajando: 2, libres: 2 });
  });
});

describe("distribución", () => {
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
});
