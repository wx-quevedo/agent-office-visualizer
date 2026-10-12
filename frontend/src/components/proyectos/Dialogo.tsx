"use client";

/**
 * Confirmation dialog of the projects (Prompt 38): modal, focus starts on the
 * safe button, Tab stays inside, Escape cancels and the focus goes back to
 * whatever had it before opening. Used by "Detener" (no window.confirm).
 */

import { useEffect, useId, useRef, type KeyboardEvent } from "react";
import s from "./proyectos.module.css";

export interface PropsDialogo {
  titulo: string;
  texto: string;
  textoConfirmar: string;
  textoCancelar?: string;
  confirmar: () => void;
  cancelar: () => void;
}

export default function Dialogo({
  titulo,
  texto,
  textoConfirmar,
  textoCancelar = "Cancelar",
  confirmar,
  cancelar,
}: PropsDialogo) {
  const id = useId();
  const caja = useRef<HTMLDivElement>(null);
  const seguro = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const antes =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    seguro.current?.focus();
    return () => {
      if (antes && antes.isConnected) antes.focus();
    };
  }, []);

  const tecla = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Escape") {
      e.preventDefault();
      cancelar();
      return;
    }
    if (e.key !== "Tab") return;
    const botones = [
      ...(caja.current?.querySelectorAll<HTMLButtonElement>("button") ?? []),
    ];
    if (botones.length === 0) return;
    const primero = botones[0];
    const ultimo = botones[botones.length - 1];
    if (e.shiftKey && document.activeElement === primero) {
      e.preventDefault();
      ultimo.focus();
    } else if (!e.shiftKey && document.activeElement === ultimo) {
      e.preventDefault();
      primero.focus();
    }
  };

  return (
    <div className={s.velo}>
      <div
        ref={caja}
        className={s.dialogo}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={`${id}-t`}
        aria-describedby={`${id}-d`}
        onKeyDown={tecla}
      >
        <h2 id={`${id}-t`} className={s.subtitulo}>
          {titulo}
        </h2>
        <p id={`${id}-d`} className={s.dialogoTexto}>
          {texto}
        </p>
        <div className={s.dialogoBotones}>
          <button type="button" className={s.botonPeligro} onClick={confirmar}>
            {textoConfirmar}
          </button>
          <button
            ref={seguro}
            type="button"
            className={s.boton}
            onClick={cancelar}
          >
            {textoCancelar}
          </button>
        </div>
      </div>
    </div>
  );
}
