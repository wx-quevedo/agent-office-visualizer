"use client";

/**
 * Floating cards with the alerts of the orchestrators that can be answered
 * (Prompt 43): a question or an order waiting for Washington, one card each,
 * bottom right on desktop and full width at the bottom on phones. Each card
 * has Responder (goes to the chat of the project, to that message or order),
 * Ignorar (it never comes back) and Esperar (silent until the orchestrator
 * writes again); both leave at once. Reads GET /avisos-orquestador every 5 s.
 * Every key gives voice and a Windows notification once (keys kept in
 * localStorage); the first read of the page only records them. Used in
 * /oficina, /oficina/3d, /proyectos and /proyectos/ver (there without the
 * cards of that same project, so the chat field stays free).
 */

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useAhora } from "@/components/proyectos/acciones";
import { apiFetch } from "@/utils/api";
import { useLectura } from "@/utils/useLectura";
import {
  LECTURA_AVISOS_MS,
  RUTA_AVISOS_ORQUESTADOR,
  avisosVisibles,
  enlaceResponder,
  guardarAvisadas,
  haceCuanto,
  leerAvisadas,
  revisarClaves,
  rutaAccion,
  segundosDesde,
  textoTarjeta,
  textoTipo,
  tituloAviso,
  vozAviso,
  type AccionAviso,
  type AvisoOrquestador,
  type RespuestaAvisos,
} from "./logicaOrquestador";
import { darAvisoExterno } from "./useAvisos";
import s from "./avisosOrquestador.module.css";

/** Gives the voice and notification of a new alert; `abrir` does what Responder does. */
export type DarAvisoOrquestador = (
  a: AvisoOrquestador,
  abrir: () => void,
) => void;

const darPorDefecto: DarAvisoOrquestador = (a, abrir) =>
  darAvisoExterno({
    voz: vozAviso(a),
    titulo: tituloAviso(a),
    cuerpo: textoTarjeta(a),
    tag: `orquestador-${a.clave}`,
    alHacerClic: abrir,
  });

const irPorDefecto = (url: string) => window.location.assign(url);

function almacen(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export interface PropsAvisosOrquestador {
  /** Id of the project whose page is open: its alerts are not shown. */
  proyectoActual?: string | null;
  /** Navigation (router.push); by default a normal page load. */
  irA?: (url: string) => void;
  /** Voice and notification (injected in tests). */
  dar?: DarAvisoOrquestador;
  /** Time between reads (5 s; shorter in tests). */
  cadaMs?: number;
  /** Hides the cards (the 3D editor) but keeps reading and alerting. */
  oculta?: boolean;
}

function Tarjeta({
  aviso: a,
  ahora,
  quitar,
}: {
  aviso: AvisoOrquestador;
  ahora: number;
  quitar: (a: AvisoOrquestador, accion: AccionAviso) => void;
}) {
  const orden = a.tipo === "orden";
  const idTitulo = `aviso-orq-${a.clave.replace(/[^A-Za-z0-9_-]/g, "-")}`;
  return (
    <li
      className={orden ? `${s.tarjeta} ${s.tarjetaOrden}` : s.tarjeta}
      aria-labelledby={idTitulo}
    >
      <div className={s.cabeza}>
        <p id={idTitulo} className={s.proyecto}>
          {a.proyecto}
        </p>
        <span className={s.hace}>
          <time dateTime={a.desde}>{haceCuanto(segundosDesde(a, ahora))}</time>
        </span>
      </div>
      <p className={orden ? `${s.tipo} ${s.tipoOrden}` : s.tipo}>
        El orquestador {textoTipo(a.tipo)}
      </p>
      <p className={s.texto}>{textoTarjeta(a)}</p>
      <div className={s.botones}>
        <Link
          href={enlaceResponder(a)}
          className={orden ? `${s.responder} ${s.responderOrden}` : s.responder}
        >
          Responder
          <span className={s.oculto}> a {a.proyecto}</span>
        </Link>
        <button
          type="button"
          className={s.boton}
          onClick={() => quitar(a, "ignorar")}
        >
          Ignorar
          <span className={s.oculto}> el aviso de {a.proyecto}</span>
        </button>
        <button
          type="button"
          className={s.boton}
          title="No vuelve a avisar hasta que el orquestador escriba de nuevo"
          onClick={() => quitar(a, "esperar")}
        >
          Esperar
          <span className={s.oculto}>
            {" "}
            hasta que el orquestador de {a.proyecto} escriba de nuevo
          </span>
        </button>
      </div>
    </li>
  );
}

export default function AvisosOrquestador({
  proyectoActual = null,
  irA = irPorDefecto,
  dar = darPorDefecto,
  cadaMs = LECTURA_AVISOS_MS,
  oculta = false,
}: PropsAvisosOrquestador) {
  const { datos } = useLectura<RespuestaAvisos>(
    RUTA_AVISOS_ORQUESTADOR,
    cadaMs,
  );
  const ahora = useAhora(15000);
  const [quitadas, setQuitadas] = useState<ReadonlySet<string>>(
    () => new Set(),
  );
  const [error, setError] = useState<string | null>(null);
  const primera = useRef(true);
  const memoria = useRef<string[]>([]);
  const darRef = useRef(dar);
  const irRef = useRef(irA);
  useEffect(() => {
    darRef.current = dar;
    irRef.current = irA;
  }, [dar, irA]);

  const avisos = datos?.avisos;

  // One alert per key: new keys of this read (never on the first one).
  useEffect(() => {
    if (!avisos) return;
    const st = almacen();
    const conocidas = [...new Set([...memoria.current, ...leerAvisadas(st)])];
    const r = revisarClaves(
      avisos.map((a) => a.clave),
      conocidas,
      primera.current,
    );
    primera.current = false;
    memoria.current = r.avisadas;
    guardarAvisadas(st, r.avisadas);
    for (const clave of r.nuevas) {
      const a = avisos.find((x) => x.clave === clave);
      if (a) darRef.current(a, () => irRef.current(enlaceResponder(a)));
    }
    // A key the server no longer sends is forgotten here: if it ever comes
    // back (Esperar and the orchestrator wrote again) it shows again.
    const presentes = new Set(avisos.map((a) => a.clave));
    // eslint-disable-next-line react-hooks/set-state-in-effect -- pruning local removals against the new read
    setQuitadas((v) => {
      const quedan = [...v].filter((c) => presentes.has(c));
      return quedan.length === v.size ? v : new Set(quedan);
    });
  }, [avisos]);

  const quitar = useCallback((a: AvisoOrquestador, accion: AccionAviso) => {
    setError(null);
    setQuitadas((v) => new Set(v).add(a.clave));
    apiFetch(rutaAccion(accion), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ clave: a.clave }),
    })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
      })
      .catch(() => {
        setQuitadas((v) => {
          const n = new Set(v);
          n.delete(a.clave);
          return n;
        });
        setError(
          accion === "ignorar"
            ? `No se pudo ignorar el aviso de ${a.proyecto}; intenta de nuevo.`
            : `No se pudo dejar en espera el aviso de ${a.proyecto}; intenta de nuevo.`,
        );
      });
  }, []);

  const visibles = avisosVisibles(avisos ?? [], quitadas, proyectoActual);
  if (oculta || (visibles.length === 0 && !error)) return null;
  return (
    <section className={s.pila} aria-label="Avisos de los orquestadores">
      {error && (
        <div className={s.error} role="alert">
          <p className={s.errorTexto}>{error}</p>
          <button
            type="button"
            className={s.boton}
            onClick={() => setError(null)}
          >
            Cerrar
          </button>
        </div>
      )}
      {visibles.length > 0 && (
        <ul className={s.lista} aria-live="polite" aria-relevant="additions">
          {visibles.map((a) => (
            <Tarjeta key={a.clave} aviso={a} ahora={ahora} quitar={quitar} />
          ))}
        </ul>
      )}
    </section>
  );
}
