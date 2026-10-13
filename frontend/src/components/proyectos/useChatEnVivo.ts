"use client";

/**
 * Live state of the chat of a project (Prompt 45): listens to the
 * Server-Sent Events of `/chat/eventos` (one event on connecting and one on
 * each change; EventSource reconnects by itself when the server closes). When
 * EventSource does not exist, closes for good or fails MAX_ERRORES_SSE times
 * in a row without a message, polls `/chat/en-vivo` every CONSULTA_MS.
 * Everything is closed on unmount or when the project changes.
 */

import { useEffect, useState } from "react";
import { API_BASE, apiFetch } from "@/utils/api";
import type { EnVivo, Mensaje } from "./logica";
import {
  CONSULTA_MS,
  conexionInicial,
  leerChatEnVivo,
  rutaEnVivo,
  rutaEventos,
  siguienteConexion,
  type ChatEnVivo,
} from "./logicaEnVivo";

export interface DatosEnVivo {
  enVivo: EnVivo | null;
  recientes: Mensaje[];
}

const VACIO: DatosEnVivo = { enVivo: null, recientes: [] };

/** EventSource.CLOSED (the constant is not there when the class is faked). */
const CERRADO = 2;

export function useChatEnVivo(proyectoId: string | null): DatosEnVivo {
  const [estado, setEstado] = useState<{
    id: string | null;
    datos: ChatEnVivo | null;
  }>({ id: proyectoId, datos: null });

  useEffect(() => {
    if (!proyectoId) return;
    let vivo = true;
    let fuente: EventSource | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let version: string | null = null;
    let consultando = false;
    const ES = typeof EventSource === "undefined" ? undefined : EventSource;
    let conexion = conexionInicial(ES !== undefined);

    const recibir = (d: ChatEnVivo) => {
      if (!vivo) return;
      if (d.version && d.version === version) return;
      version = d.version || null;
      setEstado({ id: proyectoId, datos: d });
    };

    const consultar = async () => {
      try {
        const r = await apiFetch(rutaEnVivo(proyectoId), {
          cache: "no-store",
        });
        if (r.ok) {
          const d = leerChatEnVivo(await r.json());
          if (d) recibir(d);
        }
      } catch {
        // Kept the last state; the next poll retries.
      } finally {
        if (vivo) timer = setTimeout(consultar, CONSULTA_MS);
      }
    };

    const aConsulta = () => {
      fuente?.close();
      fuente = null;
      if (!vivo || consultando) return;
      consultando = true;
      void consultar();
    };

    if (conexion.modo === "sse" && ES) {
      try {
        fuente = new ES(`${API_BASE}${rutaEventos(proyectoId)}`, {
          withCredentials: true,
        });
      } catch {
        conexion = { modo: "consulta", errores: 0 };
      }
    }
    if (fuente) {
      fuente.addEventListener("chat", (e) => {
        conexion = siguienteConexion(conexion, "mensaje");
        const d = leerChatEnVivo((e as MessageEvent).data);
        if (d) recibir(d);
      });
      fuente.onerror = () => {
        const cerrado = fuente?.readyState === CERRADO;
        conexion = siguienteConexion(conexion, cerrado ? "cerrado" : "error");
        if (conexion.modo === "consulta") aConsulta();
      };
    } else {
      aConsulta();
    }

    return () => {
      vivo = false;
      fuente?.close();
      fuente = null;
      if (timer) clearTimeout(timer);
    };
  }, [proyectoId]);

  if (!proyectoId || estado.id !== proyectoId || !estado.datos) return VACIO;
  return { enVivo: estado.datos.en_vivo, recientes: estado.datos.recientes };
}
