"use client";

/**
 * /proyectos/ver?id=<id>&seccion=chat|equipo|donde (Prompt 37): the header of
 * the project and three sections. Chat (Prompt 38) talks with the orchestrator
 * and shows its orders to the code agents; Equipo shows each member with what
 * the office sees, the pause/resume/stop buttons, the switch to approve orders
 * automatically, "Agregar agente de código" and the history of orders; "Dónde
 * quedamos" reuses that view fixed to this project. Prompt 39 adds to Equipo
 * the house rules and safe commands of the project, each with its switch, and
 * the switch note says what happens in its current state. Refreshed every 3 s.
 */

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useId, useState, type FormEvent, type ReactNode } from "react";
import DondeQuedamos from "@/components/donde/DondeQuedamos";
import { useLectura } from "@/utils/useLectura";
import { enviarJson, mensajeDe, useAhora } from "./acciones";
import { ChatVista } from "./Chat";
import Dialogo from "./Dialogo";
import { Estado, nombreMaquina } from "./ListaProyectos";
import { ReglasProyectoVista } from "./Reglas";
import type { ReglasDeProyecto } from "./logicaReglas";
import SelectorModelo from "./SelectorModelo";
import {
  AGENTE_POR_DEFECTO,
  MAX_AGENTES,
  accionesDe,
  cuantosAgentes,
  enlaceProyecto,
  estadoMiembro,
  estadoOrden,
  haciendoDe,
  historialOrdenes,
  nombreCuenta,
  nombreEsfuerzo,
  nombreModelo,
  nombrePlantilla,
  nombreRol,
  textoAuto,
  textoCorto,
  textoDificultad,
  textoEstimado,
  textoOficina,
  unirOrdenes,
  type Chat,
  type ConfigModelo,
  type Maquina,
  type Orden,
  type Proyecto,
} from "./logica";
import s from "./proyectos.module.css";

export type Seccion = "chat" | "equipo" | "donde";

export type Accion = "pausar" | "reanudar" | "detener";

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

const TEXTO_DETENER =
  "Se cierran las sesiones del orquestador y los agentes. La carpeta queda intacta y puedes reanudar después.";

/** History of the orders of the project, the newest first. */
function HistorialOrdenes({
  ordenes,
  proyectoId,
}: {
  ordenes: Orden[] | null;
  proyectoId: string;
}) {
  return (
    <section className={s.bloque} aria-labelledby="historial-titulo">
      <h3 id="historial-titulo" className={s.campoTitulo}>
        Órdenes
      </h3>
      {!ordenes && <p className={s.secundario}>Cargando las órdenes…</p>}
      {ordenes && ordenes.length === 0 && (
        <p className={s.secundario}>
          Todavía no hay órdenes. El orquestador las propone en el chat.
        </p>
      )}
      {ordenes && ordenes.length > 0 && (
        <ul className={s.historial}>
          {historialOrdenes(ordenes).map((o) => {
            const e = estadoOrden(o.estado);
            return (
              <li
                key={o.id}
                className={
                  o.estado === "por_aprobar"
                    ? `${s.historialFila} ${s.historialPendiente}`
                    : s.historialFila
                }
              >
                <span className={s.historialTitulo}>
                  Orden {o.numero} · {o.agente}
                </span>
                <span className={`${s.estado} ${s[e.tono]}`}>{e.texto}</span>
                <span className={s.historialResto}>
                  <span className={s.filaHaciendo}>
                    {o.titulo || textoCorto(o.texto)}
                  </span>
                  {(o.estimado || o.dificultad) && (
                    <span className={s.secundario}>
                      {[
                        o.estimado && textoEstimado(o.estimado),
                        o.dificultad && textoDificultad(o.dificultad),
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                  )}
                  {o.resumen && (
                    <span className={s.secundario}>
                      Resultado: {textoCorto(o.resumen, 200)}
                    </span>
                  )}
                  {o.estado === "por_aprobar" && (
                    <Link
                      href={enlaceProyecto(proyectoId, "chat")}
                      className={s.enlace}
                    >
                      Decidir en el chat
                      <span className={s.oculto}> la orden {o.numero}</span>
                    </Link>
                  )}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

/** "Agregar agente de código": a small form with model and effort. */
function AgregarAgente({
  proyecto: p,
  agregar,
  ocupado,
}: {
  proyecto: Proyecto;
  agregar: (c: ConfigModelo) => Promise<void>;
  ocupado: boolean;
}) {
  const [abierto, setAbierto] = useState(false);
  const [config, setConfig] = useState<ConfigModelo>({
    ...AGENTE_POR_DEFECTO,
  });
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lleno = cuantosAgentes(p.equipo) >= MAX_AGENTES;

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      await agregar(config);
      setAbierto(false);
      setConfig({ ...AGENTE_POR_DEFECTO });
    } catch (err) {
      setError(mensajeDe(err));
    } finally {
      setEnviando(false);
    }
  };

  if (!abierto)
    return (
      <div className={s.botonesEquipo}>
        <button
          type="button"
          className={s.boton}
          disabled={lleno || ocupado}
          aria-describedby={lleno ? "agregar-nota" : undefined}
          onClick={() => {
            setError(null);
            setAbierto(true);
          }}
        >
          Agregar agente de código
        </button>
        {lleno && (
          <p id="agregar-nota" className={s.nota}>
            Ya tiene {MAX_AGENTES} agentes de código, el máximo.
          </p>
        )}
      </div>
    );
  return (
    <form className={s.bloque} onSubmit={enviar}>
      <SelectorModelo
        titulo="Nuevo agente de código"
        valor={config}
        cambiar={setConfig}
      />
      {error && (
        <p className={s.avisoError} role="alert">
          {error}
        </p>
      )}
      <div className={s.pie}>
        <button
          type="submit"
          className={s.botonPrincipal}
          disabled={enviando || lleno}
        >
          {enviando ? "Agregando…" : "Agregar"}
        </button>
        <button
          type="button"
          className={s.boton}
          disabled={enviando}
          onClick={() => setAbierto(false)}
        >
          Cancelar
        </button>
      </div>
    </form>
  );
}

export interface PropsEquipo {
  proyecto: Proyecto;
  /** Sends pause, resume or stop; rejects with the message of the server. */
  accion: (tipo: Accion) => Promise<void>;
  /** Orders of the project (null while they are read). */
  ordenes?: Orden[] | null;
  /** POST auto-aprobar; rejects with the message of the server. */
  autoAprobar?: (activo: boolean) => Promise<void>;
  /** POST agentes; rejects with the message of the server. */
  agregarAgente?: (c: ConfigModelo) => Promise<void>;
  /** House rules and safe commands of the project (null while they are read). */
  reglas?: ReglasDeProyecto | null;
  errorReglas?: string | null;
  /** POST .../reglas/{id}; rejects with the message of the server. */
  cambiarRegla?: (id: string, activa: boolean) => Promise<void>;
  /** POST .../comandos/{id}; rejects with the message of the server. */
  cambiarComando?: (id: string, activo: boolean) => Promise<void>;
}

const nada = async () => {};

/** Equipo section: members, buttons, switch, history and the error. */
export function EquipoVista({
  proyecto: p,
  accion,
  ordenes = null,
  autoAprobar = nada,
  agregarAgente = nada,
  reglas = null,
  errorReglas = null,
  cambiarRegla = nada,
  cambiarComando = nada,
}: PropsEquipo) {
  const id = useId();
  const [enviando, setEnviando] = useState<Accion | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmar, setConfirmar] = useState(false);
  const [auto, setAuto] = useState<boolean | null>(null);
  const [errorAuto, setErrorAuto] = useState<string | null>(null);
  const a = accionesDe(p.estado);
  const hacer = async (tipo: Accion) => {
    setEnviando(tipo);
    setError(null);
    try {
      await accion(tipo);
    } catch (e) {
      setError(mensajeDe(e));
    } finally {
      setEnviando(null);
    }
  };
  const cambiarAuto = async () => {
    const nuevo = !(auto ?? p.auto_aprobar);
    setAuto(nuevo);
    setErrorAuto(null);
    try {
      await autoAprobar(nuevo);
    } catch (e) {
      setErrorAuto(mensajeDe(e));
    } finally {
      setAuto(null);
    }
  };
  const equipo = [...p.equipo].sort(
    (x, y) =>
      (x.rol === "orquestador" ? 0 : 1) - (y.rol === "orquestador" ? 0 : 1) ||
      x.orden - y.orden,
  );
  const bloqueado = a.ocupado || enviando !== null;
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
      {(a.ocupado || p.estado === "detenido") && (
        <p className={s.aviso} role="status">
          {p.estado === "detenido"
            ? "El equipo está detenido. La carpeta quedó intacta; con Reanudar vuelve a trabajar."
            : haciendoDe({ ...p, haciendo: null })}
        </p>
      )}
      <div className={s.botonesEquipo}>
        {a.pausar && (
          <button
            type="button"
            className={s.boton}
            disabled={bloqueado}
            onClick={() => void hacer("pausar")}
          >
            {enviando === "pausar" ? "Pausando…" : "Pausar el equipo"}
          </button>
        )}
        {a.reanudar && (
          <button
            type="button"
            className={s.botonPrincipal}
            disabled={bloqueado}
            onClick={() => void hacer("reanudar")}
          >
            {enviando === "reanudar" ? "Reanudando…" : "Reanudar"}
          </button>
        )}
        {a.detener && (
          <button
            type="button"
            className={s.botonPeligro}
            disabled={bloqueado}
            onClick={() => setConfirmar(true)}
          >
            {enviando === "detener" ? "Deteniendo…" : "Detener"}
          </button>
        )}
      </div>
      {confirmar && (
        <Dialogo
          titulo="¿Detener el equipo?"
          texto={TEXTO_DETENER}
          textoConfirmar="Detener"
          confirmar={() => {
            setConfirmar(false);
            void hacer("detener");
          }}
          cancelar={() => setConfirmar(false)}
        />
      )}
      {error && (
        <p className={s.avisoError} role="alert">
          {error}
        </p>
      )}
      <div className={s.bloque}>
        <div className={s.interruptorFila}>
          <button
            type="button"
            role="switch"
            className={s.interruptor}
            aria-checked={auto ?? p.auto_aprobar}
            aria-labelledby={`${id}-auto-t`}
            aria-describedby={`${id}-auto-n`}
            disabled={auto !== null}
            onClick={() => void cambiarAuto()}
          />
          <span id={`${id}-auto-t`} className={s.campoTitulo}>
            Aprobar órdenes automáticamente
          </span>
        </div>
        <p id={`${id}-auto-n`} className={s.nota}>
          {textoAuto(auto ?? p.auto_aprobar)}
        </p>
        {errorAuto && (
          <p className={s.avisoError} role="alert">
            {errorAuto}
          </p>
        )}
      </div>
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
      <AgregarAgente
        proyecto={p}
        agregar={agregarAgente}
        ocupado={a.ocupado || p.estado === "creando"}
      />
      <ReglasProyectoVista
        datos={reglas}
        error={errorReglas}
        cambiarRegla={cambiarRegla}
        cambiarComando={cambiarComando}
      />
      <HistorialOrdenes ordenes={ordenes} proyectoId={p.id} />
    </section>
  );
}

export interface PropsVista {
  proyecto: Proyecto | null;
  seccion: Seccion;
  maquinas?: Maquina[] | null;
  error?: string | null;
  accion: (tipo: Accion) => Promise<void>;
  /** Chat of the project (messages and orders), null while it is read. */
  chat?: Chat | null;
  errorChat?: string | null;
  ahora?: number;
  autoAprobar?: (activo: boolean) => Promise<void>;
  agregarAgente?: (c: ConfigModelo) => Promise<void>;
  reglas?: ReglasDeProyecto | null;
  errorReglas?: string | null;
  cambiarRegla?: (id: string, activa: boolean) => Promise<void>;
  cambiarComando?: (id: string, activo: boolean) => Promise<void>;
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
  chat = null,
  errorChat = null,
  ahora = 0,
  autoAprobar,
  agregarAgente,
  reglas,
  errorReglas,
  cambiarRegla,
  cambiarComando,
  donde,
}: PropsVista) {
  // Orders decided here: the chat and the Equipo history show them at once.
  const [locales, setLocales] = useState<Record<string, Orden>>({});
  const cambioOrden = (o: Orden) => setLocales((v) => ({ ...v, [o.id]: o }));
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
              <ChatVista
                proyecto={p}
                chat={chat}
                error={errorChat}
                ahora={ahora}
                cambioOrden={cambioOrden}
                ordenesLocales={locales}
              />
            )}
            {seccion === "equipo" && (
              <EquipoVista
                proyecto={p}
                accion={accion}
                ordenes={chat ? unirOrdenes(chat.ordenes, locales) : null}
                autoAprobar={autoAprobar}
                agregarAgente={agregarAgente}
                reglas={reglas}
                errorReglas={errorReglas}
                cambiarRegla={cambiarRegla}
                cambiarComando={cambiarComando}
              />
            )}
            {seccion === "donde" && donde?.(p.nombre)}
          </>
        )}
      </main>
    </div>
  );
}

/**
 * The page with its reads: project, chat and rules of the project (3 s),
 * machines (30 s).
 */
export default function VerProyecto() {
  const params = useSearchParams();
  const id = params.get("id");
  const seccion = seccionDe(params.get("seccion"));
  const base = id
    ? `/api/v1/proyectos-creados/${encodeURIComponent(id)}`
    : null;
  const api = useLectura<Proyecto>(base, 3000);
  const chat = useLectura<Chat>(
    base && seccion !== "donde" ? `${base}/chat` : null,
    3000,
  );
  const maq = useLectura<{ maquinas: Maquina[] }>(
    "/api/v1/proyectos-creados/maquinas",
    30000,
  );
  const leidas = useLectura<ReglasDeProyecto>(
    base && seccion === "equipo" ? `${base}/reglas` : null,
    3000,
  );
  // The answer of a switch, shown until the next read.
  const [reglasLocal, setReglasLocal] = useState<{
    base: ReglasDeProyecto | null;
    datos: ReglasDeProyecto;
  } | null>(null);
  const reglas =
    reglasLocal && reglasLocal.base === leidas.datos
      ? reglasLocal.datos
      : leidas.datos;
  const cambiarAjuste = async (
    lista: "reglas" | "comandos",
    ajusteId: string,
    cuerpo: { activa: boolean } | { activo: boolean },
  ) => {
    if (!base) return;
    const antes = leidas.datos;
    const datos = await enviarJson<ReglasDeProyecto>(
      `${base}/${lista}/${encodeURIComponent(ajusteId)}`,
      cuerpo,
    );
    setReglasLocal({ base: antes, datos });
  };
  const ahora = useAhora();
  const [local, setLocal] = useState<Proyecto | null>(null);
  const accion = async (tipo: Accion) => {
    if (!base) return;
    setLocal(await enviarJson<Proyecto>(`${base}/${tipo}`));
  };
  const autoAprobar = async (activo: boolean) => {
    if (!base) return;
    setLocal(await enviarJson<Proyecto>(`${base}/auto-aprobar`, { activo }));
  };
  const agregarAgente = async (c: ConfigModelo) => {
    if (!base) return;
    setLocal(
      await enviarJson<Proyecto>(`${base}/agentes`, {
        modelo: c.modelo,
        esfuerzo: c.esfuerzo,
      }),
    );
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
      chat={chat.datos}
      errorChat={chat.error}
      ahora={ahora}
      autoAprobar={autoAprobar}
      agregarAgente={agregarAgente}
      reglas={reglas}
      errorReglas={leidas.error}
      cambiarRegla={(rid, activa) => cambiarAjuste("reglas", rid, { activa })}
      cambiarComando={(cid, activo) =>
        cambiarAjuste("comandos", cid, { activo })
      }
      donde={(nombre) => <DondeQuedamos proyecto={nombre} />}
    />
  );
}
