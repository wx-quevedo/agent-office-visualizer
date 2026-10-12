"use client";

/**
 * House rules and safe commands of one project (Prompt 39), inside the Equipo
 * section: each global rule and command with its switch for this project
 * (POST /proyectos-creados/{id}/reglas/{regla_id} and .../comandos/{id}),
 * "Ajustada en este proyecto" when it differs from the global value, and the
 * link to edit the global lists in /ajustes. Also the switch used by /ajustes.
 */

import Link from "next/link";
import { useId, useState } from "react";
import { mensajeDe } from "./acciones";
import { nombreTipo, type ReglasDeProyecto } from "./logicaReglas";
import s from "./proyectos.module.css";

export interface PropsInterruptor {
  activo: boolean;
  /** Ids of the visible texts that name it (aria-labelledby). */
  nombradoPor: string;
  describe?: string;
  ocupado?: boolean;
  cambiar: () => void;
}

/** The switch of the projects (44 px tall, blue when on). */
export function Interruptor({
  activo,
  nombradoPor,
  describe,
  ocupado = false,
  cambiar,
}: PropsInterruptor) {
  return (
    <button
      type="button"
      role="switch"
      className={s.interruptor}
      aria-checked={activo}
      aria-labelledby={nombradoPor}
      aria-describedby={describe}
      disabled={ocupado}
      onClick={cambiar}
    />
  );
}

export interface PropsReglasProyecto {
  /** GET /proyectos-creados/{id}/reglas (null while it is read). */
  datos: ReglasDeProyecto | null;
  error?: string | null;
  /** POST .../reglas/{id}; rejects with the message of the server. */
  cambiarRegla: (id: string, activa: boolean) => Promise<void>;
  /** POST .../comandos/{id}; rejects with the message of the server. */
  cambiarComando: (id: string, activo: boolean) => Promise<void>;
}

/** "Reglas de la casa" and "Comandos seguros" of the project. */
export function ReglasProyectoVista({
  datos,
  error = null,
  cambiarRegla,
  cambiarComando,
}: PropsReglasProyecto) {
  const id = useId();
  // Value sent and not answered yet, by "r:<id>" or "c:<id>".
  const [enviando, setEnviando] = useState<Record<string, boolean>>({});
  const [errorReglas, setErrorReglas] = useState<string | null>(null);
  const [errorComandos, setErrorComandos] = useState<string | null>(null);

  const cambiar = async (
    clave: string,
    valor: boolean,
    enviar: () => Promise<void>,
    ponerError: (e: string | null) => void,
  ) => {
    setEnviando((v) => ({ ...v, [clave]: valor }));
    ponerError(null);
    try {
      await enviar();
    } catch (e) {
      ponerError(mensajeDe(e));
    } finally {
      setEnviando((v) => {
        const otro = { ...v };
        delete otro[clave];
        return otro;
      });
    }
  };

  const cargando = !datos && (
    <p className={s.secundario}>
      {error
        ? `No se pudieron leer las reglas (${error}); se reintenta solo.`
        : "Cargando…"}
    </p>
  );

  return (
    <>
      <section className={s.bloque} aria-labelledby={`${id}-reglas`}>
        <h3 id={`${id}-reglas`} className={s.campoTitulo}>
          Reglas de la casa
        </h3>
        <p className={s.nota}>
          Se escriben en el CLAUDE.md de este proyecto. Puedes apagar las que no
          le sirvan.
        </p>
        {cargando}
        {datos && datos.reglas.length === 0 && (
          <p className={s.secundario}>No hay reglas en la lista global.</p>
        )}
        {datos && datos.reglas.length > 0 && (
          <ul className={s.listaReglas}>
            {datos.reglas.map((r) => {
              const clave = `r:${r.id}`;
              const base = `${id}-r-${r.id}`;
              return (
                <li key={r.id} className={s.reglaFila}>
                  <Interruptor
                    activo={enviando[clave] ?? r.activa}
                    nombradoPor={`${base}-t`}
                    describe={r.ajustada ? `${base}-a` : undefined}
                    ocupado={clave in enviando}
                    cambiar={() =>
                      void cambiar(
                        clave,
                        !r.activa,
                        () => cambiarRegla(r.id, !r.activa),
                        setErrorReglas,
                      )
                    }
                  />
                  <span className={s.reglaTexto}>
                    <span className={s.etiqueta}>{nombreTipo(r.tipo)}</span>
                    <span id={`${base}-t`}>{r.texto}</span>
                    {r.ajustada && (
                      <span id={`${base}-a`} className={s.ajustada}>
                        Ajustada en este proyecto
                      </span>
                    )}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
        {errorReglas && (
          <p className={s.avisoError} role="alert">
            {errorReglas}
          </p>
        )}
      </section>
      <section className={s.bloque} aria-labelledby={`${id}-comandos`}>
        <h3 id={`${id}-comandos`} className={s.campoTitulo}>
          Comandos seguros
        </h3>
        <p className={s.nota}>
          Los agentes de código los corren sin pedirte permiso. Todo lo demás
          sigue pidiéndolo.
        </p>
        {cargando}
        {datos && datos.comandos.length === 0 && (
          <p className={s.secundario}>No hay comandos en la lista global.</p>
        )}
        {datos && datos.comandos.length > 0 && (
          <ul className={s.listaReglas}>
            {datos.comandos.map((c) => {
              const clave = `c:${c.id}`;
              const base = `${id}-c-${c.id}`;
              return (
                <li key={c.id} className={s.reglaFila}>
                  <Interruptor
                    activo={enviando[clave] ?? c.activo}
                    nombradoPor={`${base}-t`}
                    describe={c.ajustado ? `${base}-a` : undefined}
                    ocupado={clave in enviando}
                    cambiar={() =>
                      void cambiar(
                        clave,
                        !c.activo,
                        () => cambiarComando(c.id, !c.activo),
                        setErrorComandos,
                      )
                    }
                  />
                  <span className={s.reglaTexto}>
                    <span id={`${base}-t`} className={s.mono}>
                      {c.comando}
                    </span>
                    {c.ajustado && (
                      <span id={`${base}-a`} className={s.ajustada}>
                        Ajustado en este proyecto
                      </span>
                    )}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
        {errorComandos && (
          <p className={s.avisoError} role="alert">
            {errorComandos}
          </p>
        )}
      </section>
      <p className={s.secundario}>
        <Link href="/ajustes" className={s.enlace}>
          Editar la lista global en Ajustes
        </Link>
      </p>
    </>
  );
}
