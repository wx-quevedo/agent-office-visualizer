"use client";

/**
 * /oficina/3d — the office as a 3D scene (based on Agent Office 3D, MIT),
 * fed by our engine. Own simple top bar (light theme), the same alerts
 * (useAvisos) and presence heartbeat as /oficina. Loaded only in the browser.
 * Clicking an agent opens its card (FichaAgente) over the scene.
 */

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import BotonSalir from "@/components/acceso/BotonSalir";
import PanelAvisos from "@/components/avisos/PanelAvisos";
import { useVisitaOficina } from "@/components/donde/visita";
import FichaAgente from "@/components/ficha/FichaAgente";
import PanelConfigPermisos from "@/components/permisos/PanelConfigPermisos";
import { useAvisos } from "@/components/avisos/useAvisos";
import {
  useEstadoOficina,
  useLatidoPresencia,
} from "@/components/oficina/useEstadoOficina";
import {
  adaptar,
  contar3d,
  estadoInicial,
  type EstadoAdaptador,
} from "./adaptador";
import {
  cargarDistribucion,
  distribucionActual,
  guardarDistribucion,
  useLayout,
} from "./distribucion";
import { activarEntorno, ENTORNOS } from "./entornos/activo";
import type { ClaveEntorno } from "./entornos/tipos";
import { useEditor } from "./editor";
import EditorPanel from "./EditorPanel";
import Escena3D from "./Escena3D";
import { useSettings } from "./settings";
import { useOffice } from "./store";
import { t } from "./textos";
import s from "./oficina3d.module.css";

const ANGOSTA = 700;

function leerEncuadre(search: string): {
  zoom?: number;
  centro?: [number, number];
} {
  const q = new URLSearchParams(search);
  const zoom = Number(q.get("zoom"));
  const c = (q.get("centro") ?? "").split(",").map(Number);
  return {
    zoom: Number.isFinite(zoom) && zoom > 0 ? Math.min(zoom, 120) : undefined,
    centro:
      c.length === 2 && c.every(Number.isFinite) ? [c[0], c[1]] : undefined,
  };
}

export default function Oficina3D() {
  const router = useRouter();
  const { datos, error, ahora } = useEstadoOficina();
  useLatidoPresencia();
  const [panelAvisos, setPanelAvisos] = useState(false);
  const [panelPermisos, setPanelPermisos] = useState(false);
  // Panel of the clicked agent, over the scene (the scene stays mounted).
  // ?agente=<id> opens it too; read from Next (not window.location, which
  // still has the previous page during a client-side navigation).
  const panel = useOffice((st) => st.panel);
  const setPanel = useOffice((st) => st.setPanel);
  const params = useSearchParams();
  const agenteUrl = params.get("agente");
  // More than 8 h since the last visit on this device: "Dónde quedamos" first.
  useVisitaOficina(Boolean(agenteUrl));
  useEffect(() => {
    setPanel(agenteUrl);
  }, [agenteUrl, setPanel]);
  const editando = useEditor((st) => st.activo);
  const [angosta, setAngosta] = useState(false);
  const memoria = useRef<EstadoAdaptador>(estadoInicial());
  // Optional framing from the URL (?zoom=60&centro=x,z), handy for close-ups.
  const [encuadre] = useState(() => leerEncuadre(window.location.search));
  const setAgents = useOffice((st) => st.setAgents);

  const abrirAgente = useCallback(
    (id: string) =>
      router.push(
        id ? `/oficina/3d?agente=${encodeURIComponent(id)}` : "/oficina/3d",
      ),
    [router],
  );
  const avisos = useAvisos(datos?.agentes ?? null, { abrirAgente });

  const agentePanel = panel
    ? datos?.agentes.find((a) => a.agente.session_id === panel)
    : undefined;
  const cerrarPanel = useCallback(() => {
    setPanel(null);
    if (agenteUrl) {
      // Only ?agente goes away (the framing ?zoom=&centro= stays).
      const resto = new URLSearchParams(params.toString());
      resto.delete("agente");
      const q = resto.toString();
      router.replace(q ? `/oficina/3d?${q}` : "/oficina/3d");
    }
  }, [agenteUrl, params, router, setPanel]);

  // Layout of this copy (environment, furniture, theme). Read again every
  // 30 s (not while editing) so the PC and the iPhone show the same environment.
  useEffect(() => {
    void cargarDistribucion();
    const id = setInterval(() => {
      if (!useEditor.getState().activo) void cargarDistribucion();
    }, 30000);
    return () => clearInterval(id);
  }, []);

  // Your desk: you sit there while the presence says you are connected.
  useEffect(() => {
    useOffice.getState().setPresente(datos?.presencia?.estado === "conectado");
  }, [datos]);

  // Phones (< 700 px): low quality and no shadows by default.
  useEffect(() => {
    const medir = () => {
      const a = window.innerWidth < ANGOSTA;
      setAngosta(a);
      useSettings
        .getState()
        .set(
          a
            ? { quality: "low", shadows: false }
            : { quality: "high", shadows: true },
        );
    };
    medir();
    window.addEventListener("resize", medir);
    return () => window.removeEventListener("resize", medir);
  }, []);

  // Engine state → scene: behaviour per state, stable desks, walking in and
  // out through the door, closed desks (note or kept empty for one hour).
  const salidos = useOffice((st) => st.salidos);
  const clave = useLayout((st) => st.entorno);
  const ent = activarEntorno(clave);
  const claveAnterior = useRef(clave);
  useEffect(() => {
    if (!datos) return;
    const office = useOffice.getState();
    if (claveAnterior.current !== clave) {
      // New environment: agents appear directly at their places (no walk from the door).
      claveAnterior.current = clave;
      memoria.current = estadoInicial();
      office.olvidarSalidos([...office.salidos]);
    }
    const r = adaptar(datos.agentes, memoria.current, Date.now(), salidos);
    memoria.current = r.estado;
    setAgents(r.vistas);
    office.setCerrados(r.cerrados);
    office.setGrupos(r.estado.grupos);
    office.olvidarSalidos(r.reentradas);
  }, [datos, salidos, setAgents, clave]);

  const cambiarEntorno = async (k: ClaveEntorno) => {
    useLayout.getState().cambiarEntorno(k);
    await guardarDistribucion(distribucionActual());
  };

  const n = datos ? contar3d(datos.agentes) : null;

  return (
    <div className={s.pagina}>
      <header className={s.barra}>
        <h1 className={s.titulo}>{t("barra.titulo")}</h1>
        <div className={s.contadores}>
          <span
            className={
              n && n.espera > 0 ? `${s.contador} ${s.urgente}` : s.contador
            }
          >
            <b>{n ? n.espera : "–"}</b> {t("barra.teEsperan")}
          </span>
          <span className={s.contador}>
            <b>{n ? n.trabajando : "–"}</b> {t("barra.trabajando")}
          </span>
          <span className={s.contador}>
            <b>{n ? n.libres : "–"}</b> {t("barra.libres")}
          </span>
        </div>
        <label className={s.entorno}>
          <span>{t("barra.entorno")}</span>
          <select
            aria-label={t("barra.entorno")}
            value={clave}
            disabled={editando}
            onChange={(e) =>
              void cambiarEntorno(e.target.value as ClaveEntorno)
            }
          >
            {ENTORNOS.map((e) => (
              <option key={e.clave} value={e.clave}>
                {e.nombre}
              </option>
            ))}
          </select>
        </label>
        <div className={s.acciones}>
          <button
            type="button"
            className={s.boton}
            aria-pressed={editando}
            disabled={editando}
            onClick={() => {
              setPanelAvisos(false);
              cerrarPanel();
              useEditor.getState().entrar();
            }}
          >
            {t("barra.editar")}
          </button>
          <Link href="/donde-quedamos" className={s.boton}>
            {t("barra.dondeQuedamos")}
          </Link>
          <Link href="/oficina" className={s.boton}>
            {t("barra.vistaCajas")}
          </Link>
          <button
            type="button"
            className={s.boton}
            aria-expanded={panelAvisos}
            onClick={() => {
              cerrarPanel();
              setPanelAvisos((v) => !v);
            }}
          >
            {t("barra.avisos")}
            <span className={s.mono}>
              {avisos.config.activos
                ? t("barra.avisosActivos")
                : t("barra.avisosApagados")}
            </span>
          </button>
          <button
            type="button"
            className={s.boton}
            aria-expanded={panelPermisos}
            onClick={() => {
              cerrarPanel();
              setPanelPermisos((v) => !v);
            }}
          >
            {t("barra.permisos")}
          </button>
          <BotonSalir className={s.boton} />
        </div>
      </header>

      <main className={s.lienzo}>
        {panelAvisos && (
          <div className={s.capaAvisos}>
            <PanelAvisos api={avisos} onCerrar={() => setPanelAvisos(false)} />
          </div>
        )}
        {panelPermisos && (
          <div className={s.capaAvisos}>
            <PanelConfigPermisos onCerrar={() => setPanelPermisos(false)} />
          </div>
        )}
        {editando && <EditorPanel />}
        <Escena3D
          zoom={
            encuadre.zoom ??
            (angosta ? Math.round((10 * 46) / ent.tamano.ancho) : ent.zoom)
          }
          vertical={angosta}
          centro={encuadre.centro}
        />
        {error && <div className={s.aviso}>{t("barra.error")}</div>}
        {!datos && !error && (
          <div className={s.aviso}>{t("barra.cargando")}</div>
        )}
        {datos && n && n.espera + n.trabajando + n.libres === 0 && (
          <div className={s.aviso}>{t("barra.sinAgentes")}</div>
        )}
        {!editando && <div className={s.ayuda}>{t("barra.ayuda")}</div>}
        {panel && (
          <FichaAgente
            agente={agentePanel}
            id={panel}
            cargando={!datos}
            ahora={ahora}
            onCerrar={cerrarPanel}
          />
        )}
      </main>
    </div>
  );
}
