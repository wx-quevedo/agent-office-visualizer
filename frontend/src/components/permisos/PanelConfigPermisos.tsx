"use client";

/** Settings of the permission requests (next to Avisos): policy, wait and commands to confirm. */

import { useEffect, useState } from "react";
import {
  CONFIG_POR_DEFECTO,
  guardarConfigPermisos,
  POLITICAS,
  type ConfigPermisos,
  type Politica,
} from "./logica";
import {
  fijarConfigPermisos,
  recargarConfigPermisos,
  useConfigPermisos,
} from "./useConfigPermisos";
import s from "./permisos.module.css";

export default function PanelConfigPermisos({
  onCerrar,
}: {
  onCerrar: () => void;
}) {
  const actual = useConfigPermisos();
  const [borrador, setBorrador] = useState<ConfigPermisos>(actual);
  const [lista, setLista] = useState(actual.confirmar.join("\n"));
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    void recargarConfigPermisos().then((c) => {
      setBorrador(c);
      setLista(c.confirmar.join("\n"));
    });
  }, []);

  const min = actual.limites?.espera_min ?? 10;
  const max = actual.limites?.espera_max ?? 540;
  const ayuda = POLITICAS.find((p) => p.id === borrador.politica)?.ayuda;

  const guardar = async () => {
    setGuardando(true);
    setMensaje(null);
    const r = await guardarConfigPermisos({
      ...borrador,
      confirmar: lista
        .split("\n")
        .map((x) => x.trim())
        .filter(Boolean),
    });
    setGuardando(false);
    if (r.ok && r.config) {
      fijarConfigPermisos(r.config);
      setBorrador(r.config);
      setLista(r.config.confirmar.join("\n"));
      setMensaje("Guardado.");
    } else {
      setMensaje(r.error ?? "No se pudo guardar.");
    }
  };

  return (
    <section className={s.config} aria-label="Permisos desde la oficina">
      <div className={s.cabeza}>
        <h2>Permisos desde la oficina</h2>
        <button type="button" className={s.boton} onClick={onCerrar}>
          Cerrar
        </button>
      </div>
      <p className={s.nota}>
        Cuando un agente te pide permiso (13), la oficina puede aprobarlo o
        rechazarlo. Si nadie responde a tiempo, sigue el diálogo normal de VS
        Code.
      </p>
      <div className={s.columnas}>
        <label className={s.campo}>
          Cuándo esperar tu respuesta
          <select
            value={borrador.politica}
            onChange={(e) =>
              setBorrador({ ...borrador, politica: e.target.value as Politica })
            }
          >
            {POLITICAS.map((p) => (
              <option key={p.id} value={p.id}>
                {p.nombre}
              </option>
            ))}
          </select>
          {ayuda && <small>{ayuda}</small>}
        </label>
        <label className={s.campo}>
          Tiempo de espera (segundos)
          <input
            type="number"
            min={min}
            max={max}
            step={5}
            value={borrador.espera_seg}
            onChange={(e) =>
              setBorrador({
                ...borrador,
                espera_seg: Math.round(Number(e.target.value) || 0),
              })
            }
          />
          <small>
            Entre {min} y {max} s. Por defecto {CONFIG_POR_DEFECTO.espera_seg}{" "}
            s.
          </small>
        </label>
      </div>
      <label className={s.campo}>
        Comandos que piden confirmación en el celular
        <small>
          Uno por línea. Antes de aprobar un comando que empiece con alguno de
          estos (o los use), el celular pregunta de nuevo.
        </small>
        <textarea value={lista} onChange={(e) => setLista(e.target.value)} />
      </label>
      <div className={s.botones}>
        <button
          type="button"
          className={`${s.boton} ${s.aprobar}`}
          disabled={guardando}
          onClick={() => void guardar()}
        >
          Guardar
        </button>
        <button
          type="button"
          className={s.boton}
          onClick={() => {
            setBorrador({ ...borrador, ...CONFIG_POR_DEFECTO });
            setLista(CONFIG_POR_DEFECTO.confirmar.join("\n"));
          }}
        >
          Valores por defecto
        </button>
        {mensaje && (
          <span className={s.restante} role="status">
            {mensaje}
          </span>
        )}
      </div>
    </section>
  );
}
