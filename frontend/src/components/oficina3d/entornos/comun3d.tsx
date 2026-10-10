"use client";

/** Pieces shared by the drawings of the environments: canvas text and the entrance door. */

import { useEffect, useMemo } from "react";
import * as THREE from "three";
import { Box } from "../escena/OfficeDecor";

export type V3 = [number, number, number];

/** Text on a canvas texture (no web fonts: works offline and on the phone). */
export function useTextura(
  ancho: number,
  alto: number,
  dibujar: (ctx: CanvasRenderingContext2D) => void,
  deps: unknown[],
) {
  const tex = useMemo(() => {
    const c = document.createElement("canvas");
    c.width = ancho;
    c.height = alto;
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    return t;
  }, [ancho, alto]);
  useEffect(() => {
    const ctx = (tex.image as HTMLCanvasElement).getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, ancho, alto);
    dibujar(ctx);
    tex.needsUpdate = true;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tex, ...deps]);
  useEffect(() => () => tex.dispose(), [tex]);
  return tex;
}

/** Entrance door on a wall (the same as in the Original office). */
export function Puerta({ p, ry }: { p: V3; ry: number }) {
  return (
    <group position={p} rotation={[0, ry, 0]}>
      <Box p={[0.02, 1.08, 0]} s={[0.08, 2.16, 1.5]} c="#2f343c" rough={0.6} />
      <Box p={[0.07, 1.04, 0]} s={[0.04, 2.04, 1.3]} c="#8a6a4a" rough={0.7} />
      <Box
        p={[0.11, 1.02, 0.45]}
        s={[0.04, 0.05, 0.16]}
        c="#d9d4c7"
        rough={0.3}
      />
      <Box p={[0.06, 0.005, 0]} s={[1.2, 0.01, 1.6]} c="#3a3f47" rough={0.95} />
    </group>
  );
}

/** Sign with a name on both faces. */
export function Cartel({
  texto,
  ancho,
  alto,
  fondo = "#ffffff",
  tinta = "#111111",
}: {
  texto: string;
  ancho: number;
  alto: number;
  fondo?: string;
  tinta?: string;
}) {
  const W = 512;
  const H = Math.round((512 * alto) / ancho);
  const tex = useTextura(
    W,
    H,
    (ctx) => {
      ctx.fillStyle = fondo;
      ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = tinta;
      let size = Math.round(H * 0.56);
      ctx.font = "bold " + size + "px system-ui, sans-serif";
      while (ctx.measureText(texto).width > W - 32 && size > 12) {
        size -= 2;
        ctx.font = "bold " + size + "px system-ui, sans-serif";
      }
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(texto, W / 2, H / 2 + 2);
    },
    [texto, fondo, tinta],
  );
  return (
    <group>
      <Box p={[0, 0, 0]} s={[ancho + 0.08, alto + 0.08, 0.04]} c="#2a2e35" />
      {[1, -1].map((lado) => (
        <mesh
          key={lado}
          position={[0, 0, lado * 0.023]}
          rotation={[0, lado > 0 ? 0 : Math.PI, 0]}
        >
          <planeGeometry args={[ancho, alto]} />
          <meshBasicMaterial map={tex} toneMapped={false} />
        </mesh>
      ))}
    </group>
  );
}
