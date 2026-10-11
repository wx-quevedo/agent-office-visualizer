import { describe, expect, it } from "vitest";
import {
  CLAVE_VISITA,
  almacenDisponible,
  motivoApertura,
  debeAbrirDondeQuedamos,
  guardarVisita,
  leerUltimaVisita,
} from "@/components/donde/visita";

const HORA = 3600 * 1000;

function memoria(): Pick<Storage, "getItem" | "setItem"> & {
  datos: Map<string, string>;
} {
  const datos = new Map<string, string>();
  return {
    datos,
    getItem: (k) => datos.get(k) ?? null,
    setItem: (k, v) => void datos.set(k, v),
  };
}

describe("regla de las 8 horas", () => {
  const ahora = Date.parse("2026-10-11T16:00:00Z");

  it("abre Dónde quedamos solo si pasaron más de 8 h", () => {
    expect(debeAbrirDondeQuedamos(ahora - 8 * HORA - 1, ahora)).toBe(true);
    expect(debeAbrirDondeQuedamos(ahora - 8 * HORA, ahora)).toBe(false);
    expect(debeAbrirDondeQuedamos(ahora - 2 * HORA, ahora)).toBe(false);
  });

  it("primera visita del dispositivo: abre; reloj atrasado: no abre", () => {
    expect(debeAbrirDondeQuedamos(null, ahora)).toBe(true);
    expect(debeAbrirDondeQuedamos(ahora + HORA, ahora)).toBe(false);
  });

  it("motivo de apertura: nuevo, 8 horas o nada", () => {
    expect(motivoApertura(null, ahora, true)).toBe("nuevo");
    expect(motivoApertura(ahora - 9 * HORA, ahora, true)).toBe("oficina");
    expect(motivoApertura(ahora - HORA, ahora, true)).toBeNull();
    // Sin almacenamiento la "primera visita" se repetiría: no abre nunca.
    expect(motivoApertura(null, ahora, false)).toBeNull();
    expect(motivoApertura(ahora - 9 * HORA, ahora, false)).toBeNull();
  });

  it("guarda y lee la última visita por dispositivo", () => {
    const m = memoria();
    expect(leerUltimaVisita(m)).toBeNull();
    guardarVisita(ahora, m);
    expect(m.datos.get(CLAVE_VISITA)).toBe(String(ahora));
    expect(leerUltimaVisita(m)).toBe(ahora);
    m.datos.set(CLAVE_VISITA, "basura");
    expect(leerUltimaVisita(m)).toBeNull();
  });

  it("almacenamiento bloqueado: no recuerda y no falla", () => {
    const roto = {
      getItem: () => {
        throw new Error("bloqueado");
      },
      setItem: () => {
        throw new Error("bloqueado");
      },
    };
    expect(() => guardarVisita(ahora, roto)).not.toThrow();
    expect(almacenDisponible(roto)).toBe(false);
    expect(almacenDisponible(null)).toBe(false);
    expect(almacenDisponible(memoria())).toBe(true);
    expect(leerUltimaVisita(roto)).toBeNull();
    expect(leerUltimaVisita(null)).toBeNull();
  });
});
