"use client";

/**
 * In every page: with access on and no session, go to /entrar (and come back
 * here afterwards). With access off (local) it does nothing.
 */

import { useEffect } from "react";
import { irAEntrar } from "@/utils/api";
import { debeEntrar, leerEstadoAcceso } from "./logica";

export default function GuardaSesion() {
  useEffect(() => {
    void leerEstadoAcceso().then((e) => {
      if (debeEntrar(e, window.location.pathname)) irAEntrar();
    });
  }, []);
  return null;
}
