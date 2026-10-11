"use client";

/** /proyectos — the projects created from the office (see components/proyectos). */

import { Suspense } from "react";
import ListaProyectos from "@/components/proyectos/ListaProyectos";

export default function ProyectosPage() {
  return (
    <Suspense fallback={null}>
      <ListaProyectos />
    </Suspense>
  );
}
