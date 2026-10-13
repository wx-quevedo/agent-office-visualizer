"use client";

/**
 * "Decisiones" block over the projects list (Prompt 38): every order of the
 * orchestrators that waits for approval, in purple, with Aprobar, Rechazar
 * (asks for a reason) and a link to the chat of its project. Hidden when
 * nothing waits. The iOS app has its own inbox; this is the web one.
 * Prompt 43: orders of test projects are left out.
 */

import Link from "next/link";
import { useId, useState } from "react";
import { haceTiempo } from "@/components/ficha/logica";
import { DecidirOrden } from "./TarjetaOrden";
import {
  enlaceProyecto,
  ordenesParaDecidir,
  textoCorto,
  tituloOrden,
  unirOrdenes,
  type Orden,
} from "./logica";
import s from "./proyectos.module.css";

function Decision({
  orden: o,
  ahora,
  cambio,
}: {
  orden: Orden;
  ahora: number;
  cambio: (o: Orden) => void;
}) {
  const id = useId();
  return (
    <li className={s.decision}>
      <div className={s.decisionCabeza}>
        <span className={s.etiqueta}>{o.proyecto}</span>
        <span className={s.secundario}>{haceTiempo(o.creado, ahora)}</span>
      </div>
      <h3 id={`${id}-t`} className={s.ordenTitulo}>
        {tituloOrden(o)}
        <span className={s.oculto}> en {o.proyecto}</span>
      </h3>
      <p className={s.decisionTexto}>{textoCorto(o.texto, 220)}</p>
      <DecidirOrden
        orden={o}
        cambio={cambio}
        editar={false}
        etiquetaRechazar="Rechazar"
        describe={`${id}-t`}
      />
      <Link href={enlaceProyecto(o.proyecto_id, "chat")} className={s.enlace}>
        Abrir el chat
        <span className={s.oculto}> de {o.proyecto}</span>
      </Link>
    </li>
  );
}

export interface PropsDecisiones {
  ordenes: Orden[] | null;
  ahora: number;
}

export function DecisionesVista({ ordenes, ahora }: PropsDecisiones) {
  const [locales, setLocales] = useState<Record<string, Orden>>({});
  const [anuncio, setAnuncio] = useState("");
  const pendientes = ordenesParaDecidir(unirOrdenes(ordenes ?? [], locales));
  const cambio = (o: Orden) => {
    setLocales((v) => ({ ...v, [o.id]: o }));
    setAnuncio(
      `${tituloOrden(o)} ${o.estado === "rechazada" ? "rechazada" : "aprobada"}.`,
    );
  };
  return (
    <>
      <p className={s.oculto} aria-live="polite">
        {anuncio}
      </p>
      {pendientes.length > 0 && (
        <section className={s.decisiones} aria-labelledby="decisiones-titulo">
          <div className={s.cabezaTexto}>
            <h2 id="decisiones-titulo" className={s.subtitulo}>
              Decisiones
            </h2>
            <p className={s.secundario}>
              {pendientes.length === 1
                ? "Una orden del orquestador espera tu aprobación."
                : `${pendientes.length} órdenes de los orquestadores esperan tu aprobación.`}
            </p>
          </div>
          <ul className={s.filas} aria-label="Órdenes por aprobar">
            {pendientes.map((o) => (
              <Decision key={o.id} orden={o} ahora={ahora} cambio={cambio} />
            ))}
          </ul>
        </section>
      )}
    </>
  );
}
