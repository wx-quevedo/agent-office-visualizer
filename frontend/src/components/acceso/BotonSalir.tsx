"use client";

/** "Salir" next to Avisos and Permisos; only when sign-in is on and there is a session. */

import { useEffect, useState } from "react";
import { leerEstadoAcceso, salir } from "./logica";

export default function BotonSalir({ className }: { className?: string }) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    void leerEstadoAcceso().then((e) =>
      setVisible(!!e && e.modo === "activado" && e.sesion),
    );
  }, []);
  if (!visible) return null;
  return (
    <button type="button" className={className} onClick={() => void salir()}>
      Salir
    </button>
  );
}
