"use client";

/**
 * Rule of the 8 hours: if more than 8 h passed since your last visit to the
 * office on this device, entering the office opens "Dónde quedamos" first.
 * The time of the last visit lives in this browser only (localStorage); with
 * blocked storage nothing is remembered and the office opens as always.
 */

import { useRouter } from "next/navigation";
import { useEffect } from "react";

export const CLAVE_VISITA = "oficina-ultima-visita";
export const HORAS_SIN_VISITA = 8;
const LIMITE_MS = HORAS_SIN_VISITA * 3600 * 1000;
const CADA_MS = 60 * 1000;

type Almacen = Pick<Storage, "getItem" | "setItem">;

function almacenLocal(): Almacen | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

/** Time of the last visit (ms), or null if unknown. */
export function leerUltimaVisita(
  almacen: Almacen | null = almacenLocal(),
): number | null {
  try {
    const v = almacen?.getItem(CLAVE_VISITA);
    if (!v) return null;
    const n = Number(v);
    return Number.isFinite(n) && n > 0 ? n : null;
  } catch {
    return null;
  }
}

export function guardarVisita(
  ahora: number,
  almacen: Almacen | null = almacenLocal(),
): void {
  try {
    almacen?.setItem(CLAVE_VISITA, String(Math.round(ahora)));
  } catch {
    // private window or blocked storage: the visit is not remembered
  }
}

/**
 * True when "Dónde quedamos" should open first: a known last visit more than
 * 8 h ago. Never on the first visit of a device or with a clock in the past.
 */
export function debeAbrirDondeQuedamos(
  ultima: number | null,
  ahora: number,
): boolean {
  if (ultima === null) return false;
  return ahora - ultima > LIMITE_MS;
}

/**
 * In /oficina and /oficina/3d: on entry, opens "Dónde quedamos" if it is due
 * (not when the link points to an agent); then keeps the visit time fresh
 * every minute and when the page is hidden.
 */
export function useVisitaOficina(conAgente: boolean): void {
  const router = useRouter();
  useEffect(() => {
    const ahora = Date.now();
    const abrir =
      !conAgente && debeAbrirDondeQuedamos(leerUltimaVisita(), ahora);
    guardarVisita(ahora);
    if (abrir) {
      router.replace("/donde-quedamos?desde=oficina");
      return;
    }
    const id = setInterval(() => guardarVisita(Date.now()), CADA_MS);
    const oculta = () => {
      if (document.visibilityState === "hidden") guardarVisita(Date.now());
    };
    document.addEventListener("visibilitychange", oculta);
    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", oculta);
    };
    // Only on entry: the rule is checked once per visit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
