/**
 * Markdown of the orchestrator's chat bubbles (Prompt 41): renders the tree of
 * logicaMarkdown.ts as React elements only, never as raw HTML, so any tag in
 * the text is shown literally. Links (already limited to http, https and
 * mailto by the parser) open in a new tab without access to this page.
 */

import { Fragment, useMemo, type ReactNode } from "react";
import { parsearMarkdown, type Bloque, type Inline } from "./logicaMarkdown";
import s from "./proyectos.module.css";

const TITULO = { 1: s.mdTitulo1, 2: s.mdTitulo2, 3: s.mdTitulo3 } as const;

function enLinea(nodos: Inline[]): ReactNode[] {
  return nodos.map((n, i) => {
    switch (n.tipo) {
      case "texto":
        return <Fragment key={i}>{n.texto}</Fragment>;
      case "salto":
        return <br key={i} />;
      case "negrita":
        return <strong key={i}>{enLinea(n.hijos)}</strong>;
      case "cursiva":
        return <em key={i}>{enLinea(n.hijos)}</em>;
      case "codigo":
        return (
          <code key={i} className={s.mdCodigo}>
            {n.texto}
          </code>
        );
      case "enlace":
        return (
          <a
            key={i}
            className={s.mdEnlace}
            href={n.url}
            target="_blank"
            rel="noopener noreferrer"
          >
            {enLinea(n.hijos)}
          </a>
        );
    }
  });
}

function enBloques(bloques: Bloque[]): ReactNode[] {
  return bloques.map((b, i) => {
    switch (b.tipo) {
      case "parrafo":
        return <p key={i}>{enLinea(b.hijos)}</p>;
      case "encabezado":
        return (
          <p key={i} className={TITULO[b.nivel]}>
            <strong>{enLinea(b.hijos)}</strong>
          </p>
        );
      case "codigo":
        return (
          <pre
            key={i}
            className={s.mdBloqueCodigo}
            data-lenguaje={b.lenguaje ?? undefined}
            tabIndex={0}
          >
            <code>{b.texto}</code>
          </pre>
        );
      case "lista": {
        const items = b.items.map((it, j) => (
          <li key={j}>{enBloques(it.bloques)}</li>
        ));
        return b.ordenada ? (
          <ol key={i} start={b.inicio === 1 ? undefined : b.inicio}>
            {items}
          </ol>
        ) : (
          <ul key={i}>{items}</ul>
        );
      }
      case "cita":
        return <blockquote key={i}>{enBloques(b.bloques)}</blockquote>;
      case "separador":
        return <hr key={i} />;
    }
  });
}

export function Markdown({
  texto,
  className,
}: {
  texto: string;
  className?: string;
}) {
  const arbol = useMemo(() => parsearMarkdown(texto), [texto]);
  return (
    <div className={className ? `${s.md} ${className}` : s.md}>
      {enBloques(arbol)}
    </div>
  );
}
