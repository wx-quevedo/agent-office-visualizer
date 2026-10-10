import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import type { JSX } from "react";
import * as THREE from "three";
import { useLayout } from "../distribucion";
import { useSettings } from "../settings";
import { type AgentView, useOffice } from "../store";
import { t } from "../textos";
import { useDaylight } from "./daylight";
import { stdMat, UNIT_BOX } from "./resources";
import { visiblePoint } from "./visibility";

// ── Katta ko'p-xonali ofis (server/xojatxona/kutubxona/shisha) ──
// Hammasi qutı/silindr/konus — yengil. Xona: x[-23,23], z[-16,16].

type V3 = [number, number, number];
const M = (color: string, rough = 0.9) => (
  <meshStandardMaterial color={color} roughness={rough} />
);
// Metall/chrome (zamonaviy oyoq-ramkalar uchun)
const MM = (color: string, rough = 0.35, metal = 0.85) => (
  <meshStandardMaterial color={color} roughness={rough} metalness={metal} />
);
const WALL_H = 2.6;
const WALL_T = 0.24;
// ── Zamonaviy palitra ──
const WALL_C = "#e6e3dd"; // toza och kul-oq devor
const DOORW = "#3a3f47"; // matte charcoal eshik
const FRAME = "#2a2e35"; // qora ramka
const STEEL = "#8b929c"; // chrome/po'lat oyoq
const DESKTOP = "#f2efe9"; // oq stol usti
const ACCENT = "#4c8bf5"; // ko'k aksent

// Barcha qutilar — BITTA birlik geometriya (scale bilan) + KESHLANGAN material.
function Box({
  p,
  s,
  c,
  rough = 0.9,
}: {
  p: V3;
  s: V3;
  c: string;
  rough?: number;
}) {
  return (
    <mesh
      position={p}
      scale={s}
      geometry={UNIT_BOX}
      material={stdMat(c, { roughness: rough })}
      castShadow
      receiveShadow
    />
  );
}

function Floor({
  x0,
  x1,
  z0,
  z1,
  c,
}: {
  x0: number;
  x1: number;
  z0: number;
  z1: number;
  c: string;
}) {
  return (
    <mesh
      position={[(x0 + x1) / 2, 0.02, (z0 + z1) / 2]}
      rotation={[-Math.PI / 2, 0, 0]}
      receiveShadow
    >
      <planeGeometry args={[x1 - x0, z1 - z0]} />
      {M(c, 1)}
    </mesh>
  );
}

// Dekorativ gilam — poldan ozgina baland (z-fight yo'q), ikki qatlamli (chegara
// + ichki rang). Yassi, shu bois agentlar ustidan bemalol yuradi (collision yo'q).
function Rug({
  p,
  w,
  d,
  c = "#9c4a38",
  accent = "#c1735c",
}: {
  p: V3;
  w: number;
  d: number;
  c?: string;
  accent?: string;
}) {
  return (
    <group position={[p[0], 0.028, p[2]]}>
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[w, d]} />
        {M(c, 1)}
      </mesh>
      <mesh position={[0, 0.004, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[w - 0.45, d - 0.45]} />
        {M(accent, 1)}
      </mesh>
    </group>
  );
}

// Devor (X bo'ylab) — eshik + ramka + tavaqa.
// Eshik HAR DOIM markaziy yo'lak (tashqi) tomonga ochiladi: yo'nalish z'dan
// hisoblanadi — yuqori xonalar (z<0) +z ga, pastki xonalar (z>0) −z ga.
function WallX({
  x0,
  x1,
  z,
  door = 2,
}: {
  x0: number;
  x1: number;
  z: number;
  door?: number;
}) {
  const cx = (x0 + x1) / 2;
  const seg = Math.max(0.01, (x1 - x0 - door) / 2);
  const wc = useLayout((s) => s.wallColor) ?? WALL_C; // mavzu devor rangi
  const swing = z < 0 ? 1 : -1; // markazga (yo'lakka) ochilsin
  const W = door * 0.94; // tavaqa eni — teshik enига mos (deyarli to'ldiradi)
  const openH = WALL_H - 0.3; // teshik balandligi (pol → lintel)
  return (
    <group>
      <Box
        p={[cx - (door / 2 + seg / 2), WALL_H / 2, z]}
        s={[seg, WALL_H, WALL_T]}
        c={wc}
      />
      <Box
        p={[cx + (door / 2 + seg / 2), WALL_H / 2, z]}
        s={[seg, WALL_H, WALL_T]}
        c={wc}
      />
      <Box p={[cx, WALL_H - 0.15, z]} s={[door, 0.3, WALL_T]} c={wc} />
      <Box
        p={[cx - door / 2, openH / 2, z]}
        s={[0.1, openH, WALL_T + 0.06]}
        c={FRAME}
      />
      <Box
        p={[cx + door / 2, openH / 2, z]}
        s={[0.1, openH, WALL_T + 0.06]}
        c={FRAME}
      />
      {/* Tavaqa deyarli tekis ochiladi (devorga taqaladi) — yo'lakka chiqib
          turmaydi, agent undan "arvohdek" o'tmaydi. Yo'lak tomon 0.1 siljigan
          (devor bilan z-fight bo'lmasin). */}
      <group
        position={[cx - door / 2, openH / 2, z + 0.1 * swing]}
        rotation={[0, -2.8 * swing, 0]}
      >
        <mesh position={[W / 2, 0, 0]} castShadow>
          <boxGeometry args={[W, openH - 0.04, 0.05]} />
          <meshStandardMaterial color={DOORW} roughness={0.5} metalness={0.2} />
        </mesh>
        {/* shisha chizig'i */}
        <mesh position={[W / 2, 0.1, 0.02 * swing]}>
          <boxGeometry args={[door * 0.16, WALL_H - 0.9, 0.04]} />
          <meshStandardMaterial
            color="#bfe0ff"
            transparent
            opacity={0.35}
            roughness={0.1}
            metalness={0.1}
          />
        </mesh>
        {/* zamonaviy uzun tutqich (erkin chetда) */}
        <mesh position={[W - 0.12, -0.05, 0.05 * swing]}>
          <boxGeometry args={[0.04, 0.4, 0.04]} />
          {MM("#c8ccd2")}
        </mesh>
      </group>
    </group>
  );
}

// Bo'luvchi devor (X qat'iy, eshiksiz)
function DividerZ({ x, z0, z1 }: { x: number; z0: number; z1: number }) {
  const wc = useLayout((s) => s.wallColor) ?? WALL_C;
  return (
    <Box
      p={[x, WALL_H / 2, (z0 + z1) / 2]}
      s={[WALL_T, WALL_H, z1 - z0]}
      c={wc}
    />
  );
}

// Shisha devor (X bo'ylab, eshik teshigi bilan)
function GlassPanel({ p, s }: { p: V3; s: V3 }) {
  return (
    <group position={p}>
      <mesh>
        <boxGeometry args={s} />
        <meshStandardMaterial
          color="#bfe0ff"
          transparent
          opacity={0.16}
          roughness={0.08}
          metalness={0.1}
        />
      </mesh>
      <Box
        p={[0, s[1] / 2 - 0.03, 0]}
        s={[s[0] + 0.02, 0.06, s[2] + 0.02]}
        c={FRAME}
      />
    </group>
  );
}
function GlassWallX({
  x0,
  x1,
  z,
  door = 2,
}: {
  x0: number;
  x1: number;
  z: number;
  door?: number;
}) {
  const cx = (x0 + x1) / 2;
  const seg = Math.max(0.01, (x1 - x0 - door) / 2);
  return (
    <group>
      <GlassPanel
        p={[cx - (door / 2 + seg / 2), WALL_H / 2, z]}
        s={[seg, WALL_H, 0.08]}
      />
      <GlassPanel
        p={[cx + (door / 2 + seg / 2), WALL_H / 2, z]}
        s={[seg, WALL_H, 0.08]}
      />
      <Box
        p={[cx - door / 2, (WALL_H - 0.3) / 2, z]}
        s={[0.1, WALL_H - 0.3, 0.14]}
        c={FRAME}
      />
      <Box
        p={[cx + door / 2, (WALL_H - 0.3) / 2, z]}
        s={[0.1, WALL_H - 0.3, 0.14]}
        c={FRAME}
      />
    </group>
  );
}

// ── Jihozlar ──
export function Plant({ p, scale = 1 }: { p: V3; scale?: number }) {
  const leaves = useRef<THREE.Group>(null);
  const ph = useMemo(() => Math.random() * Math.PI * 2, []); // har o'simlik boshqa fazada
  // Yumshoq shamol tebranishi — barglar tuvak ustidan (y=0.4) chayqaladi.
  useFrame((state) => {
    const g = leaves.current;
    if (!g) return;
    // Kamaytirilgan harakat — barglar tik turadi (bir marta nolga qaytariladi).
    if (useSettings.getState().reducedMotion) {
      if (g.rotation.z !== 0 || g.rotation.x !== 0) {
        g.rotation.z = 0;
        g.rotation.x = 0;
      }
      return;
    }
    if (!visiblePoint(p[0], 0.6, p[2])) return; // ekrandan tashqari — tebranishni o'tkazamiz
    const t = state.clock.elapsedTime;
    g.rotation.z = Math.sin(t * 1.1 + ph) * 0.05;
    g.rotation.x = Math.cos(t * 0.85 + ph) * 0.04;
  });
  return (
    <group position={p} scale={scale}>
      <mesh position={[0, 0.2, 0]} castShadow>
        <cylinderGeometry args={[0.22, 0.17, 0.4, 10]} />
        {M("#b5643c")}
      </mesh>
      <group ref={leaves} position={[0, 0.4, 0]}>
        {[0, 1, 2, 3, 4].map((i) => {
          const a = (i / 5) * Math.PI * 2;
          return (
            <mesh
              key={i}
              position={[Math.cos(a) * 0.12, 0.35, Math.sin(a) * 0.12]}
              rotation={[Math.sin(a) * 0.5, 0, Math.cos(a) * -0.5]}
              castShadow
            >
              <coneGeometry args={[0.16, 0.8, 5]} />
              {M(i % 2 ? "#4a8a52" : "#3c7444")}
            </mesh>
          );
        })}
        <mesh position={[0, 0.6, 0]} castShadow>
          <coneGeometry args={[0.18, 0.7, 5]} />
          {M("#579a5e")}
        </mesh>
      </group>
    </group>
  );
}
export function Sofa({
  p,
  ry = 0,
  c = "#3d4756",
}: {
  p: V3;
  ry?: number;
  c?: string;
}) {
  return (
    <group position={p} rotation={[0, ry, 0]}>
      {/* pastki blok + yumshoq yostiqlar */}
      <Box p={[0, 0.22, 0]} s={[2.2, 0.24, 0.9]} c={c} rough={0.85} />
      <Box p={[-0.55, 0.4, 0.05]} s={[1.0, 0.16, 0.78]} c={c} rough={0.7} />
      <Box p={[0.55, 0.4, 0.05]} s={[1.0, 0.16, 0.78]} c={c} rough={0.7} />
      <Box p={[0, 0.6, -0.38]} s={[2.2, 0.5, 0.18]} c={c} rough={0.7} />
      <Box p={[-1.05, 0.42, 0]} s={[0.16, 0.44, 0.9]} c={c} rough={0.7} />
      <Box p={[1.05, 0.42, 0]} s={[0.16, 0.44, 0.9]} c={c} rough={0.7} />
      {/* nozik chrome oyoqlar */}
      {[
        [-0.95, -0.35],
        [0.95, -0.35],
        [-0.95, 0.35],
        [0.95, 0.35],
      ].map(([x, z], i) => (
        <mesh key={i} position={[x, 0.06, z]}>
          <cylinderGeometry args={[0.03, 0.03, 0.12, 8]} />
          {MM(STEEL)}
        </mesh>
      ))}
    </group>
  );
}
export function CoffeeTable({ p }: { p: V3 }) {
  return (
    <group position={p}>
      {/* shisha usti + chrome ramka */}
      <mesh position={[0, 0.38, 0]}>
        <boxGeometry args={[1.1, 0.04, 0.6]} />
        <meshStandardMaterial
          color="#cfeaff"
          transparent
          opacity={0.4}
          roughness={0.05}
          metalness={0.2}
        />
      </mesh>
      <Box p={[0, 0.2, 0]} s={[0.95, 0.03, 0.45]} c="#e8e6e0" />
      {[
        [-0.48, -0.23],
        [0.48, -0.23],
        [-0.48, 0.23],
        [0.48, 0.23],
      ].map(([x, z], i) => (
        <mesh key={i} position={[x, 0.19, z]}>
          <cylinderGeometry args={[0.025, 0.025, 0.38, 8]} />
          {MM(STEEL)}
        </mesh>
      ))}
    </group>
  );
}
export function MeetingTable({ p, r = 1.1 }: { p: V3; r?: number }) {
  return (
    <group position={p}>
      {/* oq yaltiroq usti + chrome ustun-oyoq */}
      <mesh position={[0, 0.72, 0]} castShadow>
        <cylinderGeometry args={[r, r, 0.07, 28]} />
        <meshStandardMaterial color={DESKTOP} roughness={0.3} metalness={0.1} />
      </mesh>
      <mesh position={[0, 0.68, 0]}>
        <cylinderGeometry args={[r - 0.04, r - 0.04, 0.02, 28]} />
        {M(ACCENT, 0.5)}
      </mesh>
      <mesh position={[0, 0.35, 0]} castShadow>
        <cylinderGeometry args={[0.09, 0.09, 0.68, 12]} />
        {MM("#6a7078")}
      </mesh>
      <mesh position={[0, 0.03, 0]}>
        <cylinderGeometry args={[0.42, 0.42, 0.05, 20]} />
        {MM("#5a6068")}
      </mesh>
      {[0, 1, 2, 3, 4, 5].map((i) => {
        const a = (i / 6) * Math.PI * 2;
        // Stul stol markaziga QARASHI kerak (ModChair +z ga qaraydi) → -a - π/2.
        return (
          <group
            key={i}
            position={[Math.cos(a) * (r + 0.4), 0, Math.sin(a) * (r + 0.4)]}
            rotation={[0, -a - Math.PI / 2, 0]}
          >
            <ModChair />
          </group>
        );
      })}
    </group>
  );
}
// Zamonaviy ergonomik stul (oq qobiq + chrome oyoq)
function ModChair({ c = "#2c313a" }: { c?: string }) {
  return (
    <group>
      <Box p={[0, 0.44, 0]} s={[0.44, 0.07, 0.44]} c={c} rough={0.6} />
      <Box p={[0, 0.7, -0.18]} s={[0.44, 0.46, 0.06]} c={c} rough={0.6} />
      <mesh position={[0, 0.22, 0]}>
        <cylinderGeometry args={[0.03, 0.03, 0.4, 8]} />
        {MM(STEEL)}
      </mesh>
      {[0, 1, 2, 3, 4].map((i) => {
        const a = (i / 5) * Math.PI * 2;
        return (
          <mesh key={i} position={[Math.cos(a) * 0.2, 0.03, Math.sin(a) * 0.2]}>
            <boxGeometry args={[0.2, 0.04, 0.05]} />
            {MM("#4a4f57")}
          </mesh>
        );
      })}
    </group>
  );
}
export function Bookshelf({ p, ry = 0 }: { p: V3; ry?: number }) {
  const books = useMemo(() => {
    const cols = [
      "#c0392b",
      "#2980b9",
      "#27ae60",
      "#e67e22",
      "#8e44ad",
      "#16a085",
      "#c99a2e",
    ];
    const rows: JSX.Element[] = [];
    for (let shelf = 0; shelf < 4; shelf++) {
      let x = -0.5;
      let k = 0;
      while (x < 0.5) {
        const w = 0.05 + ((shelf * 7 + k) % 4) * 0.02;
        const h = 0.28 + ((shelf * 3 + k) % 3) * 0.05;
        rows.push(
          <Box
            key={`${shelf}-${k}`}
            p={[x + w / 2, 0.42 + shelf * 0.55 + h / 2, 0.02]}
            s={[w, h, 0.22]}
            c={cols[(shelf * 5 + k) % cols.length]}
            rough={0.7}
          />,
        );
        x += w + 0.012;
        k++;
      }
    }
    return rows;
  }, []);
  return (
    <group position={p} rotation={[0, ry, 0]}>
      <Box p={[0, 1.3, 0]} s={[1.2, 2.6, 0.35]} c="#dfdcd4" rough={0.6} />
      <Box p={[0, 1.3, 0.02]} s={[1.1, 2.5, 0.3]} c="#33373e" />
      {/* javon taxtalari */}
      {[0.4, 0.95, 1.5, 2.05].map((y) => (
        <Box key={y} p={[0, y, 0.03]} s={[1.1, 0.03, 0.28]} c="#c8c5bd" />
      ))}
      {books}
    </group>
  );
}
function Kitchen({ p, ry = 0 }: { p: V3; ry?: number }) {
  return (
    <group position={p} rotation={[0, ry, 0]}>
      {/* matte kabinetlar + qora granit usti */}
      <Box p={[0, 0.45, 0]} s={[5, 0.9, 0.7]} c="#e8e6e0" rough={0.5} />
      {[-2, -1, 0, 1, 2].map((x) => (
        <Box key={x} p={[x, 0.45, 0.36]} s={[0.02, 0.86, 0.02]} c="#b8b5ad" />
      ))}
      <Box p={[0, 0.92, 0]} s={[5.05, 0.07, 0.75]} c="#20242b" rough={0.3} />
      <mesh position={[-1.6, 0.94, 0]}>
        <boxGeometry args={[0.7, 0.03, 0.5]} />
        {MM("#7a8290", 0.2)}
      </mesh>
      {/* jomkalik kran */}
      <mesh position={[-1.6, 1.1, -0.1]}>
        <cylinderGeometry args={[0.02, 0.02, 0.3, 8]} />
        {MM("#c8ccd2")}
      </mesh>
      {/* baland shkaf + aksent */}
      <Box p={[2.9, 0.95, 0]} s={[0.75, 1.9, 0.7]} c="#eceae4" rough={0.5} />
      <Box p={[2.9, 0.95, 0.36]} s={[0.5, 0.02, 0.02]} c={ACCENT} />
      {/* NEON yozuv — "retro diner" districtining imzosi. Faqat emissive
          (pointLight EMAS) → perf narxi nol, lekin kechаsi kuchli porlaydi. */}
      <mesh position={[0, 1.78, -0.3]}>
        <boxGeometry args={[2.1, 0.54, 0.06]} />
        <meshStandardMaterial color="#191216" roughness={0.5} />
      </mesh>
      <mesh position={[0, 1.78, -0.26]}>
        <boxGeometry args={[1.78, 0.24, 0.03]} />
        <meshStandardMaterial
          color="#ff4d8d"
          emissive="#ff4d8d"
          emissiveIntensity={2.8}
          toneMapped={false}
        />
      </mesh>
    </group>
  );
}
// Boardroom prezentatsiya ekrani (avval oddiy oq doska edi) — "majlis"
// districtining imzosi. Emissive displey: qorong'i shifer-ko'k polda porlaydi.
function Whiteboard({ p, ry = 0 }: { p: V3; ry?: number }) {
  return (
    <group position={p} rotation={[0, ry, 0]}>
      <Box p={[0, 1.4, 0]} s={[1.95, 1.12, 0.07]} c="#161a20" rough={0.4} />
      {/* Endi JONLI statistika taxtasi (kamerага qaraydi — asosiy displey). */}
      <group position={[0, 1.4, 0.05]}>
        <StatsBoard size={[1.74, 0.92]} />
      </group>
    </group>
  );
}
export function EmptyDesk({ p, ry = 0 }: { p: V3; ry?: number }) {
  return (
    <group position={p} rotation={[0, ry, 0]}>
      {/* oq usti + qora aksent qirra */}
      <Box p={[0, 0.72, 0]} s={[1.4, 0.06, 0.75]} c={DESKTOP} rough={0.4} />
      <Box p={[0, 0.68, 0]} s={[1.42, 0.03, 0.77]} c="#2a2e35" />
      {/* nozik chrome A-oyoqlar */}
      {[-0.6, 0.6].map((x) => (
        <mesh key={x} position={[x, 0.34, 0]}>
          <boxGeometry args={[0.05, 0.68, 0.64]} />
          {MM("#4a4f57", 0.4, 0.6)}
        </mesh>
      ))}
      {/* ingichka slim monitor + stend */}
      <Box p={[0, 1.04, -0.22]} s={[0.66, 0.4, 0.03]} c="#12151a" rough={0.3} />
      <mesh position={[0, 1.04, -0.2]}>
        <planeGeometry args={[0.6, 0.34]} />
        <meshBasicMaterial color="#1c3350" />
      </mesh>
      <Box p={[0, 0.82, -0.22]} s={[0.05, 0.2, 0.05]} c="#3a3f47" />
      <Box p={[0, 0.76, -0.22]} s={[0.24, 0.02, 0.14]} c="#2a2e35" />
      {/* klaviatura */}
      <Box p={[0, 0.76, 0.12]} s={[0.44, 0.02, 0.15]} c="#e2e2e0" />
      {/* stul stolga (monitorga, -z) qarasin */}
      <ModChairAt p={[0, 0, 0.58]} ry={Math.PI} />
    </group>
  );
}
function ModChairAt({ p, ry = 0 }: { p: V3; ry?: number }) {
  return (
    <group position={p} rotation={[0, ry, 0]}>
      <ModChair />
    </group>
  );
}
export function Painting({ p, ry = 0, c }: { p: V3; ry?: number; c: string }) {
  return (
    <group position={p} rotation={[0, ry, 0]}>
      <Box p={[0, 0, 0]} s={[1.1, 0.8, 0.06]} c="#3a2e22" rough={0.6} />
      <mesh position={[0, 0, 0.04]}>
        <planeGeometry args={[0.9, 0.6]} />
        <meshBasicMaterial color={c} />
      </mesh>
    </group>
  );
}
// Devor soati — yuzi +z (Painting kabi), ry bilan devorга buriladi. Strelkalar
// HAQIQIY joriy vaqtни ko'rsatadi va jonli yuradi (useFrame — React re-render
// yo'q). Avval qotib turardi (statik 10:10 — "soxta") — endi tirik.
export function WallClock({ p, ry = 0 }: { p: V3; ry?: number }) {
  const hourRef = useRef<THREE.Group>(null);
  const minRef = useRef<THREE.Group>(null);
  useFrame(() => {
    const d = new Date();
    const min = d.getMinutes() + d.getSeconds() / 60;
    const hr = (d.getHours() % 12) + min / 60;
    if (hourRef.current) hourRef.current.rotation.z = -(hr / 12) * Math.PI * 2; // soat oqimida
    if (minRef.current) minRef.current.rotation.z = -(min / 60) * Math.PI * 2;
  });
  return (
    <group position={p} rotation={[0, ry, 0]}>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.3, 0.3, 0.06, 22]} />
        {M("#2a2e35", 0.6)}
      </mesh>
      <mesh position={[0, 0, 0.035]} rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.26, 0.26, 0.01, 22]} />
        {M("#f4f1ea", 0.5)}
      </mesh>
      {/* Strelkalar markazdan +y (12 tomon) chiqadi; group z bo'ylab buriladi. */}
      <group ref={hourRef}>
        <Box p={[0, 0.07, 0.05]} s={[0.028, 0.14, 0.012]} c="#23262b" />
      </group>
      <group ref={minRef}>
        <Box p={[0, 0.1, 0.052]} s={[0.02, 0.2, 0.012]} c="#3a3f47" />
      </group>
      <mesh position={[0, 0, 0.055]}>
        <cylinderGeometry args={[0.022, 0.022, 0.02, 8]} />
        {M("#c0392b", 0.4)}
      </mesh>
    </group>
  );
}
// ── Jonli statistika taxtasi (TV ekrani) ────────────────────
// Ofis TV'si endi JONLI raqamlar ko'rsatadi: faol/jami agentlar, jami xarajat,
// ogohlantirishlar soni. WebGL matni CSP tufayli drei <Text> orqali emas — 2D
// canvas → CanvasTexture (Monitor ekrani bilan bir xil usul). Hammasi
// O'LCHANGAN holatdan (store + buildInsights); hech narsa to'qib chiqarilmaydi.
// Taxta soniqlari — store SNAPSHOT'idan (obuna'siz), buildInsights bilan.
function computeBoardStats() {
  const s = useOffice.getState();
  const list = s.order.map((id) => s.agents[id]).filter(Boolean) as AgentView[];
  let espera = 0,
    trabajando = 0,
    inactivos = 0;
  for (const a of list) {
    if (a.permission || a.question) espera++;
    else if (a.status === "idle") inactivos++;
    else trabajando++;
  }
  return { espera, trabajando, inactivos };
}
function StatsBoard({
  size = [1.85, 1.0] as [number, number],
}: {
  size?: [number, number];
}) {
  // PERF: store-churn'ga OBUNA BO'LMAYMIZ (har token yangilanishда emas) — taxta
  // 2s'da bir yangilanadi (soniqlar sub-soniya yangilikni talab qilmaydi), shu
  // bilan doim-mount TV+doska buildInsights'ni ortiqcha chaqirmaydi. Faqat qiymat
  // O'ZGARSA setState (aks holda qayta chizmaymiz).
  const [stats, setStats] = useState(computeBoardStats);
  useEffect(() => {
    const tick = () =>
      setStats((prev) => {
        const n = computeBoardStats();
        return prev.espera === n.espera &&
          prev.trabajando === n.trabajando &&
          prev.inactivos === n.inactivos
          ? prev
          : n;
      });
    tick();
    const t = setInterval(tick, 2000);
    return () => clearInterval(t);
  }, []);

  const tex = useMemo(() => {
    const c = document.createElement("canvas");
    c.width = 512;
    c.height = 288;
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    return t;
  }, []);
  useEffect(() => {
    const c = tex.image as HTMLCanvasElement;
    const ctx = c.getContext("2d");
    if (!ctx) return;
    const W = 512,
      H = 288;
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = "#0d1016";
    ctx.fillRect(0, 0, W, H);
    // Sarlavha paneli
    ctx.fillStyle = "#3987e5";
    ctx.fillRect(0, 0, W, 44);
    ctx.fillStyle = "#f2f5fa";
    ctx.font = "bold 26px system-ui, sans-serif";
    ctx.fillText(t("pantalla.titulo"), 18, 32);
    // "jonli" nuqta
    ctx.fillStyle = "#0d1016";
    ctx.beginPath();
    ctx.arc(W - 30, 22, 7, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#30d158";
    ctx.beginPath();
    ctx.arc(W - 30, 22, 4, 0, Math.PI * 2);
    ctx.fill();
    // 3 ta ustun: agentlar / xarajat / ogohlantirish
    const tile = (x: number, val: string, label: string, color: string) => {
      ctx.textAlign = "center";
      ctx.fillStyle = color;
      ctx.font = "bold 54px system-ui, sans-serif";
      ctx.fillText(val, x, 168);
      ctx.fillStyle = "#8b929c";
      ctx.font = "600 18px system-ui, sans-serif";
      ctx.fillText(label, x, 210);
      ctx.textAlign = "left";
    };
    tile(
      96,
      `${stats.espera}`,
      t("barra.teEsperan").toUpperCase(),
      stats.espera > 0 ? "#ff9f0a" : "#f2f5fa",
    );
    tile(
      256,
      `${stats.trabajando}`,
      t("barra.trabajando").toUpperCase(),
      "#30d158",
    );
    tile(
      416,
      `${stats.inactivos}`,
      t("barra.inactivos").toUpperCase(),
      "#8b929c",
    );
    // pastki chiziq
    ctx.fillStyle = "rgba(255,255,255,0.08)";
    ctx.fillRect(18, 244, W - 36, 2);
    tex.needsUpdate = true;
  }, [tex, stats]);
  useEffect(() => () => tex.dispose(), [tex]);

  return (
    <mesh>
      <planeGeometry args={size} />
      <meshBasicMaterial map={tex} toneMapped={false} />
    </mesh>
  );
}

export function TV({ p, ry = 0 }: { p: V3; ry?: number }) {
  return (
    <group position={p} rotation={[0, ry, 0]}>
      <Box p={[0, 0, 0]} s={[2, 1.15, 0.08]} c="#15181d" rough={0.4} />
      <group position={[0, 0, 0.05]}>
        <StatsBoard />
      </group>
    </group>
  );
}
export function StandingLamp({ p }: { p: V3 }) {
  const lampsOn = useDaylight((s) => s.params.lamps);
  return (
    <group position={p}>
      <mesh position={[0, 0.05, 0]}>
        <cylinderGeometry args={[0.2, 0.22, 0.08, 12]} />
        {M("#3a3f48")}
      </mesh>
      <mesh position={[0, 0.9, 0]}>
        <cylinderGeometry args={[0.025, 0.025, 1.7, 8]} />
        {M("#6a6f78", 0.4)}
      </mesh>
      <mesh position={[0, 1.75, 0]}>
        <coneGeometry args={[0.28, 0.35, 12, 1, true]} />
        <meshStandardMaterial
          color="#f0e6c8"
          emissive="#fff0c0"
          emissiveIntensity={lampsOn ? 1.7 : 0.35}
          side={2}
        />
      </mesh>
      {/* Shade ostini yopadigan yorug' disk — ilgari konus OCHIQ edi, ichi
          ko'rinib "tugallanmagandek" turardi. Endi u yerdan nur chiqadi. */}
      <mesh position={[0, 1.6, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <circleGeometry args={[0.25, 16]} />
        <meshStandardMaterial
          color="#fff4d0"
          emissive="#ffe6a0"
          emissiveIntensity={lampsOn ? 2.2 : 0.6}
          side={2}
          toneMapped={false}
        />
      </mesh>
      {/* Tunda yumshoq porlash + haqiqiy nur */}
      {lampsOn && (
        <>
          <mesh position={[0, 1.7, 0]}>
            <sphereGeometry args={[0.36, 10, 8]} />
            <meshBasicMaterial
              color="#ffe9b0"
              transparent
              opacity={0.22}
              depthWrite={false}
            />
          </mesh>
          <pointLight
            position={[0, 1.7, 0]}
            intensity={7}
            distance={5.5}
            decay={2}
            color="#ffd98a"
          />
        </>
      )}
    </group>
  );
}

// Shift chirog'i (pendant) — ochiq ofis ustida osilgan. Bulb KUNDUZ ham porlaydi
// (ilgari to'q konus + o'chiq bulb → "qora uzunchoq" ko'rinardi). Shade iliq och
// rangда, bulb har doim yorug' (toneMapped=false → haqiqatan porlaydi).
export function PendantLight({ p }: { p: V3 }) {
  const lampsOn = useDaylight((s) => s.params.lamps);
  return (
    <group position={p}>
      <mesh position={[0, 2.35, 0]}>
        <cylinderGeometry args={[0.012, 0.012, 0.9, 6]} />
        {M("#2a2e35")}
      </mesh>
      {/* Shade — iliq och (lampa abajurıdek), to'q emas */}
      <mesh position={[0, 1.85, 0]}>
        <coneGeometry args={[0.24, 0.22, 16, 1, true]} />
        <meshStandardMaterial color="#e6dcc8" roughness={0.6} side={2} />
      </mesh>
      {/* Bulb — kunduz ham yonib turadi */}
      <mesh position={[0, 1.78, 0]}>
        <sphereGeometry args={[0.095, 10, 10]} />
        <meshStandardMaterial
          color="#fff4d6"
          emissive="#ffdf9e"
          emissiveIntensity={lampsOn ? 2.6 : 1.5}
          toneMapped={false}
        />
      </mesh>
      {/* Yumshoq halo — kunduz nozik, kechаsi kuchli */}
      <mesh position={[0, 1.78, 0]}>
        <sphereGeometry args={[0.3, 10, 8]} />
        <meshBasicMaterial
          color="#ffe9b0"
          transparent
          opacity={lampsOn ? 0.22 : 0.12}
          depthWrite={false}
        />
      </mesh>
      {lampsOn && (
        <>
          <pointLight
            position={[0, 1.78, 0]}
            intensity={5}
            distance={5}
            decay={2}
            color="#ffd98a"
          />
        </>
      )}
    </group>
  );
}

// Shift yoritgich paneli (recessed office light) — pol lampasi o'rniga. Ofisdek
// tepadan yoritadi: yassi porlab turgan panel + qora ramka, WH=3.4 shift ostida.
// Emissive TEKIN (yorug' hisoblanmaydi); haqiqiy pointLight faqat kechаsi.
export function CeilingPanel({
  p,
  w = 2.6,
  d = 1.3,
}: {
  p: V3;
  w?: number;
  d?: number;
}) {
  const lampsOn = useDaylight((s) => s.params.lamps);
  // Fixtura FAQAT ichkaridan (FPV) ko'rinadi — shift kabi tepadan (iso) yashirin
  // (ilgari oq panel bo'shliqда "osilib" ko'rinardi). Iso'da faqat pol yorug'ligi
  // (pointLight, kechаsi) qoladi — bu aynan recessed downlight ko'rinishi.
  const fpv = useOffice((s) => s.cameraMode === "fpv");
  return (
    <group position={p}>
      {fpv && (
        <>
          {/* Ramka */}
          <Box
            p={[0, 3.3, 0]}
            s={[w + 0.14, 0.05, d + 0.14]}
            c="#2a2e35"
            rough={0.4}
          />
          {/* Porlab turgan panel */}
          <mesh position={[0, 3.34, 0]}>
            <boxGeometry args={[w, 0.05, d]} />
            <meshStandardMaterial
              color="#fff8ec"
              emissive="#fff2d4"
              emissiveIntensity={lampsOn ? 2.3 : 0.85}
              toneMapped={false}
            />
          </mesh>
        </>
      )}
      {lampsOn && (
        <pointLight
          position={[0, 2.9, 0]}
          intensity={6}
          distance={7.5}
          decay={2}
          color="#ffe9c0"
        />
      )}
    </group>
  );
}

// ── YANGI: server rack ──
function ServerRack({ p, ry = 0 }: { p: V3; ry?: number }) {
  const lights = useMemo(() => {
    const out: JSX.Element[] = [];
    for (let i = 0; i < 8; i++) {
      out.push(
        <Box
          key={`s${i}`}
          p={[0, 0.35 + i * 0.2, 0.42]}
          s={[0.62, 0.14, 0.02]}
          c="#2a2e35"
        />,
      );
      const col = ["#33d158", "#5aa0e0", "#33d158", "#ffd60a"][i % 4];
      // LED — kattaroq + ANCHA yorqinroq. Qora "g'or" polida portlab turadi.
      // toneMapped=false → ACES tone-mapping'ni chetlab o'tadi, haqiqatan porlaydi.
      out.push(
        <mesh key={`l${i}`} position={[0.24, 0.35 + i * 0.2, 0.44]}>
          <boxGeometry args={[0.06, 0.05, 0.02]} />
          <meshStandardMaterial
            color={col}
            emissive={col}
            emissiveIntensity={3}
            toneMapped={false}
          />
        </mesh>,
      );
    }
    return out;
  }, []);
  return (
    <group position={p} rotation={[0, ry, 0]}>
      <Box p={[0, 1.1, 0]} s={[0.8, 2.2, 0.9]} c="#15181d" rough={0.5} />
      {/* Vertikal porlash chizig'i — rack'ni qorong'i polda ajratib turadi (1 mesh) */}
      <mesh position={[-0.3, 1.1, 0.46]}>
        <boxGeometry args={[0.03, 1.9, 0.02]} />
        <meshStandardMaterial
          color="#4fa8ff"
          emissive="#4fa8ff"
          emissiveIntensity={2.2}
          toneMapped={false}
        />
      </mesh>
      {lights}
    </group>
  );
}
function CoolingUnit({ p, ry = 0 }: { p: V3; ry?: number }) {
  return (
    <group position={p} rotation={[0, ry, 0]}>
      <Box p={[0, 0.8, 0]} s={[1.0, 1.6, 0.5]} c="#c4c8cc" />
      {[0.5, 0.9, 1.3].map((y) => (
        <Box key={y} p={[0, y, 0.26]} s={[0.8, 0.1, 0.02]} c="#8a8f98" />
      ))}
    </group>
  );
}

// ── YANGI: xojatxona ──
function Toilet({ p, ry = 0 }: { p: V3; ry?: number }) {
  return (
    <group position={p} rotation={[0, ry, 0]}>
      <mesh position={[0, 0.25, 0]} castShadow>
        <cylinderGeometry args={[0.22, 0.17, 0.42, 12]} />
        {M("#eef2f4", 0.4)}
      </mesh>
      <Box p={[0, 0.38, -0.28]} s={[0.42, 0.55, 0.16]} c="#eef2f4" />
      <mesh position={[0, 0.48, 0.02]}>
        <cylinderGeometry args={[0.24, 0.24, 0.05, 12]} />
        {M("#e2e6e8", 0.4)}
      </mesh>
    </group>
  );
}
function Sink({ p, ry = 0 }: { p: V3; ry?: number }) {
  return (
    <group position={p} rotation={[0, ry, 0]}>
      <Box p={[0, 0.42, 0]} s={[0.5, 0.16, 0.4]} c="#eef2f4" />
      <Box p={[0, 0.2, 0]} s={[0.1, 0.4, 0.1]} c="#dfe3e8" />
      <Box p={[0, 1.25, -0.16]} s={[0.5, 0.6, 0.03]} c="#a8c8d8" rough={0.2} />
    </group>
  );
}
function Stall({ p }: { p: V3 }) {
  return (
    <group position={p}>
      <Toilet p={[0, 0, 0]} />
      <Box p={[-0.75, 0.9, -0.2]} s={[0.06, 1.8, 1.6]} c="#c8d0d4" />
      <Box p={[0.75, 0.9, -0.2]} s={[0.06, 1.8, 1.6]} c="#c8d0d4" />
      <Box p={[0, 0.9, -1.0]} s={[1.5, 1.8, 0.06]} c="#c8d0d4" />
    </group>
  );
}

// ── YANGI: kutubxona o'qish stoli ──
function ReadingTable({ p }: { p: V3 }) {
  return (
    <group position={p}>
      <Box p={[0, 0.72, 0]} s={[2.2, 0.06, 1.0]} c={DESKTOP} rough={0.4} />
      <Box p={[0, 0.68, 0]} s={[2.22, 0.03, 1.02]} c="#2a2e35" />
      {[
        [-0.95, -0.4],
        [0.95, -0.4],
        [-0.95, 0.4],
        [0.95, 0.4],
      ].map(([x, z], i) => (
        <mesh key={i} position={[x, 0.35, z]}>
          <cylinderGeometry args={[0.035, 0.035, 0.7, 10]} />
          {MM(STEEL)}
        </mesh>
      ))}
      {[
        [-0.6, -0.78],
        [0.6, -0.78],
        [-0.6, 0.78],
        [0.6, 0.78],
      ].map(([x, z], i) => (
        <group
          key={i}
          position={[x, 0, z]}
          rotation={[0, z > 0 ? Math.PI : 0, 0]}
        >
          <ModChair />
        </group>
      ))}
    </group>
  );
}

// District tungi nuri — FAQAT kechаsi mavjud bo'ladi (kunduzда `null` qaytaradi,
// ya'ni pointLight umuman yaratilmaydi → kunduzги perf narxi NOL). Tunda jami
// 9 pointLight (2 torsher + 4 pendant + 3 district) — xavfsiz chegara.
function DistrictLight({
  p,
  c,
  intensity = 9,
  distance = 14,
}: {
  p: V3;
  c: string;
  intensity?: number;
  distance?: number;
}) {
  const lampsOn = useDaylight((s) => s.params.lamps);
  if (!lampsOn) return null;
  return (
    <pointLight
      position={p}
      color={c}
      intensity={intensity}
      distance={distance}
      decay={2}
    />
  );
}

// ── District palitrasi (0.1.5) ───────────────────────────────
// Muammo: eski pol ranglari hammasi och pastel edi — iso kameradan bir xil
// bej/kul bo'lib ko'rinardi ("generic quti" hissi). Yechim: har xonaga
// XARAKTERLI, kontrastli, lekin uyg'un pol. Pol rangi BEPUL (nur emas) va
// KUNDUZи ham ishlaydi — shu bois district identikasining asosi shu.
const DISTRICT = {
  server: "#252a31", // ma'lumot g'ori — deyarli qora (yagona dramatik langar)
  kitchen: "#7fbcae", // retro diner — moviy-yashil
  meeting: "#41536b", // boardroom — jiddiy shifer-ko'k
  bathroom: "#c3dde3", // toza kafel — och akva
  library: "#6d4c30", // sobor — to'q yong'oq yog'och
  focus: "#8aa88c", // sokin zona — sage yashil
  lounge: "#b87a52", // uy — terakota
  glass: "#dde1e8", // shisha xonalar — salqin och (yengillik = ularning identikasi)
} as const;

export default function OfficeDecor() {
  return (
    <group>
      {/* ══════ YUQORI QATOR (z[-16,-9.5]) ══════ */}
      {/* Dividerlar */}
      {[-9, -1, 8, 15].map((x) => (
        <DividerZ key={x} x={x} z0={-16} z1={-9.5} />
      ))}

      {/* SERVER XONASI [-23,-9] */}
      <Floor x0={-23} x1={-9} z0={-16} z1={-9.5} c={DISTRICT.server} />
      <WallX x0={-23} x1={-9} z={-9.5} door={2.6} />
      {[-21, -19, -17, -15, -13, -11].map((x) => (
        <ServerRack key={x} p={[x, 0, -15.4]} />
      ))}
      {[-21, -19, -17, -15, -13, -11].map((x) => (
        <ServerRack key={`b${x}`} p={[x, 0, -11]} ry={Math.PI} />
      ))}
      <CoolingUnit p={[-22.6, 0, -13]} ry={Math.PI / 2} />
      {/* Tunда: sovuq ko'k "ma'lumot g'ori" hovuzi */}
      <DistrictLight
        p={[-16, 2.2, -12.8]}
        c="#4fa8ff"
        intensity={10}
        distance={15}
      />

      {/* OSHXONA [-9,-1] */}
      <Floor x0={-9} x1={-1} z0={-16} z1={-9.5} c={DISTRICT.kitchen} />
      <WallX x0={-9} x1={-1} z={-9.5} door={2} />
      <Kitchen p={[-5, 0, -15.5]} />
      {/* Tunда: neon yozuvdan taralayotgan pushti porlash */}
      <DistrictLight
        p={[-5, 1.9, -14.3]}
        c="#ff5c9d"
        intensity={7}
        distance={11}
      />

      {/* MAJLIS [-1,8] */}
      <Floor x0={-1} x1={8} z0={-16} z1={-9.5} c={DISTRICT.meeting} />
      <WallX x0={-1} x1={8} z={-9.5} door={2} />
      <MeetingTable p={[3.5, 0, -12.5]} />
      <Whiteboard p={[3.5, 0, -15.82]} />

      {/* XOJATXONA [8,15] */}
      <Floor x0={8} x1={15} z0={-16} z1={-9.5} c={DISTRICT.bathroom} />
      <WallX x0={8} x1={15} z={-9.5} door={2} />
      <Stall p={[9.8, 0, -15]} />
      <Stall p={[11.8, 0, -15]} />
      <Sink p={[13.6, 0, -15.675]} />
      <Sink p={[14.4, 0, -15.675]} />

      {/* SHISHA XONA A [15,23] */}
      <Floor x0={15} x1={23} z0={-16} z1={-9.5} c={DISTRICT.glass} />
      <GlassWallX x0={15} x1={23} z={-9.5} door={2} />
      <MeetingTable p={[19, 0, -12.8]} r={0.9} />

      {/* ══════ PAST QATOR (z[9.5,16]) ══════ */}
      {[-11, -3, 7, 15].map((x) => (
        <DividerZ key={`b${x}`} x={x} z0={9.5} z1={16} />
      ))}

      {/* KUTUBXONA [-23,-11] */}
      <Floor x0={-23} x1={-11} z0={9.5} z1={16} c={DISTRICT.library} />
      <WallX x0={-23} x1={-11} z={9.5} door={2.4} />
      {[-21.5, -18.5, -15.5].map((x) => (
        <Bookshelf key={x} p={[x, 0, 15.68]} ry={Math.PI} />
      ))}
      {[-21.5, -18.5, -15.5].map((x) => (
        <Bookshelf key={`c${x}`} p={[x, 0, 11]} />
      ))}
      <ReadingTable p={[-13.5, 0, 13]} />
      {/* Tunда: to'q yog'och ustidа iliq amber "sobor" nuri */}
      <DistrictLight
        p={[-17, 2.2, 13]}
        c="#ffb463"
        intensity={10}
        distance={15}
      />

      {/* FOKUS [-11,-3] */}
      <Floor x0={-11} x1={-3} z0={9.5} z1={16} c={DISTRICT.focus} />
      <WallX x0={-11} x1={-3} z={9.5} door={2} />
      <EmptyDesk p={[-7, 0, 14.5]} ry={Math.PI} />
      <Plant p={[-4, 0, 15]} scale={1.0} />

      {/* DAM OLISH [-3,7] */}
      <Floor x0={-3} x1={7} z0={9.5} z1={16} c={DISTRICT.lounge} />
      <WallX x0={-3} x1={7} z={9.5} door={2} />
      <Sofa p={[2, 0, 15]} c="#4a5568" />
      <Sofa p={[5.5, 0, 13]} ry={-Math.PI / 2} c="#556070" />
      <CoffeeTable p={[2, 0, 13]} />
      {/* ekran xona ichiga (divanlar tomonga, -z) qarasin — devorga emas */}
      <TV p={[2, 1.7, 15.8]} ry={Math.PI} />

      {/* SHISHA XONA B [7,15] — ofis */}
      <Floor x0={7} x1={15} z0={9.5} z1={16} c={DISTRICT.glass} />
      <GlassWallX x0={7} x1={15} z={9.5} door={2} />
      <EmptyDesk p={[9.5, 0, 14.5]} ry={Math.PI} />
      <EmptyDesk p={[12.5, 0, 14.5]} ry={Math.PI} />

      {/* SHISHA XONA C [15,23] — majlis */}
      <Floor x0={15} x1={23} z0={9.5} z1={16} c={DISTRICT.glass} />
      <GlassWallX x0={15} x1={23} z={9.5} door={2} />
      <MeetingTable p={[19, 0, 13]} r={0.9} />

      {/* ══════ MARKAZ — ochiq ish maydoni ══════ */}
      {/* Reception */}
      <group position={[0, 0, 7.5]}>
        <Box p={[0, 0.5, 0]} s={[3.2, 1.0, 0.8]} c="#eceae4" rough={0.5} />
        <Box p={[0, 0.5, 0.42]} s={[2.9, 0.7, 0.02]} c={ACCENT} rough={0.6} />
        <Box p={[0, 1.06, 0]} s={[3.5, 0.07, 1.05]} c="#20242b" rough={0.3} />
        {/* logo bloklari */}
        {[-0.5, 0, 0.5].map((x) => (
          <Box
            key={x}
            p={[x, 0.55, 0.44]}
            s={[0.12, 0.12, 0.02]}
            c="#ffffff"
            rough={0.4}
          />
        ))}
      </group>
      {/* Markazdagi x=±13 stollar endi AGENT o'rindiqlari (SEATS 7-10) —
          Workstation ular ustiga stol chizadi (overflow agentlar shu yerda). */}
      {/* Pol lampalari o'rniga SHIFT yoritgichlari — ofisdek tepadan yoritadi.
          Markazdagi pendant'larга tegmaydi (x=±4); bular tashqi stollar (x=±13)
          ustida — ilgari u yer yoritilmagan edi. */}
      <CeilingPanel p={[-12, 0, -3.2]} />
      <CeilingPanel p={[-12, 0, 3.2]} />
      <CeilingPanel p={[12, 0, -3.2]} />
      <CeilingPanel p={[12, 0, 3.2]} />
      {/* o'simliklar */}
      <Plant p={[-16, 0, 6]} scale={1.1} />
      <Plant p={[16, 0, 6]} scale={1.1} />
      <Plant p={[-16, 0, -6]} scale={1.1} />
      <Plant p={[16, 0, -6]} scale={1.1} />
      <Plant p={[-1.5, 0, 5]} scale={0.9} />
      <Plant p={[1.5, 0, 5]} scale={0.9} />

      {/* Devor rasmlari */}
      <Painting p={[-22.85, 1.7, 0]} ry={Math.PI / 2} c="#c85a3c" />
      <Painting p={[22.85, 1.7, 0]} ry={-Math.PI / 2} c="#3a7bc8" />
      {/* Shift chiroqlari — ochiq ofis ustida (kechаsi porlaydi) */}
      <PendantLight p={[-4, 0, -3.2]} />
      <PendantLight p={[4, 0, -3.2]} />
      <PendantLight p={[-4, 0, 3.2]} />
      <PendantLight p={[4, 0, 3.2]} />
      {/* Devor soati + qo'shimcha rasmlar (yon devorlarда, ochiq ofisga qaragan) */}
      <WallClock p={[-22.85, 2.35, -6]} ry={Math.PI / 2} />
      <Painting p={[-22.85, 1.6, 6]} ry={Math.PI / 2} c="#5a8c5a" />
      <Painting p={[22.85, 1.6, -6]} ry={-Math.PI / 2} c="#c8a03a" />

      {/* Dekorativ gilamlar — xona mebeli ostida (yassi, yurishga xalaqit yo'q) */}
      <Rug p={[3, 0, 13.6]} w={5} d={3.6} c="#7d4a6b" accent="#a06a8c" />
      <Rug p={[-13.5, 0, 13]} w={4.2} d={3.2} c="#8a5a2e" accent="#b0824a" />
      <Rug p={[3.5, 0, -12.5]} w={4.6} d={3.6} c="#3f5e7a" accent="#5c82a0" />
      <Rug p={[19, 0, -12.8]} w={3.4} d={3} c="#4a6b4f" accent="#6a8f70" />
      <Rug p={[19, 0, 13]} w={3.4} d={3} c="#8a4038" accent="#ac5c52" />
    </group>
  );
}
