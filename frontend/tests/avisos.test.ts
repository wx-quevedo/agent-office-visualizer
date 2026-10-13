import { describe, expect, it } from "vitest";
import {
  CONFIG_INICIAL,
  ColaVoz,
  DetectorAvisos,
  EsperaResumenes,
  avisable,
  construirAviso,
  elegirVoz,
  nombreAviso,
  textoParaLeer,
  type ConfigAvisos,
} from "@/components/avisos/deteccion";
import type { Agente } from "@/components/oficina/logica";

const T0 = Date.parse("2026-10-10T18:00:00Z");
const ACTIVOS: ConfigAvisos = { ...CONFIG_INICIAL, activos: true };

function agente(
  id: string,
  numero: number,
  extra: Partial<Agente> & { proyecto?: string; cuenta?: string } = {},
): Agente {
  const { proyecto, cuenta, ...resto } = extra;
  return {
    agente: {
      session_id: id,
      proyecto: proyecto ?? "E:\\vive-demo",
      cuenta: cuenta ?? "demo",
    },
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
      contexto_usado_pct: 0,
      errores_seguidos: 0,
      errores_motivo: null,
    },
    eventos_recientes: [],
    ...resto,
  };
}

const permiso = (id = "a1") =>
  agente(id, 13, {
    espera: {
      tipo: "tu_permiso",
      evidencia: { herramienta: "Bash", comando: "git push origin dev" },
    },
  });

/** Observes the same list every second from `desde` to `hasta` (ms after T0). */
function correr(
  d: DetectorAvisos,
  lista: Agente[],
  desde: number,
  hasta: number,
  config = ACTIVOS,
) {
  const avisos = [];
  for (let t = desde; t <= hasta; t += 1000)
    avisos.push(...d.observar(lista, T0 + t, config));
  return avisos;
}

describe("detección de avisos", () => {
  it("al cargar no avisa: solo registra los estados actuales", () => {
    const d = new DetectorAvisos();
    expect(
      correr(
        d,
        [permiso(), agente("b", 14, { pregunta_pendiente: "¿Sigo?" })],
        0,
        60_000,
      ),
    ).toEqual([]);
  });

  it("avisa al pasar a 13 con lo que pide y la cuenta", () => {
    const d = new DetectorAvisos();
    d.observar([agente("a1", 6)], T0, ACTIVOS);
    const avisos = correr(d, [permiso()], 1000, 5000);
    expect(avisos).toHaveLength(1);
    expect(avisos[0].tipo).toBe("permiso");
    expect(avisos[0].voz).toBe(
      "vive-demo te pide permiso. Bash: git push origin dev. Responde en VS Code.",
    );
    expect(avisos[0].titulo).toBe("vive-demo te pide permiso");
    expect(avisos[0].cuerpo).toBe(
      "Bash: git push origin dev\nResponde en VS Code.\nCuenta Demo Org",
    );
    expect(avisos[0].tag).toBe("agente-a1");
    expect(avisos[0].notificar).toBe(true);
  });

  it("avisa al pasar a 14 y lee la pregunta sin código, URLs ni rutas", () => {
    const d = new DetectorAvisos();
    d.observar([agente("a1", 3)], T0, ACTIVOS);
    const q =
      "Revisé `config.py` en E:\\vive-demo\\src\\app\\config.py y https://example.com/doc. ¿Lo subo a producción?";
    const avisos = correr(
      d,
      [agente("a1", 14, { pregunta_pendiente: q })],
      1000,
      5000,
    );
    expect(avisos).toHaveLength(1);
    expect(avisos[0].voz).toBe(
      "vive-demo te hizo una pregunta. Revisé en y. ¿Lo subo a producción?",
    );
  });

  it("avisa al pasar a 11 sin pregunta, solo con voz por defecto", () => {
    const d = new DetectorAvisos();
    d.observar([agente("a1", 5)], T0, ACTIVOS);
    const avisos = correr(d, [agente("a1", 11)], 1000, 5000);
    expect(avisos.map((a) => [a.tipo, a.voz, a.notificar])).toEqual([
      ["termino", "vive-demo terminó", false],
    ]);
    // With a pending question, 11 does not count as "terminó".
    const d2 = new DetectorAvisos();
    d2.observar([agente("a1", 5)], T0, ACTIVOS);
    expect(
      correr(d2, [agente("a1", 11, { pregunta_pendiente: "¿Y?" })], 1000, 5000),
    ).toEqual([]);
  });

  it("solo avisa si el nuevo estado se mantiene 3 s (13 → 6 no cuenta)", () => {
    const d = new DetectorAvisos();
    d.observar([agente("a1", 6)], T0, ACTIVOS);
    expect(d.observar([permiso()], T0 + 1000, ACTIVOS)).toEqual([]);
    expect(d.observar([permiso()], T0 + 3000, ACTIVOS)).toEqual([]); // 2 s
    expect(d.observar([agente("a1", 6)], T0 + 3500, ACTIVOS)).toEqual([]); // back: flicker
    expect(correr(d, [agente("a1", 6)], 4000, 10_000)).toEqual([]);
    // Holding 13 for 3 s does alert.
    expect(correr(d, [permiso()], 11_000, 13_000)).toEqual([]);
    expect(d.observar([permiso()], T0 + 14_000, ACTIVOS)).toHaveLength(1);
  });

  it("enfriamiento de 30 s por agente y evento", () => {
    const d = new DetectorAvisos();
    d.observar([agente("a1", 6)], T0, ACTIVOS);
    expect(correr(d, [permiso()], 1000, 5000)).toHaveLength(1); // at 4 s
    expect(correr(d, [agente("a1", 6)], 6000, 10_000)).toEqual([]);
    expect(correr(d, [permiso()], 11_000, 20_000)).toEqual([]); // 13 again at 14 s: cooling down
    expect(correr(d, [agente("a1", 6)], 21_000, 30_000)).toEqual([]);
    expect(correr(d, [permiso()], 40_000, 45_000)).toHaveLength(1); // 43 s > 4 s + 30 s
  });

  it("recordatorio cada N minutos mientras sigue en 13 o 14; nunca si se elige", () => {
    const d = new DetectorAvisos();
    d.observar([agente("a1", 6)], T0, ACTIVOS);
    const lista = [permiso()];
    const avisos = correr(d, lista, 1000, 4000 + 10 * 60_000);
    // First alert at 4 s, reminders at 5 min 4 s and 10 min 4 s.
    expect(avisos.map((a) => a.recordatorio)).toEqual([false, true, true]);
    expect(
      avisos[1].voz.startsWith("Sigue esperando: vive-demo te pide permiso"),
    ).toBe(true);
    expect(avisos[1].tag).toBe(avisos[0].tag); // replaces the notification

    const nunca: ConfigAvisos = { ...ACTIVOS, recordatorioMin: 0 };
    const d2 = new DetectorAvisos();
    d2.observar([agente("a1", 6)], T0, nunca);
    expect(correr(d2, lista, 1000, 4000 + 11 * 60_000, nunca)).toHaveLength(1);
  });

  it("un agente que ya esperaba al cargar recibe su recordatorio un intervalo después", () => {
    const d = new DetectorAvisos();
    const avisos = correr(d, [permiso()], 0, 5 * 60_000);
    expect(avisos.map((a) => a.recordatorio)).toEqual([true]);
  });

  it("nunca avisa de sesiones prueba-", () => {
    const d = new DetectorAvisos();
    d.observar([agente("prueba-x", 6)], T0, ACTIVOS);
    expect(correr(d, [permiso("prueba-x")], 1000, 10 * 60_000)).toEqual([]);
  });

  it("nunca avisa de un proyecto prueba- aunque el id sea un UUID (Prompt 43)", () => {
    const id = "3f1c2a9e-8b7d-4c6e-9a1f-0d2b3c4e5f60";
    const conPregunta = (n: number) =>
      agente(id, n, {
        proyecto: "E:/proyectos/prueba-chat",
        pregunta_pendiente: n === 14 ? "¿Sigo?" : null,
      });
    expect(avisable(conPregunta(14))).toBe(false);
    const d = new DetectorAvisos();
    d.observar([conPregunta(6)], T0, ACTIVOS);
    expect(correr(d, [conPregunta(14)], 1000, 10 * 60_000)).toEqual([]);
    // the same session in a normal project does alert
    const otro = agente(id, 14, {
      proyecto: "E:/proyectos/mi-prueba",
      pregunta_pendiente: "¿Sigo?",
    });
    expect(avisable(otro)).toBe(true);
    const d2 = new DetectorAvisos();
    d2.observar(
      [agente(id, 6, { proyecto: "E:/proyectos/mi-prueba" })],
      T0,
      ACTIVOS,
    );
    expect(correr(d2, [otro], 1000, 5000).map((x) => x.tipo)).toEqual([
      "pregunta",
    ]);
  });

  it("no avisa por las sesiones del equipo: ni estado 14, ni permiso, ni recordatorios (Prompt 43)", () => {
    const delEquipo = (n: number, extra: Partial<Agente> = {}): Agente => {
      const a = agente("orq-1", n, {
        proyecto: "E:/proyectos/tienda-web",
        pregunta_pendiente: n === 14 ? "¿Qué catálogo uso?" : null,
        ...extra,
      });
      return { ...a, agente: { ...a.agente, proyecto_equipo: "p1" } };
    };
    expect(avisable(delEquipo(14))).toBe(false);
    const d = new DetectorAvisos();
    d.observar([delEquipo(6)], T0, ACTIVOS);
    expect(correr(d, [delEquipo(14)], 1000, 20 * 60_000)).toEqual([]);
    const d2 = new DetectorAvisos();
    d2.observar([delEquipo(6)], T0, ACTIVOS);
    const pide = delEquipo(13, {
      espera: {
        tipo: "tu_permiso",
        evidencia: { herramienta: "Bash", comando: "git push" },
      },
    });
    expect(correr(d2, [pide], 1000, 20 * 60_000)).toEqual([]);
    // the same agent without proyecto_equipo alerts as before
    const d3 = new DetectorAvisos();
    d3.observar([agente("orq-1", 6)], T0, ACTIVOS);
    expect(
      correr(
        d3,
        [agente("orq-1", 14, { pregunta_pendiente: "¿Sigo?" })],
        1000,
        5000,
      ).map((x) => x.tipo),
    ).toEqual(["pregunta"]);
  });

  it("no avisa con los avisos desactivados ni con el evento apagado", () => {
    const d = new DetectorAvisos();
    d.observar([agente("a1", 6)], T0, CONFIG_INICIAL);
    expect(correr(d, [permiso()], 1000, 5000, CONFIG_INICIAL)).toEqual([]);
    const sinPermiso: ConfigAvisos = {
      ...ACTIVOS,
      eventos: { ...ACTIVOS.eventos, permiso: false },
    };
    const d2 = new DetectorAvisos();
    d2.observar([agente("a1", 6)], T0, sinPermiso);
    expect(correr(d2, [permiso()], 1000, 5000, sinPermiso)).toEqual([]);
  });

  it("cerrado con pregunta pendiente solo si está activado", () => {
    const cerrado = agente("a1", 21, { pregunta_pendiente: "¿Lo subo?" });
    const d = new DetectorAvisos();
    d.observar(
      [agente("a1", 14, { pregunta_pendiente: "¿Lo subo?" })],
      T0,
      ACTIVOS,
    );
    expect(correr(d, [cerrado], 1000, 5000)).toEqual([]);
    const con: ConfigAvisos = {
      ...ACTIVOS,
      eventos: { ...ACTIVOS.eventos, cerrado: true },
    };
    const d2 = new DetectorAvisos();
    d2.observar(
      [agente("a1", 14, { pregunta_pendiente: "¿Lo subo?" })],
      T0,
      con,
    );
    const avisos = correr(d2, [cerrado], 1000, 5000, con);
    expect(avisos.map((a) => a.voz)).toEqual([
      "vive-demo se cerró con una pregunta pendiente",
    ]);
  });

  it("un agente nuevo que aparece esperando sí avisa", () => {
    const d = new DetectorAvisos();
    d.observar([], T0, ACTIVOS);
    expect(correr(d, [permiso()], 1000, 5000)).toHaveLength(1);
  });
});

describe("nombres y textos", () => {
  it("agrega la cuenta cuando dos agentes comparten proyecto", () => {
    const a = agente("a", 13, { cuenta: "demo" });
    const b = agente("b", 6, { cuenta: "personal" });
    expect(nombreAviso(a, [a, b])).toBe("vive-demo, cuenta Demo Org");
    expect(nombreAviso(b, [a, b])).toBe("vive-demo"); // the personal account is never named
    expect(nombreAviso(a, [a])).toBe("vive-demo");
  });

  it("recorta lo que se lee", () => {
    expect(textoParaLeer("x".repeat(300), 200)).toHaveLength(200);
    expect(textoParaLeer("```py\nprint(1)\n```\n¿Listo?", 200)).toBe("¿Listo?");
  });

  it("prefiere es-MX, luego es-US, luego cualquier es-*", () => {
    const v = (lang: string) => ({ name: lang, lang, voiceURI: `v-${lang}` });
    expect(
      elegirVoz([v("en-US"), v("es-ES"), v("es-US"), v("es-MX")], null)?.lang,
    ).toBe("es-MX");
    expect(elegirVoz([v("es-ES"), v("es-US")], null)?.lang).toBe("es-US");
    expect(elegirVoz([v("en-US"), v("es-ES")], null)?.lang).toBe("es-ES");
    expect(elegirVoz([v("es-MX"), v("es-ES")], "v-es-ES")?.lang).toBe("es-ES");
    expect(elegirVoz([v("en-US")], null)).toBeNull();
  });
});

describe("cola de voz", () => {
  it("dice los avisos uno detrás de otro, sin cortarse", () => {
    const dichos: string[] = [];
    const fines: Array<() => void> = [];
    const cola = new ColaVoz<string>((t, fin) => {
      dichos.push(t);
      fines.push(fin);
    });
    cola.encolar("uno");
    cola.encolar("dos");
    cola.encolar("tres");
    expect(dichos).toEqual(["uno"]); // "dos" waits for "uno" to end
    expect(cola.enCola).toBe(2);
    fines[0]();
    fines[0](); // a duplicated end does not skip an item
    expect(dichos).toEqual(["uno", "dos"]);
    fines[1]();
    expect(dichos).toEqual(["uno", "dos", "tres"]);
    fines[2]();
    expect(cola.hablando).toBe(false);
  });
});

// -- etapa 2.4: avisos resumidos por el agente auxiliar -----------------------------

describe("avisos resumidos", () => {
  const frase =
    "vive-demo quiere subir los cambios al repositorio y necesita tu permiso.";
  const conResumen = (estado: "listo" | "fallo" | "pendiente" | "apagado") =>
    agente("r1", 13, {
      espera: permiso().espera,
      resumenes: {
        permiso: {
          clave: "r1:permiso:x",
          estado,
          texto: estado === "listo" ? frase : null,
        },
      },
    });

  it("con el resumen listo, la voz lo lee y la notificación lo pone primero", () => {
    const d = new DetectorAvisos();
    d.observar([agente("r1", 4)], T0, ACTIVOS);
    const [aviso] = correr(d, [conResumen("listo")], 1000, 5000);
    expect(aviso.voz).toBe(`${frase} Responde en VS Code.`);
    expect(aviso.voz).not.toContain("git push");
    expect(aviso.cuerpo.split("\n")[0]).toBe(frase);
    expect(aviso.cuerpo).toContain("Bash: git push origin dev");
    expect(aviso.esperaResumen).toBe(false);
  });

  it("espera el resumen hasta 8 s y después usa el texto de siempre", () => {
    const d = new DetectorAvisos();
    const espera = new EsperaResumenes();
    d.observar([agente("r1", 4)], T0, ACTIVOS);
    const [aviso] = correr(d, [conResumen("pendiente")], 1000, 5000);
    expect(aviso.esperaResumen).toBe(true);
    espera.agregar(aviso, T0 + 5000);
    expect(
      espera.listos([conResumen("pendiente")], T0 + 9000, ACTIVOS),
    ).toEqual([]);
    // Llega el resumen: sale con la frase.
    const [listo] = espera.listos([conResumen("listo")], T0 + 10000, ACTIVOS);
    expect(listo.voz.startsWith(frase)).toBe(true);
    expect(espera.enEspera).toBe(0);
    // Sin resumen en 8 s: sale el texto técnico, sin esperar más.
    espera.agregar(aviso, T0 + 20000);
    const [tarde] = espera.listos(
      [conResumen("pendiente")],
      T0 + 28000,
      ACTIVOS,
    );
    expect(tarde.voz).toContain("git push origin dev");
  });

  it("si el auxiliar falla, los resúmenes están apagados o el agente se fue, no espera", () => {
    const espera = new EsperaResumenes();
    const d = new DetectorAvisos();
    d.observar([agente("r1", 4)], T0, ACTIVOS);
    const [aviso] = correr(d, [conResumen("pendiente")], 1000, 5000);
    for (const lista of [[conResumen("fallo")], [conResumen("apagado")], []]) {
      espera.agregar(aviso, T0 + 5000);
      const [salio] = espera.listos(lista, T0 + 5100, ACTIVOS);
      expect(salio.voz).toContain("git push origin dev");
    }
    const sinCampo = construirAviso("permiso", permiso(), [permiso()], ACTIVOS);
    expect(sinCampo.esperaResumen).toBe(false);
  });

  it("un atasco nuevo avisa una vez, con su resumen", () => {
    const d = new DetectorAvisos();
    const trabajando = agente("r1", 4);
    d.observar([trabajando], T0, ACTIVOS);
    const atascado = agente("r1", 4, {
      atasco: {
        tipo: "error_repetido",
        motivo: "Repite el mismo error 3 veces (Bash)",
        desde: new Date(T0).toISOString(),
        ultimos_intentos: [],
        ultimo_error: null,
      },
      resumenes: {
        atasco: {
          clave: "r1:atasco:x",
          estado: "listo",
          texto:
            "vive-demo parece atascado: repite el mismo error al compilar.",
        },
      },
    });
    const avisos = correr(d, [atascado], 1000, 60000);
    expect(avisos.map((a) => a.tipo)).toEqual(["atasco"]);
    expect(avisos[0].voz).toBe(
      "vive-demo parece atascado: repite el mismo error al compilar.",
    );
    expect(avisos[0].titulo).toBe("vive-demo parece atascado");
    const apagado = new DetectorAvisos();
    apagado.observar([trabajando], T0, ACTIVOS);
    const sinAtasco = {
      ...ACTIVOS,
      eventos: { ...ACTIVOS.eventos, atasco: false },
    };
    expect(correr(apagado, [atascado], 1000, 5000, sinAtasco)).toEqual([]);
  });
});
