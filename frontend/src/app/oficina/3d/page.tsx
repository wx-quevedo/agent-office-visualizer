"use client";

/**
 * /oficina/3d — 3D office (based on Agent Office 3D, MIT). Loaded only in the
 * browser (no SSR) and in its own chunk: three, R3F and drei are not part of
 * /oficina or /datos.
 */

import dynamic from "next/dynamic";

const Oficina3D = dynamic(() => import("@/components/oficina3d/Oficina3D"), {
  ssr: false,
  loading: () => (
    <div
      style={{
        padding: 24,
        fontFamily: "var(--font-plex-sans), Arial, sans-serif",
      }}
    >
      Cargando la oficina 3D…
    </div>
  ),
});

export default function Oficina3DPage() {
  return <Oficina3D />;
}
