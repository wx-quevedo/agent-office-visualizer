import { describe, expect, it } from "vitest";
import { dondeResponder } from "@/components/avisos/deteccion";
import type { Agente } from "@/components/oficina/logica";
import {
  CONFIG_POR_DEFECTO,
  pideConfirmacion,
  segundosRestantes,
  sePuedeDecidir,
  textoRestante,
  textoSinBotones,
  type Permiso,
} from "@/components/permisos/logica";

const LISTA = CONFIG_POR_DEFECTO.confirmar;

function permiso(extra: Partial<Permiso> = {}): Permiso {
  return {
    id: "abc12345",
    session_id: "prueba-1",
    herramienta: "Bash",
    detalle: "git status",
    cuenta: "personal",
    proyecto: "demo",
    creada: "2026-10-10T18:00:00Z",
    esperando: true,
    vence: "2026-10-10T18:01:30Z",
    segundos_restantes: 90,
    estado: "pendiente",
    motivo: null,
    dispositivo: null,
    decidida: null,
    ...extra,
  };
}

describe("comandos que piden confirmación en el celular", () => {
  it.each([
    "rm -rf node_modules",
    "cd app && rm build.log",
    "sudo rm /tmp/x",
    "git push origin main",
    "git status; git push",
    "npm run deploy",
    "Remove-Item -Recurse dist",
    "del /q salida.txt",
    "git reset --hard HEAD~1",
    "ls | xargs rm",
  ])("pide confirmación: %s", (cmd) => {
    expect(pideConfirmacion("Bash", cmd, LISTA)).toBe(true);
  });

  it.each([
    "git status",
    "npm run build -- --format=json",
    "echo deployment",
    "git pull",
    "cat formato.txt",
    "ls -la",
  ])("no pide confirmación: %s", (cmd) => {
    expect(pideConfirmacion("Bash", cmd, LISTA)).toBe(false);
  });

  it("solo para comandos (Bash, PowerShell), con la lista configurable", () => {
    expect(pideConfirmacion("Write", "rm.txt", LISTA)).toBe(false);
    expect(pideConfirmacion("PowerShell", "Remove-Item x", LISTA)).toBe(true);
    expect(pideConfirmacion("Bash", "make publicar", ["make publicar"])).toBe(
      true,
    );
    expect(pideConfirmacion("Bash", "rm x", [])).toBe(false);
  });
});

describe("tiempo y estado de la solicitud", () => {
  const T = Date.parse("2026-10-10T18:00:05Z");

  it("cuenta el tiempo que queda", () => {
    expect(segundosRestantes(permiso(), T)).toBe(85);
    expect(textoRestante(85)).toBe("1:25");
    expect(textoRestante(5)).toBe("0:05");
    expect(
      segundosRestantes(permiso(), Date.parse("2026-10-10T18:05:00Z")),
    ).toBe(0);
  });

  it("solo se decide si está pendiente y el hook espera", () => {
    expect(sePuedeDecidir(permiso())).toBe(true);
    expect(sePuedeDecidir(permiso({ esperando: false }))).toBe(false);
    expect(sePuedeDecidir(permiso({ estado: "vencida" }))).toBe(false);
    expect(sePuedeDecidir(null)).toBe(false);
  });

  it("textos cuando no hay botones", () => {
    expect(textoSinBotones(permiso({ esperando: false }))).toBe(
      "Responde en VS Code.",
    );
    expect(textoSinBotones(permiso({ estado: "vencida" }))).toBe(
      "Responde en VS Code.",
    );
    expect(textoSinBotones(permiso({ estado: "resuelta_fuera" }))).toBe(
      "Ya se respondió en VS Code.",
    );
    expect(
      textoSinBotones(
        permiso({ estado: "rechazada", dispositivo: "celular", motivo: "No" }),
      ),
    ).toBe("Rechazado desde el celular: No");
    expect(
      textoSinBotones(permiso({ estado: "aprobada", dispositivo: "pc" })),
    ).toBe("Aprobado desde la PC.");
  });
});

describe("política por defecto", () => {
  it("espera solo cuando estás en el celular", () => {
    expect(CONFIG_POR_DEFECTO.politica).toBe("solo_en_el_celular");
  });
});

describe("aviso de permiso", () => {
  const a = (p: Permiso | null) => ({ permiso: p }) as unknown as Agente;

  it("dice si puedes responder desde la oficina", () => {
    expect(dondeResponder(a(permiso()))).toBe(
      "Puedes responder desde la oficina.",
    );
    expect(dondeResponder(a(permiso({ esperando: false })))).toBe(
      "Responde en VS Code.",
    );
    expect(dondeResponder(a(null))).toBe("Responde en VS Code.");
    // the phone left: the office stopped waiting
    expect(dondeResponder(a(permiso({ esperando: false, vence: null })))).toBe(
      "Responde en VS Code.",
    );
  });
});
