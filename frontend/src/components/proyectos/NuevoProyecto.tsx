"use client";

/**
 * /proyectos/nuevo (Prompt 37): name (with the folder that will be created),
 * machine, account, template, the team (orchestrator and 1 to 4 code agents)
 * and the switch to approve orders automatically. On creating, goes to the
 * project.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState, type FormEvent } from "react";
import { apiFetch } from "@/utils/api";
import { useLectura } from "@/utils/useLectura";
import {
  AGENTE_POR_DEFECTO,
  CUENTAS,
  MAX_AGENTES,
  PLANTILLAS,
  borradorInicial,
  cuerpoCrear,
  detalleError,
  enlaceProyecto,
  errorNombre,
  primeraDisponible,
  puedeCrear,
  rutaNueva,
  type Borrador,
  type Maquina,
  type Proyecto,
} from "./logica";
import SelectorModelo from "./SelectorModelo";
import s from "./proyectos.module.css";

function Segmentos<T extends string>({
  nombre,
  opciones,
  valor,
  cambiar,
}: {
  nombre: string;
  opciones: { valor: T; texto: string }[];
  valor: T;
  cambiar: (v: T) => void;
}) {
  return (
    <div className={s.segmentos}>
      {opciones.map((o) => (
        <label key={o.valor} className={s.segmento}>
          <input
            type="radio"
            name={nombre}
            value={o.valor}
            checked={valor === o.valor}
            onChange={() => cambiar(o.valor)}
          />
          {o.texto}
        </label>
      ))}
    </div>
  );
}

export interface PropsFormulario {
  maquinas: Maquina[] | null;
  errorMaquinas?: string | null;
  /** Sends the body; resolves with the new project or rejects with the message. */
  crear: (cuerpo: Borrador) => Promise<void>;
}

/** The form with its machines given (tested with sample data). */
export function FormularioNuevo({
  maquinas,
  errorMaquinas = null,
  crear,
}: PropsFormulario) {
  const [b, setB] = useState<Borrador>(() => borradorInicial());
  const [tocado, setTocado] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [errorServidor, setErrorServidor] = useState<string | null>(null);
  const idNombre = useId();

  // Preselect the first available machine (derived: no effect needed).
  const elegida =
    maquinas?.find((m) => m.id === b.maquina && m.disponible)?.id ??
    primeraDisponible(maquinas);
  const borrador: Borrador = { ...b, maquina: elegida };
  const maquina = maquinas?.find((m) => m.id === elegida) ?? null;
  const nombre = b.nombre.trim();
  const errNombre = errorNombre(nombre);
  const mostrarError = Boolean(errNombre) && (tocado || nombre.length > 0);
  const ruta = rutaNueva(maquina?.ruta_base, nombre || "nombre-del-proyecto");
  const habilitado = puedeCrear(borrador, maquinas) && !enviando;
  const hayDisponible = Boolean(maquinas?.some((m) => m.disponible));

  const poner = (cambio: Partial<Borrador>) =>
    setB((v) => ({ ...v, ...cambio }));

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    setTocado(true);
    if (!habilitado) return;
    setEnviando(true);
    setErrorServidor(null);
    try {
      await crear(cuerpoCrear(borrador));
    } catch (err) {
      setErrorServidor(err instanceof Error ? err.message : String(err));
      setEnviando(false);
    }
  };

  return (
    <div className={s.pagina}>
      <main className={`${s.contenido} ${s.angosto}`}>
        <nav className={s.migas} aria-label="Navegación">
          <Link href="/proyectos" className={s.enlace}>
            Volver a Proyectos
          </Link>
        </nav>
        <h1 className={s.titulo}>Nuevo proyecto</h1>
        <form className={s.formulario} onSubmit={enviar} noValidate>
          <div className={s.bloque}>
            <label htmlFor={idNombre} className={s.campoTitulo}>
              Nombre
            </label>
            <input
              id={idNombre}
              className={
                mostrarError ? `${s.control} ${s.controlError}` : s.control
              }
              value={b.nombre}
              onChange={(e) => poner({ nombre: e.target.value })}
              onBlur={() => setTocado(true)}
              autoComplete="off"
              autoCapitalize="none"
              spellCheck={false}
              maxLength={60}
              aria-invalid={mostrarError}
              aria-describedby={`${idNombre}-ruta ${idNombre}-error`}
              placeholder="mi-proyecto"
            />
            <p id={`${idNombre}-ruta`} className={s.ruta}>
              {ruta ? (
                <>
                  Se va a crear: <span className={s.mono}>{ruta}</span>
                </>
              ) : (
                "Elige una máquina para ver la carpeta que se va a crear."
              )}
            </p>
            <p
              id={`${idNombre}-error`}
              className={s.errorCampo}
              aria-live="polite"
            >
              {mostrarError ? errNombre : ""}
            </p>
          </div>

          <fieldset className={s.bloque}>
            <legend>Máquina</legend>
            {!maquinas && !errorMaquinas && (
              <p className={s.secundario}>Cargando las máquinas…</p>
            )}
            {!maquinas && errorMaquinas && (
              <p className={s.avisoError} role="status">
                No se pudieron leer las máquinas ({errorMaquinas}); se reintenta
                solo.
              </p>
            )}
            {maquinas && maquinas.length === 0 && (
              <p className={s.aviso}>
                No hay máquinas registradas. Instala el monitor en una máquina
                para crear proyectos en ella.
              </p>
            )}
            {maquinas && maquinas.length > 0 && (
              <ul className={s.opciones}>
                {maquinas.map((m) => (
                  <li key={m.id}>
                    <label
                      className={
                        m.disponible
                          ? s.opcion
                          : `${s.opcion} ${s.opcionApagada}`
                      }
                    >
                      <input
                        type="radio"
                        name="maquina"
                        value={m.id}
                        checked={elegida === m.id}
                        disabled={!m.disponible}
                        onChange={() => poner({ maquina: m.id })}
                      />
                      <span className={s.opcionTexto}>
                        <span className={s.opcionNombre}>{m.nombre}</span>
                        <span className={s.secundario}>
                          {m.disponible
                            ? m.encendida
                              ? "Encendida"
                              : "Disponible"
                            : (m.motivo ?? "No disponible")}
                          {m.ruta_base ? (
                            <>
                              {" · "}
                              <span className={s.mono}>{m.ruta_base}</span>
                            </>
                          ) : null}
                        </span>
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
            )}
            {maquinas && maquinas.length > 0 && !hayDisponible && (
              <p className={s.errorCampo}>
                Ninguna máquina está disponible ahora.
              </p>
            )}
          </fieldset>

          <fieldset className={s.bloque}>
            <legend>Cuenta</legend>
            <Segmentos
              nombre="cuenta"
              opciones={CUENTAS}
              valor={b.cuenta}
              cambiar={(cuenta) => poner({ cuenta })}
            />
          </fieldset>

          <fieldset className={s.bloque}>
            <legend>Plantilla</legend>
            <Segmentos
              nombre="plantilla"
              opciones={PLANTILLAS}
              valor={b.plantilla}
              cambiar={(plantilla) => poner({ plantilla })}
            />
          </fieldset>

          <fieldset className={s.bloque}>
            <legend>Equipo</legend>
            <SelectorModelo
              titulo="Orquestador"
              valor={b.orquestador}
              cambiar={(orquestador) => poner({ orquestador })}
            />
            {b.agentes.map((a, i) => (
              <SelectorModelo
                key={i}
                titulo={
                  b.agentes.length > 1
                    ? `Agente de código ${i + 1}`
                    : "Agente de código"
                }
                valor={a}
                cambiar={(v) =>
                  setB((x) => ({
                    ...x,
                    agentes: x.agentes.map((y, j) => (j === i ? v : y)),
                  }))
                }
                quitar={
                  i > 0
                    ? () =>
                        setB((x) => ({
                          ...x,
                          agentes: x.agentes.filter((_, j) => j !== i),
                        }))
                    : undefined
                }
              />
            ))}
            {b.agentes.length < MAX_AGENTES ? (
              <div>
                <button
                  type="button"
                  className={s.boton}
                  onClick={() =>
                    setB((x) => ({
                      ...x,
                      agentes: [...x.agentes, { ...AGENTE_POR_DEFECTO }],
                    }))
                  }
                >
                  Agregar otro agente de código
                </button>
              </div>
            ) : (
              <p className={s.nota}>Hasta {MAX_AGENTES} agentes de código.</p>
            )}
          </fieldset>

          <div className={s.bloque}>
            <div className={s.interruptorFila}>
              <button
                type="button"
                role="switch"
                id={`${idNombre}-auto`}
                className={s.interruptor}
                aria-checked={b.auto_aprobar}
                aria-labelledby={`${idNombre}-auto-t`}
                aria-describedby={`${idNombre}-auto-n`}
                onClick={() => poner({ auto_aprobar: !b.auto_aprobar })}
              />
              <span id={`${idNombre}-auto-t`} className={s.campoTitulo}>
                Aprobar órdenes automáticamente
              </span>
            </div>
            <p id={`${idNombre}-auto-n`} className={s.nota}>
              Encendido: las órdenes del orquestador llegan al agente sin pasar
              por ti.
            </p>
          </div>

          {errorServidor && (
            <p className={s.avisoError} role="alert">
              {errorServidor}
            </p>
          )}
          <div className={s.pie}>
            <button
              type="submit"
              className={s.botonPrincipal}
              disabled={!habilitado}
            >
              {enviando ? "Creando…" : "Crear proyecto"}
            </button>
            <Link href="/proyectos" className={s.boton}>
              Cancelar
            </Link>
          </div>
        </form>
      </main>
    </div>
  );
}

/** The page with its read of the machines (10 s) and the POST. */
export default function NuevoProyecto() {
  const router = useRouter();
  const maq = useLectura<{ maquinas: Maquina[] }>(
    "/api/v1/proyectos-creados/maquinas",
    10000,
  );
  const crear = async (cuerpo: Borrador) => {
    let r: Response;
    try {
      r = await apiFetch("/api/v1/proyectos-creados", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cuerpo),
      });
    } catch {
      throw new Error("No se pudo conectar con el servidor; intenta de nuevo.");
    }
    if (!r.ok) throw new Error(await detalleError(r));
    const p = (await r.json()) as Proyecto;
    router.push(enlaceProyecto(p.id));
  };
  return (
    <FormularioNuevo
      maquinas={maq.datos?.maquinas ?? null}
      errorMaquinas={maq.error}
      crear={crear}
    />
  );
}
