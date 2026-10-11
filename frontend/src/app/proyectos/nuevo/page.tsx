"use client";

/** /proyectos/nuevo — form to create a project with its team. */

import { Suspense } from "react";
import NuevoProyecto from "@/components/proyectos/NuevoProyecto";

export default function NuevoProyectoPage() {
  return (
    <Suspense fallback={null}>
      <NuevoProyecto />
    </Suspense>
  );
}
