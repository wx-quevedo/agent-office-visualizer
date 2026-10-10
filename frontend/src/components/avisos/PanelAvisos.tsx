"use client";

/** Alerts panel: switches, voice, speed, volume and tests. Uses the API of useAvisos. */

import type { ReactNode } from "react";
import type { ConfigAvisos } from "./deteccion";
import type { ApiAvisos } from "./useAvisos";
import s from "./avisos.module.css";

function Interruptor({
  activo,
  onCambio,
  children,
  detalle,
}: {
  activo: boolean;
  onCambio: (v: boolean) => void;
  children: ReactNode;
  detalle?: string;
}) {
  return (
    <label className={s.interruptor}>
      <input
        type="checkbox"
        checked={activo}
        onChange={(e) => onCambio(e.target.checked)}
      />
      <span>
        {children}
        {detalle && <small>{detalle}</small>}
      </span>
    </label>
  );
}

const EVENTOS: Array<[keyof ConfigAvisos["eventos"], string, string]> = [
  ["permiso", "Te pide permiso (13)", "Voz y notificación"],
  ["pregunta", "Te hizo una pregunta (14)", "Voz y notificación"],
  ["termino", "Terminó el turno (11)", "Voz; la notificación es aparte"],
  [
    "recordatorio",
    "Recordatorio mientras te espera",
    "Repite el aviso de 13 y 14",
  ],
  ["cerrado", "Se cerró con una pregunta pendiente (21)", "Voz y notificación"],
];

function textoPermiso(api: ApiAvisos): string | null {
  if (!api.contextoSeguro) {
    return "Las notificaciones de Windows solo funcionan si abres la página en localhost o por https. La voz sí funciona.";
  }
  if (api.permiso === "no-disponible")
    return "Este navegador no permite notificaciones.";
  if (api.permiso === "denied") {
    return "El navegador bloqueó las notificaciones de esta página. Para permitirlas: haz clic en el candado o en el ícono de ajustes junto a la dirección, en Notificaciones elige Permitir y recarga la página. Si aun así no aparecen, revisa en Windows Configuración > Sistema > Notificaciones que el navegador esté permitido y que No molestar esté apagado.";
  }
  if (api.permiso === "default")
    return "Las notificaciones todavía no tienen permiso: presiona Activar avisos.";
  return null;
}

export default function PanelAvisos({
  api,
  onCerrar,
}: {
  api: ApiAvisos;
  onCerrar: () => void;
}) {
  const c = api.config;
  const aviso = textoPermiso(api);
  return (
    <section className={s.panel} aria-label="Avisos">
      <div className={s.cabeza}>
        <h2 className={s.titulo}>Avisos</h2>
        <button type="button" className={s.boton} onClick={onCerrar}>
          Cerrar
        </button>
      </div>

      <div className={s.estado}>
        <strong>{c.activos ? "Avisos activos" : "Avisos desactivados"}</strong>
        <span className={s.mono}>
          {" "}
          · notificaciones:{" "}
          {api.permiso === "granted"
            ? "permitidas"
            : api.permiso === "denied"
              ? "bloqueadas"
              : api.permiso === "default"
                ? "sin permiso"
                : "no disponibles"}{" "}
          · voz: {api.audioListo ? "lista" : "haz clic en la página"}
        </span>
      </div>

      <div className={s.fila}>
        {c.activos ? (
          <button type="button" className={s.boton} onClick={api.desactivar}>
            Desactivar avisos
          </button>
        ) : (
          <button
            type="button"
            className={`${s.boton} ${s.primario}`}
            onClick={() => void api.activar()}
          >
            Activar avisos
          </button>
        )}
        <button type="button" className={s.boton} onClick={api.probarAviso}>
          Probar aviso
        </button>
      </div>

      {aviso && <p className={s.nota}>{aviso}</p>}
      {!api.audioListo && c.activos && (
        <p className={s.nota}>
          El navegador solo deja hablar a la página después de un clic: tras
          recargar, haz clic en cualquier parte de la página para que la voz
          funcione.
        </p>
      )}

      <div className={s.columnas}>
        <fieldset className={s.grupo}>
          <legend>Qué avisa</legend>
          {EVENTOS.map(([k, nombre, det]) => (
            <Interruptor
              key={k}
              activo={c.eventos[k]}
              onCambio={(v) => api.cambiarEvento(k, v)}
              detalle={det}
            >
              {nombre}
            </Interruptor>
          ))}
          <label className={s.campo}>
            <span>Repetir recordatorio cada</span>
            <select
              value={c.recordatorioMin}
              onChange={(e) =>
                api.cambiar({
                  recordatorioMin: Number(
                    e.target.value,
                  ) as ConfigAvisos["recordatorioMin"],
                })
              }
            >
              <option value={2}>2 min</option>
              <option value={5}>5 min</option>
              <option value={10}>10 min</option>
              <option value={0}>Nunca</option>
            </select>
          </label>
        </fieldset>

        <fieldset className={s.grupo}>
          <legend>Qué lee y cómo notifica</legend>
          <Interruptor
            activo={c.leerPermiso}
            onCambio={(v) => api.cambiar({ leerPermiso: v })}
          >
            Leer lo que pide un permiso (herramienta y comando)
          </Interruptor>
          <Interruptor
            activo={c.leerPregunta}
            onCambio={(v) => api.cambiar({ leerPregunta: v })}
          >
            Leer la pregunta pendiente
          </Interruptor>
          <Interruptor
            activo={c.notificarTermino}
            onCambio={(v) => api.cambiar({ notificarTermino: v })}
          >
            Notificación de Windows al terminar el turno
          </Interruptor>
          <Interruptor
            activo={c.notificarConFoco}
            onCambio={(v) => api.cambiar({ notificarConFoco: v })}
            detalle="Si lo apagas, solo notifica con la pestaña en segundo plano"
          >
            Notificar también con esta pestaña al frente
          </Interruptor>
        </fieldset>

        <fieldset className={s.grupo}>
          <legend>Voz y sonido</legend>
          {!api.vozDisponible && (
            <p className={s.nota}>Este navegador no tiene síntesis de voz.</p>
          )}
          <label className={s.campo}>
            <span>Voz</span>
            <select
              value={c.voz ?? ""}
              onChange={(e) => api.cambiar({ voz: e.target.value || null })}
            >
              <option value="">
                Automática{api.vozElegida ? ` (${api.vozElegida.name})` : ""}
              </option>
              {api.voces.map((v) => (
                <option key={v.voiceURI} value={v.voiceURI}>
                  {v.name} · {v.lang}
                </option>
              ))}
            </select>
          </label>
          {api.vozDisponible && api.voces.length === 0 && (
            <p className={s.nota}>
              No hay voces en español instaladas; se usará la voz por defecto.
            </p>
          )}
          <label className={s.campo}>
            <span>
              Velocidad <b className={s.mono}>{c.velocidad.toFixed(1)}</b>
            </span>
            <input
              type="range"
              min={0.6}
              max={1.6}
              step={0.1}
              value={c.velocidad}
              onChange={(e) =>
                api.cambiar({ velocidad: Number(e.target.value) })
              }
            />
          </label>
          <label className={s.campo}>
            <span>
              Volumen <b className={s.mono}>{Math.round(c.volumen * 100)} %</b>
            </span>
            <input
              type="range"
              min={0.1}
              max={1}
              step={0.1}
              value={c.volumen}
              onChange={(e) => api.cambiar({ volumen: Number(e.target.value) })}
            />
          </label>
          <Interruptor
            activo={c.sonido}
            onCambio={(v) => api.cambiar({ sonido: v })}
          >
            Sonido corto antes de la voz
          </Interruptor>
          <button type="button" className={s.boton} onClick={api.probarVoz}>
            Probar voz
          </button>
        </fieldset>
      </div>
    </section>
  );
}
