"use client";

/**
 * /oficina v1 — the office in plain boxes (no art, no colours, no PixiJS).
 *
 * Reads GET /api/v1/agents/state every 2 s and sends a presence heartbeat
 * (POST /api/v1/agents/presence) every 30 s so an open /oficina counts as the
 * user being present, on PC or phone. Grouping and ordering live in logica.ts.
 * Clicking an agent opens its card (FichaAgente) over the boxes (?agente=<id>).
 */

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  useCallback,
  useMemo,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import BotonSalir from "@/components/acceso/BotonSalir";
import PanelAvisos from "@/components/avisos/PanelAvisos";
import { useVisitaOficina } from "@/components/donde/visita";
import FichaAgente from "@/components/ficha/FichaAgente";
import PanelConfigPermisos from "@/components/permisos/PanelConfigPermisos";
import PanelPermiso from "@/components/permisos/PanelPermiso";
import { useAvisos } from "@/components/avisos/useAvisos";
import { MarcaCuenta } from "@/components/marca/Marca";
import {
  CONTADORES,
  GRUPOS,
  agruparPorProyecto,
  agruparPorUrgencia,
  contar,
  detalleActual,
  duracion,
  esfuerzo,
  grupoDe,
  hace,
  loQuePide,
  minutosParaDesaparecer,
  nombreProyecto,
  numero,
  recortar,
  sesionCorta,
  textoPresencia,
  tipoEspera,
  visibles,
  type Agente,
} from "./logica";
import { useEstadoOficina, useLatidoPresencia } from "./useEstadoOficina";
import s from "./oficina.module.css";

const CLAVE_VISTA = "oficina-vista";

type Vista = "urgencia" | "proyecto";

// Chosen view: localStorage when available, memory otherwise.
let vistaEnMemoria: Vista | null = null;
const oyentesVista = new Set<() => void>();

function suscribirVista(f: () => void): () => void {
  oyentesVista.add(f);
  return () => oyentesVista.delete(f);
}

function leerVista(): Vista {
  if (vistaEnMemoria) return vistaEnMemoria;
  try {
    return window.localStorage.getItem(CLAVE_VISTA) === "proyecto"
      ? "proyecto"
      : "urgencia";
  } catch {
    return "urgencia";
  }
}

function guardarVista(v: Vista): void {
  vistaEnMemoria = v;
  try {
    window.localStorage.setItem(CLAVE_VISTA, v);
  } catch {
    // private window or blocked storage: the choice is not remembered
  }
  oyentesVista.forEach((f) => f());
}

function enlace(a: Agente): string {
  return `/oficina?agente=${encodeURIComponent(a.agente.session_id)}`;
}

/** Project name with the Demo Org isotype (the personal account has no mark). */
function Proyecto({ a, className }: { a: Agente; className: string }) {
  return (
    <div className={`${className} ${s.conMarca}`}>
      <MarcaCuenta cuenta={a.agente.cuenta} />
      {nombreProyecto(a)}
    </div>
  );
}

// -- small pieces --------------------------------------------------------------

function Avatar({ tam }: { tam: 88 | 72 | 64 | 48 }) {
  return (
    <div className={`${s.avatar} ${s[`avatar${tam}`]}`} aria-hidden="true">
      avatar
    </div>
  );
}

function EstadoTexto({ a, className }: { a: Agente; className?: string }) {
  return (
    <div className={className ?? s.estado}>
      {a.estado.numero} · {a.estado.nombre}
    </div>
  );
}

function Indicador({ nombre, valor }: { nombre: string; valor: ReactNode }) {
  return (
    <span>
      {nombre} <b>{valor}</b>
    </span>
  );
}

function Indicadores({
  a,
  ahora,
  conEstado,
}: {
  a: Agente;
  ahora: number;
  conEstado?: boolean;
}) {
  const i = a.indicadores;
  return (
    <div className={s.indicadores}>
      <Indicador
        nombre="Ritmo"
        valor={numero(i.herramientas_por_minuto, " herr/min")}
      />
      <Indicador nombre="Contexto" valor={numero(i.contexto_usado_pct, " %")} />
      <Indicador nombre="Errores seguidos" valor={numero(i.errores_seguidos)} />
      <Indicador nombre="Subagentes" valor={a.subagentes_activos} />
      <Indicador
        nombre="Trabajó"
        valor={numero(i.minutos_con_actividad, " min")}
      />
      {conEstado && (
        <Indicador
          nombre="En este estado"
          valor={duracion(a.estado.desde, ahora)}
        />
      )}
    </div>
  );
}

function Cabecera({ a }: { a: Agente }) {
  return (
    <>
      <Proyecto a={a} className={s.proyecto} />
      <div className={`${s.meta} ${s.mono}`}>
        {sesionCorta(a.agente.session_id)}
      </div>
      <EstadoTexto a={a} />
    </>
  );
}

// -- desks of the urgency view ---------------------------------------------------

/**
 * 13: the request with Approve / Reject while the hook waits for the office;
 * otherwise "Responde en VS Code". Outside the desk link (buttons inside a
 * link would open the detail).
 */
function BloquePermiso({ a, ahora }: { a: Agente; ahora: number }) {
  if (a.estado.numero !== 13) return null;
  if (a.permiso) return <PanelPermiso permiso={a.permiso} ahora={ahora} />;
  return <p className={s.respondeVsCode}>Responde en VS Code.</p>;
}

function EscritorioEspera({ a, ahora }: { a: Agente; ahora: number }) {
  // With a registered request the panel below shows the full command.
  const pide = a.permiso ? null : loQuePide(a);
  return (
    <div className={s.celdaEspera}>
      <Link
        href={enlace(a)}
        className={`${s.escritorio} ${s.escritorioEspera}`}
      >
        <Avatar tam={88} />
        <div className={s.cuerpo}>
          <Cabecera a={a} />
          <div className={s.etiquetas}>
            <span className={`${s.etiqueta} ${s.etiquetaNegra}`}>
              Espera a: ti ({tipoEspera(a)})
            </span>
            <span className={s.etiqueta}>
              Desde hace {duracion(a.estado.desde, ahora)}
            </span>
          </div>
          {pide && (
            <div className={s.cajaGris}>
              <small>{pide.titulo}</small>
              {recortar(pide.texto, 400)}
            </div>
          )}
          <Indicadores a={a} ahora={ahora} />
        </div>
      </Link>
      <BloquePermiso a={a} ahora={ahora} />
    </div>
  );
}

function EscritorioTrabajo({ a, ahora }: { a: Agente; ahora: number }) {
  const e = esfuerzo(a);
  const tpm = a.indicadores.tokens_por_minuto;
  return (
    <Link href={enlace(a)} className={s.escritorio}>
      <Avatar tam={72} />
      <div className={s.cuerpo}>
        <Cabecera a={a} />
        <div className={s.cajaMono} title={detalleActual(a)}>
          {recortar(detalleActual(a), 160)}
        </div>
        <div
          className={s.barra}
          role="meter"
          aria-label="Esfuerzo"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(e * 100)}
          title={`Esfuerzo: ${numero(tpm, " tok/min")}`}
        >
          <div style={{ width: `${Math.round(e * 100)}%` }} />
        </div>
        <Indicadores a={a} ahora={ahora} conEstado />
      </div>
    </Link>
  );
}

function EscritorioChico({ a, ahora }: { a: Agente; ahora: number }) {
  return (
    <Link href={enlace(a)} className={`${s.escritorio} ${s.escritorioChico}`}>
      <Avatar tam={48} />
      <div className={s.cuerpo}>
        <Proyecto a={a} className={s.proyecto} />
        <EstadoTexto a={a} />
        <div className={s.meta}>{hace(a.estado.desde, ahora)}</div>
      </div>
    </Link>
  );
}

function notaCerrado(a: Agente, ahora: number): string {
  if (a.pregunta_pendiente) {
    return `Pregunta pendiente: ${recortar(a.pregunta_pendiente, 120)} Se queda aquí hasta que reabras la sesión.`;
  }
  return `Desaparece en ${minutosParaDesaparecer(a, ahora) ?? "?"} min`;
}

function FilaCerrado({ a, ahora }: { a: Agente; ahora: number }) {
  return (
    <Link href={enlace(a)} className={s.filaCerrado}>
      <b className={s.conMarca}>
        <MarcaCuenta cuenta={a.agente.cuenta} />
        {nombreProyecto(a)}
      </b>
      <span className={s.mono}>
        21 · Cerrado ({a.cierre?.motivo ?? "sin motivo"})
      </span>
      <span className={s.meta}>{notaCerrado(a, ahora)}</span>
    </Link>
  );
}

function Seccion({
  titulo,
  n,
  children,
}: {
  titulo: string;
  n: number;
  children: ReactNode;
}) {
  return (
    <section className={s.seccion} aria-label={titulo}>
      <h2 className={s.seccionTitulo}>
        {titulo}
        <span className={s.mono}>{n}</span>
      </h2>
      {n === 0 ? <div className={s.vacio}>Nadie.</div> : children}
    </section>
  );
}

function VistaUrgencia({
  agentes,
  ahora,
}: {
  agentes: Agente[];
  ahora: number;
}) {
  const g = agruparPorUrgencia(agentes, ahora);
  return (
    <>
      {GRUPOS.map(({ id, titulo }) => (
        <Seccion key={id} titulo={titulo} n={g[id].length}>
          {id === "espera" && (
            <div className={s.rejillaEspera}>
              {g.espera.map((a) => (
                <EscritorioEspera
                  key={a.agente.session_id}
                  a={a}
                  ahora={ahora}
                />
              ))}
            </div>
          )}
          {id === "trabajando" && (
            <div className={s.rejillaTrabajo}>
              {g.trabajando.map((a) => (
                <EscritorioTrabajo
                  key={a.agente.session_id}
                  a={a}
                  ahora={ahora}
                />
              ))}
            </div>
          )}
          {id === "inactivos" && (
            <div className={s.rejillaChica}>
              {g.inactivos.map((a) => (
                <EscritorioChico
                  key={a.agente.session_id}
                  a={a}
                  ahora={ahora}
                />
              ))}
            </div>
          )}
          {id === "cerrados" && (
            <div className={s.franjaCerrados}>
              {g.cerrados.map((a) => (
                <FilaCerrado key={a.agente.session_id} a={a} ahora={ahora} />
              ))}
            </div>
          )}
        </Seccion>
      ))}
    </>
  );
}

// -- rooms by project -------------------------------------------------------------

function EscritorioSala({ a, ahora }: { a: Agente; ahora: number }) {
  const g = grupoDe(a.estado.numero);
  const clase =
    g === "espera" ? s.escritorioEspera : g === "cerrados" ? s.cerrado : "";
  const linea =
    loQuePide(a)?.texto ??
    (g === "cerrados" ? notaCerrado(a, ahora) : detalleActual(a));
  return (
    <Link href={enlace(a)} className={`${s.escritorio} ${clase}`}>
      <Avatar tam={64} />
      <div className={s.cuerpo}>
        <EstadoTexto a={a} />
        <div className={`${s.meta} ${s.mono}`}>
          <MarcaCuenta cuenta={a.agente.cuenta} />{" "}
          {sesionCorta(a.agente.session_id)} · {hace(a.estado.desde, ahora)}
        </div>
        <div className={s.linea1} title={linea}>
          {recortar(linea, 200)}
        </div>
      </div>
    </Link>
  );
}

function VistaProyecto({
  agentes,
  ahora,
}: {
  agentes: Agente[];
  ahora: number;
}) {
  const salas = agruparPorProyecto(agentes, ahora);
  if (salas.length === 0) return <div className={s.vacio}>No hay agentes.</div>;
  return (
    <div className={s.salas}>
      {salas.map((sala) => (
        <section
          key={sala.proyecto}
          className={s.sala}
          aria-label={`Sala ${sala.proyecto}`}
        >
          <h2 className={s.salaTitulo}>
            Sala {sala.proyecto}
            <span>{sala.resumen}</span>
          </h2>
          <div className={s.rejillaSala}>
            {sala.agentes.map((a) => (
              <EscritorioSala key={a.agente.session_id} a={a} ahora={ahora} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

// -- page ---------------------------------------------------------------------------

export default function Oficina() {
  const params = useSearchParams();
  const router = useRouter();
  const agenteId = params.get("agente");
  const [panelAvisos, setPanelAvisos] = useState(false);
  const [panelPermisos, setPanelPermisos] = useState(false);
  const { datos, error, recibido, ahora } = useEstadoOficina();
  const vista = useSyncExternalStore(
    suscribirVista,
    leerVista,
    () => "urgencia" as Vista,
  );

  // Presence heartbeat: an open /oficina counts as the user being present.
  useLatidoPresencia();
  // More than 8 h since the last visit on this device: "Dónde quedamos" first.
  useVisitaOficina(Boolean(agenteId));

  const agentes = useMemo(
    () => (datos ? visibles(datos.agentes, ahora) : []),
    [datos, ahora],
  );
  const n = contar(agentes);
  const elegido = agenteId
    ? datos?.agentes.find((a) => a.agente.session_id === agenteId)
    : null;

  const cambiarVista = guardarVista;
  const cerrarFicha = useCallback(() => router.replace("/oficina"), [router]);

  // Spoken alerts and Windows notifications (module reusable in /oficina/3d).
  const abrirAgente = useCallback(
    (id: string) =>
      router.push(
        id ? `/oficina?agente=${encodeURIComponent(id)}` : "/oficina",
      ),
    [router],
  );
  const avisos = useAvisos(datos?.agentes ?? null, { abrirAgente });

  return (
    <main className={agenteId ? `${s.pagina} ${s.conFicha}` : s.pagina}>
      <header className={s.encabezado}>
        <div>
          <h1 className={s.titulo}>Oficina de agentes</h1>
          <div className={s.linea}>
            {textoPresencia(datos?.presencia)} ·{" "}
            <span className={s.mono}>{agentes.length}</span>{" "}
            {agentes.length === 1 ? "agente" : "agentes"} · actualizado{" "}
            <span className={s.mono}>
              {recibido ? hace(new Date(recibido).toISOString(), ahora) : "—"}
            </span>
          </div>
        </div>
        <div className={s.acciones}>
          <Link href="/donde-quedamos" className={s.botonAvisos}>
            Dónde quedamos
          </Link>
          <Link href="/oficina/3d" className={s.botonAvisos}>
            Vista 3D
          </Link>
          <button
            type="button"
            className={s.botonAvisos}
            aria-expanded={panelAvisos}
            onClick={() => setPanelAvisos((v) => !v)}
          >
            Avisos
            <span className={s.mono}>
              {avisos.config.activos ? "activos" : "apagados"}
            </span>
          </button>
          <button
            type="button"
            className={s.botonAvisos}
            aria-expanded={panelPermisos}
            onClick={() => setPanelPermisos((v) => !v)}
          >
            Permisos
          </button>
          <BotonSalir className={s.botonAvisos} />
          <div
            className={s.selector}
            role="group"
            aria-label="Ordenar la oficina"
          >
            <button
              type="button"
              aria-pressed={vista === "urgencia"}
              onClick={() => cambiarVista("urgencia")}
            >
              Por urgencia
            </button>
            <button
              type="button"
              aria-pressed={vista === "proyecto"}
              onClick={() => cambiarVista("proyecto")}
            >
              Por proyecto
            </button>
          </div>
        </div>
      </header>

      {panelAvisos && (
        <PanelAvisos api={avisos} onCerrar={() => setPanelAvisos(false)} />
      )}
      {panelPermisos && (
        <PanelConfigPermisos onCerrar={() => setPanelPermisos(false)} />
      )}

      {error && (
        <div className={s.aviso}>
          No se pudo leer el estado ({error}). Se reintenta cada 2 s.
        </div>
      )}

      <div className={s.contadores}>
        {CONTADORES.map((c) => (
          <div key={c.id} className={s.contador}>
            <strong>{n[c.id]}</strong>
            <span>{c.titulo}</span>
          </div>
        ))}
      </div>

      {agenteId && (
        <FichaAgente
          agente={elegido ?? undefined}
          id={agenteId}
          cargando={!datos}
          ahora={ahora}
          onCerrar={cerrarFicha}
          fija
        />
      )}

      {!datos ? (
        <div className={s.vacio}>Cargando…</div>
      ) : vista === "urgencia" ? (
        <VistaUrgencia agentes={datos.agentes} ahora={ahora} />
      ) : (
        <VistaProyecto agentes={datos.agentes} ahora={ahora} />
      )}
    </main>
  );
}
