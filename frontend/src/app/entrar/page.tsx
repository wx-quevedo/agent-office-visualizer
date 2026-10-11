"use client";

/**
 * /entrar — sign-in of the office (VISUALIZADOR_AUTH=activado). Same boxes as
 * /oficina (white, greys, black, IBM Plex). After signing in it goes back to
 * the page it came from (?volver=, only paths of this site).
 */

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState, type FormEvent } from "react";
import { destinoSeguro } from "@/components/acceso/logica";
import { API_BASE } from "@/utils/api";
import s from "./entrar.module.css";

interface Detalle {
  mensaje?: string;
  segundos?: number;
}

function Formulario() {
  const params = useSearchParams();
  const destino = destinoSeguro(params.get("volver"));
  const [contrasena, setContrasena] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [espera, setEspera] = useState(0);
  const [desactivado, setDesactivado] = useState(false);

  // Already signed in, or sign-in off in this copy: straight to the office.
  useEffect(() => {
    void fetch(`${API_BASE}/api/v1/auth/estado`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((e: { modo?: string; sesion?: boolean } | null) => {
        if (!e) return;
        if (e.sesion) window.location.replace(destino);
        else if (e.modo === "desactivado") setDesactivado(true);
      })
      .catch(() => undefined);
  }, [destino]);

  // Countdown of the wait after too many attempts.
  useEffect(() => {
    if (espera <= 0) return;
    const id = setTimeout(() => setEspera((n) => n - 1), 1000);
    return () => clearTimeout(id);
  }, [espera]);

  const entrar = async (e: FormEvent) => {
    e.preventDefault();
    if (!contrasena || enviando || espera > 0) return;
    setEnviando(true);
    setError(null);
    try {
      const r = await fetch(`${API_BASE}/api/v1/auth/entrar`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-Visualizador": "1" },
        body: JSON.stringify({ contrasena }),
      });
      if (r.ok) {
        window.location.replace(destino);
        return;
      }
      const body = (await r.json().catch(() => null)) as {
        detail?: Detalle | string;
      } | null;
      const d: Detalle =
        typeof body?.detail === "object" && body.detail ? body.detail : {};
      if (r.status === 429) {
        setEspera(d.segundos ?? 30);
        setError("Demasiados intentos. Espera antes de volver a probar.");
      } else if (r.status === 401) {
        setContrasena("");
        if (d.segundos) setEspera(d.segundos);
        setError("Contraseña incorrecta.");
      } else if (r.status === 409) {
        setDesactivado(true);
      } else {
        setError(`No se pudo entrar (HTTP ${r.status}).`);
      }
    } catch {
      setError(
        "No hay conexión con la oficina. Revisa que el servidor esté encendido.",
      );
    } finally {
      setEnviando(false);
    }
  };

  return (
    <main className={s.pagina}>
      <form className={s.caja} onSubmit={(e) => void entrar(e)}>
        <h1 className={s.titulo}>Oficina de agentes</h1>
        <p className={s.linea}>Entra con tu contraseña.</p>
        {desactivado ? (
          <p className={s.aviso}>
            El inicio de sesión está desactivado en esta copia.{" "}
            <a href="/oficina">Ir a la oficina</a>
          </p>
        ) : (
          <>
            <label className={s.campo}>
              Contraseña
              <input
                type="password"
                name="contrasena"
                autoComplete="current-password"
                autoFocus
                value={contrasena}
                onChange={(e) => setContrasena(e.target.value)}
              />
            </label>
            {error && (
              <div className={s.error} role="alert">
                {error}
                {espera > 0 && (
                  <>
                    {" "}
                    Puedes volver a intentar en{" "}
                    <span className={s.mono}>{espera} s</span>.
                  </>
                )}
              </div>
            )}
            <button
              type="submit"
              className={s.boton}
              disabled={enviando || espera > 0 || !contrasena}
            >
              {enviando ? "Entrando…" : "Entrar"}
            </button>
            <p className={s.nota}>
              La sesión dura 30 días en este dispositivo.
            </p>
          </>
        )}
      </form>
    </main>
  );
}

export default function EntrarPage() {
  return (
    <Suspense>
      <Formulario />
    </Suspense>
  );
}
