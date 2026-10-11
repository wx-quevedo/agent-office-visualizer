"use client";

/** /proyectos/ver?id=<id>&seccion=chat|equipo|donde — one project. */

import { Suspense } from "react";
import VerProyecto from "@/components/proyectos/VerProyecto";

// Suspense: the page reads ?id= with useSearchParams (static export).
export default function VerProyectoPage() {
  return (
    <Suspense fallback={null}>
      <VerProyecto />
    </Suspense>
  );
}
