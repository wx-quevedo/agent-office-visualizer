"use client";

/**
 * Model and effort of one member of the team: used by "Nuevo proyecto" and by
 * "Agregar agente de código" in the Equipo section.
 */

import { useId } from "react";
import {
  ESFUERZOS,
  MODELOS,
  type ConfigModelo,
  type Esfuerzo,
  type Modelo,
} from "./logica";
import s from "./proyectos.module.css";

export default function SelectorModelo({
  titulo,
  valor,
  cambiar,
  quitar,
}: {
  titulo: string;
  valor: ConfigModelo;
  cambiar: (v: ConfigModelo) => void;
  quitar?: () => void;
}) {
  const id = useId();
  return (
    <div className={s.miembroForm} role="group" aria-labelledby={`${id}-t`}>
      <p id={`${id}-t`} className={s.miembroTitulo}>
        {titulo}
      </p>
      <label className={s.campo}>
        Modelo
        <select
          className={s.control}
          value={valor.modelo}
          onChange={(e) =>
            cambiar({ ...valor, modelo: e.target.value as Modelo })
          }
        >
          {MODELOS.map((m) => (
            <option key={m.valor} value={m.valor}>
              {m.texto}
            </option>
          ))}
        </select>
      </label>
      <label className={s.campo}>
        Esfuerzo
        <select
          className={s.control}
          value={valor.esfuerzo}
          onChange={(e) =>
            cambiar({ ...valor, esfuerzo: e.target.value as Esfuerzo })
          }
        >
          {ESFUERZOS.map((m) => (
            <option key={m.valor} value={m.valor}>
              {m.texto}
            </option>
          ))}
        </select>
      </label>
      {quitar ? (
        <button
          type="button"
          className={s.boton}
          onClick={quitar}
          aria-label={`Quitar ${titulo.toLowerCase()}`}
        >
          Quitar
        </button>
      ) : (
        <span aria-hidden="true" />
      )}
    </div>
  );
}
