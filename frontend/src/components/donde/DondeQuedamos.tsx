"use client";

/**
 * /donde-quedamos?proyecto=<id> (stage 2.3, mockups DondeQuedamos and
 * DondeCelular): on PC, the projects on the left (last activity, where it is,
 * alert) and the chosen one on the right (plan by stages, prompts of the
 * current stage, the three cards and today's consumption). On phones, the
 * compact version with the other projects at the end.
 */

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, type CSSProperties } from "react";
import {
  cuando,
  haceTiempo,
  miles,
  pedidoDe,
  resultado,
  tiempoCorto,
  type Consumo,
  type Historial,
  type Turno,
} from "@/components/ficha/logica";
import { useEstadoOficina } from "@/components/oficina/useEstadoOficina";
import { useLectura } from "@/utils/useLectura";
import {
  ESTADOS_PROMPT,
  armarProyectos,
  consumoDe,
  dondeVa,
  etapas,
  lineaConsumo,
  promptsDeEtapa,
  quienHace,
  textoUltima,
  type ProyectoApi,
  type ProyectoVista,
} from "./logica";
import s from "./donde.module.css";

export interface PropsVista {
  proyectos: ProyectoVista[] | null;
  elegido: string | null;
  consumo: Consumo | null;
  ahora: number;
  /** Last turn of the agent when the project report does not bring it. */
  turnoExtra?: Turno | null;
  /** Opened first on entering the office: "oficina" (8 h) or "nuevo" (new device). */
  desdeOficina?: boolean | "nuevo" | "oficina";
  error?: string | null;
}

function Lista({
  proyectos,
  elegido,
  ahora,
}: {
  proyectos: ProyectoVista[];
  elegido: ProyectoVista | null;
  ahora: number;
}) {
  return (
    <nav
      className={proyectos.length < 2 ? `${s.lista} ${s.soloPc}` : s.lista}
      aria-label="Proyectos"
    >
      <h2 className={`${s.listaTitulo} ${s.soloPc}`}>Dónde quedamos</h2>
      <h2 className={`${s.etiqueta} ${s.soloCel}`}>Otros proyectos</h2>
      <Link href="/oficina/3d" className={`${s.boton} ${s.soloPc}`}>
        Ir a la oficina
      </Link>
      <ul className={s.items}>
        {proyectos.map((p) => {
          const este = p.id === elegido?.id;
          return (
            <li key={p.id} className={este ? s.elegidoItem : undefined}>
              <Link
                href={`/donde-quedamos?proyecto=${encodeURIComponent(p.id)}`}
                className={este ? `${s.item} ${s.itemElegido}` : s.item}
                aria-current={este ? "page" : undefined}
                scroll
              >
                <span className={s.itemFila}>
                  <span className={s.itemNombre}>{p.nombre}</span>
                  <span className={s.itemCuando}>{textoUltima(p, ahora)}</span>
                </span>
                <span className={s.itemDonde}>{dondeVa(p)}</span>
                <span className={`${s.itemAlerta} ${s[p.alerta.tono]}`}>
                  <span className={s.soloPc}>{p.alerta.texto}</span>
                  <span className={s.soloCel}>{p.alerta.corto}</span>
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

function Plan({ p }: { p: ProyectoApi }) {
  const lista = etapas(p.plan, p.posicion);
  if (!lista.length) return null;
  const actual = lista.find((e) => e.estado === "actual");
  const ultima = lista[lista.length - 1];
  return (
    <section className={s.plan} aria-labelledby="plan-titulo">
      <h2 id="plan-titulo" className={s.etiqueta}>
        Plan por etapas
      </h2>
      <ol className={s.etapas} style={{ "--n": lista.length } as CSSProperties}>
        {lista.map((e) => (
          <li
            key={e.etiqueta}
            className={`${s.etapa} ${s[`etapa_${e.estado}`]}`}
            aria-current={e.estado === "actual" ? "step" : undefined}
            title={`${e.etiqueta}${e.nombre ? `: ${e.nombre}` : ""}`}
          >
            <span className={s.etapaNumero} aria-hidden="true">
              <span className={s.soloPc}>{e.etiqueta}</span>
              <span className={s.soloCel}>{e.corto}</span>
            </span>
            <span className={`${s.etapaNombre} ${s.soloPc}`} aria-hidden="true">
              {e.nombre}
            </span>
            <span className={`${s.etapaEstado} ${s.soloPc}`} aria-hidden="true">
              {e.estado === "actual"
                ? "Estás aquí"
                : e.estado === "hecha"
                  ? "Hecha"
                  : "Pendiente"}
            </span>
            <span className={s.oculto}>
              {e.etiqueta}
              {e.nombre ? `: ${e.nombre}` : ""}
              {e.estado === "actual"
                ? ", estás aquí"
                : e.estado === "hecha"
                  ? ", hecha"
                  : ", pendiente"}
            </span>
          </li>
        ))}
      </ol>
      {actual && (
        <p className={`${s.secundario} ${s.soloCel}`}>
          {actual.etiqueta} de {ultima.corto}
          {actual.nombre ? ` · ${actual.nombre}` : ""}
        </p>
      )}
    </section>
  );
}

function Aqui({ p }: { p: ProyectoApi }) {
  const lista = etapas(p.plan, p.posicion);
  const actual = lista.find((e) => e.estado === "actual");
  const prompts = promptsDeEtapa(p);
  const titulo = actual
    ? `${actual.etiqueta}${actual.nombre ? ` · ${actual.nombre}` : ""}`
    : (p.posicion ?? "Posición sin anotar");
  return (
    <section className={s.aqui} aria-labelledby="aqui-titulo">
      <div className={s.aquiCabeza}>
        <span className={s.marcaAqui}>Estás aquí</span>
        <h2 id="aqui-titulo" className={s.aquiTitulo}>
          {titulo}
        </h2>
      </div>
      {prompts.length ? (
        <ol className={s.prompts}>
          {prompts.map((pr) => {
            const e = ESTADOS_PROMPT[pr.estado];
            return (
              <li
                key={pr.numero}
                className={`${s.prompt} ${pr.actual ? s.promptActual : s.promptOtro}`}
              >
                <span className={s.promptFila}>
                  <span className={s.promptNumero}>Prompt {pr.numero}</span>
                  <span className={`${s.promptEstado} ${s[e.tono]}`}>
                    {e.texto}
                  </span>
                </span>
                {pr.nombre && (
                  <span className={s.promptNombre}>{pr.nombre}</span>
                )}
                <span className={s.promptDato}>{pr.dato}</span>
              </li>
            );
          })}
        </ol>
      ) : (
        <p className={s.secundario}>
          El PROJECT.md no anota prompts para esta etapa.
        </p>
      )}
    </section>
  );
}

function Tarjetas({
  p,
  ahora,
  turnoExtra,
}: {
  p: ProyectoApi;
  ahora: number;
  turnoExtra: Turno | null;
}) {
  const c = p.ultimo_commit;
  const turno = p.ultima_actividad?.ultimo_turno ?? turnoExtra;
  const quien = quienHace(p.siguiente_paso);
  const n = p.espera_decision.length;
  return (
    <div className={s.tarjetas}>
      <section className={s.tarjeta} aria-labelledby="t-ultimo">
        <h2 id="t-ultimo" className={s.etiqueta}>
          Lo último que se hizo
        </h2>
        {c ? (
          <>
            <p className={s.fuerte}>{c.mensaje ?? "Commit sin mensaje"}</p>
            <p className={s.mono}>
              commit {c.hash}
              {c.fecha ? ` · ${cuando(c.fecha, ahora)}` : ""}
            </p>
          </>
        ) : (
          !turno && <p className={s.secundario}>Sin commits anotados.</p>
        )}
        {turno && (
          <p className={s.texto}>
            Último pedido al agente: {pedidoDe(turno)} (
            {resultado(turno.resultado).texto.toLowerCase()},{" "}
            {cuando(turno.inicio, ahora)})
          </p>
        )}
      </section>
      <section
        className={`${s.tarjeta} ${s.tarjetaSiguiente}`}
        aria-labelledby="t-siguiente"
      >
        <h2 id="t-siguiente" className={`${s.etiqueta} ${s.azul}`}>
          Lo siguiente
        </h2>
        <p className={s.fuerte}>
          {p.siguiente_paso ?? "El PROJECT.md no anota el siguiente paso."}
        </p>
        {quien && <p className={s.texto}>{quien}</p>}
      </section>
      <section
        className={`${s.tarjeta} ${n ? s.tarjetaDecision : ""}`}
        aria-labelledby="t-decision"
      >
        <h2 id="t-decision" className={`${s.etiqueta} ${n ? s.naranja : ""}`}>
          Espera tu decisión{n ? ` · ${n}` : ""}
        </h2>
        {n ? (
          <ul className={s.decisiones}>
            {p.espera_decision.map((d) => (
              <li key={d}>{d}</li>
            ))}
          </ul>
        ) : (
          <p className={s.secundario}>Nada por ahora.</p>
        )}
      </section>
    </div>
  );
}

function SinPlan({
  p,
  ahora,
  turnoExtra,
}: {
  p: ProyectoVista;
  ahora: number;
  turnoExtra: Turno | null;
}) {
  const act = p.datos.ultima_actividad;
  const agente = p.agentes[0];
  const turno = act?.ultimo_turno ?? turnoExtra;
  const estado = act?.estado ?? agente?.estado.nombre ?? null;
  const espera = act?.espera ?? agente?.espera_detalle?.texto ?? null;
  return (
    <>
      <p className={s.avisoPlan} role="note">
        Este proyecto no tiene PROJECT.md, así que no hay plan por etapas ni
        siguiente paso anotado. Abajo está lo último que hizo el agente en esta
        carpeta.
      </p>
      <section className={s.tarjeta} aria-labelledby="t-agente">
        <h2 id="t-agente" className={s.etiqueta}>
          Lo último que hizo el agente
        </h2>
        {turno ? (
          <>
            <p className={s.fuerte}>{pedidoDe(turno)}</p>
            <p className={s.texto}>
              {resultado(turno.resultado).texto} · {cuando(turno.inicio, ahora)}{" "}
              · {tiempoCorto(turno.duracion_s)}
              {turno.commits.length
                ? ` · ${turno.commits.length} ${turno.commits.length === 1 ? "commit" : "commits"}`
                : ""}
            </p>
          </>
        ) : (
          <p className={s.secundario}>
            Todavía no hay turnos registrados en esta carpeta.
          </p>
        )}
        {(estado || espera) && (
          <p className={s.secundario}>
            Ahora: {[estado, espera].filter(Boolean).join(" · ")}
          </p>
        )}
        {p.datos.ultimo_commit && (
          <p className={s.mono}>
            commit {p.datos.ultimo_commit.hash} ·{" "}
            {p.datos.ultimo_commit.mensaje ?? "sin mensaje"}
          </p>
        )}
      </section>
    </>
  );
}

/** The page with its data given (tested with sample data). */
export function DondeVista({
  proyectos,
  elegido: idElegido,
  consumo,
  ahora,
  turnoExtra = null,
  desdeOficina = false,
  error = null,
}: PropsVista) {
  const elegido =
    proyectos?.find((p) => p.id === idElegido) ?? proyectos?.[0] ?? null;
  const hoy = lineaConsumo(consumo);
  const delProyecto = elegido ? consumoDe(consumo, elegido.carpeta) : null;
  // Opened by the 8-hour rule: the reason is read first.
  const aviso = useRef<HTMLParagraphElement>(null);
  useEffect(() => {
    if (desdeOficina) aviso.current?.focus();
  }, [desdeOficina]);

  return (
    <div className={s.pagina}>
      <main className={s.principal}>
        <div className={`${s.barraCel} ${s.soloCel}`}>
          <Link href="/oficina/3d" className={s.boton}>
            Ir a la oficina
          </Link>
        </div>
        {desdeOficina && (
          <p className={s.bienvenida} ref={aviso} tabIndex={-1}>
            {desdeOficina === "nuevo"
              ? "Primera visita desde este dispositivo: así van tus proyectos."
              : "Pasaron más de 8 horas desde tu última visita: así quedaron tus proyectos."}{" "}
            <Link href="/oficina/3d" className={`${s.boton} ${s.botonAviso}`}>
              Seguir a la oficina
            </Link>
          </p>
        )}
        {error && !proyectos && (
          <p className={s.avisoPlan} role="status">
            No se pudieron leer los proyectos ({error}); se reintenta solo.
          </p>
        )}
        {!proyectos && !error && <p className={s.secundario}>Cargando…</p>}
        {proyectos && proyectos.length === 0 && (
          <>
            <h1 className={s.titulo}>Dónde quedamos</h1>
            <p className={s.avisoPlan}>
              Todavía no hay proyectos: aparecen cuando un agente trabaja en una
              carpeta (el monitor de cada máquina manda su PROJECT.md).
            </p>
          </>
        )}
        {elegido && (
          <>
            <header className={s.cabeza}>
              <div className={s.cabezaTexto}>
                <p className={`${s.secundario} ${s.soloCel}`}>Dónde quedamos</p>
                <h1 className={s.titulo}>{elegido.nombre}</h1>
                <p className={s.secundario}>
                  Última actividad: {textoUltima(elegido, ahora)}
                  {elegido.agentes[0]
                    ? ` · ${elegido.agentes[0].estado.nombre}`
                    : ""}
                  {elegido.datos.tiene_project_md && elegido.datos.recibido
                    ? ` · PROJECT.md leído ${haceTiempo(elegido.datos.recibido, ahora)}`
                    : ""}
                </p>
              </div>
              {hoy && (
                <p className={s.consumo}>
                  {hoy}
                  {delProyecto &&
                    delProyecto.segundos + delProyecto.tokens > 0 && (
                      <span className={s.consumoProyecto}>
                        En este proyecto: {tiempoCorto(delProyecto.segundos)} ·{" "}
                        {miles(delProyecto.tokens)} tokens
                      </span>
                    )}
                </p>
              )}
            </header>
            {elegido.datos.tiene_project_md ? (
              <>
                <Plan p={elegido.datos} />
                <Aqui p={elegido.datos} />
                <Tarjetas
                  p={elegido.datos}
                  ahora={ahora}
                  turnoExtra={turnoExtra}
                />
              </>
            ) : (
              <SinPlan p={elegido} ahora={ahora} turnoExtra={turnoExtra} />
            )}
          </>
        )}
      </main>
      {/* After the content in the DOM (reading order); on PC it shows on the left. */}
      {proyectos && proyectos.length > 0 && (
        <Lista proyectos={proyectos} elegido={elegido} ahora={ahora} />
      )}
    </div>
  );
}

/** The page with its reads: projects (30 s), consumption (60 s), agents (2 s). */
export default function DondeQuedamos() {
  const params = useSearchParams();
  const pedido = params.get("proyecto");
  const desde = params.get("desde");
  const desdeOficina = desde === "oficina" || desde === "nuevo" ? desde : false;
  const { datos: estado, ahora } = useEstadoOficina();
  const api = useLectura<{ proyectos: ProyectoApi[] }>(
    "/api/v1/proyectos",
    30000,
  );
  const consumo = useLectura<Consumo>("/api/v1/consumo", 60000);
  const proyectos = useMemo(
    () =>
      api.datos
        ? armarProyectos(api.datos.proyectos, estado?.agentes ?? [])
        : null,
    [api.datos, estado],
  );
  const elegido =
    proyectos?.find((p) => p.id === pedido) ?? proyectos?.[0] ?? null;
  // Without the last turn in the report (older monitor), read it from the agent.
  const sesion =
    elegido && !elegido.datos.ultima_actividad?.ultimo_turno
      ? (elegido.agentes[0]?.agente.session_id ?? null)
      : null;
  const extra = useLectura<Historial>(
    sesion
      ? `/api/v1/agents/${encodeURIComponent(sesion)}/historial?por_pagina=1`
      : null,
    30000,
  );
  return (
    <DondeVista
      proyectos={proyectos}
      elegido={elegido?.id ?? null}
      consumo={consumo.datos}
      ahora={ahora}
      turnoExtra={extra.datos?.turnos[0] ?? null}
      desdeOficina={desdeOficina}
      error={api.error}
    />
  );
}
