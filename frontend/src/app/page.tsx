"use client";

import { useEffect } from "react";

/**
 * La raíz abre la oficina 3D. Sin sesión, /oficina/3d lleva a /entrar
 * (GuardaSesion del layout), así que aquí no hace falta revisarla.
 */
export default function Inicio() {
  useEffect(() => {
    window.location.replace("/oficina/3d");
  }, []);
  return (
    <main style={{ padding: 24, fontFamily: "system-ui, sans-serif" }}>
      <a href="/oficina/3d">Abrir la oficina de agentes</a>
    </main>
  );
}
