"use client";

/**
 * Chat section of a project (Prompt 38): Washington's bubbles on the right,
 * the orchestrator's on the left, and a purple card for each order, mixed by
 * `creado`. The sent message shows at once and is replaced by the read one.
 * Scrolls to the end on new items only when the reader was already there.
 * Prompt 41: the orchestrator's text is shown as markdown (Markdown.tsx);
 * Washington's stays plain text.
 * Prompt 43: `aviso` (from "Responder" of an orchestrator alert) scrolls to
 * that message or order and marks it for a moment; for a message the text
 * field gets the focus, ready to answer.
 * Prompt 45: under each of Washington's bubbles "Enviado" and then "Leído";
 * while the orchestrator answers, a bubble of his at the end with three dots
 * or the text as it is written (`enVivo`, from useChatEnVivo). The recent
 * messages of the live state join the read ones by id, so the final answer
 * replaces the partial one in the same render.
 */

import { objetivoAviso } from "@/components/avisos/logicaOrquestador";
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
  type EnVivo,
  type Mensaje,
  type Orden,
  type Proyecto,
} from "./logica";
import { burbujaEnVivo, marcaMensaje, unirRecientes } from "./logicaEnVivo";
import { Markdown } from "./Markdown";
import { TarjetaOrden } from "./TarjetaOrden";
import s from "./proyectos.module.css";

/** Distance to the end (px) that still counts as "at the end". */
const CERCA = 48;

/** How long the message or order of the alert stays marked. */
export const RESALTADO_MS = 4000;

/** Id of the chat item that `aviso` ("mensaje:<id>" or "orden:<id>") points to. */
export function itemDeAviso(aviso: string | null | undefined): string | null {
  const o = objetivoAviso(aviso);
  if (!o) return null;
  return `${o.tipo === "orden" ? "o" : "m"}-${o.id}`;
}

export interface PropsChat {
  proyecto: Pick<Proyecto, "id" | "estado">;
  chat: Chat | null;
  error?: string | null;
  ahora: number;
  /** An order answered after deciding it (so the Equipo history sees it too). */
  cambioOrden?: (o: Orden) => void;
  /** Local answers of decided orders, kept by the page. */
  ordenesLocales?: Record<string, Orden>;
  /** Alert opened with "Responder": "mensaje:<id>" or "orden:<id>". */
  aviso?: string | null;
  /** Live state of the answer (useChatEnVivo); else `chat.en_vivo`. */
  enVivo?: EnVivo | null;
  /** Last messages of the live state, fresher than `chat.mensajes`. */
  recientes?: Mensaje[];
}

export function ChatVista({
  proyecto: p,
  chat,
  error = null,
  ahora,
  cambioOrden,
  ordenesLocales,
  aviso = null,
  enVivo = null,
  recientes,
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
  const campo = useRef<HTMLTextAreaElement>(null);
  const avisoHecho = useRef<string | null>(null);
  const [avisoVisto, setAvisoVisto] = useState<string | null>(null);

  const locales = { ...propias, ...ordenesLocales };
  const mensajes = chat
    ? unirMensajes(
        unirRecientes(chat.mensajes, recientes),
        enviados,
        pendientes,
      )
    : [];
  const items = chat
    ? mezclarChat(mensajes, unirOrdenes(chat.ordenes, locales))
    : [];
  const ultimo = items.length ? items[items.length - 1].id : "";
  const vivo = burbujaEnVivo(enVivo ?? chat?.en_vivo, mensajes);
  const largoVivo = vivo ? (vivo.tipo === "texto" ? vivo.texto.length : 0) : -1;

  // Follows new items and the partial text as it grows (when at the end).
  useLayoutEffect(() => {
    const el = lista.current;
    if (el && abajo.current) el.scrollTop = el.scrollHeight;
  }, [items.length, ultimo, largoVivo]);

  // The alert's message or order: scroll the list to it once it is there.
  const idAviso = itemDeAviso(aviso);
  const hayAviso = idAviso !== null && items.some((x) => x.id === idAviso);
  const resaltado = hayAviso && avisoVisto !== aviso ? idAviso : null;
  useLayoutEffect(() => {
    if (!aviso || !idAviso || !hayAviso || avisoHecho.current === aviso) return;
    avisoHecho.current = aviso;
    const el = lista.current;
    const destino = el
      ? [...el.querySelectorAll<HTMLElement>("[data-item]")].find(
          (x) => x.dataset.item === idAviso,
        )
      : undefined;
    if (el && destino) {
      abajo.current = false;
      el.scrollTop +=
        destino.getBoundingClientRect().top -
        el.getBoundingClientRect().top -
        12;
    }
    if (idAviso.startsWith("m-")) campo.current?.focus();
    setTimeout(() => setAvisoVisto(aviso), RESALTADO_MS);
  }, [aviso, idAviso, hayAviso]);

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
      {chat && items.length === 0 && !vivo && (
        <p className={s.aviso}>
          Todavía no hay mensajes. Cuéntale al orquestador qué quieres hacer y
          él reparte el trabajo entre los agentes de código.
        </p>
      )}
      {(items.length > 0 || vivo) && (
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
                <li
                  key={x.id}
                  data-item={x.id}
                  data-resaltado={x.id === resaltado || undefined}
                  className={
                    x.id === resaltado
                      ? `${s.chatOrden} ${s.resaltadoOrden}`
                      : s.chatOrden
                  }
                >
                  <TarjetaOrden orden={x.orden} ahora={ahora} cambio={cambio} />
                </li>
              );
            const m = x.mensaje;
            const mio = m.autor === "washington";
            const pendiente = idsPendientes.has(m.id);
            const marca = marcaMensaje(m, pendiente);
            return (
              <li
                key={x.id}
                data-item={x.id}
                data-resaltado={x.id === resaltado || undefined}
                className={
                  x.id === resaltado
                    ? `${mio ? s.burbujaMia : s.burbujaOrq} ${s.resaltado}`
                    : mio
                      ? s.burbujaMia
                      : s.burbujaOrq
                }
                aria-busy={pendiente || undefined}
              >
                <span className={s.burbujaAutor}>
                  {mio ? "Tú" : "Orquestador"}
                </span>
                {mio ? (
                  <p className={s.burbujaTexto}>{m.texto}</p>
                ) : (
                  <Markdown texto={m.texto} />
                )}
                <span className={s.hora}>
                  {pendiente ? (
                    "Enviando…"
                  ) : (
                    <time dateTime={m.creado}>{horaMinuto(m.creado)}</time>
                  )}
                  {marca && !pendiente && (
                    <span className={s.marca} data-marca={marca}>
                      {marca}
                    </span>
                  )}
                </span>
              </li>
            );
          })}
          {vivo && (
            <li
              key="en-vivo"
              data-en-vivo={vivo.tipo}
              className={s.burbujaOrq}
              aria-busy="true"
              aria-live="off"
            >
              <span className={s.burbujaAutor}>Orquestador</span>
              {vivo.tipo === "texto" ? (
                <>
                  <Markdown texto={vivo.texto} />
                  <span className={s.hora}>Escribiendo…</span>
                </>
              ) : (
                <span
                  className={s.puntos}
                  role="img"
                  aria-label="El orquestador está escribiendo"
                >
                  <span />
                  <span />
                  <span />
                </span>
              )}
            </li>
          )}
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
          ref={campo}
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
