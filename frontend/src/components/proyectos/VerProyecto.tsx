"use client";

/**
 * /proyectos/ver?id=<id>&seccion=chat|equipo|donde (Prompt 37): the header of
 * the project and three sections. Chat arrives in Prompt 38; Equipo shows each
 * member with what the office sees and the pause/resume buttons; "Dónde
 * quedamos" reuses that view fixed to this project. Refreshed every 3 s.
 */

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState, type ReactNode } from "react";
import DondeQuedamos from "@/components/donde/DondeQuedamos";
import { apiFetch } from "@/utils/api";
import { useLectura } from "@/utils/useLectura";
import { Estado, nombreMaquina } from "./ListaProyectos";
import {
  accionesDe,
  detalleError,
  enlaceProyecto,
  estadoMiembro,
  haciendoDe,
  nombreCuenta,
  nombreEsfuerzo,
  nombreModelo,
  nombrePlantilla,
  nombreRol,
  textoOficina,
  type Maquina,
  type Proyecto,
} from "./logica";
import s from "./proyectos.module.css";

export type Seccion = "chat" | "equipo" | "donde";

export const SECCIONES: { valor: Seccion; texto: string }[] = [
  { valor: "chat", texto: "Chat" },
  { valor: "equipo", texto: "Equipo" },
  { valor: "donde", texto: "Dónde quedamos" },
];

export function seccionDe(valor: string | null): Seccion {
  return SECCIONES.some((x) => x.valor === valor)
    ? (valor as Seccion)
    : "equipo";
}

/** The newer of the read project and the one answered by pause/resume. */
export function masNuevo(
  leido: Proyecto | null,
  local: Proyecto | null,
): Proyecto | null {
  if (!local || (leido && local.id !== leido.id)) return leido;
  if (!leido) return local;
  return Date.parse(local.actualizado) > Date.parse(leido.actualizado)
    ? local
    : leido;
}

export interface PropsEquipo {
  proyecto: Proyecto;
  /** Sends pause or resume; rejects with the message of the server. */
  accion: (tipo: "pausar" | "reanudar") => Promise<void>;
}

/** Equipo section: members, buttons and the error of the project. */
export function EquipoVista({ proyecto: p, accion }: PropsEquipo) {
  const [enviando, setEnviando] = useState<"pausar" | "reanudar" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const a = accionesDe(p.estado);
  const hacer = async (tipo: "pausar" | "reanudar") => {
    setEnviando(tipo);
    setError(null);
    try {
      await accion(tipo);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setEnviando(null);
    }
  };
  const equipo = [...p.equipo].sort(
    (x, y) =>
      (x.rol === "orquestador" ? 0 : 1) - (y.rol === "orquestador" ? 0 : 1) ||
      x.orden - y.orden,
  );
  return (
    <section className={s.formulario} aria-labelledby="equipo-titulo">
      <h2 id="equipo-titulo" className={s.oculto}>
        Equipo
      </h2>
      {p.estado === "error" && (
        <p className={s.avisoError} role="status">
          {p.error ?? "El equipo tuvo un error sin detalle."}
        </p>
      )}
      {a.ocupado && (
        <p className={s.aviso} role="status">
          {haciendoDe({ ...p, haciendo: null })}
        </p>
      )}
      <div className={s.botonesEquipo}>
        {a.pausar && (
          <button
            type="button"
            className={s.boton}
            disabled={a.ocupado || enviando !== null}
            onClick={() => void hacer("pausar")}
          >
            {enviando === "pausar" ? "Pausando…" : "Pausar el equipo"}
          </button>
        )}
        {a.reanudar && (
          <button
            type="button"
            className={s.botonPrincipal}
            disabled={a.ocupado || enviando !== null}
            onClick={() => void hacer("reanudar")}
          >
            {enviando === "reanudar" ? "Reanudando…" : "Reanudar"}
          </button>
        )}
      </div>
      {error && (
        <p className={s.avisoError} role="alert">
          {error}
        </p>
      )}
      {equipo.length === 0 ? (
        <p className={s.aviso}>El equipo todavía no está armado.</p>
      ) : (
        <ul className={s.equipo}>
          {equipo.map((m) => {
            const e = estadoMiembro(m.estado);
            const oficina = textoOficina(m);
            return (
              <li
                key={m.id}
                className={
                  m.rol === "orquestador"
                    ? `${s.miembro} ${s.miembroOrq}`
                    : s.miembro
                }
              >
                <div className={s.miembroCabeza}>
                  <span className={s.etiqueta}>{nombreRol(m.rol)}</span>
                  <span className={s.miembroNombre}>{m.nombre}</span>
                  <span className={s.secundario}>
                    {nombreModelo(m.modelo)} · esfuerzo{" "}
                    {nombreEsfuerzo(m.esfuerzo).toLowerCase()}
                  </span>
                </div>
                <span className={`${s.estado} ${s[e.tono]}`}>{e.texto}</span>
                {(oficina || (m.oficina && m.session_id)) && (
                  <div className={s.miembroResto}>
                    {oficina && (
                      <span className={s.secundario}>
                        En la oficina: {oficina}
                      </span>
                    )}
                    {m.oficina && m.session_id && (
                      <Link
                        href={`/oficina/3d?agente=${encodeURIComponent(m.session_id)}`}
                        className={s.enlace}
                      >
                        Ver en la oficina
                        <span className={s.oculto}> a {m.nombre}</span>
                      </Link>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

export interface PropsVista {
  proyecto: Proyecto | null;
  seccion: Seccion;
  maquinas?: Maquina[] | null;
  error?: string | null;
  accion: (tipo: "pausar" | "reanudar") => Promise<void>;
  /** "Dónde quedamos" of the project (injected: tests do not read the API). */
  donde?: (nombre: string) => ReactNode;
}

/** The page with its data given (tested with sample data). */
export function ProyectoVista({
  proyecto: p,
  seccion,
  maquinas = null,
  error = null,
  accion,
  donde,
}: PropsVista) {
  return (
    <div className={s.pagina}>
      <main className={s.contenido}>
        <nav className={s.migas} aria-label="Navegación">
          <Link href="/proyectos" className={s.enlace}>
            Volver a Proyectos
          </Link>
          <Link href="/oficina/3d" className={s.enlace}>
            Ir a la oficina
          </Link>
        </nav>
        {!p && error && (
          <p className={s.avisoError} role="status">
            {error.includes("404")
              ? "No se encontró este proyecto."
              : `No se pudo leer el proyecto (${error}); se reintenta solo.`}
          </p>
        )}
        {!p && !error && <p className={s.secundario}>Cargando…</p>}
        {p && (
          <>
            <header className={s.cabeza}>
              <div className={s.ficha}>
                <h1 className={s.titulo}>{p.nombre}</h1>
                <p className={`${s.secundario} ${s.mono}`}>{p.ruta}</p>
                <p className={s.datos}>
                  <span>{nombreCuenta(p.cuenta)}</span>
                  <span>{nombreMaquina(p.maquina, maquinas)}</span>
                  <span>Plantilla {nombrePlantilla(p.plantilla)}</span>
                </p>
              </div>
              <Estado p={p} />
            </header>
            <nav className={s.pestanas} aria-label="Secciones del proyecto">
              {SECCIONES.map((x) => (
                <Link
                  key={x.valor}
                  href={enlaceProyecto(p.id, x.valor)}
                  className={
                    x.valor === seccion
                      ? `${s.pestana} ${s.pestanaActual}`
                      : s.pestana
                  }
                  aria-current={x.valor === seccion ? "page" : undefined}
                  scroll={false}
                >
                  {x.texto}
                </Link>
              ))}
            </nav>
            {seccion === "chat" && (
              <p className={s.aviso}>
                El chat con el orquestador llega en el Prompt 38.
              </p>
            )}
            {seccion === "equipo" && (
              <EquipoVista proyecto={p} accion={accion} />
            )}
            {seccion === "donde" && donde?.(p.nombre)}
          </>
        )}
      </main>
    </div>
  );
}

/** The page with its reads: the project (3 s) and machines (30 s, for names). */
export default function VerProyecto() {
  const params = useSearchParams();
  const id = params.get("id");
  const seccion = seccionDe(params.get("seccion"));
  const api = useLectura<Proyecto>(
    id ? `/api/v1/proyectos-creados/${encodeURIComponent(id)}` : null,
    3000,
  );
  const maq = useLectura<{ maquinas: Maquina[] }>(
    "/api/v1/proyectos-creados/maquinas",
    30000,
  );
  const [local, setLocal] = useState<Proyecto | null>(null);
  const accion = async (tipo: "pausar" | "reanudar") => {
    if (!id) return;
    let r: Response;
    try {
      r = await apiFetch(
        `/api/v1/proyectos-creados/${encodeURIComponent(id)}/${tipo}`,
        { method: "POST" },
      );
    } catch {
      throw new Error("No se pudo conectar con el servidor; intenta de nuevo.");
    }
    if (!r.ok) throw new Error(await detalleError(r));
    setLocal((await r.json()) as Proyecto);
  };
  if (!id)
    return (
      <div className={s.pagina}>
        <main className={s.contenido}>
          <p className={s.aviso}>
            Falta el proyecto en el enlace.{" "}
            <Link href="/proyectos" className={s.enlace}>
              Ver los proyectos
            </Link>
          </p>
        </main>
      </div>
    );
  return (
    <ProyectoVista
      proyecto={masNuevo(api.datos, local)}
      seccion={seccion}
      maquinas={maq.datos?.maquinas ?? null}
      error={api.error}
      accion={accion}
      donde={(nombre) => <DondeQuedamos proyecto={nombre} />}
    />
  );
}
