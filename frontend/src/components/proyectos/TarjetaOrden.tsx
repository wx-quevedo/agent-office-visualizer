"use client";

/**
 * Orders of the orchestrator to the code agents (Prompt 38): the purple card
 * of the chat (number, agent, estimate, text, state, who decided, reason,
 * result; Prompt 39: "Dificultad: 3 de 10") and the buttons to decide one that waits for approval (Aprobar,
 * Editar and Rechazar with a reason). The decision is sent from here with
 * dispositivo "web"; the answered order goes back through `cambio`.
 */

import { useEffect, useId, useRef, useState } from "react";
import { cuando, horaMinuto } from "@/components/ficha/logica";
import { enviarJson, mensajeDe } from "./acciones";
import {
  MAX_MENSAJE,
  MAX_MOTIVO,
  cuerpoAprobar,
  cuerpoRechazar,
  estadoOrden,
  fueEditada,
  ordenLarga,
  quienDecidio,
  textoDificultad,
  textoEstimado,
  tituloOrden,
  type Orden,
} from "./logica";
import s from "./proyectos.module.css";

type Modo = "botones" | "editar" | "rechazar";

export interface PropsDecidir {
  orden: Orden;
  /** The order answered by the server after approving or rejecting it. */
  cambio: (o: Orden) => void;
  /** Whether "Editar" is offered (the inbox only approves or rejects). */
  editar?: boolean;
  etiquetaRechazar?: string;
  /** Id of the title of the order, to name the buttons. */
  describe?: string;
}

/** Aprobar, Editar and Rechazar of an order waiting for approval. */
export function DecidirOrden({
  orden: o,
  cambio,
  editar = true,
  etiquetaRechazar = "Rechazar con motivo",
  describe,
}: PropsDecidir) {
  const id = useId();
  const [modo, setModo] = useState<Modo>("botones");
  const [texto, setTexto] = useState(o.texto);
  const [motivo, setMotivo] = useState("");
  const [faltaMotivo, setFaltaMotivo] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const campo = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (modo !== "botones") campo.current?.focus();
  }, [modo]);

  const ruta = (accion: "aprobar" | "rechazar") =>
    `/api/v1/ordenes/${encodeURIComponent(o.id)}/${accion}`;

  const mandar = async (accion: "aprobar" | "rechazar", cuerpo: unknown) => {
    setEnviando(true);
    setError(null);
    try {
      const nueva = await enviarJson<Orden>(ruta(accion), cuerpo);
      setModo("botones");
      cambio(nueva);
    } catch (e) {
      setError(mensajeDe(e));
    } finally {
      setEnviando(false);
    }
  };

  const aprobar = (conTexto?: string) =>
    void mandar("aprobar", cuerpoAprobar(o, conTexto));

  const rechazar = () => {
    const cuerpo = cuerpoRechazar(motivo);
    if (!cuerpo) {
      setFaltaMotivo(true);
      campo.current?.focus();
      return;
    }
    void mandar("rechazar", cuerpo);
  };

  const cancelar = () => {
    setModo("botones");
    setError(null);
    setFaltaMotivo(false);
  };

  return (
    <div className={s.decidir}>
      {modo === "botones" && (
        <div className={s.botonesOrden}>
          <button
            type="button"
            className={s.botonMorado}
            disabled={enviando}
            aria-describedby={describe}
            onClick={() => aprobar()}
          >
            {enviando ? "Enviando…" : "Aprobar"}
          </button>
          {editar && (
            <button
              type="button"
              className={s.boton}
              disabled={enviando}
              aria-describedby={describe}
              onClick={() => {
                setTexto(o.texto);
                setError(null);
                setModo("editar");
              }}
            >
              Editar
            </button>
          )}
          <button
            type="button"
            className={s.boton}
            disabled={enviando}
            aria-describedby={describe}
            onClick={() => {
              setError(null);
              setModo("rechazar");
            }}
          >
            {etiquetaRechazar}
          </button>
        </div>
      )}
      {modo === "editar" && (
        <div className={s.decidirForm}>
          <label htmlFor={`${id}-texto`} className={s.campoTitulo}>
            Texto de la orden
          </label>
          <textarea
            id={`${id}-texto`}
            ref={campo}
            className={`${s.control} ${s.area}`}
            rows={8}
            maxLength={MAX_MENSAJE}
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
          />
          <div className={s.botonesOrden}>
            <button
              type="button"
              className={s.botonMorado}
              disabled={enviando || !texto.trim()}
              onClick={() => aprobar(texto)}
            >
              {enviando ? "Enviando…" : "Aprobar con cambios"}
            </button>
            <button
              type="button"
              className={s.boton}
              disabled={enviando}
              onClick={cancelar}
            >
              Cancelar
            </button>
          </div>
        </div>
      )}
      {modo === "rechazar" && (
        <div className={s.decidirForm}>
          <label htmlFor={`${id}-motivo`} className={s.campoTitulo}>
            Motivo del rechazo
          </label>
          <textarea
            id={`${id}-motivo`}
            ref={campo}
            className={
              faltaMotivo
                ? `${s.control} ${s.area} ${s.controlError}`
                : `${s.control} ${s.area}`
            }
            rows={3}
            maxLength={MAX_MOTIVO}
            value={motivo}
            required
            aria-required="true"
            aria-invalid={faltaMotivo}
            aria-describedby={`${id}-motivo-error`}
            onChange={(e) => {
              setMotivo(e.target.value);
              if (e.target.value.trim()) setFaltaMotivo(false);
            }}
          />
          <p
            id={`${id}-motivo-error`}
            className={s.errorCampo}
            aria-live="polite"
          >
            {faltaMotivo ? "Escribe el motivo del rechazo." : ""}
          </p>
          <div className={s.botonesOrden}>
            <button
              type="button"
              className={s.botonPeligro}
              disabled={enviando}
              onClick={rechazar}
            >
              {enviando ? "Enviando…" : "Rechazar"}
            </button>
            <button
              type="button"
              className={s.boton}
              disabled={enviando}
              onClick={cancelar}
            >
              Cancelar
            </button>
          </div>
        </div>
      )}
      {error && (
        <p className={s.avisoError} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

export interface PropsTarjeta {
  orden: Orden;
  ahora: number;
  cambio: (o: Orden) => void;
}

/** The purple card of one order inside the chat. */
export function TarjetaOrden({ orden: o, ahora, cambio }: PropsTarjeta) {
  const id = useId();
  const [abierta, setAbierta] = useState(false);
  const e = estadoOrden(o.estado);
  const larga = ordenLarga(o.texto);
  const quien = quienDecidio(o.decidido_por);
  const editada = fueEditada(o);
  return (
    <article
      className={
        o.estado === "por_aprobar" ? `${s.orden} ${s.ordenPendiente}` : s.orden
      }
      aria-labelledby={`${id}-t`}
    >
      <header className={s.ordenCabeza}>
        <h3 id={`${id}-t`} className={s.ordenTitulo}>
          {tituloOrden(o)}
        </h3>
        <span className={`${s.estado} ${s[e.tono]}`}>{e.texto}</span>
      </header>
      {o.titulo && <p className={s.ordenNombre}>{o.titulo}</p>}
      {(o.estimado || o.dificultad || editada) && (
        <p className={s.ordenDatos}>
          {o.estimado && <span>{textoEstimado(o.estimado)}</span>}
          {o.dificultad && <span>{textoDificultad(o.dificultad)}</span>}
          {editada && <span className={s.ordenEditada}>Editada</span>}
        </p>
      )}
      <p
        id={`${id}-texto`}
        className={
          larga && !abierta
            ? `${s.ordenTexto} ${s.ordenRecortada}`
            : s.ordenTexto
        }
      >
        {o.texto}
      </p>
      {larga && (
        <button
          type="button"
          className={s.botonTexto}
          aria-expanded={abierta}
          aria-controls={`${id}-texto`}
          onClick={() => setAbierta((v) => !v)}
        >
          {abierta ? "Ver menos" : "Ver la orden completa"}
        </button>
      )}
      {quien && (
        <p className={s.secundario}>
          Decidió: {quien}
          {o.decidido ? ` · ${cuando(o.decidido, ahora)}` : ""}
        </p>
      )}
      {o.motivo && (
        <p className={o.estado === "fallida" ? s.ordenFalla : s.ordenNota}>
          {o.estado === "fallida" ? "Error" : "Motivo"}: {o.motivo}
        </p>
      )}
      {o.resumen && (
        <p className={s.ordenNota}>
          <span className={s.ordenNotaTitulo}>Resultado:</span> {o.resumen}
        </p>
      )}
      <p className={s.hora}>
        <time dateTime={o.creado}>{horaMinuto(o.creado)}</time>
      </p>
      {o.estado === "por_aprobar" && (
        <DecidirOrden orden={o} cambio={cambio} describe={`${id}-t`} />
      )}
    </article>
  );
}
