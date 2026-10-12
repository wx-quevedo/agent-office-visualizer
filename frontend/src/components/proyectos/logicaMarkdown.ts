/**
 * Pure markdown parser for the orchestrator's chat bubbles (Prompt 41): turns
 * the text into a tree of block and inline nodes that Markdown.tsx renders as
 * React elements. It never produces HTML: any tag in the text stays plain
 * text. Supported: paragraphs and line breaks, **bold** and __bold__,
 * *italic* and _italic_ (not inside words with underscores), `inline code`,
 * ``` fenced code, -, * and 1. lists (nested by indentation), # to ###
 * headings, > quotes, --- separators, [text](url) links and bare http(s)
 * URLs. Links only keep http, https and mailto; anything else stays text.
 * Images are shown as plain links. No React, no DOM: tested in
 * tests/markdown.test.tsx.
 */

export type Inline =
  | { tipo: "texto"; texto: string }
  | { tipo: "salto" }
  | { tipo: "negrita"; hijos: Inline[] }
  | { tipo: "cursiva"; hijos: Inline[] }
  | { tipo: "codigo"; texto: string }
  | { tipo: "enlace"; url: string; hijos: Inline[] };

export interface ItemLista {
  bloques: Bloque[];
}

export type Bloque =
  | { tipo: "parrafo"; hijos: Inline[] }
  | { tipo: "encabezado"; nivel: 1 | 2 | 3; hijos: Inline[] }
  | { tipo: "codigo"; lenguaje: string | null; texto: string }
  | {
      tipo: "lista";
      ordenada: boolean;
      inicio: number;
      items: ItemLista[];
    }
  | { tipo: "cita"; bloques: Bloque[] }
  | { tipo: "separador" };

/** Schemes a link may use; anything else is shown as text. */
const ESQUEMAS = new Set(["http:", "https:", "mailto:"]);

/** Nesting limit of quotes and lists; deeper content stays as text. */
const PROFUNDIDAD = 12;

/**
 * The href to use for a link, or null when it is not allowed. The URL parser
 * is the same one the browser uses, so tabs, newlines, control characters and
 * mixed case in the scheme ("Java\tScript:") are normalized before checking,
 * and the returned href is exactly what was checked.
 */
export function enlaceSeguro(url: string): string | null {
  const limpio = url.trim();
  if (!limpio || /[\s\u0000-\u001f\u007f]/.test(limpio)) return null;
  let u: URL;
  try {
    u = new URL(limpio);
  } catch {
    return null;
  }
  if (!ESQUEMAS.has(u.protocol)) return null;
  if (u.protocol !== "mailto:" && !u.hostname) return null;
  return u.href;
}

/* ------------------------------------------------------------------ blocks */

const RE_CERCA = /^ {0,3}(`{3,})\s*([^`\s]*)[^`]*$/;
const RE_ENCABEZADO = /^ {0,3}(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$/;
const RE_CITA = /^ {0,3}> ?/;
const RE_SEPARADOR = /^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$/;
const RE_ITEM = /^([ \t]*)([-*+]|\d{1,9}[.)])([ \t]+|$)(.*)$/;

function blanca(l: string): boolean {
  return l.trim() === "";
}

/** Width of the leading whitespace, a tab counting as 4 columns. */
function sangria(l: string): number {
  let n = 0;
  for (const c of l) {
    if (c === " ") n += 1;
    else if (c === "\t") n += 4 - (n % 4);
    else break;
  }
  return n;
}

/** Removes up to `n` columns of leading whitespace. */
function quitarSangria(l: string, n: number): string {
  let col = 0;
  let i = 0;
  while (i < l.length && col < n) {
    if (l[i] === " ") col += 1;
    else if (l[i] === "\t") col += 4 - (col % 4);
    else break;
    i += 1;
  }
  return l.slice(i);
}

interface Item {
  sangria: number;
  ordenada: boolean;
  numero: number;
  contenido: number;
  resto: string;
}

function item(l: string): Item | null {
  const m = RE_ITEM.exec(l);
  if (!m) return null;
  const sang = sangria(m[1]);
  const marca = m[2];
  const espacio = m[3] ? sangria(m[3]) : 0;
  const ordenada = /\d/.test(marca);
  return {
    sangria: sang,
    ordenada,
    numero: ordenada ? parseInt(marca, 10) : 1,
    contenido:
      sang + marca.length + (espacio > 4 || espacio === 0 ? 1 : espacio),
    resto: m[4],
  };
}

/** A line that starts a block other than a paragraph. */
function iniciaBloque(l: string): boolean {
  return (
    RE_CERCA.test(l) ||
    RE_ENCABEZADO.test(l) ||
    RE_CITA.test(l) ||
    RE_SEPARADOR.test(l) ||
    (item(l) !== null && !blanca(item(l)!.resto))
  );
}

export function parsearMarkdown(texto: string): Bloque[] {
  const lineas = texto.replace(/\r\n?/g, "\n").split("\n");
  return bloques(lineas, 0);
}

function bloques(lineas: string[], prof: number): Bloque[] {
  const out: Bloque[] = [];
  let i = 0;
  while (i < lineas.length) {
    const l = lineas[i];
    if (blanca(l)) {
      i += 1;
      continue;
    }

    const cerca = RE_CERCA.exec(l);
    if (cerca) {
      const largo = cerca[1].length;
      const cuerpo: string[] = [];
      let j = i + 1;
      const cierre = new RegExp(`^ {0,3}\`{${largo},}[ \\t]*$`);
      while (j < lineas.length && !cierre.test(lineas[j])) {
        cuerpo.push(lineas[j]);
        j += 1;
      }
      out.push({
        tipo: "codigo",
        lenguaje: cerca[2] || null,
        texto: cuerpo.join("\n"),
      });
      i = j + 1;
      continue;
    }

    const enc = RE_ENCABEZADO.exec(l);
    if (enc) {
      const nivel = Math.min(enc[1].length, 3) as 1 | 2 | 3;
      out.push({ tipo: "encabezado", nivel, hijos: inline(enc[2] ?? "") });
      i += 1;
      continue;
    }

    if (RE_SEPARADOR.test(l)) {
      out.push({ tipo: "separador" });
      i += 1;
      continue;
    }

    if (prof < PROFUNDIDAD && RE_CITA.test(l)) {
      const dentro: string[] = [];
      while (i < lineas.length && RE_CITA.test(lineas[i])) {
        dentro.push(lineas[i].replace(RE_CITA, ""));
        i += 1;
      }
      out.push({ tipo: "cita", bloques: bloques(dentro, prof + 1) });
      continue;
    }

    const it = item(l);
    if (prof < PROFUNDIDAD && it) {
      i = lista(lineas, i, it, prof, out);
      continue;
    }

    // paragraph: until a blank line or the start of another block
    const parrafo: string[] = [l.trim()];
    i += 1;
    while (
      i < lineas.length &&
      !blanca(lineas[i]) &&
      !iniciaBloque(lineas[i])
    ) {
      parrafo.push(lineas[i].trim());
      i += 1;
    }
    out.push({ tipo: "parrafo", hijos: inline(parrafo.join("\n")) });
  }
  return out;
}

/** Parses a list starting at line `i`; returns the next line to read. */
function lista(
  lineas: string[],
  i: number,
  primero: Item,
  prof: number,
  out: Bloque[],
): number {
  const items: ItemLista[] = [];
  let actual: Item | null = primero;
  while (actual) {
    const cab: Item = actual;
    const cuerpo: string[] = [cab.resto];
    let j = i + 1;
    let siguiente: Item | null = null;
    while (j < lineas.length) {
      const l = lineas[j];
      if (blanca(l)) {
        let k = j + 1;
        while (k < lineas.length && blanca(lineas[k])) k += 1;
        if (k >= lineas.length) break;
        const otro = item(lineas[k]);
        if (sangria(lineas[k]) >= cab.contenido) {
          cuerpo.push(...lineas.slice(j, k).map(() => ""));
          j = k;
          continue;
        }
        if (otro && otro.sangria > cab.sangria) {
          cuerpo.push(...lineas.slice(j, k).map(() => ""));
          j = k;
          continue;
        }
        if (otro && otro.ordenada === cab.ordenada) {
          siguiente = otro;
          j = k;
        }
        break;
      }
      const otro = item(l);
      if (sangria(l) >= cab.contenido) {
        cuerpo.push(quitarSangria(l, cab.contenido));
      } else if (otro && otro.sangria > cab.sangria) {
        // a nested item indented less than the content column
        cuerpo.push(quitarSangria(l, cab.contenido));
      } else if (otro) {
        if (otro.ordenada === cab.ordenada) siguiente = otro;
        break;
      } else if (!blanca(cuerpo[cuerpo.length - 1]) && !iniciaBloque(l)) {
        // lazy continuation of the item's paragraph
        cuerpo.push(l.trim());
      } else {
        break;
      }
      j += 1;
    }
    items.push({ bloques: bloques(cuerpo, prof + 1) });
    i = j;
    actual = siguiente;
  }
  out.push({
    tipo: "lista",
    ordenada: primero.ordenada,
    inicio: primero.numero,
    items,
  });
  return i;
}

/* ------------------------------------------------------------------ inline */

const PUNTUACION = /[!-/:-@[-`{-~]/;
const ALFANUM = /[\p{L}\p{N}]/u;
const RE_URL = /^https?:\/\/[^\s<>"'`]+/i;

function esAlfanum(c: string | undefined): boolean {
  return c !== undefined && ALFANUM.test(c);
}

function esEspacio(c: string | undefined): boolean {
  return c === undefined || /\s/.test(c);
}

/** End (exclusive) of a code span starting at `i`, or -1. */
function finCodigo(s: string, i: number): number {
  let n = 0;
  while (s[i + n] === "`") n += 1;
  let j = i + n;
  while (j < s.length) {
    const k = s.indexOf("`", j);
    if (k < 0) return -1;
    let m = 0;
    while (s[k + m] === "`") m += 1;
    if (m === n) return k + m;
    j = k + m;
  }
  return -1;
}

/**
 * Index of the closing delimiter of `n` chars `c` after `desde`, or -1.
 * Skips escapes, code spans and runs of the other length.
 */
function cierre(s: string, desde: number, c: string, n: number): number {
  let j = desde;
  while (j < s.length) {
    const ch = s[j];
    if (ch === "\\") {
      j += 2;
      continue;
    }
    if (ch === "`") {
      const fin = finCodigo(s, j);
      if (fin > 0) {
        j = fin;
        continue;
      }
      while (s[j] === "`") j += 1;
      continue;
    }
    if (ch !== c) {
      j += 1;
      continue;
    }
    let r = 0;
    while (s[j + r] === c) r += 1;
    let pos = -1;
    if (n === 2 && r >= 2) pos = j + r - 2;
    if (n === 1 && (r === 1 || r >= 3)) pos = j + r - 1;
    if (
      pos >= 0 &&
      pos >= desde &&
      !esEspacio(s[j - 1]) &&
      !(c === "_" && esAlfanum(s[j + r]))
    )
      return pos;
    j += r;
  }
  return -1;
}

interface Destino {
  url: string;
  fin: number;
}

/** Parses "(url)" or "(url "title")" starting at the "(" in `i`. */
function destino(s: string, i: number): Destino | null {
  if (s[i] !== "(") return null;
  let j = i + 1;
  while (s[j] === " ") j += 1;
  let url = "";
  if (s[j] === "<") {
    const k = s.indexOf(">", j);
    if (k < 0 || s.slice(j + 1, k).includes("\n")) return null;
    url = s.slice(j + 1, k);
    j = k + 1;
  } else {
    let prof = 0;
    const ini = j;
    while (j < s.length && !/\s/.test(s[j])) {
      if (s[j] === "\\") {
        j += 2;
        continue;
      }
      if (s[j] === "(") prof += 1;
      else if (s[j] === ")") {
        if (prof === 0) break;
        prof -= 1;
      }
      j += 1;
    }
    url = s.slice(ini, Math.min(j, s.length));
  }
  while (s[j] === " ") j += 1;
  const q = s[j];
  if (q === '"' || q === "'") {
    const k = s.indexOf(q, j + 1);
    if (k < 0) return null;
    j = k + 1;
    while (s[j] === " ") j += 1;
  }
  if (s[j] !== ")") return null;
  return { url, fin: j + 1 };
}

/** End of the "[label]" starting at `i` (index of "]"), or -1. */
function finEtiqueta(s: string, i: number): number {
  let prof = 0;
  for (let j = i; j < s.length; j += 1) {
    const c = s[j];
    if (c === "\\") {
      j += 1;
      continue;
    }
    if (c === "`") {
      const fin = finCodigo(s, j);
      if (fin > 0) j = fin - 1;
      continue;
    }
    if (c === "[") prof += 1;
    else if (c === "]") {
      prof -= 1;
      if (prof === 0) return j;
    }
  }
  return -1;
}

/** A bare URL ends before trailing punctuation and unbalanced ")". */
function recortarUrl(u: string): string {
  let fin = u.length;
  for (;;) {
    const c = u[fin - 1];
    if (/[.,;:!?*_'"~]/.test(c)) {
      fin -= 1;
      continue;
    }
    if (c === ")") {
      const parte = u.slice(0, fin);
      const abre = parte.split("(").length - 1;
      const cierra = parte.split(")").length - 1;
      if (cierra > abre) {
        fin -= 1;
        continue;
      }
    }
    break;
  }
  return u.slice(0, fin);
}

export function inline(s: string, enEnlace = false): Inline[] {
  const out: Inline[] = [];
  let buf = "";
  const texto = (t: string) => {
    buf += t;
  };
  const volcar = () => {
    if (buf) out.push({ tipo: "texto", texto: buf });
    buf = "";
  };
  const nodo = (n: Inline) => {
    volcar();
    out.push(n);
  };

  let i = 0;
  while (i < s.length) {
    const c = s[i];

    if (c === "\\" && i + 1 < s.length && PUNTUACION.test(s[i + 1])) {
      texto(s[i + 1]);
      i += 2;
      continue;
    }

    if (c === "\n") {
      buf = buf.replace(/[ \t]+$/, "");
      nodo({ tipo: "salto" });
      i += 1;
      while (s[i] === " " || s[i] === "\t") i += 1;
      continue;
    }

    if (c === "`") {
      const fin = finCodigo(s, i);
      let n = 0;
      while (s[i + n] === "`") n += 1;
      if (fin < 0) {
        texto(s.slice(i, i + n));
        i += n;
        continue;
      }
      let cod = s.slice(i + n, fin - n).replace(/\n/g, " ");
      if (/^ .* $/.test(cod) && cod.trim()) cod = cod.slice(1, -1);
      nodo({ tipo: "codigo", texto: cod });
      i = fin;
      continue;
    }

    // [text](url) and ![alt](url) (the image is shown as a plain link)
    const imagen = c === "!" && s[i + 1] === "[";
    if (!enEnlace && (c === "[" || imagen)) {
      const ini = imagen ? i + 1 : i;
      const cierreEt = finEtiqueta(s, ini);
      const dest = cierreEt > 0 ? destino(s, cierreEt + 1) : null;
      if (dest) {
        const original = s.slice(i, dest.fin);
        const href = enlaceSeguro(dest.url);
        const etiqueta = s.slice(ini + 1, cierreEt);
        if (href) {
          nodo({
            tipo: "enlace",
            url: href,
            hijos: etiqueta.trim()
              ? inline(etiqueta, true)
              : [{ tipo: "texto", texto: dest.url }],
          });
        } else {
          texto(original);
        }
        i = dest.fin;
        continue;
      }
      texto(c);
      i += 1;
      continue;
    }

    // <https://...> and <mailto:...>
    if (!enEnlace && c === "<") {
      const m = /^<((?:https?|mailto):[^\s<>]+)>/i.exec(s.slice(i));
      const href = m ? enlaceSeguro(m[1]) : null;
      if (m && href) {
        nodo({
          tipo: "enlace",
          url: href,
          hijos: [{ tipo: "texto", texto: m[1] }],
        });
        i += m[0].length;
        continue;
      }
    }

    // bare http(s) URL at a word start
    if (
      !enEnlace &&
      (c === "h" || c === "H") &&
      !esAlfanum(s[i - 1]) &&
      s[i - 1] !== "/"
    ) {
      const m = RE_URL.exec(s.slice(i));
      if (m) {
        const u = recortarUrl(m[0]);
        const href = enlaceSeguro(u);
        if (href) {
          nodo({
            tipo: "enlace",
            url: href,
            hijos: [{ tipo: "texto", texto: u }],
          });
          i += u.length;
          continue;
        }
      }
    }

    if (c === "*" || c === "_") {
      let r = 0;
      while (s[i + r] === c) r += 1;
      const abre = !esEspacio(s[i + r]) && !(c === "_" && esAlfanum(s[i - 1]));
      if (abre) {
        if (r >= 2) {
          const k = cierre(s, i + 3, c, 2);
          if (k > 0) {
            nodo({
              tipo: "negrita",
              hijos: inline(s.slice(i + 2, k), enEnlace),
            });
            i = k + 2;
            continue;
          }
        }
        const k = cierre(s, i + 2, c, 1);
        if (k > 0) {
          nodo({ tipo: "cursiva", hijos: inline(s.slice(i + 1, k), enEnlace) });
          i = k + 1;
          continue;
        }
      }
      texto(s.slice(i, i + r));
      i += r;
      continue;
    }

    texto(c);
    i += 1;
  }
  volcar();
  return out;
}
