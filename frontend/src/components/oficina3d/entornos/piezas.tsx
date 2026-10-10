"use client";

/**
 * Fixed decoration drawn from data (Entorno.decoracion): the pieces of Agent
 * Office 3D (plants, sofas, bookshelves, lamps...) plus a few made here with
 * the same shared geometry and cached materials (trees, bushes, planters,
 * benches, lawn, coffee counter). Their collision boxes come from
 * huellaPieza() in tipos.ts, so paths go around them.
 */

import {
  Bookshelf,
  Box,
  CoffeeTable,
  MeetingTable,
  Painting,
  Plant,
  Rug,
  Sofa,
  StandingLamp,
  WallClock,
  Whiteboard,
} from "../escena/OfficeDecor";
import { cone, cyl, sphere, stdMat } from "../escena/resources";
import type { Pieza } from "./tipos";

type V3 = [number, number, number];

/** A lighter shade of a colour (inner part of a rug). */
function aclarar(hex: string, amt: number): string {
  const n = parseInt(hex.replace("#", ""), 16);
  const c = (v: number) => Math.max(0, Math.min(255, v + amt));
  const r = c((n >> 16) & 255);
  const g = c((n >> 8) & 255);
  const b = c(n & 255);
  return "#" + ((1 << 24) | (r << 16) | (g << 8) | b).toString(16).slice(1);
}

const HOJA = ["#4f8a4c", "#5f9a55", "#447a42"];
const TRONCO_M = stdMat("#7a5a3c", { roughness: 0.9 });

/** Tree: trunk and three rounded crowns. */
function Arbol({ p, escala = 1 }: { p: V3; escala?: number }) {
  return (
    <group position={p} scale={escala}>
      <mesh
        position={[0, 0.8, 0]}
        geometry={cyl(0.12, 0.17, 1.6, 8)}
        material={TRONCO_M}
        castShadow
      />
      {(
        [
          [0, 2.15, 0, 0.95],
          [0.45, 1.75, 0.2, 0.7],
          [-0.4, 1.8, -0.25, 0.72],
        ] as const
      ).map(([x, y, z, r], i) => (
        <mesh
          key={i}
          position={[x, y, z]}
          geometry={sphere(r, 10, 8)}
          material={stdMat(HOJA[i % HOJA.length], { roughness: 0.85 })}
          castShadow
        />
      ))}
    </group>
  );
}

/** Low bush: three spheres. */
function Arbusto({ p, escala = 1 }: { p: V3; escala?: number }) {
  return (
    <group position={p} scale={escala}>
      {(
        [
          [0, 0.4, 0, 0.5],
          [0.35, 0.3, 0.15, 0.36],
          [-0.32, 0.32, -0.12, 0.38],
        ] as const
      ).map(([x, y, z, r], i) => (
        <mesh
          key={i}
          position={[x, y, z]}
          geometry={sphere(r, 9, 7)}
          material={stdMat(HOJA[(i + 1) % HOJA.length], { roughness: 0.85 })}
          castShadow
        />
      ))}
    </group>
  );
}

/** Long planter with small plants. */
function Macetero({
  p,
  ry = 0,
  ancho = 2,
  fondo = 0.5,
}: {
  p: V3;
  ry?: number;
  ancho?: number;
  fondo?: number;
}) {
  const n = Math.max(2, Math.round(ancho / 0.55));
  return (
    <group position={p} rotation={[0, ry, 0]}>
      <Box p={[0, 0.25, 0]} s={[ancho, 0.5, fondo]} c="#9a7556" rough={0.8} />
      <Box
        p={[0, 0.51, 0]}
        s={[ancho - 0.1, 0.02, fondo - 0.1]}
        c="#5a4634"
        rough={1}
      />
      {Array.from({ length: n }, (_, i) => (
        <mesh
          key={i}
          position={[-ancho / 2 + (ancho / n) * (i + 0.5), 0.78, 0]}
          geometry={cone(0.2, 0.6 + (i % 3) * 0.12, 6)}
          material={stdMat(HOJA[i % HOJA.length], { roughness: 0.85 })}
          castShadow
        />
      ))}
    </group>
  );
}

/** Wooden bench. */
function Banca({ p, ry = 0 }: { p: V3; ry?: number }) {
  return (
    <group position={p} rotation={[0, ry, 0]}>
      {[-0.18, 0, 0.18].map((z) => (
        <Box
          key={z}
          p={[0, 0.45, z]}
          s={[1.7, 0.05, 0.14]}
          c="#b07a4a"
          rough={0.8}
        />
      ))}
      {[-0.7, 0.7].map((x) => (
        <Box
          key={x}
          p={[x, 0.22, 0]}
          s={[0.08, 0.44, 0.5]}
          c="#3a3f47"
          rough={0.5}
        />
      ))}
    </group>
  );
}

/** Lawn with a darker border. */
function Cesped({ p, ancho, fondo }: { p: V3; ancho: number; fondo: number }) {
  return (
    <group position={[p[0], 0.022, p[2]]}>
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[ancho, fondo]} />
        <meshStandardMaterial color="#8fb873" roughness={1} />
      </mesh>
      <mesh
        position={[0, 0.003, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
        receiveShadow
      >
        <planeGeometry args={[ancho - 0.5, fondo - 0.5]} />
        <meshStandardMaterial color="#a3c98a" roughness={1} />
      </mesh>
    </group>
  );
}

/** Coffee counter against a wall: cabinets, dark top, coffee machine, cups. */
function Cafeteria({ p, ry = 0 }: { p: V3; ry?: number }) {
  return (
    <group position={p} rotation={[0, ry, 0]}>
      <Box p={[0, 0.45, 0]} s={[6.4, 0.9, 0.7]} c="#e8e2d6" rough={0.6} />
      {[-2.4, -1.2, 0, 1.2, 2.4].map((x) => (
        <Box
          key={x}
          p={[x, 0.45, 0.36]}
          s={[0.02, 0.84, 0.02]}
          c="#b8b0a2"
          rough={0.6}
        />
      ))}
      <Box p={[0, 0.93, 0]} s={[6.5, 0.06, 0.76]} c="#3a3229" rough={0.4} />
      <Box
        p={[-2.2, 1.18, -0.1]}
        s={[0.5, 0.46, 0.4]}
        c="#2b2f36"
        rough={0.4}
      />
      <Box
        p={[-2.2, 1.1, 0.12]}
        s={[0.3, 0.06, 0.06]}
        c="#c8ccd2"
        rough={0.3}
      />
      {[0.4, 0.62, 0.84, 1.06].map((x) => (
        <mesh
          key={x}
          position={[x, 1.0, 0.05]}
          geometry={cyl(0.05, 0.045, 0.1, 12)}
          material={stdMat(x > 0.7 ? "#c2410c" : "#f4f1ea", { roughness: 0.5 })}
        />
      ))}
      {/* shelf with jars above */}
      <Box
        p={[1.6, 1.7, -0.25]}
        s={[2.4, 0.05, 0.25]}
        c="#b07a4a"
        rough={0.7}
      />
      {[0.7, 1.1, 1.5, 1.9, 2.3].map((x, i) => (
        <mesh
          key={x}
          position={[x, 1.84, -0.25]}
          geometry={cyl(0.07, 0.07, 0.22, 10)}
          material={stdMat(["#d9c7a0", "#8a5a3c", "#e8e2d6"][i % 3], {
            roughness: 0.6,
          })}
        />
      ))}
    </group>
  );
}

function UnaPieza({ p }: { p: Pieza }) {
  const pos: V3 = [p.x, 0, p.z];
  const ry = p.ry ?? 0;
  switch (p.tipo) {
    case "planta":
      return <Plant p={pos} scale={p.escala ?? 1.1} />;
    case "plantaGrande":
      return <Plant p={pos} scale={p.escala ?? 1.6} />;
    case "arbol":
      return <Arbol p={pos} escala={p.escala} />;
    case "arbusto":
      return <Arbusto p={pos} escala={p.escala} />;
    case "macetero":
      return <Macetero p={pos} ry={ry} ancho={p.ancho} fondo={p.fondo} />;
    case "lampara":
      return <StandingLamp p={pos} />;
    case "librero":
      return <Bookshelf p={pos} ry={ry} />;
    case "sofa":
      return <Sofa p={pos} ry={ry} c={p.color} />;
    case "mesaCafe":
      return <CoffeeTable p={pos} />;
    case "banca":
      return <Banca p={pos} ry={ry} />;
    case "mesaReuniones":
      return <MeetingTable p={pos} />;
    case "pizarra":
      return <Whiteboard p={pos} ry={ry} />;
    case "cafeteria":
      return <Cafeteria p={pos} ry={ry} />;
    case "cuadro":
      return <Painting p={[p.x, 1.7, p.z]} ry={ry} c={p.color ?? "#3a7bc8"} />;
    case "reloj":
      return <WallClock p={[p.x, 2.2, p.z]} ry={ry} />;
    case "alfombra":
      return (
        <Rug
          p={pos}
          w={p.ancho ?? 3}
          d={p.fondo ?? 2}
          c={p.color ?? "#8a6e5a"}
          accent={aclarar(p.color ?? "#8a6e5a", 26)}
        />
      );
    case "cesped":
      return <Cesped p={pos} ancho={p.ancho ?? 4} fondo={p.fondo ?? 4} />;
  }
}

/** All the data pieces of an environment. */
export function Piezas({ lista }: { lista: Pieza[] | undefined }) {
  if (!lista?.length) return null;
  return (
    <group>
      {lista.map((p, i) => (
        <UnaPieza key={`${p.tipo}-${i}`} p={p} />
      ))}
    </group>
  );
}
