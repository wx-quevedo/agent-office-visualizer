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
import { adaptar, contar3d } from "./adaptador";
import { cargarDistribucion } from "./distribucion";
import Escena3D from "./Escena3D";
import { useSettings } from "./settings";
import { useOffice } from "./store";
import { t } from "./textos";
import s from "./oficina3d.module.css";

const ANGOSTA = 700;

export default function Oficina3D() {
  const router = useRouter();
  const { datos, error } = useEstadoOficina();
  useLatidoPresencia();
  const [panelAvisos, setPanelAvisos] = useState(false);
  const [angosta, setAngosta] = useState(false);
  const puestos = useRef<Record<string, number>>({});
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

  // Engine state → scene (stable desks by session_id; closed agents out).
  useEffect(() => {
    if (!datos) return;
    const r = adaptar(datos.agentes, puestos.current, Date.now());
    puestos.current = r.puestos;
    setAgents(r.vistas);
  }, [datos, setAgents]);

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
            <b>{n ? n.inactivos : "–"}</b> {t("barra.inactivos")}
          </span>
        </div>
        <div className={s.acciones}>
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
        <Escena3D zoom={angosta ? 10 : 20} vertical={angosta} />
        {error && <div className={s.aviso}>{t("barra.error")}</div>}
        {!datos && !error && (
          <div className={s.aviso}>{t("barra.cargando")}</div>
        )}
        {datos && n && n.espera + n.trabajando + n.inactivos === 0 && (
          <div className={s.aviso}>{t("barra.sinAgentes")}</div>
        )}
        <div className={s.ayuda}>{t("barra.ayuda")}</div>
      </main>
    </div>
  );
}
