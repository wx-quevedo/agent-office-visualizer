"use client";

/**
 * What an agent in state 13 asks for, and the Approve / Reject buttons while
 * the hook waits for the office (with the time left). Reject takes an
 * optional short reason that Claude receives. On the phone, commands that
 * delete or upload something ask for confirmation before approving. When
 * the office cannot answer (policy, time up, answered in VS Code) it says so.
 */

import { useState, useSyncExternalStore, type MouseEvent } from "react";
import { fraseDePermiso, haceTiempo } from "@/components/ficha/logica";
import { dispositivo } from "@/components/oficina/logica";
import {
  decidirPermiso,
  pideConfirmacion,
  segundosRestantes,
  sePuedeDecidir,
  textoRestante,
  textoSinBotones,
  type Permiso,
} from "./logica";
import { useConfigPermisos } from "./useConfigPermisos";
import s from "./permisos.module.css";

function suscribirAncho(f: () => void): () => void {
  window.addEventListener("resize", f);
  return () => window.removeEventListener("resize", f);
}

/** "pc" or "celular" (same rule as the presence heartbeat). */
export function useDispositivo(): "pc" | "celular" {
  return useSyncExternalStore(
    suscribirAncho,
    () => dispositivo(window.innerWidth, navigator.userAgent),
    () => "pc",
  );
}

type Fase = "botones" | "confirmar" | "motivo";

export default function PanelPermiso({
  permiso,
  ahora,
  variante = "caja",
}: {
  permiso: Permiso;
  ahora: number;
  /** "ficha": the agent card's version (one clear sentence, blue card). */
  variante?: "caja" | "ficha";
}) {
  const ficha = variante === "ficha";
  const disp = useDispositivo();
  const config = useConfigPermisos();
  const [fase, setFase] = useState<Fase>("botones");
  const [motivo, setMotivo] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Decision taken here, shown until the next read brings it.
  const [hecho, setHecho] = useState<Permiso | null>(null);

  const actual = hecho && hecho.id === permiso.id ? hecho : permiso;
  const restante = segundosRestantes(actual, ahora);
  const puede = sePuedeDecidir(actual) && restante > 0 && !hecho;
  const confirmar =
    disp === "celular" &&
    pideConfirmacion(actual.herramienta, actual.detalle, config.confirmar);

  const parar = (e: MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const enviar = async (decision: "aprobar" | "rechazar") => {
    setEnviando(true);
    setError(null);
    const r = await decidirPermiso(
      actual.id,
      decision,
      decision === "rechazar" ? motivo : null,
      disp,
    );
    setEnviando(false);
    if (r.ok && r.permiso) {
      setHecho(r.permiso);
      setFase("botones");
    } else {
      setError(r.error ?? "No se pudo enviar.");
    }
  };

  return (
    <section
      className={ficha ? `${s.permiso} ${s.ficha}` : s.permiso}
      aria-label="Permiso solicitado"
      onClick={(e) => e.stopPropagation()}
    >
      {ficha ? (
        <>
          <h3 className={s.fichaEtiqueta}>
            {puede ? "Te pide permiso" : "Pidió permiso"} ·{" "}
            {haceTiempo(actual.creada, ahora)}
          </h3>
          <p className={s.fichaFrase}>
            {fraseDePermiso(actual.herramienta, actual.detalle)}
          </p>
        </>
      ) : (
        <div className={s.titulo}>
          Pide permiso para usar {actual.herramienta}
          <small>
            {actual.herramienta === "Bash" ||
            actual.herramienta === "PowerShell"
              ? "Comando completo"
              : "Lo que pide"}
          </small>
        </div>
      )}
      <pre className={s.bloque}>{actual.detalle}</pre>

      {puede ? (
        <>
          <div className={s.restante}>
            Quedan <b>{textoRestante(restante)}</b> para responder desde aquí;
            después responde VS Code.
          </div>
          {/* Only the last 30 s are announced (the count changes every 2 s). */}
          <span className={s.oculto} aria-live="polite">
            {restante <= 30
              ? "Quedan menos de 30 segundos para responder."
              : ""}
          </span>
          {fase === "botones" && (
            <div className={s.botones}>
              <button
                type="button"
                className={`${s.boton} ${s.aprobar}`}
                disabled={enviando}
                onClick={(e) => {
                  parar(e);
                  if (confirmar) setFase("confirmar");
                  else void enviar("aprobar");
                }}
              >
                Aprobar
              </button>
              <button
                type="button"
                className={s.boton}
                disabled={enviando}
                onClick={(e) => {
                  parar(e);
                  setFase("motivo");
                }}
              >
                {ficha ? "Rechazar con motivo" : "Rechazar"}
              </button>
            </div>
          )}
          {fase === "confirmar" && (
            <>
              <div className={s.alerta} role="alert">
                Este comando borra o sube algo. ¿Lo apruebas de todas formas?
              </div>
              <div className={s.botones}>
                <button
                  type="button"
                  className={`${s.boton} ${s.aprobar}`}
                  disabled={enviando}
                  onClick={(e) => {
                    parar(e);
                    void enviar("aprobar");
                  }}
                >
                  Sí, aprobar
                </button>
                <button
                  type="button"
                  className={s.boton}
                  disabled={enviando}
                  onClick={(e) => {
                    parar(e);
                    setFase("botones");
                  }}
                >
                  Cancelar
                </button>
              </div>
            </>
          )}
          {fase === "motivo" && (
            <>
              <label className={s.campo}>
                Motivo (opcional)
                <small>Claude lo recibe junto con el rechazo.</small>
                <input
                  type="text"
                  maxLength={300}
                  value={motivo}
                  placeholder="Por ejemplo: usa la rama de prueba"
                  onChange={(e) => setMotivo(e.target.value)}
                  onClick={(e) => e.stopPropagation()}
                />
              </label>
              <div className={s.botones}>
                <button
                  type="button"
                  className={`${s.boton} ${s.aprobar}`}
                  disabled={enviando}
                  onClick={(e) => {
                    parar(e);
                    void enviar("rechazar");
                  }}
                >
                  Enviar rechazo
                </button>
                <button
                  type="button"
                  className={s.boton}
                  disabled={enviando}
                  onClick={(e) => {
                    parar(e);
                    setFase("botones");
                  }}
                >
                  Cancelar
                </button>
              </div>
            </>
          )}
          {error && (
            <div className={s.error} role="status">
              {error}
            </div>
          )}
        </>
      ) : (
        <p className={s.vscode}>{textoSinBotones(actual)}</p>
      )}
    </section>
  );
}
