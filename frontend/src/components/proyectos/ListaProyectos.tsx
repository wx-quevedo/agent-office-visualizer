"use client";

/**
 * /proyectos (Prompt 37): the projects created from the office, with account,
 * machine, what they are doing, the team and the state. Prompt 38 adds the
 * "Decisiones" block on top (orders waiting for approval). Prompt 39 adds the
 * link to /ajustes (house rules and safe commands). Refreshed every 3 s.
 * Prompt 43: the grey "Prueba" tag of test projects and the floating alerts
 * of the orchestrators (AvisosOrquestador).
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import AvisosOrquestador from "@/components/avisos/AvisosOrquestador";
import { useLectura } from "@/utils/useLectura";
import { useAhora } from "./acciones";
import { DecisionesVista } from "./Decisiones";
import {
  enlaceProyecto,
  estadoDe,
  haciendoDe,
  nombreCuenta,
  resumenEquipo,
  type Maquina,
  type Orden,
  type Proyecto,
} from "./logica";
import s from "./proyectos.module.css";

/** Name of the machine with that id (its id when the list does not have it). */
export function nombreMaquina(
  id: string,
  maquinas: Maquina[] | null | undefined,
): string {
  return maquinas?.find((m) => m.id === id)?.nombre ?? id;
}

export function Estado({
  p,
}: {
  p: Pick<Proyecto, "estado" | "ordenes_por_aprobar">;
}) {
  const e = estadoDe(p);
  return <span className={`${s.estado} ${s[e.tono]}`}>{e.texto}</span>;
}

export interface PropsLista {
  proyectos: Proyecto[] | null;
  maquinas?: Maquina[] | null;
  error?: string | null;
  /** Orders waiting for approval (GET /ordenes?estado=por_aprobar). */
  ordenes?: Orden[] | null;
  ahora?: number;
}

/** The page with its data given (tested with sample data). */
export function ListaVista({
  proyectos,
  maquinas = null,
  error = null,
  ordenes = null,
  ahora = 0,
}: PropsLista) {
  return (
    <div className={s.pagina}>
      <main className={s.contenido}>
        <header className={s.cabeza}>
          <div className={s.cabezaTexto}>
            <h1 className={s.titulo}>Proyectos</h1>
            <p className={s.secundario}>
              Cada proyecto tiene su carpeta, un orquestador y sus agentes de
              código.
            </p>
          </div>
          <div className={s.acciones}>
            <Link href="/oficina/3d" className={s.boton}>
              Ir a la oficina
            </Link>
            <Link href="/ajustes" className={s.boton}>
              Ajustes
            </Link>
            <Link href="/proyectos/nuevo" className={s.botonPrincipal}>
              Nuevo proyecto
            </Link>
          </div>
        </header>
        <DecisionesVista ordenes={ordenes} ahora={ahora} />
        {error && !proyectos && (
          <p className={s.avisoError} role="status">
            No se pudieron leer los proyectos ({error}); se reintenta solo.
          </p>
        )}
        {!proyectos && !error && <p className={s.secundario}>Cargando…</p>}
        {proyectos && proyectos.length === 0 && (
          <p className={s.aviso}>
            Todavía no creaste ningún proyecto. Con &quot;Nuevo proyecto&quot;
            eliges la máquina, la cuenta y el equipo, y la oficina crea la
            carpeta y lanza al orquestador y a sus agentes.
          </p>
        )}
        {proyectos && proyectos.length > 0 && (
          <ul className={s.filas} aria-label="Proyectos creados">
            {proyectos.map((p) => {
              const e = estadoDe(p);
              const haciendo = haciendoDe(p);
              return (
                <li key={p.id}>
                  <Link
                    href={enlaceProyecto(p.id)}
                    className={
                      e.tono === "morado" ? `${s.fila} ${s.filaFuerte}` : s.fila
                    }
                  >
                    <span className={s.filaNombre}>
                      {p.nombre}
                      {p.prueba && <span className={s.prueba}>Prueba</span>}
                    </span>
                    <span className={`${s.estado} ${s[e.tono]}`}>
                      {e.texto}
                    </span>
                    <span className={s.filaDatos}>
                      <span
                        className={
                          p.estado === "error"
                            ? s.filaHaciendoError
                            : s.filaHaciendo
                        }
                      >
                        {haciendo}
                      </span>
                      <span className={s.secundario}>
                        {nombreCuenta(p.cuenta)} ·{" "}
                        {nombreMaquina(p.maquina, maquinas)} ·{" "}
                        {resumenEquipo(p.equipo)}
                      </span>
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
        {error && proyectos && (
          <p className={s.secundario} role="status">
            La última lectura falló ({error}); se reintenta solo.
          </p>
        )}
      </main>
    </div>
  );
}

/** The page with its reads: projects and orders (3 s), machines (30 s). */
export default function ListaProyectos() {
  const router = useRouter();
  const api = useLectura<{ proyectos: Proyecto[] }>(
    "/api/v1/proyectos-creados",
    3000,
  );
  const maq = useLectura<{ maquinas: Maquina[] }>(
    "/api/v1/proyectos-creados/maquinas",
    30000,
  );
  const ord = useLectura<{ ordenes: Orden[] }>(
    "/api/v1/ordenes?estado=por_aprobar",
    3000,
  );
  const ahora = useAhora();
  return (
    <>
      <ListaVista
        proyectos={api.datos?.proyectos ?? null}
        maquinas={maq.datos?.maquinas ?? null}
        error={api.error}
        ordenes={ord.datos?.ordenes ?? null}
        ahora={ahora}
      />
      <AvisosOrquestador irA={(url) => router.push(url)} />
    </>
  );
}
