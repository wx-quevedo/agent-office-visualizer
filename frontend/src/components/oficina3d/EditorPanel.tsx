"use client";

/**
 * Office editor panel (left side of /oficina/3d): furniture catalog, selected
 * piece, undo/redo, colour theme, warnings of blocked paths, save/cancel and
 * JSON export/import. Adapted from the editor of Agent Office 3D (MIT).
 */

import { useEffect, useMemo, useRef } from "react";
import { bloqueos } from "./caminos";
import {
  distribucionActual,
  exportarDistribucion,
  leerDistribucion,
  useLayout,
} from "./distribucion";
import { useEditor } from "./editor";
import { defMueble, MUEBLES } from "./muebles";
import { TEMAS } from "./temas";
import { t } from "./textos";
import s from "./editor.module.css";

export default function EditorPanel() {
  const items = useLayout((st) => st.items);
  const tema = useLayout((st) => st.tema);
  const ed = useEditor();
  const archivo = useRef<HTMLInputElement>(null);
  const tapan = useMemo(() => bloqueos(items), [items]);
  const elegido = items.find((it) => it.id === ed.seleccion);

  // Keyboard shortcuts while editing.
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      const destino = e.target as HTMLElement | null;
      if (destino && ["INPUT", "SELECT", "TEXTAREA"].includes(destino.tagName))
        return;
      const st = useEditor.getState();
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
        e.preventDefault();
        if (e.shiftKey) st.rehacer();
        else st.deshacer();
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "y") {
        e.preventDefault();
        st.rehacer();
      } else if (e.key === "r" || e.key === "R") st.rotar();
      else if (e.key === "Delete" || e.key === "Backspace") st.borrar();
      else if (e.key === "Escape") st.elegirPaleta(null);
    };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, []);

  const importar = async (f: File | undefined) => {
    if (!f) return;
    try {
      const d = leerDistribucion(JSON.parse(await f.text()));
      ed.importar(d);
    } catch {
      useEditor.setState({ mensaje: t("editor.importarError") });
    }
    if (archivo.current) archivo.current.value = "";
  };

  return (
    <aside className={s.panel} aria-label={t("editor.titulo")}>
      <h2 className={s.titulo}>{t("editor.titulo")}</h2>
      <p className={s.ayuda}>{t("editor.ayuda")}</p>

      <section className={s.grupo}>
        <h3>{t("editor.muebles")}</h3>
        <div className={s.catalogo}>
          {MUEBLES.map((m) => (
            <button
              key={m.type}
              type="button"
              className={s.boton}
              aria-pressed={ed.paleta === m.type}
              onClick={() =>
                ed.elegirPaleta(ed.paleta === m.type ? null : m.type)
              }
            >
              {m.label}
            </button>
          ))}
        </div>
        <div className={s.meta}>
          <b className={s.mono}>{items.length}</b> {t("editor.cantidad")}
        </div>
      </section>

      <section className={s.grupo}>
        <h3>{t("editor.seleccionado")}</h3>
        {elegido ? (
          <>
            <div className={s.meta}>
              {defMueble(elegido.type)?.label} ·{" "}
              <span className={s.mono}>
                x {elegido.x.toFixed(1)} · z {elegido.z.toFixed(1)} ·{" "}
                {Math.round((elegido.ry * 180) / Math.PI)}°
              </span>
            </div>
            <div className={s.fila}>
              <button
                type="button"
                className={s.boton}
                onClick={() => ed.rotar()}
              >
                {t("editor.rotar")}
              </button>
              <button
                type="button"
                className={s.boton}
                onClick={() => ed.borrar()}
              >
                {t("editor.borrar")}
              </button>
            </div>
          </>
        ) : (
          <div className={s.meta}>{t("editor.ninguno")}</div>
        )}
        <div className={s.fila}>
          <button
            type="button"
            className={s.boton}
            disabled={!ed.pasado.length}
            onClick={ed.deshacer}
          >
            {t("editor.deshacer")}
          </button>
          <button
            type="button"
            className={s.boton}
            disabled={!ed.futuro.length}
            onClick={ed.rehacer}
          >
            {t("editor.rehacer")}
          </button>
        </div>
      </section>

      <section className={s.grupo}>
        <h3>{t("editor.tema")}</h3>
        <select
          className={s.selector}
          value={tema ?? "claro"}
          onChange={(e) => ed.aplicarTema(e.target.value)}
          aria-label={t("editor.tema")}
        >
          {TEMAS.map((tm) => (
            <option key={tm.key} value={tm.key}>
              {tm.nombre}
            </option>
          ))}
        </select>
      </section>

      {tapan.length > 0 && (
        <section className={s.aviso} role="alert">
          <b>{t("editor.avisoBloqueo")}</b>
          <ul>
            {tapan.map((b) => {
              const it = items.find((x) => x.id === b.id);
              return (
                <li key={b.id}>
                  <button
                    type="button"
                    className={s.enlace}
                    onClick={() => ed.seleccionar(b.id)}
                  >
                    {defMueble(it?.type ?? "")?.label} ({it?.x.toFixed(1)},{" "}
                    {it?.z.toFixed(1)})
                  </button>{" "}
                  {b.motivo === "camino"
                    ? t("editor.tapaCamino")
                    : t("editor.tapaEscritorio")}
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {ed.mensaje && <p className={s.mensaje}>{ed.mensaje}</p>}

      <div className={s.fila}>
        <button
          type="button"
          className={`${s.boton} ${s.primario}`}
          disabled={tapan.length > 0 || ed.guardando}
          onClick={() => void ed.guardar()}
        >
          {ed.guardando ? t("editor.guardando") : t("editor.guardar")}
        </button>
        <button type="button" className={s.boton} onClick={ed.cancelar}>
          {t("editor.cancelar")}
        </button>
      </div>
      <div className={s.fila}>
        <button
          type="button"
          className={s.boton}
          onClick={() => exportarDistribucion(distribucionActual())}
        >
          {t("editor.exportar")}
        </button>
        <button
          type="button"
          className={s.boton}
          onClick={() => archivo.current?.click()}
        >
          {t("editor.importar")}
        </button>
        <input
          ref={archivo}
          type="file"
          accept="application/json,.json"
          hidden
          onChange={(e) => void importar(e.target.files?.[0])}
        />
      </div>
      <p className={s.ayuda}>{t("editor.atajos")}</p>
    </aside>
  );
}
