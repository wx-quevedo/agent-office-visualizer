"use client";

/**
 * Panel of an agent over the 3D scene: opened by clicking the agent (or its
 * desk) or with /oficina/3d?agente=<id>. The scene stays mounted behind it.
 * State, time in it and what it does; for 13 the request with Approve /
 * Reject (or "Responde en VS Code"); for 14 the pending question. The full
 * detail of /oficina is one link away.
 */

import Link from "next/link";
import {
  detalleActual,
  duracion,
  nombreProyecto,
  recortar,
  type Agente,
} from "@/components/oficina/logica";
import PanelPermiso from "@/components/permisos/PanelPermiso";
import { t } from "./textos";
import s from "./oficina3d.module.css";

export default function PanelAgente3D({
  agente,
  id,
  cargando = false,
  ahora,
  onCerrar,
}: {
  agente: Agente | undefined;
  /** Id asked for (the agent may have left the office meanwhile). */
  id: string;
  /** The first read of the state has not arrived yet (link with ?agente=). */
  cargando?: boolean;
  ahora: number;
  onCerrar: () => void;
}) {
  const titulo = agente
    ? nombreProyecto(agente)
    : cargando
      ? t("barra.cargando")
      : t("panel.noEsta");
  return (
    <div
      className={s.capaPermiso}
      role="dialog"
      aria-label={agente ? `Agente ${titulo}` : titulo}
    >
      <div className={s.permisoCabeza}>
        <b>{titulo}</b>
        {agente && (
          <span>
            {agente.estado.numero} · {agente.estado.nombre}
          </span>
        )}
        <button type="button" className={s.boton} onClick={onCerrar}>
          {t("permiso.cerrar")}
        </button>
      </div>
      {agente && (
        <>
          <div className={s.panelDato}>
            {t("detalle.enEsteEstado")} {duracion(agente.estado.desde, ahora)}
          </div>
          {agente.estado.numero === 13 ? (
            agente.permiso ? (
              <PanelPermiso permiso={agente.permiso} ahora={ahora} />
            ) : (
              <p className={s.permisoVsCode}>{t("permiso.vscode")}</p>
            )
          ) : agente.pregunta_pendiente ? (
            <div className={s.panelBloque}>
              <b>{t("detalle.pregunta")}:</b> {agente.pregunta_pendiente}
            </div>
          ) : (
            <div className={s.panelBloque} title={detalleActual(agente)}>
              {recortar(detalleActual(agente), 300)}
            </div>
          )}
        </>
      )}
      {/* Also for a closed agent (its desk): /oficina may still show its history. */}
      {!cargando && (
        <Link
          href={`/oficina?agente=${encodeURIComponent(id)}`}
          className={s.permisoEnlace}
        >
          {t("permiso.detalle")}
        </Link>
      )}
    </div>
  );
}
