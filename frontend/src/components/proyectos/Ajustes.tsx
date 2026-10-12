"use client";

/**
 * /ajustes (Prompt 39): the global lists that every project uses. "Reglas de
 * la casa" (text, type and whether it is on by default; add, edit in place and
 * delete with confirmation) are written in the CLAUDE.md of each project;
 * "Comandos seguros" are run by the code agents without asking for permission.
 * Each project can turn rules and commands off in its Equipo section.
 * Refreshed every 3 s; a change is shown at once from the answer of the server.
 */

import Link from "next/link";
import { useId, useState, type FormEvent } from "react";
import { useLectura } from "@/utils/useLectura";
import { enviarJson, mensajeDe } from "./acciones";
import Dialogo from "./Dialogo";
import { Interruptor } from "./Reglas";
import {
  MAX_COMANDO,
  MAX_REGLA,
  cambiosRegla,
  cuerpoComando,
  cuerpoRegla,
  nombreTipo,
  opcionesTipo,
  ponerEnLista,
  quitarDeLista,
  type Comando,
  type ListaComandos,
  type ListaReglas,
  type Regla,
} from "./logicaReglas";
import s from "./proyectos.module.css";

type Opcion = { valor: string; texto: string };

export interface CambiosRegla {
  texto?: string;
  tipo?: string;
  activa_por_defecto?: boolean;
}

export interface CambiosComando {
  comando?: string;
  activo_por_defecto?: boolean;
}

export interface PropsAjustes {
  reglas: Regla[] | null;
  tipos?: string[] | null;
  comandos: Comando[] | null;
  errorReglas?: string | null;
  errorComandos?: string | null;
  /** Each one rejects with the message of the server. */
  agregarRegla: (c: {
    texto: string;
    tipo: string;
    activa_por_defecto: boolean;
  }) => Promise<void>;
  editarRegla: (id: string, c: CambiosRegla) => Promise<void>;
  borrarRegla: (id: string) => Promise<void>;
  agregarComando: (c: {
    comando: string;
    activo_por_defecto: boolean;
  }) => Promise<void>;
  editarComando: (id: string, c: CambiosComando) => Promise<void>;
  borrarComando: (id: string) => Promise<void>;
}

const TEXTO_BORRAR_REGLA =
  "Se quita de la lista y del CLAUDE.md de cada proyecto. No se puede deshacer.";

/** One rule: type, text, switch, and Editar / Borrar (or the edit form). */
function FilaRegla({
  regla: r,
  opciones,
  editar,
  borrar,
}: {
  regla: Regla;
  opciones: Opcion[];
  editar: PropsAjustes["editarRegla"];
  borrar: PropsAjustes["borrarRegla"];
}) {
  const id = useId();
  const [editando, setEditando] = useState(false);
  const [texto, setTexto] = useState(r.texto);
  const [tipo, setTipo] = useState<string>(r.tipo);
  const [enviando, setEnviando] = useState(false);
  const [activa, setActiva] = useState<boolean | null>(null);
  const [confirmar, setConfirmar] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hacer = async (trabajo: () => Promise<void>) => {
    setEnviando(true);
    setError(null);
    try {
      await trabajo();
      return true;
    } catch (e) {
      setError(mensajeDe(e));
      return false;
    } finally {
      setEnviando(false);
    }
  };

  const guardar = async (e: FormEvent) => {
    e.preventDefault();
    if (!texto.trim()) return;
    const c = cambiosRegla(r, texto, tipo);
    if (!c) {
      setEditando(false);
      return;
    }
    if (await hacer(() => editar(r.id, c))) setEditando(false);
  };

  const cambiarActiva = async () => {
    const nuevo = !r.activa_por_defecto;
    setActiva(nuevo);
    await hacer(() => editar(r.id, { activa_por_defecto: nuevo }));
    setActiva(null);
  };

  return (
    <li className={s.ajuste}>
      {editando ? (
        <form className={s.decidirForm} onSubmit={guardar}>
          <label htmlFor={`${id}-texto`} className={s.campoTitulo}>
            Texto de la regla
          </label>
          <textarea
            id={`${id}-texto`}
            className={`${s.control} ${s.area}`}
            rows={3}
            maxLength={MAX_REGLA}
            value={texto}
            required
            onChange={(e) => setTexto(e.target.value)}
          />
          <label htmlFor={`${id}-tipo`} className={s.campoTitulo}>
            Tipo
          </label>
          <select
            id={`${id}-tipo`}
            className={s.control}
            value={tipo}
            onChange={(e) => setTipo(e.target.value)}
          >
            {opciones.map((o) => (
              <option key={o.valor} value={o.valor}>
                {o.texto}
              </option>
            ))}
          </select>
          <div className={s.botonesOrden}>
            <button
              type="submit"
              className={s.botonPrincipal}
              disabled={enviando || !texto.trim()}
            >
              {enviando ? "Guardando…" : "Guardar"}
            </button>
            <button
              type="button"
              className={s.boton}
              disabled={enviando}
              onClick={() => {
                setEditando(false);
                setError(null);
              }}
            >
              Cancelar
            </button>
          </div>
        </form>
      ) : (
        <>
          <div className={s.ajusteCabeza}>
            <span className={s.etiqueta}>{nombreTipo(r.tipo)}</span>
            <span id={`${id}-t`} className={s.ajusteTexto}>
              {r.texto}
            </span>
          </div>
          <div className={s.ajustePie}>
            <div className={s.interruptorFila}>
              <Interruptor
                activo={activa ?? r.activa_por_defecto}
                nombradoPor={`${id}-a ${id}-t`}
                ocupado={enviando}
                cambiar={() => void cambiarActiva()}
              />
              <span id={`${id}-a`} className={s.nota}>
                Activa por defecto
              </span>
            </div>
            <div className={s.botonesOrden}>
              <button
                type="button"
                className={s.boton}
                disabled={enviando}
                aria-describedby={`${id}-t`}
                onClick={() => {
                  setTexto(r.texto);
                  setTipo(r.tipo);
                  setError(null);
                  setEditando(true);
                }}
              >
                Editar
              </button>
              <button
                type="button"
                className={s.boton}
                disabled={enviando}
                aria-describedby={`${id}-t`}
                onClick={() => setConfirmar(true)}
              >
                Borrar
              </button>
            </div>
          </div>
        </>
      )}
      {confirmar && (
        <Dialogo
          titulo="¿Borrar la regla?"
          texto={TEXTO_BORRAR_REGLA}
          textoConfirmar="Borrar"
          confirmar={() => {
            setConfirmar(false);
            void hacer(() => borrar(r.id));
          }}
          cancelar={() => setConfirmar(false)}
        />
      )}
      {error && (
        <p className={s.avisoError} role="alert">
          {error}
        </p>
      )}
    </li>
  );
}

/** "Agregar regla": text, type and whether it is on by default. */
function AgregarRegla({
  opciones,
  agregar,
}: {
  opciones: Opcion[];
  agregar: PropsAjustes["agregarRegla"];
}) {
  const id = useId();
  const [texto, setTexto] = useState("");
  const [tipo, setTipo] = useState("otra");
  const [activa, setActiva] = useState(true);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const valor = opciones.some((o) => o.valor === tipo)
    ? tipo
    : (opciones[0]?.valor ?? "otra");

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    const cuerpo = cuerpoRegla(texto, valor, activa);
    if (!cuerpo) return;
    setEnviando(true);
    setError(null);
    try {
      await agregar(cuerpo);
      setTexto("");
      setActiva(true);
    } catch (err) {
      setError(mensajeDe(err));
    } finally {
      setEnviando(false);
    }
  };

  return (
    <form className={s.ajusteNuevo} onSubmit={enviar}>
      <label htmlFor={`${id}-texto`} className={s.campoTitulo}>
        Nueva regla
      </label>
      <textarea
        id={`${id}-texto`}
        className={`${s.control} ${s.area}`}
        rows={3}
        maxLength={MAX_REGLA}
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
      />
      <label htmlFor={`${id}-tipo`} className={s.campoTitulo}>
        Tipo
      </label>
      <select
        id={`${id}-tipo`}
        className={s.control}
        value={valor}
        onChange={(e) => setTipo(e.target.value)}
      >
        {opciones.map((o) => (
          <option key={o.valor} value={o.valor}>
            {o.texto}
          </option>
        ))}
      </select>
      <div className={s.interruptorFila}>
        <Interruptor
          activo={activa}
          nombradoPor={`${id}-a`}
          cambiar={() => setActiva((v) => !v)}
        />
        <span id={`${id}-a`} className={s.nota}>
          Activa por defecto
        </span>
      </div>
      {error && (
        <p className={s.avisoError} role="alert">
          {error}
        </p>
      )}
      <div className={s.pie}>
        <button
          type="submit"
          className={s.botonPrincipal}
          disabled={enviando || !texto.trim()}
        >
          {enviando ? "Agregando…" : "Agregar regla"}
        </button>
      </div>
    </form>
  );
}

/** One command: the text, its switch and Borrar. */
function FilaComando({
  comando: c,
  editar,
  borrar,
}: {
  comando: Comando;
  editar: PropsAjustes["editarComando"];
  borrar: PropsAjustes["borrarComando"];
}) {
  const id = useId();
  const [enviando, setEnviando] = useState(false);
  const [activo, setActivo] = useState<boolean | null>(null);
  const [confirmar, setConfirmar] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hacer = async (trabajo: () => Promise<void>) => {
    setEnviando(true);
    setError(null);
    try {
      await trabajo();
    } catch (e) {
      setError(mensajeDe(e));
    } finally {
      setEnviando(false);
    }
  };

  return (
    <li className={s.ajuste}>
      <span id={`${id}-t`} className={`${s.ajusteTexto} ${s.mono}`}>
        {c.comando}
      </span>
      <div className={s.ajustePie}>
        <div className={s.interruptorFila}>
          <Interruptor
            activo={activo ?? c.activo_por_defecto}
            nombradoPor={`${id}-a ${id}-t`}
            ocupado={enviando}
            cambiar={() => {
              const nuevo = !c.activo_por_defecto;
              setActivo(nuevo);
              void hacer(() =>
                editar(c.id, { activo_por_defecto: nuevo }),
              ).finally(() => setActivo(null));
            }}
          />
          <span id={`${id}-a`} className={s.nota}>
            Activo por defecto
          </span>
        </div>
        <div className={s.botonesOrden}>
          <button
            type="button"
            className={s.boton}
            disabled={enviando}
            aria-describedby={`${id}-t`}
            onClick={() => setConfirmar(true)}
          >
            Borrar
          </button>
        </div>
      </div>
      {confirmar && (
        <Dialogo
          titulo="¿Borrar el comando?"
          texto={`Los agentes de código van a volver a pedirte permiso para correr "${c.comando}".`}
          textoConfirmar="Borrar"
          confirmar={() => {
            setConfirmar(false);
            void hacer(() => borrar(c.id));
          }}
          cancelar={() => setConfirmar(false)}
        />
      )}
      {error && (
        <p className={s.avisoError} role="alert">
          {error}
        </p>
      )}
    </li>
  );
}

/** "Agregar comando": one text field; the server says why it rejects one. */
function AgregarComando({
  agregar,
}: {
  agregar: PropsAjustes["agregarComando"];
}) {
  const id = useId();
  const [comando, setComando] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    const cuerpo = cuerpoComando(comando);
    if (!cuerpo) return;
    setEnviando(true);
    setError(null);
    try {
      await agregar(cuerpo);
      setComando("");
    } catch (err) {
      setError(mensajeDe(err));
    } finally {
      setEnviando(false);
    }
  };

  return (
    <form className={s.ajusteNuevo} onSubmit={enviar}>
      <label htmlFor={`${id}-c`} className={s.campoTitulo}>
        Nuevo comando
      </label>
      <input
        id={`${id}-c`}
        type="text"
        className={`${s.control} ${s.mono}${error ? ` ${s.controlError}` : ""}`}
        maxLength={MAX_COMANDO}
        autoComplete="off"
        autoCapitalize="none"
        spellCheck={false}
        placeholder="npm run build"
        value={comando}
        aria-invalid={error ? true : undefined}
        aria-describedby={`${id}-n`}
        onChange={(e) => setComando(e.target.value)}
      />
      <p id={`${id}-n`} className={s.nota}>
        Un comando por vez, sin * ( ) ; &amp; | &gt; &lt; ` ni $.
      </p>
      {error && (
        <p className={s.avisoError} role="alert">
          {error}
        </p>
      )}
      <div className={s.pie}>
        <button
          type="submit"
          className={s.botonPrincipal}
          disabled={enviando || !comando.trim()}
        >
          {enviando ? "Agregando…" : "Agregar comando"}
        </button>
      </div>
    </form>
  );
}

/** The page with its data given (tested with sample data). */
export function AjustesVista({
  reglas,
  tipos = null,
  comandos,
  errorReglas = null,
  errorComandos = null,
  agregarRegla,
  editarRegla,
  borrarRegla,
  agregarComando,
  editarComando,
  borrarComando,
}: PropsAjustes) {
  const opciones = opcionesTipo(tipos);
  return (
    <div className={s.pagina}>
      <main className={`${s.contenido} ${s.angosto}`}>
        <nav className={s.migas} aria-label="Navegación">
          <Link href="/proyectos" className={s.enlace}>
            Volver a Proyectos
          </Link>
          <Link href="/oficina/3d" className={s.enlace}>
            Ir a la oficina
          </Link>
        </nav>
        <header className={s.cabeza}>
          <div className={s.cabezaTexto}>
            <h1 className={s.titulo}>Ajustes</h1>
            <p className={s.secundario}>
              Las listas que usan todos los proyectos.
            </p>
          </div>
        </header>

        <section className={s.bloque} aria-labelledby="reglas-titulo">
          <h2 id="reglas-titulo" className={s.subtitulo}>
            Reglas de la casa
          </h2>
          <p className={s.nota}>
            Se escriben en el CLAUDE.md de cada proyecto. Cada proyecto puede
            apagar las que no le sirvan.
          </p>
          {!reglas && (
            <p
              className={errorReglas ? s.avisoError : s.secundario}
              role="status"
            >
              {errorReglas
                ? `No se pudieron leer las reglas (${errorReglas}); se reintenta solo.`
                : "Cargando…"}
            </p>
          )}
          {reglas && reglas.length === 0 && (
            <p className={s.secundario}>Todavía no hay reglas.</p>
          )}
          {reglas && reglas.length > 0 && (
            <ul className={s.listaAjustes} aria-label="Reglas de la casa">
              {reglas.map((r) => (
                <FilaRegla
                  key={r.id}
                  regla={r}
                  opciones={opciones}
                  editar={editarRegla}
                  borrar={borrarRegla}
                />
              ))}
            </ul>
          )}
          <AgregarRegla opciones={opciones} agregar={agregarRegla} />
        </section>

        <section className={s.bloque} aria-labelledby="comandos-titulo">
          <h2 id="comandos-titulo" className={s.subtitulo}>
            Comandos seguros
          </h2>
          <p className={s.nota}>
            Los agentes de código los corren sin pedirte permiso. Todo lo demás
            sigue pidiéndolo.
          </p>
          {!comandos && (
            <p
              className={errorComandos ? s.avisoError : s.secundario}
              role="status"
            >
              {errorComandos
                ? `No se pudieron leer los comandos (${errorComandos}); se reintenta solo.`
                : "Cargando…"}
            </p>
          )}
          {comandos && comandos.length === 0 && (
            <p className={s.secundario}>Todavía no hay comandos.</p>
          )}
          {comandos && comandos.length > 0 && (
            <ul className={s.listaAjustes} aria-label="Comandos seguros">
              {comandos.map((c) => (
                <FilaComando
                  key={c.id}
                  comando={c}
                  editar={editarComando}
                  borrar={borrarComando}
                />
              ))}
            </ul>
          )}
          <AgregarComando agregar={agregarComando} />
        </section>
      </main>
    </div>
  );
}

/** The local copy of a read list after a change, until the next read. */
interface Local<T> {
  base: unknown;
  lista: T[];
}

/** The page with its reads: rules and commands (3 s). */
export default function Ajustes() {
  const leidas = useLectura<ListaReglas>("/api/v1/reglas", 3000);
  const leidos = useLectura<ListaComandos>("/api/v1/comandos", 3000);
  const [reglasLocal, setReglasLocal] = useState<Local<Regla> | null>(null);
  const [comandosLocal, setComandosLocal] = useState<Local<Comando> | null>(
    null,
  );
  const reglas =
    reglasLocal && reglasLocal.base === leidas.datos
      ? reglasLocal.lista
      : (leidas.datos?.reglas ?? null);
  const comandos =
    comandosLocal && comandosLocal.base === leidos.datos
      ? comandosLocal.lista
      : (leidos.datos?.comandos ?? null);

  const cambiarReglas = (f: (l: Regla[]) => Regla[]) => {
    const base = leidas.datos;
    setReglasLocal((v) => ({
      base,
      lista: f(v && v.base === base ? v.lista : (base?.reglas ?? [])),
    }));
  };
  const cambiarComandos = (f: (l: Comando[]) => Comando[]) => {
    const base = leidos.datos;
    setComandosLocal((v) => ({
      base,
      lista: f(v && v.base === base ? v.lista : (base?.comandos ?? [])),
    }));
  };

  const ruta = (lista: "reglas" | "comandos", id: string) =>
    `/api/v1/${lista}/${encodeURIComponent(id)}`;

  return (
    <AjustesVista
      reglas={reglas}
      tipos={leidas.datos?.tipos ?? null}
      comandos={comandos}
      errorReglas={leidas.error}
      errorComandos={leidos.error}
      agregarRegla={async (c) => {
        const r = await enviarJson<Regla>("/api/v1/reglas", c);
        cambiarReglas((l) => ponerEnLista(l, r));
      }}
      editarRegla={async (id, c) => {
        const r = await enviarJson<Regla>(ruta("reglas", id), c, "PATCH");
        cambiarReglas((l) => ponerEnLista(l, r));
      }}
      borrarRegla={async (id) => {
        await enviarJson(ruta("reglas", id), undefined, "DELETE");
        cambiarReglas((l) => quitarDeLista(l, id));
      }}
      agregarComando={async (c) => {
        const x = await enviarJson<Comando>("/api/v1/comandos", c);
        cambiarComandos((l) => ponerEnLista(l, x));
      }}
      editarComando={async (id, c) => {
        const x = await enviarJson<Comando>(ruta("comandos", id), c, "PATCH");
        cambiarComandos((l) => ponerEnLista(l, x));
      }}
      borrarComando={async (id) => {
        await enviarJson(ruta("comandos", id), undefined, "DELETE");
        cambiarComandos((l) => quitarDeLista(l, id));
      }}
    />
  );
}
