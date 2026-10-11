"use client";

/**
 * /historial?agente=<id>&pagina=<n>: every turn of an agent, newest first, 20
 * per page (GET /agents/{id}/historial). Opened from the agent card.
 */

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useLectura } from "@/utils/useLectura";
import {
  cuando,
  enlaceDonde,
  enlaceHistorial,
  miles,
  nombreCarpeta,
  nombreMaquina,
  nombreModelo,
  pedidoDe,
  resultado,
  textoCuenta,
  tiempoCorto,
  type Historial,
  type Turno,
} from "./logica";
import s from "./historial.module.css";

const POR_PAGINA = 20;
const ARCHIVOS_VISIBLES = 8;

function TurnoCompleto({ t, ahora }: { t: Turno; ahora: number }) {
  const r = resultado(t.resultado);
  const herramientas = Object.entries(t.herramientas);
  const extra = t.archivos_editados.length - ARCHIVOS_VISIBLES;
  return (
    <li className={s.turno}>
      <div className={s.turnoCabeza}>
        <h2 className={s.turnoTitulo}>Turno {t.numero}</h2>
        <span className={s.meta}>
          <time dateTime={t.inicio}>{cuando(t.inicio, ahora)}</time> ·{" "}
          {tiempoCorto(t.duracion_s)}
        </span>
        <span className={`${s.resultado} ${s[`tono_${r.tono}`]}`}>
          {r.texto}
        </span>
      </div>
      <p className={s.pedido}>{pedidoDe(t)}</p>
      <dl className={s.datos}>
        <div>
          <dt>Herramientas</dt>
          <dd>
            {herramientas.length
              ? `${miles(t.total_herramientas)}: ${herramientas
                  .map(([k, v]) => `${k} ${v}`)
                  .join(" · ")}`
              : "Ninguna"}
          </dd>
        </div>
        <div>
          <dt>Archivos editados</dt>
          <dd>
            {t.archivos_editados.length ? (
              <ul className={s.archivos}>
                {t.archivos_editados.slice(0, ARCHIVOS_VISIBLES).map((a) => (
                  <li key={a}>{a}</li>
                ))}
                {extra > 0 && <li>y {extra} más</li>}
              </ul>
            ) : (
              "Ninguno"
            )}
          </dd>
        </div>
        <div>
          <dt>Commits</dt>
          <dd>
            {t.commits.length ? (
              <ul className={s.archivos}>
                {t.commits.map((c, i) => (
                  <li key={`${c.hora}-${i}`}>
                    {cuando(c.hora, ahora)}: {c.mensaje ?? "sin mensaje"}
                  </li>
                ))}
              </ul>
            ) : (
              "Ninguno"
            )}
          </dd>
        </div>
        <div>
          <dt>Errores</dt>
          <dd>{t.errores}</dd>
        </div>
        <div>
          <dt>Tokens de salida</dt>
          <dd>{miles(t.tokens_salida)}</dd>
        </div>
      </dl>
      {t.pregunta && (
        <p className={s.pregunta}>
          <b>Preguntó:</b> {t.pregunta}
        </p>
      )}
    </li>
  );
}

export function HistorialVista({
  id,
  pagina,
  datos,
  error,
  ahora,
}: {
  id: string;
  pagina: number;
  datos: Historial | null;
  error: string | null;
  ahora: number;
}) {
  const nombre = datos?.proyecto ? nombreCarpeta(datos.proyecto) : "Agente";
  const meta = [
    textoCuenta(datos?.cuenta),
    nombreModelo(datos?.modelo),
    nombreMaquina(datos?.maquina),
  ].filter(Boolean);
  return (
    <main className={s.pagina}>
      <nav className={s.barra} aria-label="Navegación del historial">
        <Link
          href={`/oficina/3d?agente=${encodeURIComponent(id)}`}
          className={s.boton}
        >
          Volver a la oficina
        </Link>
        {datos?.proyecto && (
          <Link href={enlaceDonde(datos.proyecto)} className={s.boton}>
            Dónde quedamos
          </Link>
        )}
      </nav>
      <header className={s.cabeza}>
        <p className={s.etiqueta}>Historial completo</p>
        <h1 className={s.titulo}>{nombre}</h1>
        {datos && (
          <p className={s.meta}>
            {[...meta, `${miles(datos.total)} turnos`].join(" · ")}
            {datos.proyecto ? ` · ${datos.proyecto}` : ""}
          </p>
        )}
      </header>
      {!id && <p className={s.aviso}>Falta el agente (?agente=).</p>}
      {id && error && !datos && (
        <p className={s.aviso} role="status">
          {error.includes("404")
            ? "No hay historial de ese agente (se guardan 7 días)."
            : `No se pudo leer el historial (${error}); se reintenta solo.`}
        </p>
      )}
      {id && !error && !datos && <p className={s.meta}>Cargando…</p>}
      {datos && datos.turnos.length === 0 && (
        <p className={s.aviso}>Todavía sin turnos registrados.</p>
      )}
      {datos && datos.turnos.length > 0 && (
        <ol className={s.turnos}>
          {datos.turnos.map((t) => (
            <TurnoCompleto key={t.numero} t={t} ahora={ahora} />
          ))}
        </ol>
      )}
      {datos && datos.paginas > 1 && (
        <nav className={s.paginas} aria-label="Páginas del historial">
          {pagina > 1 ? (
            <Link href={enlaceHistorial(id, pagina - 1)} className={s.boton}>
              Más recientes
            </Link>
          ) : (
            <span />
          )}
          <span className={s.meta}>
            Página {pagina} de {datos.paginas}
          </span>
          {pagina < datos.paginas ? (
            <Link href={enlaceHistorial(id, pagina + 1)} className={s.boton}>
              Más antiguos
            </Link>
          ) : (
            <span />
          )}
        </nav>
      )}
    </main>
  );
}

export default function HistorialCompleto() {
  const params = useSearchParams();
  const id = params.get("agente") ?? "";
  const [ahora, setAhora] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setAhora(Date.now()), 30000);
    return () => clearInterval(id);
  }, []);
  const pagina = Math.max(1, Math.floor(Number(params.get("pagina")) || 1));
  const { datos, error } = useLectura<Historial>(
    id
      ? `/api/v1/agents/${encodeURIComponent(id)}/historial?pagina=${pagina}&por_pagina=${POR_PAGINA}`
      : null,
    15000,
  );
  return (
    <HistorialVista
      id={id}
      pagina={pagina}
      datos={datos}
      error={error}
      ahora={ahora}
    />
  );
}
