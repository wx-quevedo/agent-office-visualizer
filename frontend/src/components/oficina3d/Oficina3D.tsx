"use client";

/**
 * /oficina/3d — the office as a 3D scene (based on Agent Office 3D, MIT),
 * fed by our engine. Own simple top bar (light theme), the same alerts
 * (useAvisos) and presence heartbeat as /oficina. Loaded only in the browser.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import PanelAvisos from "@/components/avisos/PanelAvisos";
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
import { cargarDistribucion } from "./distribucion";
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
  const { datos, error } = useEstadoOficina();
  useLatidoPresencia();
  const [panelAvisos, setPanelAvisos] = useState(false);
  const editando = useEditor((st) => st.activo);
  const [angosta, setAngosta] = useState(false);
  const memoria = useRef<EstadoAdaptador>(estadoInicial());
  // Optional framing from the URL (?zoom=60&centro=x,z), handy for close-ups.
  const [encuadre] = useState(() => leerEncuadre(window.location.search));
  const setAgents = useOffice((st) => st.setAgents);
  const setAbrir = useOffice((st) => st.setAbrir);

  const abrirAgente = useCallback(
    (id: string) =>
      router.push(
        id ? `/oficina?agente=${encodeURIComponent(id)}` : "/oficina",
      ),
    [router],
  );
  const avisos = useAvisos(datos?.agentes ?? null, { abrirAgente });

  // Clicking an agent or its desk opens the existing detail.
  useEffect(() => {
    setAbrir(abrirAgente);
  }, [abrirAgente, setAbrir]);

  // Layout from the repo (frontend/public/oficina3d/distribucion.json).
  useEffect(() => {
    void cargarDistribucion();
  }, []);

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
  useEffect(() => {
    if (!datos) return;
    const office = useOffice.getState();
    const r = adaptar(datos.agentes, memoria.current, Date.now(), salidos);
    memoria.current = r.estado;
    setAgents(r.vistas);
    office.setCerrados(r.cerrados);
    office.olvidarSalidos(r.reentradas);
  }, [datos, salidos, setAgents]);

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
        <div className={s.acciones}>
          <button
            type="button"
            className={s.boton}
            aria-pressed={editando}
            disabled={editando}
            onClick={() => {
              setPanelAvisos(false);
              useEditor.getState().entrar();
            }}
          >
            {t("barra.editar")}
          </button>
          <Link href="/oficina" className={s.boton}>
            {t("barra.vistaCajas")}
          </Link>
          <button
            type="button"
            className={s.boton}
            aria-expanded={panelAvisos}
            onClick={() => setPanelAvisos((v) => !v)}
          >
            {t("barra.avisos")}
            <span className={s.mono}>
              {avisos.config.activos
                ? t("barra.avisosActivos")
                : t("barra.avisosApagados")}
            </span>
          </button>
        </div>
      </header>

      {panelAvisos && (
        <div className={s.capaAvisos}>
          <PanelAvisos api={avisos} onCerrar={() => setPanelAvisos(false)} />
        </div>
      )}

      <main className={s.lienzo}>
        {editando && <EditorPanel />}
        <Escena3D
          zoom={encuadre.zoom ?? (angosta ? 10 : 20)}
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
      </main>
    </div>
  );
}
