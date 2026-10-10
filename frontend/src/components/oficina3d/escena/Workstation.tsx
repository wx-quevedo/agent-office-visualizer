import { Html } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { memo, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import type { EscritorioCerrado } from "../adaptador";
import type { Monitor } from "../comportamiento";
import type { AgentView } from "../store";
import { t } from "../textos";
import { MarcaCuenta } from "@/components/marca/Marca";
import { useEditor } from "../editor";
import { capaEtiquetas } from "./capaEtiquetas";
import { useOffice } from "../store";
import { clutterLevel } from "./clutter";
import { useDaylight } from "./daylight";
import { basicMat, cyl, sphere, stdMat, UNIT_BOX } from "./resources";
import { roleKeyFor, seatFor, STATUS_COLOR } from "./roles";

// ── Ish joyi — MEBEL (personaj AgentAvatar'da, alohida) ──────
// Stollar OLDINDAN turadi (bo'sh yoki band). Bo'sh stol = qorong'i ekran, toza
// stol → "band bo'lmagan ish joyi" ko'rinadi. Agent qo'shilganda O'SHA stolga
// o'tiradi (ekran yonadi, tartibsizlik paydo bo'ladi) — mebel yo'qdan paydo
// bo'lmaydi, ofis haqiqiy ofisdek to'ladi.

const DESK_TOP = 0.72;
type V3 = [number, number, number];
function B({
  p,
  s,
  m,
  cast = true,
}: {
  p?: V3;
  s: V3;
  m: THREE.Material;
  cast?: boolean;
}) {
  return (
    <mesh
      position={p}
      scale={s}
      geometry={UNIT_BOX}
      material={m}
      castShadow={cast}
    />
  );
}
// Statik (holatga bog'liq bo'lmagan) materiallar — bir marta keshlanadi.
const DESK_TOP_M = stdMat("#f2efe9", { roughness: 0.4 });
const DESK_EDGE_M = stdMat("#2a2e35", { roughness: 0.4 });
const LEG_M = stdMat("#4a4f57", { roughness: 0.4, metalness: 0.6 });
const MON_M = stdMat("#12151a", { roughness: 0.3 });
const SCREEN_OFF_M = stdMat("#1b1f27", { roughness: 0.35 }); // o'chiq ekran (bo'sh stol)
const STAND_M = stdMat("#3a3f47");
const KEY_M = stdMat("#e2e2e0", { roughness: 0.6 });
const MUG_M = stdMat("#ffffff", { roughness: 0.4 });
// Tartibsizlik buyumlari (toolCalls o'sgan sari qo'shiladi)
const PAPER_M = stdMat("#f7f5ef", { roughness: 0.9 });
const MUG2_M = stdMat("#c96a4e", { roughness: 0.5 });
const NOTE_M = stdMat("#ffd60a", { roughness: 0.85 });
const CHAIR_M = stdMat("#2c313a", { roughness: 0.6 });
/** Chair of an agent waiting for you (Estudio): soft blue. */
const CHAIR_LUZ_M = stdMat("#4c8bf5", { roughness: 0.5 });
const ARM_M = stdMat("#1c2027");
const POST_M = stdMat("#8b929c", { roughness: 0.35, metalness: 0.85 });
const STAR_M = stdMat("#3a3f47", { roughness: 0.4, metalness: 0.6 });
const SCREEN_G = new THREE.PlaneGeometry(0.64, 0.36);
const GLOW_G = new THREE.PlaneGeometry(0.98, 0.66);

// ── Rol stol odati — har rolning belgili buyumi (stolда, o'ng-orqa burchakда) ──
// Backend — debug o'rdagi · Tadqiqot — kitob uyumi · Hujjatlar — qog'oz+kitob
// Ma'lumot — mini grafik (bar) · QA — checklist planshet · Frontend — rang palitrasi.
const DUCK_M = stdMat("#f2c94c", { roughness: 0.6 });
const BEAK_M = stdMat("#e8913a", { roughness: 0.6 });
const CLIP_M = stdMat("#eceae4", { roughness: 0.7 });
const CLIPTOP_M = stdMat("#3a3f47", { roughness: 0.5 });
const BAR_M = [
  stdMat("#3987e5"),
  stdMat("#e66767"),
  stdMat("#199e70"),
  stdMat("#c98500"),
];
const BOOK_M = [
  stdMat("#c0392b"),
  stdMat("#2f6bd6"),
  stdMat("#27ae60"),
  stdMat("#8a5a2b"),
];
const SWATCH_M = [
  stdMat("#e0518a"),
  stdMat("#3fb4c6"),
  stdMat("#f2c94c"),
  stdMat("#7d5ae0"),
];
function DeskProp({ roleKey }: { roleKey: string }) {
  const y = DESK_TOP + 0.05;
  switch (roleKey) {
    case "backend": // debug o'rdagi
      return (
        <group position={[0.5, y, -0.16]} scale={0.85}>
          <mesh
            position={[0, 0.05, 0]}
            castShadow
            geometry={sphere(0.075, 10, 8)}
            material={DUCK_M}
          />
          <mesh
            position={[0, 0.14, -0.05]}
            castShadow
            geometry={sphere(0.05, 10, 8)}
            material={DUCK_M}
          />
          <B
            p={[0, 0.13, -0.11]}
            s={[0.04, 0.025, 0.05]}
            m={BEAK_M}
            cast={false}
          />
        </group>
      );
    case "research": // kitob uyumi
      return (
        <group position={[0.52, y, -0.14]}>
          {[0, 1, 2].map((i) => (
            <B
              key={i}
              p={[i * 0.01, 0.02 + i * 0.04, 0]}
              s={[0.26, 0.035, 0.19]}
              m={BOOK_M[i]}
            />
          ))}
        </group>
      );
    case "docs": // qog'oz uyumi + kitob
      return (
        <group position={[0.5, y, -0.14]}>
          <B p={[0, 0.02, 0]} s={[0.24, 0.035, 0.3]} m={CLIP_M} />
          <B p={[0.02, 0.06, -0.02]} s={[0.22, 0.04, 0.16]} m={BOOK_M[3]} />
        </group>
      );
    case "data": // mini grafik (barlar)
      return (
        <group position={[0.52, y, -0.15]}>
          <B p={[0, 0.09, 0.02]} s={[0.28, 0.18, 0.02]} m={CLIPTOP_M} />
          {[0, 1, 2, 3].map((i) => (
            <B
              key={i}
              p={[-0.09 + i * 0.06, 0.04 + i * 0.02, 0.03]}
              s={[0.035, 0.05 + i * 0.04, 0.01]}
              m={BAR_M[i]}
              cast={false}
            />
          ))}
        </group>
      );
    case "qa": // checklist planshet
      return (
        <group position={[0.5, y, -0.12]} rotation={[0.2, 0, 0]}>
          <B p={[0, 0.09, 0]} s={[0.24, 0.32, 0.02]} m={CLIP_M} />
          <B p={[0, 0.24, 0.02]} s={[0.1, 0.045, 0.02]} m={CLIPTOP_M} />
          {[0, 1, 2].map((i) => (
            <B
              key={i}
              p={[-0.05, 0.15 - i * 0.06, 0.02]}
              s={[0.03, 0.03, 0.01]}
              m={BAR_M[2]}
              cast={false}
            />
          ))}
        </group>
      );
    case "frontend": // rang palitrasi
      return (
        <group position={[0.5, y, -0.14]} rotation={[0.25, 0, 0]}>
          <B p={[0, 0.03, 0]} s={[0.3, 0.02, 0.22]} m={CLIP_M} />
          {[0, 1, 2, 3].map((i) => (
            <B
              key={i}
              p={[
                -0.09 + (i % 2) * 0.18,
                0.045,
                -0.05 + Math.floor(i / 2) * 0.1,
              ]}
              s={[0.07, 0.02, 0.07]}
              m={SWATCH_M[i]}
              cast={false}
            />
          ))}
        </group>
      );
    default:
      return null;
  }
}

// ── Monitor ekrani — HAQIQIY tool/fayl ko'rsatiladi ──────────────
// Flat rang o'rniga ekranda joriy ish ko'rinadi: fayl nomi + holat rangidagi
// "kod satrlari". WebGL tuvaliga matn drei <Text> orqali chizilmaydi — u troika
// CDN shriftini yuklaydi (CSP bloklaydi). Shuning uchun 2D CANVAS'ga chizib,
// CanvasTexture qilamiz (o'zicha, ichki shrift, tekstura — performant). Ma'lumot
// O'LCHANGAN (toolLabel); yorliq o'zgarganда qayta chiziladi.
function fitText(
  ctx: CanvasRenderingContext2D,
  s: string,
  maxW: number,
): string {
  if (ctx.measureText(s).width <= maxW) return s;
  let t = s;
  while (t.length > 1 && ctx.measureText(t + "…").width > maxW)
    t = t.slice(0, -1);
  return t + "…";
}
function MonitorScreen({ label, color }: { label?: string; color: string }) {
  const tex = useMemo(() => {
    const c = document.createElement("canvas");
    c.width = 256;
    c.height = 144;
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    return t;
  }, []);
  useEffect(() => {
    const c = tex.image as HTMLCanvasElement;
    const ctx = c.getContext("2d");
    if (!ctx) return;
    const W = 256,
      H = 144;
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = "#0d1016";
    ctx.fillRect(0, 0, W, H);
    // Yuqori "oyna" paneli — holat rangida + qora nuqtalar
    ctx.globalAlpha = 0.9;
    ctx.fillStyle = color;
    ctx.fillRect(0, 0, W, 14);
    ctx.globalAlpha = 1;
    ctx.fillStyle = "rgba(0,0,0,0.4)";
    for (const x of [10, 26, 42]) {
      ctx.beginPath();
      ctx.arc(x, 7, 3, 0, Math.PI * 2);
      ctx.fill();
    }
    if (label) {
      ctx.fillStyle = "#f2f5fa";
      ctx.font = "bold 19px system-ui, sans-serif";
      ctx.fillText(fitText(ctx, label, W - 24), 12, 42);
      // "Kod satrlari" — holat rangida, susayib boradi (ekran tirik ko'rinsin)
      ctx.fillStyle = color;
      [0.72, 0.44, 0.86, 0.55, 0.33].forEach((w, i) => {
        ctx.globalAlpha = 0.4 - i * 0.04;
        ctx.fillRect(12, 60 + i * 15, (W - 24) * w, 6);
      });
      ctx.globalAlpha = 1;
    } else {
      // Band, lekin tool yo'q (o'ylayapti/idle) — nozik kursor
      ctx.globalAlpha = 0.5;
      ctx.fillStyle = color;
      ctx.fillRect(12, 38, 8, 15);
      ctx.globalAlpha = 1;
    }
    tex.needsUpdate = true;
  }, [tex, label, color]);
  useEffect(() => () => tex.dispose(), [tex]);
  return (
    <mesh position={[0, 0.26, -0.019]} geometry={SCREEN_G}>
      <meshBasicMaterial map={tex} toneMapped={false} />
    </mesh>
  );
}

// ── Drawn badges over the monitor (no emojis) ──
const BADGE_M = stdMat("#2a2f38", { roughness: 0.5 });
const SAND_M = basicMat("#e0b04a", { toneMapped: false });
const BAR_BG_M = basicMat("#ffffff", { toneMapped: false });
const BAR_FG_M = basicMat("#111111", { toneMapped: false });
const NOTA_M = stdMat("#fbfaf4", { roughness: 0.8 });
const LUZ_M = basicMat("#4c8bf5", {
  transparent: true,
  opacity: 0.9,
  toneMapped: false,
});
const HALO_M = basicMat("#4c8bf5", {
  transparent: true,
  opacity: 0.22,
  toneMapped: false,
});

/** Project name on the monitor side of the desk, facing away from the agent. */
function PlacaNombre({ texto }: { texto: string }) {
  const tex = useMemo(() => {
    const c = document.createElement("canvas");
    c.width = 512;
    c.height = 112;
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    return t;
  }, []);
  useEffect(() => {
    const ctx = (tex.image as HTMLCanvasElement).getContext("2d");
    if (!ctx) return;
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, 512, 112);
    ctx.fillStyle = "#111111";
    ctx.fillRect(0, 0, 512, 8);
    ctx.font = "bold 54px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(fitText(ctx, texto, 488), 256, 78);
    tex.needsUpdate = true;
  }, [tex, texto]);
  useEffect(() => () => tex.dispose(), [tex]);
  return (
    <group position={[0, DESK_TOP + 0.13, -0.405]} rotation={[0, Math.PI, 0]}>
      <B s={[0.82, 0.2, 0.02]} m={DESK_EDGE_M} cast={false} />
      <mesh position={[0, 0, 0.012]}>
        <planeGeometry args={[0.78, 0.17]} />
        <meshBasicMaterial map={tex} toneMapped={false} />
      </mesh>
    </group>
  );
}

/** Soft blue light along the desk edge and on the floor around it. */
function BordeLuz() {
  return (
    <group>
      <B
        p={[0, DESK_TOP + 0.035, 0.41]}
        s={[1.52, 0.025, 0.02]}
        m={LUZ_M}
        cast={false}
      />
      <B
        p={[0, DESK_TOP + 0.035, -0.41]}
        s={[1.52, 0.025, 0.02]}
        m={LUZ_M}
        cast={false}
      />
      <B
        p={[0.76, DESK_TOP + 0.035, 0]}
        s={[0.02, 0.025, 0.82]}
        m={LUZ_M}
        cast={false}
      />
      <B
        p={[-0.76, DESK_TOP + 0.035, 0]}
        s={[0.02, 0.025, 0.82]}
        m={LUZ_M}
        cast={false}
      />
      <mesh
        position={[0, 0.015, 0.2]}
        rotation={[-Math.PI / 2, 0, 0]}
        material={HALO_M}
      >
        <circleGeometry args={[1.35, 40]} />
      </mesh>
    </group>
  );
}
const LINEA_M = basicMat("#555555");

/** 15 — waits for a program: an hourglass that turns over slowly. */
function RelojDeArena() {
  const g = useRef<THREE.Group>(null);
  useFrame((st) => {
    if (!g.current) return;
    const ciclo = (st.clock.elapsedTime % 4) / 4; // 3 s still, 1 s turning
    g.current.rotation.z = ciclo < 0.75 ? 0 : ((ciclo - 0.75) / 0.25) * Math.PI;
  });
  return (
    <group ref={g}>
      <B p={[0, 0.13, 0]} s={[0.17, 0.025, 0.17]} m={BADGE_M} cast={false} />
      <B p={[0, -0.13, 0]} s={[0.17, 0.025, 0.17]} m={BADGE_M} cast={false} />
      <mesh
        position={[0, 0.06, 0]}
        rotation={[Math.PI, 0, 0]}
        geometry={CONO_G}
        material={SAND_M}
      />
      <mesh position={[0, -0.06, 0]} geometry={CONO_G} material={SAND_M} />
    </group>
  );
}
const CONO_G = new THREE.ConeGeometry(0.07, 0.12, 12);

/** 16 — upload or download: a progress bar that fills up and starts again. */
function BarraProgreso() {
  const fg = useRef<THREE.Mesh>(null);
  useFrame((st) => {
    if (!fg.current) return;
    const k = 0.05 + ((st.clock.elapsedTime * 0.25) % 1) * 0.95;
    fg.current.scale.x = 0.4 * k;
    fg.current.position.x = -0.2 + 0.2 * k;
  });
  return (
    <group>
      <B s={[0.46, 0.1, 0.02]} m={BADGE_M} cast={false} />
      <B p={[0, 0, 0.012]} s={[0.42, 0.065, 0.01]} m={BAR_BG_M} cast={false} />
      <mesh
        ref={fg}
        position={[-0.2, 0, 0.02]}
        scale={[0.02, 0.05, 0.01]}
        geometry={UNIT_BOX}
        material={BAR_FG_M}
      />
    </group>
  );
}

function DistintivoMonitor({ tipo }: { tipo: Monitor }) {
  if (!tipo) return null;
  return (
    <group position={[0, DESK_TOP + 0.02 + 0.8, -0.22]} scale={2}>
      {tipo === "reloj" ? <RelojDeArena /> : <BarraProgreso />}
    </group>
  );
}

/** 21 with a pending question: a paper note standing on the desk; hover shows it. */
function NotaCerrado({ cerrado }: { cerrado: EscritorioCerrado }) {
  const [ver, setVer] = useState(false);
  return (
    <group
      position={[0.05, DESK_TOP + 0.14, 0.08]}
      rotation={[-0.35, 0.25, 0]}
      onPointerOver={(e) => {
        if (useEditor.getState().activo) return;
        e.stopPropagation();
        setVer(true);
        document.body.style.cursor = "pointer";
      }}
      onPointerOut={() => {
        setVer(false);
        document.body.style.cursor = "";
      }}
    >
      <B s={[0.34, 0.26, 0.012]} m={NOTA_M} />
      {[0.07, 0.02, -0.03, -0.08].map((y, i) => (
        <B
          key={y}
          p={[-0.02 * i, y, 0.008]}
          s={[0.24 - 0.03 * i, 0.012, 0.004]}
          m={LINEA_M}
          cast={false}
        />
      ))}
      {ver && (
        <Html
          portal={capaEtiquetas}
          position={[0, 0.5, 0]}
          center
          zIndexRange={[1000, 900]}
          style={{ pointerEvents: "none" }}
        >
          <div
            style={{
              padding: "6px 10px",
              background: "#fff",
              color: "#111",
              border: "2px solid #111",
              fontFamily: "var(--font-plex-sans), system-ui, sans-serif",
              fontSize: 12,
              maxWidth: 280,
              minWidth: 180,
              boxShadow: "0 2px 6px rgba(0,0,0,0.25)",
            }}
          >
            <div
              style={{
                fontWeight: 700,
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <MarcaCuenta cuenta={cerrado.cuenta} alto={16} />
              {cerrado.proyecto}
            </div>
            <div style={{ color: "#555", marginTop: 2 }}>
              {t("nota.cerrado")}
            </div>
            <div style={{ marginTop: 4 }}>
              <b>{t("detalle.pregunta")}:</b> {cerrado.pregunta}
            </div>
          </div>
        </Html>
      )}
    </group>
  );
}

function Workstation({
  seatIndex,
  agent,
  cerrado,
  placa,
  resaltado = false,
  sillaGirada = false,
  giroSilla = 0,
  luzSilla = false,
}: {
  seatIndex: number;
  agent?: AgentView;
  /** Desk of a closed agent (21): a note when it left a question. */
  cerrado?: EscritorioCerrado;
  /** Project name on a plate at the monitor side (environments with nameplates). */
  placa?: string;
  /** Soft blue light on the desk edge: the agent waits for you (Puente de mando). */
  resaltado?: boolean;
  /** The agent left its desk to queue at the counter: chair turned. */
  sillaGirada?: boolean;
  /** Chair turned by this angle (Estudio: towards your desk while it waits). */
  giroSilla?: number;
  /** Chair lit blue (Estudio: the agent waits for you). */
  luzSilla?: boolean;
}) {
  const seat = seatFor(seatIndex);
  const select = useOffice((s) => s.select);
  const occupied = !!agent;
  const color = agent ? STATUS_COLOR[agent.status] : "#3a4150";
  // Ekran porlashi kechаsi kuchayadi (qorong'uда monitorlar ko'proq ajralib turadi).
  const lampsOn = useDaylight((s) => s.params.lamps);
  const glowOpacity = lampsOn ? 0.4 : 0.2;
  const clutter = agent ? clutterLevel(agent.toolCalls) : 0;

  return (
    <group
      position={[seat.x, 0, seat.z]}
      rotation={[0, seat.ry, 0]}
      onClick={(e) => {
        if (useEditor.getState().activo) return; // editing: the click goes to the floor
        e.stopPropagation();
        select(agent ? agent.id : (cerrado?.sessionId ?? null));
      }}
    >
      {/* Stol usti — oq + qora aksent qirra */}
      <B p={[0, DESK_TOP, 0]} s={[1.5, 0.06, 0.8]} m={DESK_TOP_M} />
      <B
        p={[0, DESK_TOP - 0.045, 0]}
        s={[1.52, 0.03, 0.82]}
        m={DESK_EDGE_M}
        cast={false}
      />
      {/* nozik chrome A-oyoqlar */}
      {[-0.64, 0.64].map((x) => (
        <B
          key={x}
          p={[x, DESK_TOP / 2 - 0.03, 0]}
          s={[0.05, DESK_TOP - 0.06, 0.68]}
          m={LEG_M}
        />
      ))}

      {/* Slim monitor — band bo'lsa ekran holat rangida yonadi, bo'sh bo'lsa o'chiq */}
      <group position={[0, DESK_TOP + 0.02, -0.22]}>
        <B p={[0, 0.26, 0]} s={[0.7, 0.42, 0.03]} m={MON_M} />
        {agent ? (
          <>
            {/* Ekranда joriy tool/fayl (canvas-tekstura) */}
            <MonitorScreen label={agent.toolLabel} color={color} />
            {/* ekran porlashi — holat rangida yumshoq halo */}
            <mesh
              position={[0, 0.26, -0.025]}
              geometry={GLOW_G}
              material={basicMat(color, {
                transparent: true,
                opacity: glowOpacity,
                blending: THREE.AdditiveBlending,
                side: THREE.DoubleSide,
                toneMapped: false,
              })}
            />
          </>
        ) : (
          // Bo'sh stol — o'chiq (qorong'i) ekran, porlash yo'q
          <mesh
            position={[0, 0.26, -0.02]}
            geometry={SCREEN_G}
            material={SCREEN_OFF_M}
          />
        )}
        {/* nozik stend */}
        <B p={[0, 0.05, 0]} s={[0.05, 0.16, 0.05]} m={STAND_M} />
        <B
          p={[0, -0.02, 0]}
          s={[0.26, 0.02, 0.14]}
          m={DESK_EDGE_M}
          cast={false}
        />
      </group>

      {placa && <PlacaNombre texto={placa} />}
      {resaltado && <BordeLuz />}
      {/* 15/16: drawn badge over the monitor */}
      {agent && <DistintivoMonitor tipo={agent.monitor} />}
      {/* 21 with a pending question: paper note */}
      {!agent && cerrado?.pregunta && <NotaCerrado cerrado={cerrado} />}

      {/* Klaviatura — doim (stolning bir qismi) */}
      <B p={[0, DESK_TOP + 0.04, 0.14]} s={[0.5, 0.02, 0.16]} m={KEY_M} />
      {/* Rol stol odati — faqat band stolда (kimningdir buyumi) */}
      {agent && <DeskProp roleKey={roleKeyFor(agent.role, agent.seatIndex)} />}
      {/* Krujka — faqat band stolда (kimningdir shaxsiy buyumi) */}
      {occupied && (
        <mesh
          position={[0.55, DESK_TOP + 0.08, 0.05]}
          castShadow
          geometry={cyl(0.05, 0.045, 0.1, 12)}
          material={MUG_M}
        />
      )}

      {/* ── Tartibsizlik — ISH BELGISI, bezak emas (manba: toolCalls) ──
          Har daraja bir buyum qo'shadi: qog'oz → 2-krujka → stiker+qog'oz uyumi
          → g'ijimlangan qog'oz. Toza stol = yangi sessiya yoki bo'sh joy. */}
      {clutter >= 1 && (
        <B
          p={[-0.48, DESK_TOP + 0.04, 0.12]}
          s={[0.28, 0.012, 0.34]}
          m={PAPER_M}
        />
      )}
      {clutter >= 2 && (
        <mesh
          position={[-0.6, DESK_TOP + 0.09, -0.12]}
          castShadow
          geometry={cyl(0.055, 0.05, 0.12, 12)}
          material={MUG2_M}
        />
      )}
      {clutter >= 3 && (
        <>
          <B
            p={[-0.44, DESK_TOP + 0.07, 0.15]}
            s={[0.26, 0.05, 0.32]}
            m={PAPER_M}
          />
          {/* Monitor chetidagi stiker */}
          <B
            p={[0.4, DESK_TOP + 0.4, -0.2]}
            s={[0.13, 0.13, 0.006]}
            m={NOTE_M}
            cast={false}
          />
        </>
      )}
      {clutter >= 4 && (
        <>
          <mesh
            position={[0.34, DESK_TOP + 0.09, 0.24]}
            castShadow
            geometry={sphere(0.06, 6, 5)}
            material={PAPER_M}
          />
          <B
            p={[-0.2, DESK_TOP + 0.05, -0.24]}
            s={[0.24, 0.02, 0.28]}
            m={PAPER_M}
          />
          <B
            p={[0.28, DESK_TOP + 0.4, -0.2]}
            s={[0.11, 0.11, 0.006]}
            m={NOTE_M}
            cast={false}
          />
        </>
      )}

      {/* Zamonaviy ergonomik kursi (5-yulduzli baza) */}
      <group
        position={[0, 0, 0.62]}
        rotation={[0, sillaGirada ? 0.9 : giroSilla, 0]}
      >
        <B
          p={[0, 0.46, 0]}
          s={[0.48, 0.07, 0.48]}
          m={luzSilla ? CHAIR_LUZ_M : CHAIR_M}
        />
        <B
          p={[0, 0.74, 0.22]}
          s={[0.46, 0.5, 0.06]}
          m={luzSilla ? CHAIR_LUZ_M : CHAIR_M}
        />
        {luzSilla && (
          <mesh
            position={[0, 0.016, 0]}
            rotation={[-Math.PI / 2, 0, 0]}
            material={HALO_M}
          >
            <circleGeometry args={[0.6, 32]} />
          </mesh>
        )}
        {/* qo'l tayanchlar */}
        {[-0.26, 0.26].map((x) => (
          <B
            key={x}
            p={[x, 0.56, 0.05]}
            s={[0.05, 0.04, 0.3]}
            m={ARM_M}
            cast={false}
          />
        ))}
        <mesh
          position={[0, 0.22, 0]}
          geometry={cyl(0.04, 0.05, 0.44, 10)}
          material={POST_M}
        />
        {[0, 1, 2, 3, 4].map((i) => {
          const a = (i / 5) * Math.PI * 2;
          return (
            <B
              key={i}
              p={[Math.cos(a) * 0.22, 0.04, Math.sin(a) * 0.22]}
              s={[0.22, 0.04, 0.05]}
              m={STAR_M}
            />
          );
        })}
      </group>
    </group>
  );
}

// memo — o'zgarmagan agentda qayta render bo'lmaydi (perf).
export default memo(Workstation);
