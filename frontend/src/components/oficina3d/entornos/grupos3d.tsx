"use client";

/**
 * Drawing of the environments that seat by project. Cabinas: glass cabins
 * with the project sign over the door, warm light while someone works (low
 * otherwise) and a blue strip on the door while someone waits for you.
 * Estudio: long window on the back wall and a hanging sign over each island.
 */

import { useEffect, useMemo, useState } from "react";
import * as THREE from "three";
import { Rug } from "../escena/OfficeDecor";
import { basicMat, stdMat, UNIT_BOX } from "../escena/resources";
import { useOffice } from "../store";
import { t } from "../textos";
import { CABINA_GENERAL, CABINAS, PASILLO } from "./cabinas";
import { Cartel, Puerta } from "./comun3d";
import { ISLAS } from "./estudio";
import { Piezas } from "./piezas";
import { GRUPO_GENERAL, type Entorno } from "./tipos";

interface EstadoGrupo {
  /** Project, GRUPO_GENERAL or null (free group). */
  nombre: string | null;
  general: boolean;
  /** Some agent of the group works at its desk. */
  trabajando: boolean;
  /** Some agent of the group waits for you. */
  espera: boolean;
}

/** State of each group from the agents in the scene (stable while nothing changes). */
function useGrupos(ent: Entorno, cuantos: number): EstadoGrupo[] {
  const agents = useOffice((s) => s.agents);
  const duenos = useOffice((s) => s.grupos);
  const lista = useMemo(() => {
    const out: EstadoGrupo[] = Array.from({ length: cuantos }, (_, g) => ({
      nombre: duenos[g] ?? null,
      general: duenos[g] === GRUPO_GENERAL,
      trabajando: false,
      espera: false,
    }));
    const agr = ent.agrupacion;
    if (!agr) return out;
    for (const a of Object.values(agents)) {
      const e = out[Math.min(agr.grupoDe(a.seatIndex).g, cuantos - 1)];
      if (!e) continue;
      if (a.permission || a.question) e.espera = true;
      else if (a.destino === "escritorio") e.trabajando = true;
    }
    return out;
  }, [agents, duenos, ent, cuantos]);
  const [estable, setEstable] = useState(lista);
  useEffect(() => {
    setEstable((prev) =>
      JSON.stringify(prev) === JSON.stringify(lista) ? prev : lista,
    );
  }, [lista]);
  return estable;
}

// -- Cabinas por proyecto ---------------------------------------------------------------

const VIDRIO_M = stdMat("#bfe0ff", {
  roughness: 0.1,
  transparent: true,
  opacity: 0.16,
});
const ZOCALO_M = stdMat("#dedad2", { roughness: 0.8 });
const MARCO_M = stdMat("#2a2e35", { roughness: 0.5 });
const FRANJA_M = basicMat("#4c8bf5", { toneMapped: false });
const PISO_ACTIVO_M = stdMat("#f4efe4", { roughness: 0.7 });
const PISO_BAJO_M = stdMat("#bdb9b0", { roughness: 0.9 });
const FOCO_ON_M = stdMat("#fff4d6", {
  emissive: "#ffdf9e",
  emissiveIntensity: 1.6,
});
const FOCO_OFF_M = stdMat("#8a8780", { roughness: 0.8 });
const ALTO_VIDRIO = 2.3;
const PUERTA = 0.8;

/** A wall stretch of a cabin: low base, glass above, dark top rail. */
function TramoVidrio({
  x0,
  x1,
  z0,
  z1,
}: {
  x0: number;
  x1: number;
  z0: number;
  z1: number;
}) {
  const w = Math.max(0.06, x1 - x0);
  const d = Math.max(0.06, z1 - z0);
  return (
    <group position={[(x0 + x1) / 2, 0, (z0 + z1) / 2]}>
      <mesh
        position={[0, 0.25, 0]}
        scale={[w, 0.5, d]}
        geometry={UNIT_BOX}
        material={ZOCALO_M}
        receiveShadow
      />
      <mesh
        position={[0, 0.5 + (ALTO_VIDRIO - 0.5) / 2, 0]}
        scale={[w, ALTO_VIDRIO - 0.5, d]}
        geometry={UNIT_BOX}
        material={VIDRIO_M}
      />
      <mesh
        position={[0, ALTO_VIDRIO, 0]}
        scale={[w + 0.02, 0.06, d + 0.02]}
        geometry={UNIT_BOX}
        material={MARCO_M}
      />
    </group>
  );
}

function CabinaVidrio({
  indice,
  estado,
}: {
  indice: number;
  estado: EstadoGrupo;
}) {
  const c = CABINAS[indice];
  const zp = c.lado * PASILLO;
  const zf = c.lado * c.fondo;
  const e = 0.05;
  const nombre = estado.general ? t("grupo.cabinaGeneral") : estado.nombre;
  const encendida = estado.trabajando;
  const marco = estado.espera ? FRANJA_M : MARCO_M;
  return (
    <group>
      {/* floor: warm while someone works, low light otherwise */}
      <mesh
        position={[c.cx, 0.018, (zp + zf) / 2]}
        rotation={[-Math.PI / 2, 0, 0]}
        material={encendida ? PISO_ACTIVO_M : PISO_BAJO_M}
        receiveShadow
      >
        <planeGeometry args={[c.hw * 2 - 0.1, c.fondo - PASILLO - 0.1]} />
      </mesh>
      {/* walls: corridor side with the door, far side, both sides */}
      <TramoVidrio
        x0={c.cx - c.hw}
        x1={c.cx - PUERTA}
        z0={zp - e}
        z1={zp + e}
      />
      <TramoVidrio
        x0={c.cx + PUERTA}
        x1={c.cx + c.hw}
        z0={zp - e}
        z1={zp + e}
      />
      <TramoVidrio x0={c.cx - c.hw} x1={c.cx + c.hw} z0={zf - e} z1={zf + e} />
      {[c.cx - c.hw, c.cx + c.hw].map((x) => (
        <TramoVidrio
          key={x}
          x0={x - e}
          x1={x + e}
          z0={Math.min(zp, zf)}
          z1={Math.max(zp, zf)}
        />
      ))}
      {/* door frame: blue strip while someone of the cabin waits for you */}
      {[-PUERTA, PUERTA].map((dx) => (
        <mesh
          key={dx}
          position={[c.cx + dx, ALTO_VIDRIO / 2, zp]}
          scale={[0.09, ALTO_VIDRIO, 0.16]}
          geometry={UNIT_BOX}
          material={marco}
        />
      ))}
      <mesh
        position={[c.cx, ALTO_VIDRIO - 0.04, zp]}
        scale={[PUERTA * 2 + 0.1, 0.14, 0.18]}
        geometry={UNIT_BOX}
        material={marco}
      />
      {estado.espera && (
        <mesh
          position={[c.cx, 0.02, zp - c.lado * 0.45]}
          rotation={[-Math.PI / 2, 0, 0]}
          material={FRANJA_M}
        >
          <planeGeometry args={[PUERTA * 2, 0.12]} />
        </mesh>
      )}
      {/* ceiling lamp: on while someone works */}
      <mesh
        position={[c.cx, 3.0, (zp + zf) / 2]}
        scale={[1.8, 0.06, 0.5]}
        geometry={UNIT_BOX}
        material={encendida ? FOCO_ON_M : FOCO_OFF_M}
      />
      {/* sign over the door, readable from the corridor */}
      {nombre && (
        <group position={[c.cx, ALTO_VIDRIO + 0.42, zp]}>
          <Cartel
            texto={nombre}
            ancho={2.8}
            alto={0.55}
            fondo={encendida || estado.espera ? "#ffffff" : "#d9d6cf"}
          />
        </group>
      )}
    </group>
  );
}

export function DecoracionCabinas({ entorno }: { entorno: Entorno }) {
  const grupos = useGrupos(entorno, CABINAS.length);
  return (
    <group>
      <Piezas lista={entorno.decoracion} />
      {CABINAS.map((_, g) => (
        <CabinaVidrio
          key={g}
          indice={g}
          estado={
            g === CABINA_GENERAL ? { ...grupos[g], general: true } : grupos[g]
          }
        />
      ))}
      {/* runner around your desk in the corridor */}
      <Rug p={[0, 0, 0]} w={6.4} d={3.6} c="#6f7f99" accent="#8796ae" />
      <Puerta p={[24.8, 0, 13]} ry={Math.PI} />
    </group>
  );
}

// -- Estudio abierto con jardín --------------------------------------------------------------

const MARCO_VENTANA_M = stdMat("#2a2e35", { roughness: 0.5 });
const CIELO_M = basicMat("#d6ecfb", { toneMapped: false });
const ALFEIZAR_M = stdMat("#e8e2d6", { roughness: 0.6 });
const PIEDRA_G = new THREE.CylinderGeometry(0.42, 0.46, 0.04, 14);
const PIEDRA_M = stdMat("#cfc9bd", { roughness: 0.95 });

/** Long window on the back wall: sky panes, mullions and a sill. */
function Ventanal({ x0, x1, z }: { x0: number; x1: number; z: number }) {
  const ancho = x1 - x0;
  const n = Math.round(ancho / 2.2);
  return (
    <group position={[(x0 + x1) / 2, 0, z]}>
      <mesh position={[0, 1.95, 0]} material={CIELO_M}>
        <planeGeometry args={[ancho, 2.1]} />
      </mesh>
      {Array.from({ length: n + 1 }, (_, i) => (
        <mesh
          key={i}
          position={[-ancho / 2 + (ancho / n) * i, 1.95, 0.03]}
          scale={[0.08, 2.2, 0.06]}
          geometry={UNIT_BOX}
          material={MARCO_VENTANA_M}
        />
      ))}
      {[0.9, 2.2, 3.0].map((y) => (
        <mesh
          key={y}
          position={[0, y, 0.03]}
          scale={[ancho + 0.08, y === 2.2 ? 0.04 : 0.08, 0.06]}
          geometry={UNIT_BOX}
          material={MARCO_VENTANA_M}
        />
      ))}
      <mesh
        position={[0, 0.86, 0.12]}
        scale={[ancho + 0.1, 0.05, 0.26]}
        geometry={UNIT_BOX}
        material={ALFEIZAR_M}
      />
    </group>
  );
}

/** Hanging sign over an island. */
function CartelIsla({
  x,
  z,
  texto,
  activa,
}: {
  x: number;
  z: number;
  texto: string;
  activa: boolean;
}) {
  return (
    <group position={[x, 0, z]}>
      {[-0.8, 0.8].map((dx) => (
        <mesh
          key={dx}
          position={[dx, 2.98, 0]}
          scale={[0.015, 0.84, 0.015]}
          geometry={UNIT_BOX}
          material={MARCO_M}
        />
      ))}
      <group position={[0, 2.5, 0]}>
        <Cartel
          texto={texto}
          ancho={2.2}
          alto={0.5}
          fondo={activa ? "#ffffff" : "#e6e2da"}
        />
      </group>
    </group>
  );
}

export function DecoracionEstudio({ entorno }: { entorno: Entorno }) {
  const grupos = useGrupos(entorno, ISLAS.length);
  return (
    <group>
      <Piezas lista={entorno.decoracion} />
      <Ventanal x0={-20.5} x1={20.5} z={-16.82} />
      {ISLAS.map((c, g) => {
        const e = grupos[g];
        if (!e?.nombre) return null;
        return (
          <CartelIsla
            key={g}
            x={c.x}
            z={c.z}
            texto={e.general ? t("grupo.islaGeneral") : e.nombre}
            activa={e.trabajando || e.espera}
          />
        );
      })}
      {/* stepping stones from the entrance to the garden */}
      {[-18.6, -17.2, -15.8, -14.4, -13.0, -11.6, -10.2].map((x, i) => (
        <mesh
          key={x}
          position={[x, 0.03, 13.6 - Math.max(0, i - 3) * 0.6]}
          geometry={PIEDRA_G}
          material={PIEDRA_M}
          receiveShadow
        />
      ))}
      <Puerta p={[-21.8, 0, 13.6]} ry={0} />
    </group>
  );
}
