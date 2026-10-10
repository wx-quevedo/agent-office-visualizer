"use client";

/**
 * /datos — raw view of the catalog state engine (GET /api/v1/agents/state).
 *
 * Deliberately unstyled: plain HTML tables, no own CSS, no classic-view
 * components. Used to validate the data before building the new canvas.
 */

import { useEffect, useState, type ReactNode } from "react";
import { API_BASE } from "@/utils/api";

const REFRESH_MS = 2000;

// The root layout's global CSS (Tailwind preflight) removes table borders and
// padding; this page adds no CSS, so cells are separated with plain spaces.
const SEP = "   ";

interface Espera {
  tipo: string;
  evidencia: Record<string, unknown> | null;
}

interface EventoReciente {
  hora: string;
  tipo: string;
  agente: string | null;
  herramienta: string | null;
  detalle: string | null;
}

interface Agente {
  agente: {
    session_id: string;
    proyecto: string | null;
    cuenta: string | null;
  };
  estado: { numero: number; nombre: string; desde: string };
  espera: Espera | null;
  herramienta_actual: string | null;
  ultimo_evento: { tipo: string | null; hora: string | null };
  subagentes_activos: number;
  indicadores: Record<string, number | string | null>;
  eventos_recientes: EventoReciente[];
}

interface Respuesta {
  generado: string;
  presencia: {
    estado: string;
    motivo: string;
    navegadores_conectados: number;
    ultimo_encargo: string | null;
    desconectado_desde: string | null;
  };
  umbrales_segundos: Record<string, number>;
  agentes: Agente[];
}

function hora(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("es", { hour12: false });
}

function hace(iso: string | null, ahora: string): string {
  if (!iso) return "";
  const s = Math.max(0, (Date.parse(ahora) - Date.parse(iso)) / 1000);
  if (s < 60) return `hace ${Math.round(s)} s`;
  if (s < 3600) return `hace ${Math.floor(s / 60)} min`;
  return `hace ${(s / 3600).toFixed(1)} h`;
}

function valor(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

const INDICADORES: Array<[string, string]> = [
  ["herramientas_por_minuto", "Herramientas por minuto (últimos 5 min)"],
  ["tokens_por_minuto", "Tokens por minuto (últimos 5 min)"],
  ["tokens_totales", "Tokens totales"],
  ["tokens_contexto", "Tokens en el contexto"],
  ["tokens_motivo", "Motivo si faltan tokens"],
  ["minutos_con_actividad", "Minutos con actividad"],
  ["contexto_usado_pct", "Contexto usado (%)"],
  ["errores_seguidos", "Errores seguidos"],
  ["errores_motivo", "Motivo si faltan errores"],
];

function Fila({ nombre, children }: { nombre: string; children: ReactNode }) {
  return (
    <tr>
      <th align="left">
        {nombre}:{SEP}
      </th>
      <td>{children}</td>
    </tr>
  );
}

function TablaAgente({ a, ahora }: { a: Agente; ahora: string }) {
  return (
    <section>
      <h2>
        Agente {a.agente.session_id} — {a.estado.numero}. {a.estado.nombre}
      </h2>
      <table border={1} cellPadding={4}>
        <tbody>
          <Fila nombre="Sesión">{a.agente.session_id}</Fila>
          <Fila nombre="Proyecto">{valor(a.agente.proyecto)}</Fila>
          <Fila nombre="Cuenta">{valor(a.agente.cuenta)}</Fila>
          <Fila nombre="Estado">
            {a.estado.numero}. {a.estado.nombre}
          </Fila>
          <Fila nombre="Desde">
            {hora(a.estado.desde)} ({hace(a.estado.desde, ahora)})
          </Fila>
          <Fila nombre="Espera">{a.espera ? a.espera.tipo : "—"}</Fila>
          <Fila nombre="Evidencia de la espera">
            {a.espera ? valor(a.espera.evidencia) : "—"}
          </Fila>
          <Fila nombre="Herramienta actual">{valor(a.herramienta_actual)}</Fila>
          <Fila nombre="Último evento">
            {valor(a.ultimo_evento.tipo)} a las {hora(a.ultimo_evento.hora)} (
            {hace(a.ultimo_evento.hora, ahora)})
          </Fila>
          <Fila nombre="Subagentes activos">{a.subagentes_activos}</Fila>
          {INDICADORES.map(([clave, nombre]) => (
            <Fila key={clave} nombre={nombre}>
              {valor(a.indicadores[clave])}
            </Fila>
          ))}
        </tbody>
      </table>
      <h3>Últimos {a.eventos_recientes.length} eventos en bruto</h3>
      <table border={1} cellPadding={4}>
        <thead>
          <tr>
            <th align="left">Hora{SEP}</th>
            <th align="left">Tipo{SEP}</th>
            <th align="left">Agente{SEP}</th>
            <th align="left">Herramienta{SEP}</th>
            <th align="left">Comando o texto</th>
          </tr>
        </thead>
        <tbody>
          {a.eventos_recientes.map((e, i) => (
            <tr key={`${e.hora}-${i}`}>
              <td>
                {hora(e.hora)}
                {SEP}
              </td>
              <td>
                {e.tipo}
                {SEP}
              </td>
              <td>
                {valor(e.agente)}
                {SEP}
              </td>
              <td>
                {valor(e.herramienta)}
                {SEP}
              </td>
              <td>{valor(e.detalle)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <hr />
    </section>
  );
}

export default function DatosPage() {
  const [datos, setDatos] = useState<Respuesta | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let activo = true;
    const cargar = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/v1/agents/state`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = (await res.json()) as Respuesta;
        if (activo) {
          setDatos(json);
          setError(null);
        }
      } catch (e) {
        if (activo) setError(String(e));
      }
    };
    void cargar();
    const id = setInterval(cargar, REFRESH_MS);
    return () => {
      activo = false;
      clearInterval(id);
    };
  }, []);

  return (
    <main>
      <h1>Datos en bruto del motor de estados</h1>
      <p>
        Fuente: {API_BASE}/api/v1/agents/state. Se actualiza cada{" "}
        {REFRESH_MS / 1000} s.
        {datos && <> Última lectura: {hora(datos.generado)}.</>}
      </p>
      {error && <p>Error al leer el backend: {error}</p>}
      {datos && (
        <>
          <h2>Presencia</h2>
          <table border={1} cellPadding={4}>
            <tbody>
              <Fila nombre="Estado">{datos.presencia.estado}</Fila>
              <Fila nombre="Motivo">{datos.presencia.motivo}</Fila>
              <Fila nombre="Navegadores conectados">
                {datos.presencia.navegadores_conectados}
              </Fila>
              <Fila nombre="Último encargo">
                {hora(datos.presencia.ultimo_encargo)}{" "}
                {hace(datos.presencia.ultimo_encargo, datos.generado)}
              </Fila>
              <Fila nombre="Desconectado desde">
                {hora(datos.presencia.desconectado_desde)}
              </Fila>
              <Fila nombre="Umbrales (s)">
                {valor(datos.umbrales_segundos)}
              </Fila>
            </tbody>
          </table>
          <h2>Agentes activos: {datos.agentes.length}</h2>
          {datos.agentes.map((a) => (
            <TablaAgente
              key={a.agente.session_id}
              a={a}
              ahora={datos.generado}
            />
          ))}
        </>
      )}
    </main>
  );
}
