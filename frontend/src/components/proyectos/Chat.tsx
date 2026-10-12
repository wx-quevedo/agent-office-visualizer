"use client";

/**
 * Chat section of a project (Prompt 38): Washington's bubbles on the right,
 * the orchestrator's on the left, and a purple card for each order, mixed by
 * `creado`. The sent message shows at once and is replaced by the read one.
 * Scrolls to the end on new items only when the reader was already there.
 */

import {
  useLayoutEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { horaMinuto } from "@/components/ficha/logica";
import { enviarJson, mensajeDe } from "./acciones";
import {
  MAX_MENSAJE,
  mezclarChat,
  notaChat,
  unirMensajes,
  unirOrdenes,
  type Chat,
  type Mensaje,
  type Orden,
  type Proyecto,
} from "./logica";
import { TarjetaOrden } from "./TarjetaOrden";
import s from "./proyectos.module.css";

/** Distance to the end (px) that still counts as "at the end". */
const CERCA = 48;

export interface PropsChat {
  proyecto: Pick<Proyecto, "id" | "estado">;
  chat: Chat | null;
  error?: string | null;
  ahora: number;
  /** An order answered after deciding it (so the Equipo history sees it too). */
  cambioOrden?: (o: Orden) => void;
  /** Local answers of decided orders, kept by the page. */
  ordenesLocales?: Record<string, Orden>;
}

export function ChatVista({
  proyecto: p,
  chat,
  error = null,
  ahora,
  cambioOrden,
  ordenesLocales,
}: PropsChat) {
  const [enviados, setEnviados] = useState<Mensaje[]>([]);
  const [pendientes, setPendientes] = useState<Mensaje[]>([]);
  const [propias, setPropias] = useState<Record<string, Orden>>({});
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [errorEnvio, setErrorEnvio] = useState<string | null>(null);
  const lista = useRef<HTMLOListElement>(null);
  const abajo = useRef(true);
  const contador = useRef(0);

  const locales = { ...propias, ...ordenesLocales };
  const items = chat
    ? mezclarChat(
        unirMensajes(chat.mensajes, enviados, pendientes),
        unirOrdenes(chat.ordenes, locales),
      )
    : [];
  const ultimo = items.length ? items[items.length - 1].id : "";

  useLayoutEffect(() => {
    const el = lista.current;
    if (el && abajo.current) el.scrollTop = el.scrollHeight;
  }, [items.length, ultimo]);

  const alDesplazar = () => {
    const el = lista.current;
    if (!el) return;
    abajo.current = el.scrollHeight - el.scrollTop - el.clientHeight < CERCA;
  };

  const cambio = (o: Orden) => {
    setPropias((v) => ({ ...v, [o.id]: o }));
    cambioOrden?.(o);
  };

  const enviar = async () => {
    const t = texto.trim();
    if (!t || enviando) return;
    contador.current += 1;
    const provisorio: Mensaje = {
      id: `local-${contador.current}`,
      autor: "washington",
      texto: t,
      creado: new Date().toISOString(),
    };
    abajo.current = true;
    setPendientes((v) => [...v, provisorio]);
    setTexto("");
    setEnviando(true);
    setErrorEnvio(null);
    try {
      const m = await enviarJson<Mensaje>(
        `/api/v1/proyectos-creados/${encodeURIComponent(p.id)}/chat`,
        { texto: t },
      );
      setEnviados((v) => [...v, m]);
    } catch (e) {
      setErrorEnvio(mensajeDe(e));
      setTexto((v) => v || t);
    } finally {
      setPendientes((v) => v.filter((x) => x.id !== provisorio.id));
      setEnviando(false);
    }
  };

  const alEnviar = (e: FormEvent) => {
    e.preventDefault();
    void enviar();
  };

  const tecla = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      void enviar();
    }
  };

  const nota = notaChat(p.estado);
  const idsPendientes = new Set(pendientes.map((m) => m.id));

  return (
    <section className={s.chat} aria-labelledby="chat-titulo">
      <h2 id="chat-titulo" className={s.oculto}>
        Chat con el orquestador
      </h2>
      {nota && (
        <p className={s.aviso} role="status">
          {nota}
        </p>
      )}
      {!chat && !error && (
        <p className={s.secundario}>Cargando la conversación…</p>
      )}
      {!chat && error && (
        <p className={s.avisoError} role="status">
          No se pudo leer el chat ({error}); se reintenta solo.
        </p>
      )}
      {chat && items.length === 0 && (
        <p className={s.aviso}>
          Todavía no hay mensajes. Cuéntale al orquestador qué quieres hacer y
          él reparte el trabajo entre los agentes de código.
        </p>
      )}
      {items.length > 0 && (
        <ol
          ref={lista}
          className={s.chatLista}
          role="log"
          aria-label="Conversación con el orquestador"
          tabIndex={0}
          onScroll={alDesplazar}
        >
          {items.map((x) => {
            if (x.tipo === "orden")
              return (
                <li key={x.id} className={s.chatOrden}>
                  <TarjetaOrden orden={x.orden} ahora={ahora} cambio={cambio} />
                </li>
              );
            const m = x.mensaje;
            const mio = m.autor === "washington";
            const pendiente = idsPendientes.has(m.id);
            return (
              <li
                key={x.id}
                className={mio ? s.burbujaMia : s.burbujaOrq}
                aria-busy={pendiente || undefined}
              >
                <span className={s.burbujaAutor}>
                  {mio ? "Tú" : "Orquestador"}
                </span>
                <p className={s.burbujaTexto}>{m.texto}</p>
                <span className={s.hora}>
                  {pendiente ? (
                    "Enviando…"
                  ) : (
                    <time dateTime={m.creado}>{horaMinuto(m.creado)}</time>
                  )}
                </span>
              </li>
            );
          })}
        </ol>
      )}
      {error && chat && (
        <p className={s.secundario} role="status">
          La última lectura falló ({error}); se reintenta solo.
        </p>
      )}
      <form className={s.chatForm} onSubmit={alEnviar}>
        <label htmlFor="chat-mensaje" className={s.oculto}>
          Mensaje para el orquestador
        </label>
        <textarea
          id="chat-mensaje"
          className={`${s.control} ${s.area}`}
          rows={3}
          maxLength={MAX_MENSAJE}
          placeholder="Escribe al orquestador…"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={tecla}
          aria-describedby="chat-ayuda"
        />
        <div className={s.chatPie}>
          <p id="chat-ayuda" className={s.nota}>
            Enter envía; Shift+Enter hace un salto de línea.
          </p>
          <button
            type="submit"
            className={s.botonPrincipal}
            disabled={enviando || !texto.trim()}
          >
            {enviando ? "Enviando…" : "Enviar"}
          </button>
        </div>
        {errorEnvio && (
          <p className={s.avisoError} role="alert">
            {errorEnvio}
          </p>
        )}
      </form>
    </section>
  );
}
