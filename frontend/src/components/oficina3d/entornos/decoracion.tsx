"use client";

/**
 * Drawing of each environment (the fixed building and decoration), with the
 * pieces of Agent Office 3D (MIT): Original keeps OfficeDecor; Puente de mando
 * and Sala de control are built here. Also the parts every environment
 * shares: your desk (bigger, "Tú" sign, you seated when present) and the big
 * screen with the counters.
 */

import { useEffect, useMemo, useState } from "react";
import * as THREE from "three";
import { useOffice, type AgentView } from "../store";
import { t } from "../textos";
import OfficeDecor, {
  Box,
  CoffeeTable,
  Painting,
  Plant,
  Rug,
  Sofa,
  StandingLamp,
  WallClock,
} from "../escena/OfficeDecor";
import PixelPerson from "../escena/PixelPerson";
import type { CharSkin } from "../escena/roles";
import { CENTRO_PUENTE } from "./puente";
import {
  sitPoint,
  type ClaveEntorno,
  type Entorno,
  type Puesto,
} from "./tipos";

type V3 = [number, number, number];

/** Text on a canvas texture (no web fonts: works offline and on the phone). */
function useTextura(
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

// -- big screen ---------------------------------------------------------------------

function resumen(agents: Record<string, AgentView>) {
  const lista = Object.values(agents);
  const esperan = lista.filter((a) => a.permission || a.question);
  const libres = lista.filter(
    (a) => !a.permission && !a.question && a.destino !== "escritorio",
  ).length;
  return {
    espera: esperan.length,
    trabajando: lista.length - esperan.length - libres,
    libres,
    nombres: esperan.map((a) => a.folderName),
  };
}

/** Big wall screen: counters and the names of who waits for you (every 2 s). */
export function PantallaGrande({
  p,
  ry = 0,
  ancho = 8,
}: {
  p: V3;
  ry?: number;
  ancho?: number;
}) {
  const [r, setR] = useState(() => resumen(useOffice.getState().agents));
  useEffect(() => {
    const id = setInterval(() => {
      const n = resumen(useOffice.getState().agents);
      setR((prev) => (JSON.stringify(prev) === JSON.stringify(n) ? prev : n));
    }, 2000);
    return () => clearInterval(id);
  }, []);
  const W = 1024;
  const H = 400;
  const tex = useTextura(
    W,
    H,
    (ctx) => {
      ctx.fillStyle = "#f4f4f2";
      ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = "#111";
      ctx.fillRect(0, 0, W, 58);
      ctx.fillStyle = "#fff";
      ctx.font = "bold 34px system-ui, sans-serif";
      ctx.fillText(t("pantalla.titulo"), 28, 41);
      const cols: Array<[number, string, string]> = [
        [r.espera, t("barra.teEsperan"), r.espera > 0 ? "#c2410c" : "#111"],
        [r.trabajando, t("barra.trabajando"), "#111"],
        [r.libres, t("barra.libres"), "#555"],
      ];
      cols.forEach(([n, nombre, color], i) => {
        const x = 170 + i * 340;
        ctx.textAlign = "center";
        ctx.fillStyle = color;
        ctx.font = "bold 110px system-ui, sans-serif";
        ctx.fillText(String(n), x, 190);
        ctx.fillStyle = "#555";
        ctx.font = "600 30px system-ui, sans-serif";
        ctx.fillText(nombre.toUpperCase(), x, 236);
      });
      ctx.textAlign = "left";
      ctx.fillStyle = "#111";
      ctx.font = "600 30px system-ui, sans-serif";
      const nombres = r.nombres.length
        ? r.nombres.join(" · ")
        : t("pantalla.nadie");
      let texto = `${t("barra.teEsperan")}: ${nombres}`;
      while (ctx.measureText(texto).width > W - 56 && texto.length > 4)
        texto = texto.slice(0, -2);
      ctx.fillText(texto, 28, 330);
    },
    [r],
  );
  const alto = (ancho * H) / W;
  return (
    <group position={p} rotation={[0, ry, 0]}>
      <Box
        p={[0, 0, -0.05]}
        s={[ancho + 0.25, alto + 0.25, 0.08]}
        c="#1b1d22"
        rough={0.4}
      />
      <mesh>
        <planeGeometry args={[ancho, alto]} />
        <meshBasicMaterial map={tex} toneMapped={false} />
      </mesh>
    </group>
  );
}

// -- your desk ----------------------------------------------------------------------

/** You: different clothes from the agents (teal top, dark trousers). */
const PIEL_USUARIO: CharSkin = {
  label: "Tú",
  skin: "#e2b08c",
  hair: "#2b2118",
  hairStyle: "short",
  top: "#0f766e",
  bottom: "#1f2937",
  shoes: "#111111",
};

function Letrero({ texto }: { texto: string }) {
  const tex = useTextura(
    256,
    96,
    (ctx) => {
      ctx.fillStyle = "#111";
      ctx.fillRect(0, 0, 256, 96);
      ctx.fillStyle = "#fff";
      ctx.font = "bold 64px system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(texto, 128, 72);
    },
    [texto],
  );
  return (
    <>
      <mesh position={[0, 0, 0.006]}>
        <planeGeometry args={[0.7, 0.26]} />
        <meshBasicMaterial map={tex} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0, -0.006]} rotation={[0, Math.PI, 0]}>
        <planeGeometry args={[0.7, 0.26]} />
        <meshBasicMaterial map={tex} toneMapped={false} />
      </mesh>
    </>
  );
}

/**
 * Your desk: 2 × 0.9 m with two monitors and a "Tú" sign; you sit on the
 * chair while the presence says you are connected, the chair is empty otherwise.
 */
export function PuestoUsuario({
  puesto,
  presente,
}: {
  puesto: Puesto;
  presente: boolean;
}) {
  const s = sitPoint(puesto);
  const alto = 0.76;
  return (
    <>
      <group position={[puesto.x, 0, puesto.z]} rotation={[0, puesto.ry, 0]}>
        <Box p={[0, alto, 0]} s={[2.0, 0.07, 0.9]} c="#f2efe9" rough={0.4} />
        <Box
          p={[0, alto - 0.05, 0]}
          s={[2.04, 0.035, 0.94]}
          c="#1f2329"
          rough={0.5}
        />
        {[-0.9, 0.9].map((x) => (
          <Box
            key={x}
            p={[x, alto / 2, 0]}
            s={[0.06, alto, 0.78]}
            c="#3a3f47"
            rough={0.5}
          />
        ))}
        {/* two monitors on the far side, screens towards the chair */}
        {[-0.42, 0.42].map((x) => (
          <group key={x} position={[x, alto + 0.02, -0.25]}>
            <Box
              p={[0, 0.28, 0]}
              s={[0.74, 0.44, 0.04]}
              c="#15181d"
              rough={0.4}
            />
            <mesh position={[0, 0.28, 0.022]}>
              <planeGeometry args={[0.68, 0.38]} />
              <meshBasicMaterial color="#cfe0f4" toneMapped={false} />
            </mesh>
            <Box
              p={[0, 0.04, 0]}
              s={[0.06, 0.12, 0.06]}
              c="#2b2f36"
              rough={0.5}
            />
          </group>
        ))}
        <Box
          p={[0, alto + 0.04, 0.18]}
          s={[0.55, 0.02, 0.17]}
          c="#2b2f36"
          rough={0.5}
        />
        {/* sign on a post above the monitors */}
        <Box
          p={[0, alto + 0.75, -0.35]}
          s={[0.03, 0.5, 0.03]}
          c="#2b2f36"
          rough={0.5}
        />
        <group position={[0, alto + 1.05, -0.35]}>
          <Letrero texto={t("tuPuesto.letrero")} />
        </group>
        {/* chair */}
        <group position={[0, 0, 0.72]}>
          <Box
            p={[0, 0.47, 0]}
            s={[0.52, 0.07, 0.52]}
            c="#2a2f36"
            rough={0.6}
          />
          <Box
            p={[0, 0.78, 0.24]}
            s={[0.5, 0.56, 0.07]}
            c="#2a2f36"
            rough={0.6}
          />
          <Box
            p={[0, 0.23, 0]}
            s={[0.07, 0.46, 0.07]}
            c="#5a5f66"
            rough={0.4}
          />
        </group>
      </group>
      {presente && (
        <group position={[s.x, 0, s.z]} rotation={[0, puesto.ry, 0]}>
          <PixelPerson
            skin={PIEL_USUARIO}
            status="waiting"
            getState={() => ({ sit: true, moving: false, speed: 0 })}
          />
        </group>
      )}
    </>
  );
}

// -- shared pieces ------------------------------------------------------------------------

/** Entrance door on a wall (the same as in the Original office). */
function Puerta({ p, ry }: { p: V3; ry: number }) {
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

/** Lying ring sector (rug under the arc of desks). */
function SectorPiso({
  centro,
  r0,
  r1,
  color,
}: {
  centro: { x: number; z: number };
  r0: number;
  r1: number;
  color: string;
}) {
  const arco = (140 * Math.PI) / 180;
  return (
    <mesh
      position={[centro.x, 0.011, centro.z]}
      rotation={[-Math.PI / 2, 0, 0]}
      receiveShadow
    >
      {/* thetaStart: around +y of the ring plane, which lies on -z of the floor */}
      <ringGeometry args={[r0, r1, 64, 1, Math.PI / 2 - arco / 2, arco]} />
      <meshStandardMaterial color={color} roughness={0.95} />
    </mesh>
  );
}

// -- Puente de mando -----------------------------------------------------------------------

function DecoracionPuente() {
  return (
    <group>
      <SectorPiso centro={CENTRO_PUENTE} r0={5.6} r1={8.6} color="#cfc8b8" />
      <PantallaGrande p={[0, 2.25, -13.75]} ancho={9} />
      {/* break corner, top right */}
      <Rug
        p={[13.9, 0.012, -10.8]}
        w={5.2}
        d={4.0}
        c="#8a6e5a"
        accent="#a88c74"
      />
      <Sofa p={[12.6, 0, -12.6]} c="#4a5568" />
      <Sofa p={[16.5, 0, -9.6]} ry={-Math.PI / 2} c="#556070" />
      <CoffeeTable p={[13.6, 0, -10.4]} />
      <StandingLamp p={[16.9, 0, -13.0]} />
      {[
        [-16.8, -12.8],
        [-16.8, 12.8],
        [16.8, 12.8],
        [9.4, -12.9],
      ].map(([x, z]) => (
        <Plant key={`${x}${z}`} p={[x, 0, z]} scale={1.15} />
      ))}
      <Puerta p={[-17.8, 0, 11]} ry={0} />
      <Painting p={[-17.85, 1.7, -2]} ry={Math.PI / 2} c="#c85a3c" />
      <Painting p={[17.85, 1.7, 3]} ry={-Math.PI / 2} c="#3a7bc8" />
      <WallClock p={[-8, 2.2, -13.85]} />
    </group>
  );
}

// -- Sala de control con mostrador -------------------------------------------------------------

function DecoracionControl({ entorno }: { entorno: Entorno }) {
  const m = entorno.mostrador;
  return (
    <group>
      <PantallaGrande p={[0, 2.3, -15.75]} ancho={10} />
      {m && (
        <group>
          {/* long low counter (bar) */}
          <Box
            p={[(m.rect.x0 + m.rect.x1) / 2, 0.5, (m.rect.z0 + m.rect.z1) / 2]}
            s={[m.rect.x1 - m.rect.x0, 1.0, m.rect.z1 - m.rect.z0]}
            c="#e8e4dc"
            rough={0.5}
          />
          <Box
            p={[(m.rect.x0 + m.rect.x1) / 2, 1.03, (m.rect.z0 + m.rect.z1) / 2]}
            s={[
              m.rect.x1 - m.rect.x0 + 0.12,
              0.06,
              m.rect.z1 - m.rect.z0 + 0.14,
            ]}
            c="#20242b"
            rough={0.3}
          />
          {/* queue marks on the floor */}
          {Array.from({ length: 5 }, (_, i) => {
            const f = m.fila(i);
            return (
              <Box
                key={i}
                p={[f.x, 0.012, f.z]}
                s={[0.6, 0.005, 0.12]}
                c="#8a8f98"
                rough={0.9}
              />
            );
          })}
        </group>
      )}
      {/* break room at the back */}
      <Rug
        p={[-8.6, 0.012, 13.4]}
        w={8.0}
        d={4.4}
        c="#7a6a5a"
        accent="#9a8774"
      />
      <Sofa p={[-10.4, 0, 15.0]} ry={Math.PI} c="#4a5568" />
      <Sofa p={[-6.8, 0, 15.0]} ry={Math.PI} c="#556070" />
      <CoffeeTable p={[-8.6, 0, 12.4]} />
      {[
        [-14.8, 14.8],
        [-3.4, 15.0],
        [-14.8, -14.8],
        [14.8, -14.8],
      ].map(([x, z]) => (
        <Plant key={`${x}${z}`} p={[x, 0, z]} scale={1.15} />
      ))}
      <Puerta p={[15.8, 0, 13.5]} ry={Math.PI} />
      <Painting p={[-15.85, 1.7, 2]} ry={Math.PI / 2} c="#3a7bc8" />
      <WallClock p={[8, 2.3, -15.85]} />
    </group>
  );
}

/** Building and decoration of the active environment. */
export function DecoracionEntorno({
  clave,
  entorno,
}: {
  clave: ClaveEntorno;
  entorno: Entorno;
}) {
  if (clave === "puente") return <DecoracionPuente />;
  if (clave === "control") return <DecoracionControl entorno={entorno} />;
  return <OfficeDecor />;
}
