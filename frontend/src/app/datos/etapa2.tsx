"use client";

/**
 * /datos, etapa 2.1: los datos nuevos en bruto (sin diseño), para comprobarlos
 * antes de la ficha del agente y "Dónde quedamos" (Prompt 28).
 */

import { useEffect, useState, type ReactNode } from "react";
import { apiFetch } from "@/utils/api";

const SEP = "   ";
const REFRESCO_MS = 10000;

function valor(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function hora(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es", { hour12: false });
}

export function duracion(s: number | null | undefined): string {
  if (s === null || s === undefined) return "—";
  if (s < 60) return `${s} s`;
  if (s < 3600) return `${Math.floor(s / 60)} min`;
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return m ? `${h} h ${m} min` : `${h} h`;
}

/** Lee un endpoint cada 10 s (null mientras no hay datos). */
function useLectura<T>(ruta: string): {
  datos: T | null;
  error: string | null;
} {
  const [datos, setDatos] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let activo = true;
    const cargar = async () => {
      try {
        const r = await apiFetch(ruta);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const j = (await r.json()) as T;
        if (activo) {
          setDatos(j);
          setError(null);
        }
      } catch (e) {
        if (activo) setError(String(e));
      }
    };
    void cargar();
    const id = setInterval(cargar, REFRESCO_MS);
    return () => {
      activo = false;
      clearInterval(id);
    };
  }, [ruta]);
  return { datos, error };
}

function Celdas({ valores }: { valores: ReactNode[] }) {
  return (
    <tr>
      {valores.map((v, i) => (
        <td key={i}>
          {v}
          {SEP}
        </td>
      ))}
    </tr>
  );
}

function Tabla({
  titulos,
  filas,
}: {
  titulos: string[];
  filas: ReactNode[][];
}) {
  return (
    <table border={1} cellPadding={4}>
      <thead>
        <tr>
          {titulos.map((t) => (
            <th key={t} align="left">
              {t}
              {SEP}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {filas.map((f, i) => (
          <Celdas key={i} valores={f} />
        ))}
      </tbody>
    </table>
  );
}

// -- historial de un agente -----------------------------------------------------------

interface Turno {
  numero: number;
  inicio: string;
  duracion_s: number;
  pedido: string | null;
  herramientas: Record<string, number>;
  total_herramientas: number;
  archivos_editados: string[];
  commits: { hora: string; mensaje: string | null }[];
  errores: number;
  tokens_salida: number | null;
  resultado: string;
}

interface Historial {
  total: number;
  turnos: Turno[];
}

export function HistorialAgente({ sesion }: { sesion: string }) {
  const { datos, error } = useLectura<Historial>(
    `/api/v1/agents/${encodeURIComponent(sesion)}/historial?por_pagina=5`,
  );
  if (error) return <p>Historial: {error}</p>;
  if (!datos) return <p>Historial: …</p>;
  return (
    <>
      <h3>
        Historial: últimos {datos.turnos.length} de {datos.total} turnos
      </h3>
      <Tabla
        titulos={[
          "#",
          "Inicio",
          "Duración",
          "Pedido",
          "Herramientas",
          "Archivos editados",
          "Commits",
          "Errores",
          "Tokens",
          "Resultado",
        ]}
        filas={datos.turnos.map((t) => [
          t.numero,
          hora(t.inicio),
          duracion(t.duracion_s),
          valor(t.pedido),
          `${t.total_herramientas} (${Object.entries(t.herramientas)
            .map(([k, v]) => `${k} ${v}`)
            .join(", ")})`,
          t.archivos_editados.join(", ") || "—",
          t.commits.map((c) => valor(c.mensaje)).join(" | ") || "—",
          t.errores,
          valor(t.tokens_salida),
          t.resultado,
        ])}
      />
    </>
  );
}

// -- consumo, límites y "Dónde quedamos" -------------------------------------------------

interface Grupo {
  sesiones: number;
  tokens_salida: number;
  segundos_trabajo: number;
  cuenta?: string;
  modelo?: string;
}

interface Consumo {
  dia: string;
  zona: string;
  total: {
    sesiones: number;
    tokens_salida: number;
    segundos_trabajo: number;
    segundos_con_agentes: number;
  };
  por_cuenta: Grupo[];
  por_modelo: Grupo[];
  por_sesion: {
    session_id: string;
    proyecto: string | null;
    cuenta: string;
    modelo: string;
    turnos: number;
    tokens_salida: number;
    segundos_trabajo: number;
    continuo_s: number;
  }[];
  auxiliar?: {
    por_cuenta: {
      cuenta: string;
      llamadas: number;
      fallos: number;
      tokens_entrada: number;
      tokens_salida: number;
      segundos: number;
    }[];
  };
}

interface Ventana {
  usado_pct?: number;
  reinicia?: string;
  vencida?: boolean | null;
}

interface Limites {
  fuente: string;
  cuentas: {
    maquina: string;
    cuenta: string;
    modelo?: string | null;
    cinco_horas?: Ventana | null;
    semanal?: Ventana | null;
    visto?: string | null;
  }[];
}

interface Proyecto {
  carpeta: string;
  maquina: string;
  tiene_project_md: boolean;
  titulo: string | null;
  plan: { nombre: string; estado: string }[];
  posicion: string | null;
  siguiente_paso: string | null;
  espera_decision: string[];
  ultimo_commit: {
    hash: string;
    mensaje: string | null;
    fecha: string | null;
  } | null;
  error: string | null;
  recibido: string;
  ultima_actividad: {
    session_id: string;
    estado: string;
    espera: string | null;
    ultimo_evento: string | null;
    ultimo_turno: Turno | null;
  } | null;
}

function textoVentana(v: Ventana | null | undefined): string {
  if (!v || v.usado_pct === undefined) return "—";
  const fin = v.reinicia ? `, reinicia ${hora(v.reinicia)}` : "";
  return `${v.usado_pct} %${fin}${v.vencida ? " (ya reinició: dato viejo)" : ""}`;
}

export function SeccionesEtapa2() {
  const consumo = useLectura<Consumo>("/api/v1/consumo");
  const limites = useLectura<Limites>("/api/v1/limites");
  const proyectos = useLectura<{ proyectos: Proyecto[] }>("/api/v1/proyectos");
  const c = consumo.datos;
  return (
    <>
      <h2>Consumo de hoy{c ? ` (${c.dia}, ${c.zona})` : ""}</h2>
      {consumo.error && <p>Error: {consumo.error}</p>}
      {c && (
        <>
          <p>
            Total: {c.total.tokens_salida} tokens de salida,{" "}
            {duracion(c.total.segundos_trabajo)} de trabajo sumando agentes,{" "}
            {duracion(c.total.segundos_con_agentes)} con al menos un agente
            trabajando, {c.total.sesiones} sesiones.
          </p>
          <h3>Por cuenta</h3>
          <Tabla
            titulos={[
              "Cuenta",
              "Sesiones",
              "Tokens de salida",
              "Tiempo de trabajo",
            ]}
            filas={c.por_cuenta.map((g) => [
              valor(g.cuenta),
              g.sesiones,
              g.tokens_salida,
              duracion(g.segundos_trabajo),
            ])}
          />
          <h3>Por modelo</h3>
          <Tabla
            titulos={[
              "Modelo",
              "Sesiones",
              "Tokens de salida",
              "Tiempo de trabajo",
            ]}
            filas={c.por_modelo.map((g) => [
              valor(g.modelo),
              g.sesiones,
              g.tokens_salida,
              duracion(g.segundos_trabajo),
            ])}
          />
          <h3>Por sesión</h3>
          <Tabla
            titulos={[
              "Sesión",
              "Proyecto",
              "Cuenta",
              "Modelo",
              "Turnos",
              "Tokens",
              "Trabajo",
              "Continuo ahora",
            ]}
            filas={c.por_sesion.map((s) => [
              s.session_id.slice(0, 8),
              valor(s.proyecto),
              s.cuenta,
              s.modelo,
              s.turnos,
              s.tokens_salida,
              duracion(s.segundos_trabajo),
              s.continuo_s ? duracion(s.continuo_s) : "—",
            ])}
          />
          <h3>Auxiliar de avisos (aparte de los agentes)</h3>
          <Tabla
            titulos={[
              "Cuenta",
              "Resúmenes",
              "Fallos",
              "Tokens de entrada",
              "Tokens de salida",
              "Tiempo",
            ]}
            filas={(c.auxiliar?.por_cuenta ?? []).map((g) => [
              g.cuenta,
              g.llamadas,
              g.fallos,
              g.tokens_entrada,
              g.tokens_salida,
              `${g.segundos} s`,
            ])}
          />
        </>
      )}
      <h2>Límites de la suscripción</h2>
      {limites.error && <p>Error: {limites.error}</p>}
      {limites.datos && (
        <>
          <p>Fuente: {limites.datos.fuente}.</p>
          {limites.datos.cuentas.length === 0 ? (
            <p>
              Todavía sin datos: llegan cuando la barra de estado de Claude Code
              recibe una respuesta en una sesión (solo Pro y Max).
            </p>
          ) : (
            <Tabla
              titulos={[
                "Máquina",
                "Cuenta",
                "5 horas",
                "Semanal",
                "Modelo",
                "Visto",
              ]}
              filas={limites.datos.cuentas.map((l) => [
                l.maquina,
                l.cuenta,
                textoVentana(l.cinco_horas),
                textoVentana(l.semanal),
                valor(l.modelo),
                hora(l.visto),
              ])}
            />
          )}
        </>
      )}
      <h2>Dónde quedamos (por proyecto)</h2>
      {proyectos.error && <p>Error: {proyectos.error}</p>}
      {proyectos.datos?.proyectos.map((p) => (
        <section key={`${p.maquina}|${p.carpeta}`}>
          <h3>
            {p.carpeta} ({p.maquina})
          </h3>
          <table border={1} cellPadding={4}>
            <tbody>
              {(
                [
                  [
                    "PROJECT.md",
                    p.tiene_project_md ? valor(p.titulo) : "no tiene",
                  ],
                  ["Error", valor(p.error)],
                  [
                    "Plan",
                    p.plan.length
                      ? p.plan
                          .map((i) => `${i.nombre} (${i.estado})`)
                          .join(" · ")
                      : "—",
                  ],
                  ["Posición actual", valor(p.posicion)],
                  ["Siguiente paso", valor(p.siguiente_paso)],
                  ["Espera decisión", p.espera_decision.join(" · ") || "—"],
                  [
                    "Último commit",
                    p.ultimo_commit
                      ? `${p.ultimo_commit.hash} ${valor(p.ultimo_commit.mensaje)} (${valor(p.ultimo_commit.fecha)})`
                      : "—",
                  ],
                  [
                    "Lo último del agente",
                    p.ultima_actividad
                      ? `${p.ultima_actividad.estado}${p.ultima_actividad.espera ? ` — ${p.ultima_actividad.espera}` : ""}; último turno: ${valor(p.ultima_actividad.ultimo_turno?.pedido)} (${valor(p.ultima_actividad.ultimo_turno?.resultado)}), ${hora(p.ultima_actividad.ultimo_evento)}`
                      : "sin agentes activos en esa carpeta",
                  ],
                  ["Recibido", hora(p.recibido)],
                ] as Array<[string, string]>
              ).map(([k, v]) => (
                <tr key={k}>
                  <th align="left">
                    {k}:{SEP}
                  </th>
                  <td>{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}
      {proyectos.datos && proyectos.datos.proyectos.length === 0 && (
        <p>
          Todavía sin proyectos: el monitor los manda cuando un agente trabaja
          en una carpeta.
        </p>
      )}
    </>
  );
}
