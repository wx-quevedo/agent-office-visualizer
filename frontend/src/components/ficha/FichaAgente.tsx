"use client";

/**
 * Agent card (stage 2.3, mockups docs/bocetos/etapa-2/Main and FichaCelular):
 * right panel of about 460 px over the office on PC, bottom sheet with its own
 * scroll on phones (< 700 px). Opened from /oficina/3d and /oficina.
 *
 * Order: header, pending permission (Approve / Reject with reason), stuck
 * card, pending question, "Ahora mismo", three figures, current turn,
 * previous turns, links to the full history and to "Dónde quedamos".
 */

import Link from "next/link";
import {
  useEffect,
  useId,
  useRef,
  useSyncExternalStore,
  type KeyboardEvent as TeclaReact,
  type RefObject,
} from "react";
import type { Agente, TipoResumen } from "@/components/oficina/logica";
import PanelPermiso from "@/components/permisos/PanelPermiso";
import { useLectura } from "@/utils/useLectura";
import {
  ahoraMismo,
  cifras,
  enlaceDonde,
  enlaceHistorial,
  haceTiempo,
  horaMinuto,
  iniciales,
  nombreCarpeta,
  nombreMaquina,
  nombreModelo,
  pedidoDe,
  resultado,
  resumenTurno,
  separarTurnos,
  textoCuenta,
  tokensHoy,
  type Consumo,
  type Historial,
} from "./logica";
import s from "./ficha.module.css";

const TURNOS_EN_FICHA = 6;

/** The helper agent's sentence for this alert, when ready (stage 2.4). */
function resumenDe(a: Agente, tipo: TipoResumen): string | null {
  const r = a.resumenes?.[tipo];
  return r?.estado === "listo" && r.texto ? r.texto : null;
}
const ENFOCABLES =
  'a[href], button:not([disabled]), input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])';

function suscribirAncho(f: () => void): () => void {
  window.addEventListener("resize", f);
  return () => window.removeEventListener("resize", f);
}

/** Phones (< 700 px): the card is a modal bottom sheet. */
function useCelular(): boolean {
  return useSyncExternalStore(
    suscribirAncho,
    () => window.innerWidth < 700,
    () => false,
  );
}

export interface PropsFicha {
  /** The agent in the office (undefined: it left, or the state is loading). */
  agente: Agente | undefined;
  /** Session asked for (?agente=). */
  id: string;
  /** The first read of the state has not arrived yet. */
  cargando?: boolean;
  ahora: number;
  onCerrar: () => void;
  /** Fixed to the window (/oficina) instead of inside the 3D canvas. */
  fija?: boolean;
}

export interface PropsVista extends PropsFicha {
  historial: Historial | null;
  errorHistorial?: string | null;
  consumo: Consumo | null;
}

function Cerrar({
  onCerrar,
  boton,
}: {
  onCerrar: () => void;
  boton: RefObject<HTMLButtonElement | null>;
}) {
  return (
    <button
      ref={boton}
      type="button"
      className={s.cerrar}
      aria-label="Cerrar ficha"
      onClick={onCerrar}
    >
      <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
        <path
          d="M3 3l10 10M13 3L3 13"
          stroke="currentColor"
          strokeWidth="1.6"
          fill="none"
        />
      </svg>
    </button>
  );
}

/** The card itself, with its data given (tested with sample data). */
export function FichaVista({
  agente: a,
  id,
  cargando = false,
  ahora,
  onCerrar,
  fija = false,
  historial,
  errorHistorial = null,
  consumo,
}: PropsVista) {
  const idTitulo = useId();
  const boton = useRef<HTMLButtonElement>(null);

  const celular = useCelular();
  const raiz = useRef<HTMLElement>(null);

  // Focus goes to the card when it opens (or changes agent) and back where it
  // was when it closes; Esc closes it.
  useEffect(() => {
    const previo = document.activeElement as HTMLElement | null;
    boton.current?.focus({ preventScroll: true });
    return () => {
      if (previo?.isConnected) previo.focus({ preventScroll: true });
    };
  }, [id]);
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || e.defaultPrevented) return;
      const el = e.target as HTMLElement | null;
      if (el?.tagName && ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName))
        return;
      // Escape inside another panel (alerts, permissions) is not for the card.
      if (
        el instanceof HTMLElement &&
        el !== document.body &&
        !el.closest("aside")
      )
        return;
      onCerrar();
    };
    document.addEventListener("keydown", tecla);
    return () => document.removeEventListener("keydown", tecla);
  }, [onCerrar]);

  const carpeta = a?.agente.proyecto ?? historial?.proyecto ?? null;
  const nombre = a
    ? nombreCarpeta(carpeta)
    : cargando
      ? "Cargando…"
      : historial?.proyecto
        ? nombreCarpeta(historial.proyecto)
        : "Agente";
  const maquina = nombreMaquina(a?.agente.maquina ?? historial?.maquina);
  const cuenta = textoCuenta(a?.agente.cuenta ?? historial?.cuenta);
  const modelo = nombreModelo(a?.agente.modelo ?? historial?.modelo);
  const { actual, anteriores } = separarTurnos(historial?.turnos ?? []);
  const ya = a ? ahoraMismo(a, ahora) : null;
  const permisoPendiente = a?.estado.numero === 13;

  // On phones the sheet covers the page: Tab stays inside it.
  const atrapar = (e: TeclaReact<HTMLElement>) => {
    if (!celular || e.key !== "Tab" || !raiz.current) return;
    const lista = [
      ...raiz.current.querySelectorAll<HTMLElement>(ENFOCABLES),
    ].filter((x) => x.offsetParent !== null);
    if (!lista.length) return;
    const primero = lista[0];
    const ultimo = lista[lista.length - 1];
    if (e.shiftKey && document.activeElement === primero) {
      e.preventDefault();
      ultimo.focus();
    } else if (!e.shiftKey && document.activeElement === ultimo) {
      e.preventDefault();
      primero.focus();
    }
  };

  return (
    <aside
      ref={raiz}
      className={fija ? `${s.ficha} ${s.fija}` : s.ficha}
      aria-labelledby={idTitulo}
      role={celular ? "dialog" : undefined}
      aria-modal={celular ? true : undefined}
      onKeyDown={atrapar}
    >
      <div className={s.asa} aria-hidden="true" />
      <header className={s.cabeza}>
        <div className={s.avatar} aria-hidden="true">
          {iniciales(nombre)}
        </div>
        <div className={s.identidad}>
          <h2 id={idTitulo} className={s.nombre}>
            {nombre}
          </h2>
          {(carpeta || maquina) && (
            <div className={s.ruta}>
              {[carpeta, maquina].filter(Boolean).join(" · ")}
            </div>
          )}
          {(cuenta || modelo) && (
            <div className={s.chips}>
              {cuenta && <span className={s.chip}>{cuenta}</span>}
              {modelo && <span className={s.chip}>{modelo}</span>}
            </div>
          )}
        </div>
        <Cerrar onCerrar={onCerrar} boton={boton} />
      </header>

      <div
        className={s.cuerpo}
        tabIndex={0}
        role="region"
        aria-label="Detalle del agente"
      >
        {!a && !cargando && (
          <p className={s.nota} role="status">
            Ese agente ya no está en la oficina; su historial sigue disponible.
          </p>
        )}

        {a && permisoPendiente && (
          <div className={s.arriba}>
            {a.permiso ? (
              <PanelPermiso
                permiso={a.permiso}
                ahora={ahora}
                variante="ficha"
                resumen={resumenDe(a, "permiso")}
              />
            ) : (
              <section
                className={s.tarjetaAzul}
                aria-label="Permiso solicitado"
              >
                <h3 className={s.etiquetaAzul}>Te pide permiso</h3>
                {resumenDe(a, "permiso") && (
                  <p className={s.texto}>{resumenDe(a, "permiso")}</p>
                )}
                <p className={s.texto}>Responde en VS Code.</p>
              </section>
            )}
          </div>
        )}

        {a?.atasco && (
          <section className={s.atasco} aria-label="Parece atascado">
            <h3 className={s.etiquetaRoja}>
              Parece atascado ·{" "}
              {haceTiempo(a.atasco.desde, ahora).replace("hace ", "")}
            </h3>
            {resumenDe(a, "atasco") ? (
              <>
                <p className={s.texto}>{resumenDe(a, "atasco")}</p>
                <p className={s.secundario}>{a.atasco.motivo}</p>
              </>
            ) : (
              <p className={s.texto}>{a.atasco.motivo}</p>
            )}
            {a.atasco.ultimos_intentos.length > 0 && (
              <p className={s.secundario}>
                Último intento:{" "}
                <span className={s.mono}>
                  {
                    a.atasco.ultimos_intentos[
                      a.atasco.ultimos_intentos.length - 1
                    ]
                  }
                </span>
              </p>
            )}
            {a.atasco.ultimo_error && (
              <p className={s.secundario}>
                Último error: {a.atasco.ultimo_error}
              </p>
            )}
          </section>
        )}

        {a?.pregunta_pendiente && (
          <section className={s.tarjetaAzul} aria-label="Te pregunta">
            <h3 className={s.etiquetaAzul}>Te pregunta</h3>
            {resumenDe(a, "pregunta") ? (
              <>
                <p className={s.texto}>{resumenDe(a, "pregunta")}</p>
                <p className={s.secundario}>{a.pregunta_pendiente}</p>
              </>
            ) : (
              <p className={s.texto}>{a.pregunta_pendiente}</p>
            )}
            <p className={s.secundario}>Responde en VS Code.</p>
          </section>
        )}

        {ya && (
          <section className={s.seccion} aria-labelledby={`${idTitulo}-ahora`}>
            <h3 id={`${idTitulo}-ahora`} className={s.etiqueta}>
              Ahora mismo
            </h3>
            <div className={s.ahoraFila}>
              <div className={s.ahoraTexto}>{ya.texto}</div>
              <div className={s.ahoraTiempo}>{ya.tiempo}</div>
            </div>
            {ya.razonable && <p className={s.secundario}>{ya.razonable}</p>}
          </section>
        )}

        {a && (
          <dl className={s.cifras}>
            {cifras(a, tokensHoy(consumo, a.agente.session_id), ahora).map(
              (c) => (
                <div
                  key={c.titulo}
                  className={c.alerta ? `${s.cifra} ${s.cifraAlerta}` : s.cifra}
                >
                  <dt>{c.titulo}</dt>
                  <dd>{c.valor}</dd>
                </div>
              ),
            )}
          </dl>
        )}

        <section className={s.seccion} aria-labelledby={`${idTitulo}-turno`}>
          <h3 id={`${idTitulo}-turno`} className={s.etiqueta}>
            {actual
              ? `${actual.fin ? "Último turno" : "Turno actual"} · ${actual.numero}`
              : "Turno actual"}
          </h3>
          {actual ? (
            <>
              <p className={s.pedido}>{pedidoDe(actual)}</p>
              <p className={s.secundario}>{resumenTurno(actual)}</p>
            </>
          ) : (
            <p className={s.secundario}>
              {errorHistorial && !historial
                ? "No se pudo leer el historial; se reintenta solo."
                : historial
                  ? "Todavía sin turnos registrados."
                  : "Cargando el historial…"}
            </p>
          )}
        </section>

        {anteriores.length > 0 && (
          <section
            className={s.seccionLista}
            aria-labelledby={`${idTitulo}-ant`}
          >
            <h3 id={`${idTitulo}-ant`} className={s.etiqueta}>
              Turnos anteriores
            </h3>
            <ol className={s.turnos}>
              {anteriores.map((t) => {
                const r = resultado(t.resultado);
                return (
                  <li key={t.numero} className={s.turno}>
                    <time className={s.hora} dateTime={t.inicio}>
                      {horaMinuto(t.inicio)}
                    </time>
                    <span className={s.turnoPedido}>{pedidoDe(t)}</span>
                    <span className={`${s.fin} ${s[r.tono]}`}>{r.texto}</span>
                  </li>
                );
              })}
            </ol>
          </section>
        )}
      </div>

      <nav className={s.pie} aria-label="Más sobre este agente">
        <Link
          href={enlaceHistorial(id)}
          className={a?.atasco ? `${s.enlace} ${s.enlaceFuerte}` : s.enlace}
        >
          {a?.atasco ? "Ver qué intentó" : "Historial completo"}
        </Link>
        <Link href={enlaceDonde(carpeta)} className={s.enlace}>
          Dónde quedamos
        </Link>
      </nav>
    </aside>
  );
}

/** The card with its own reads: history (every 10 s) and today's tokens (every 30 s). */
export default function FichaAgente(props: PropsFicha) {
  const hist = useLectura<Historial>(
    `/api/v1/agents/${encodeURIComponent(props.id)}/historial?por_pagina=${TURNOS_EN_FICHA}`,
    10000,
  );
  const consumo = useLectura<Consumo>("/api/v1/consumo", 30000);
  return (
    <FichaVista
      {...props}
      historial={hist.datos}
      errorHistorial={hist.error}
      consumo={consumo.datos}
    />
  );
}
