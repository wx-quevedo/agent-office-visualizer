"use client";

/** /historial?agente=<id>&pagina=<n> — full history of an agent (see components/ficha). */

import { Suspense } from "react";
import HistorialCompleto from "@/components/ficha/HistorialCompleto";

export default function HistorialPage() {
  return (
    <Suspense fallback={null}>
      <HistorialCompleto />
    </Suspense>
  );
}
