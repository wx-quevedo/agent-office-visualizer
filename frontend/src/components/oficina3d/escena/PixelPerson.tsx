import { useFrame } from "@react-three/fiber";
import { useRef } from "react";
import * as THREE from "three";
import { useSettings } from "../settings";
import type { AgentStatus } from "../store";
import type { Accessory as AccessoryType, CharSkin, HairStyle } from "./roles";
import { STATUS_COLOR } from "./roles";
import { basicMat, sphere, stdMat, UNIT_BOX } from "./resources";
import { visibleObject } from "./visibility";

// Ulashilgan birlik-kub qutisi: har voxel bo'lagi bitta geometriya + keshlangan
// material (20 agentda minglab dublikat o'rniga o'nlab noyob obyekt).
type V3 = [number, number, number];
// cast default FALSE — 20 agentда ~600 mayda soya-tashlovchi mesh perf'ni yeydi.
// Faqat tana+bosh (siluet) soya tashlaydi — yerga o'tirtirish uchun yetarli.
function VB({
  p,
  s,
  m,
  cast = false,
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
const EYE_WHITE = stdMat("#f4f0ea", { roughness: 0.5 });
const EYE_PUPIL = stdMat("#1a1a22");
const RING_GEO = new THREE.RingGeometry(0.06, 0.1, 18);

// ── Voxel chibi personaj: o'tirish / turish / yurish ─────────
// pose="sit" — stolda o'tirib yozadi (working/thinking...).
// pose="stand" + moving — tik turib yuradi (bo'sh turganda sayr).

interface Props {
  skin: CharSkin;
  status: AgentStatus;
  pose?: "sit" | "stand";
  moving?: boolean;
  /** "low" — soddalashtirilgan (yuz tafsilotsiz) — kichik yordamchilar uchun. */
  detail?: "high" | "low";
  /** Har freym o'qiladi (re-render'siz poza/harakatni yangilash uchun). */
  getState?: () => {
    sit: boolean;
    moving: boolean;
    speed?: number;
    /** Seated variants: relaxed on the sofa (19) or one arm up (13). */
    pose?: "normal" | "sofa" | "brazoAlzado";
  };
  /** Rol "energiyasi" (~0.7 xotirjam … 1.3 faol) — bo'sh vaqtда qanchalik
   *  tez-tez atrofga qaraydi/qimirlaydi. Faqat mavjud harakatlarni shkalalaydi
   *  (geometriyaga tegmaydi). Standart 1. */
  energy?: number;
}

function damp(c: number, t: number, l: number, dt: number): number {
  return THREE.MathUtils.lerp(c, t, 1 - Math.exp(-l * dt));
}

// Bosh aksessuari — per-agent xilma-xillik (bosh markazida, old = -z).
function Accessory({ type }: { type: AccessoryType }) {
  if (type === "glasses") {
    const gm = stdMat("#15181d", { roughness: 0.4, metalness: 0.3 });
    return (
      <group position={[0, 0.025, -0.152]}>
        {[-0.07, 0.07].map((x) => (
          <mesh key={x} position={[x, 0, 0]} material={gm}>
            <torusGeometry args={[0.043, 0.008, 6, 14]} />
          </mesh>
        ))}
        <VB s={[0.055, 0.008, 0.008]} m={gm} cast={false} />
        {[-0.11, 0.11].map((x) => (
          <VB
            key={x}
            p={[x, 0, 0.09]}
            s={[0.008, 0.008, 0.18]}
            m={gm}
            cast={false}
          />
        ))}
      </group>
    );
  }
  if (type === "headphones") {
    const hm = stdMat("#23262b", { roughness: 0.5 });
    return (
      <group>
        <mesh position={[0, 0.02, 0]} material={hm}>
          <torusGeometry args={[0.175, 0.022, 8, 16, Math.PI]} />
        </mesh>
        {[-0.162, 0.162].map((x) => (
          <VB key={x} p={[x, 0.0, 0]} s={[0.05, 0.13, 0.13]} m={hm} />
        ))}
      </group>
    );
  }
  if (type === "cap") {
    const cm = stdMat("#2f6bd6", { roughness: 0.8 });
    return (
      <group position={[0, 0.155, 0]}>
        <VB s={[0.335, 0.11, 0.335]} m={cm} />
        <VB p={[0, -0.045, -0.22]} s={[0.3, 0.03, 0.16]} m={cm} />
      </group>
    );
  }
  if (type === "beanie") {
    // Jun shapka — kepkadan farqli: kozirоksiz, boshni ko'proq yopadi, pastда
    // qatlam (buklama). Iliq jun rangi.
    const bm = stdMat("#7a5a8c", { roughness: 0.98 });
    return (
      <group position={[0, 0.15, 0]}>
        <VB s={[0.345, 0.17, 0.345]} m={bm} />
        <VB p={[0, -0.085, 0]} s={[0.365, 0.055, 0.365]} m={bm} />
      </group>
    );
  }
  return null;
}

function Hair({ style, color }: { style: HairStyle; color: string }) {
  const hm = stdMat(color, { roughness: 0.9 });
  const hm2 = stdMat(color, { roughness: 0.95 }); // sferik soch (afro/curly)
  const cap = <VB p={[0, 0.16, 0]} s={[0.33, 0.09, 0.33]} m={hm} />;
  switch (style) {
    case "short":
      return (
        <group>
          {cap}
          <VB p={[0, 0.02, 0.13]} s={[0.33, 0.3, 0.09]} m={hm} />
        </group>
      );
    case "long":
      // Yon tutamlar biroz ORQAROQ (z=0.05) — oldiда yuzни kesib o'tmasin.
      return (
        <group>
          {cap}
          {[-0.185, 0.185].map((x) => (
            <VB key={x} p={[x, -0.14, 0.05]} s={[0.06, 0.4, 0.32]} m={hm} />
          ))}
          <VB p={[0, -0.11, 0.16]} s={[0.34, 0.5, 0.08]} m={hm} />
        </group>
      );
    case "afro":
      // Shar ORQAGA surildi (z=0.1) va kichraytirildi — oldi z≈-0.12'da tugaydi,
      // ko'zlar (z=-0.151) OLDIда qoladi → yuz ko'rinadi (avval afro yuzni yopardi).
      return (
        <mesh
          position={[0, 0.15, 0.1]}
          castShadow
          geometry={sphere(0.22, 12, 10)}
          material={hm2}
        />
      );
    case "curly":
      return (
        <group>
          <mesh
            position={[0, 0.15, 0.1]}
            castShadow
            geometry={sphere(0.2, 12, 10)}
            material={hm2}
          />
          {[-0.17, 0.17].map((x) => (
            <mesh
              key={x}
              position={[x, 0, 0.04]}
              castShadow
              geometry={sphere(0.095, 8, 8)}
              material={hm2}
            />
          ))}
        </group>
      );
    case "spiky":
      return (
        <group>
          {cap}
          {[-0.1, 0, 0.1].map((x) =>
            [-0.08, 0.08].map((z) => (
              <mesh
                key={`${x}_${z}`}
                position={[x, 0.23, z]}
                rotation={[0.15 * z, 0, 0.2 * x]}
                castShadow
                material={hm}
              >
                <coneGeometry args={[0.05, 0.13, 4]} />
              </mesh>
            )),
          )}
        </group>
      );
    default:
      return (
        <group>
          {cap}
          <VB p={[0, -0.02, 0.14]} s={[0.34, 0.36, 0.09]} m={hm} />
          {[-0.185, 0.185].map((x) => (
            <VB key={x} p={[x, 0, 0.02]} s={[0.06, 0.24, 0.3]} m={hm} />
          ))}
        </group>
      );
  }
}

export default function PixelPerson({
  skin: s,
  status,
  pose = "sit",
  moving = false,
  detail = "high",
  getState,
  energy = 1,
}: Props) {
  const lod = detail === "low";
  const en = Math.max(0.5, Math.min(1.6, energy)); // xavfsiz oraliq
  const rootRef = useRef<THREE.Group>(null);
  const bodyRef = useRef<THREE.Group>(null); // tos+yuqori (balandligi poza bilan)
  const upperRef = useRef<THREE.Group>(null);
  const headRef = useRef<THREE.Group>(null);
  const hipL = useRef<THREE.Group>(null);
  const hipR = useRef<THREE.Group>(null);
  const kneeL = useRef<THREE.Group>(null);
  const kneeR = useRef<THREE.Group>(null);
  const shoL = useRef<THREE.Group>(null);
  const shoR = useRef<THREE.Group>(null);
  const elbowL = useRef<THREE.Group>(null);
  const elbowR = useRef<THREE.Group>(null);
  const ankleL = useRef<THREE.Group>(null);
  const ankleR = useRef<THREE.Group>(null);
  const walkPhase = useRef(0); // masofaga bog'liq qadam fazasi (oyoq sirg'anmaydi)
  const walkBlend = useRef(0); // yurish amplitudasi 0→1 (silliq kirish/chiqish)
  const ringRef = useRef<THREE.Mesh>(null);
  const t = useRef(Math.random() * 10);
  const stretchLeft = useRef(0); // cho'zilish davomi (s)
  const stretchCd = useRef(6 + Math.random() * 10); // keyingi cho'zilishgacha
  const eyesRef = useRef<THREE.Group>(null);
  const blinkLeft = useRef(0);
  const blinkCd = useRef(2 + Math.random() * 4); // keyingi pirpirashgacha
  const glanceCd = useRef(3 + Math.random() * 5); // keyingi qarashgacha
  const headYaw = useRef(0); // atrofga qarash (maqsad)

  const cloth = (c: string) => stdMat(c, { roughness: 0.85 });
  const skin = stdMat(s.skin, { roughness: 0.6 });

  useFrame((_, delta) => {
    const dt = Math.min(delta, 0.05);
    // Perf: ekrandan tashqarida bo'lsa rigni MUZLATAMIZ (faqat kosmetika —
    // harakat/joylashuv AgentAvatar'da, bunga bog'liq emas). damp() eksponensial
    // bo'lgani uchun qayta ko'ринganda silliq davom etadi (sakramaydi).
    if (rootRef.current && !visibleObject(rootRef.current)) return;
    // Kamaytirilgan harakat: vaqtni oldinga surmaymiz → nafas, yozish tebranishi,
    // bosh chayqalishi va pirpirash to'xtaydi. Poza (o'tirish/turish) va YURISH
    // baribir ishlaydi — ular mazmunли, bezak emas.
    const rm = useSettings.getState().reducedMotion;
    t.current += rm ? 0 : dt;
    const tt = t.current;
    const st = getState ? getState() : { sit: pose === "sit", moving };
    const sit = st.sit;
    const sofa = sit && st.pose === "sofa";
    const brazo = sit && st.pose === "brazoAlzado";
    const working =
      sit && !sofa && (status === "working" || status === "collab");
    const thinking = sit && !sofa && status === "thinking";
    const walk = !sit && st.moving;

    // Vaqti-vaqti bilan cho'zilish — faqat HAQIQIY bo'sh (idle) turganда
    // (ishlayotgan yordamchi subagentlar cho'zilmasin).
    const standingIdle = !sit && !st.moving && status === "idle" && !rm;
    if (standingIdle) {
      if (stretchLeft.current <= 0) {
        stretchCd.current -= dt;
        if (stretchCd.current <= 0) {
          stretchLeft.current = 1.7;
          stretchCd.current = 10 + Math.random() * 14;
        }
      } else {
        stretchLeft.current -= dt;
      }
    } else {
      stretchLeft.current = 0;
    }
    const stretching = stretchLeft.current > 0;

    // ── Qadam fazasi — MASOFAга bog'liq (oyoq sirg'anmaydi) + silliq kirish ──
    const spd = st.speed ?? 0;
    walkPhase.current += (spd / 0.34) * Math.PI * dt; // ~0.34m qadam = yarim sikl
    walkBlend.current = damp(walkBlend.current, walk ? 1 : 0, 9, dt);
    const wp = walkPhase.current,
      wb = walkBlend.current;
    const gait = Math.sin(wp); // asosiy qadam sinusi
    const gaitC = Math.cos(wp);

    // Tos balandligi — son TIK bo'lganda (mid-stance) eng baland; amplituda wb bilan.
    const pelvisY = sit
      ? sofa
        ? 0.5
        : 0.55
      : 0.92 + Math.abs(gaitC) * 0.03 * wb;
    if (bodyRef.current)
      bodyRef.current.position.y = damp(
        bodyRef.current.position.y,
        pelvisY,
        12,
        dt,
      );
    // Status halqasi — o'tirganda bosh pastga tushadi, halqa ham unga ergashadi.
    if (ringRef.current)
      ringRef.current.position.y = damp(
        ringRef.current.position.y,
        sit ? 1.42 : 1.75,
        12,
        dt,
      );

    // Oyoqlar (son + tizza + to'piq) — qadam fazasidan, wb bilan silliq
    const swing = gait * 0.6 * wb;
    const kneeSwingL = Math.max(0, gait) * 0.55 * wb; // ko'targanda tizza bukiladi
    const kneeSwingR = Math.max(0, -gait) * 0.55 * wb;
    if (hipL.current)
      hipL.current.rotation.x = damp(
        hipL.current.rotation.x,
        sit ? (sofa ? 1.2 : 1.5) : swing,
        12,
        dt,
      );
    if (hipR.current)
      hipR.current.rotation.x = damp(
        hipR.current.rotation.x,
        sit ? (sofa ? 1.2 : 1.5) : -swing,
        12,
        dt,
      );
    if (kneeL.current)
      kneeL.current.rotation.x = damp(
        kneeL.current.rotation.x,
        sit ? (sofa ? -0.95 : -1.5) : kneeSwingL + 0.02,
        12,
        dt,
      );
    if (kneeR.current)
      kneeR.current.rotation.x = damp(
        kneeR.current.rotation.x,
        sit ? (sofa ? -0.95 : -1.5) : kneeSwingR + 0.02,
        12,
        dt,
      );
    // To'piq — oyoq ko'tarilganda tumshuq yuqori (dorsifleksiya), bosganda tekis
    if (ankleL.current)
      ankleL.current.rotation.x = damp(
        ankleL.current.rotation.x,
        sit ? 0.5 : -kneeSwingL * 0.7,
        10,
        dt,
      );
    if (ankleR.current)
      ankleR.current.rotation.x = damp(
        ankleR.current.rotation.x,
        sit ? 0.5 : -kneeSwingR * 0.7,
        10,
        dt,
      );

    // Yuqori tana engashishi + NAFAS OLISH (ko'krak ko'tarilib-tushadi)
    let lean = 0.03;
    if (stretching)
      lean = -0.22; // orqaga cho'zilish
    else if (sofa)
      lean = -0.3; // relaxed, leaning back on the sofa
    else if (working) lean = 0.2 + Math.sin(tt * 9) * 0.012;
    else if (thinking) lean = -0.04;
    else if (walk) lean = 0.11; // yurganda oldinga engashadi
    // Nafas — ikki nomutanosib chastota (mexanik takror ko'rinmasin)
    const breathe =
      1 +
      Math.sin(tt * (walk ? 5 : working ? 3.5 : 1.9)) *
        (walk ? 0.014 : 0.024) *
        (1 + 0.3 * Math.sin(tt * 0.29));
    if (upperRef.current) {
      upperRef.current.rotation.x = damp(
        upperRef.current.rotation.x,
        lean,
        7,
        dt,
      );
      upperRef.current.scale.y = damp(upperRef.current.scale.y, breathe, 6, dt);
      // Yelka gavda bilan qarama-qarshi buriladi (yurish tabiiyroq)
      upperRef.current.rotation.y = damp(
        upperRef.current.rotation.y,
        -gait * 0.18 * wb,
        8,
        dt,
      );
    }

    // Bosh — nod/tilt + vaqti-vaqti bilan atrofga QARASH (yaw)
    let nod = 0,
      tilt = 0;
    if (stretching)
      nod = -0.3; // yuqoriga qaraydi
    else if (thinking) {
      tilt = 0.2;
      nod = -0.06;
    } else if (working) nod = 0.2 + Math.sin(tt * 4.5) * 0.03;
    else if (sofa) nod = -0.12;
    else if (brazo) nod = -0.05;
    else if (status === "review") nod = 0.14;
    // Bo'sh/o'ylanayotganда gohida yon-yonga qaraydi. Faol rollar (yuqori energiya)
    // tez-tez va kengroq qaraydi; xotirjam olimlar kamroq.
    if (!working && !rm) {
      glanceCd.current -= dt;
      if (glanceCd.current <= 0) {
        headYaw.current = (Math.random() - 0.5) * 0.7 * (0.7 + 0.3 * en);
        glanceCd.current = (2.5 + Math.random() * 4) / en;
      }
    } else headYaw.current = 0;
    if (headRef.current) {
      headRef.current.rotation.x = damp(
        headRef.current.rotation.x,
        nod + Math.sin(tt * 1.6) * 0.02 + Math.sin(tt * 0.37) * 0.015,
        7,
        dt,
      );
      headRef.current.rotation.z = damp(
        headRef.current.rotation.z,
        tilt,
        6,
        dt,
      );
      headRef.current.rotation.y = damp(
        headRef.current.rotation.y,
        headYaw.current + Math.sin(tt * 0.5) * 0.03,
        5,
        dt,
      );
    }

    // Ko'z pirpirash — har ~2-6s tez yumilib ochiladi (eng kuchli "tirik" belgisi)
    if (rm) {
      blinkLeft.current = 0; // kamaytirilgan harakat — ko'z ochiq turadi
    } else if (blinkLeft.current <= 0) {
      blinkCd.current -= dt;
      if (blinkCd.current <= 0) {
        blinkLeft.current = 0.12;
        blinkCd.current = 2 + Math.random() * 5;
      }
    } else {
      blinkLeft.current -= dt;
    }
    if (eyesRef.current) {
      const bl = blinkLeft.current;
      // 0.12s ичида: yopil (0→~0.06s) → och. sinus bilan silliq.
      const openY =
        bl > 0
          ? Math.max(0.08, 1 - Math.sin((1 - bl / 0.12) * Math.PI) * 0.95)
          : 1;
      eyesRef.current.scale.y = openY;
    }

    // Yelka + TIRSAK — o'tirganda yozish (tirsak bukilgan), o'ylashda qo'l iyakka
    // (tirsak katta bukiladi — endi haqiqiy), cho'zilish, yurganda tebranish.
    const armSwing = gait * 0.5 * wb;
    let shTL: number, shTR: number, elTL: number, elTR: number;
    if (stretching) {
      shTL = -2.6;
      shTR = -2.7;
      elTL = 0.15;
      elTR = 0.15; // qo'llar bosh uzra
    } else if (sofa) {
      shTL = 0.35;
      shTR = 0.35;
      elTL = 0.55;
      elTR = 0.55; // hands resting on the lap
    } else if (brazo) {
      // Asks for permission: right arm up while it lasts (a slight sway).
      shTL = 0.5;
      elTL = 0.22;
      shTR = -2.85 + Math.sin(tt * 2.2) * 0.05;
      elTR = 0.12;
    } else if (sit && thinking) {
      shTL = 0.5;
      elTL = 0.25;
      shTR = 1.2 + Math.sin(tt * 1.4) * 0.04;
      elTR = 1.7; // o'ng qo'l iyakka (tirsak bukilgan)
    } else if (sit) {
      const tapL = working ? Math.max(0, Math.sin(tt * 11)) * 0.25 : 0;
      const tapR = working ? Math.max(0, Math.sin(tt * 11 + 1.6)) * 0.25 : 0;
      shTL = working ? 0.95 + tapL : 0.5;
      shTR = working ? 0.95 + tapR : 0.5;
      elTL = working ? 0.7 + tapL : 0.22; // yozganda tirsak bukilgan
      elTR = working ? 0.7 + tapR : 0.22;
    } else {
      shTL = -armSwing;
      shTR = armSwing;
      elTL = 0.2 + Math.abs(armSwing) * 0.4;
      elTR = elTL; // yurganda passiv bukilish
    }
    if (shoL.current)
      shoL.current.rotation.x = damp(shoL.current.rotation.x, shTL, 10, dt);
    if (shoR.current)
      shoR.current.rotation.x = damp(shoR.current.rotation.x, shTR, 10, dt);
    if (elbowL.current)
      elbowL.current.rotation.x = damp(elbowL.current.rotation.x, elTL, 10, dt);
    if (elbowR.current)
      elbowR.current.rotation.x = damp(elbowR.current.rotation.x, elTR, 10, dt);

    if (rootRef.current) {
      // yurganda tabiiy yon-tebranish, turganda nozik chayqalish, blocked'da asabiy
      const sway =
        status === "blocked"
          ? Math.sin(tt * 20) * 0.02
          : walk
            ? gaitC * 0.028 * wb
            : Math.sin(tt * 0.7) * 0.01;
      rootRef.current.rotation.z = damp(
        rootRef.current.rotation.z,
        sway,
        walk ? 9 : 5,
        dt,
      );
    }
  });

  const bottomMat = cloth(s.bottom),
    topMat = cloth(s.top),
    shoeMat = cloth(s.shoes);

  // Oyoq (son + tizza + boldir + TO'PIQ + poyabzal)
  const leg = (
    x: number,
    hipRef: React.RefObject<THREE.Group | null>,
    kneeRef: React.RefObject<THREE.Group | null>,
    ankleRef: React.RefObject<THREE.Group | null>,
  ) => (
    <group ref={hipRef} position={[x, 0, 0]}>
      <VB p={[0, -0.2, 0]} s={[0.13, 0.42, 0.14]} m={bottomMat} />
      <group ref={kneeRef} position={[0, -0.4, 0]}>
        <VB p={[0, -0.2, 0]} s={[0.12, 0.42, 0.12]} m={bottomMat} />
        {/* to'piq pivotда poyabzal — yurganda tumshuq ko'tariladi, tekis bosadi */}
        <group ref={ankleRef} position={[0, -0.42, 0]}>
          <VB p={[0, 0, -0.05]} s={[0.13, 0.1, 0.26]} m={shoeMat} />
        </group>
      </group>
    </group>
  );

  // Qo'l (yelka pivot → TIRSAK → bilak + kaft)
  const arm = (
    x: number,
    shoRef: React.RefObject<THREE.Group | null>,
    elbowRef: React.RefObject<THREE.Group | null>,
  ) => (
    <group ref={shoRef} position={[x, 0.28, 0]}>
      <VB p={[0, -0.13, 0]} s={[0.1, 0.26, 0.1]} m={topMat} />
      <group ref={elbowRef} position={[0, -0.26, 0]}>
        <VB p={[0, -0.06, 0.02]} s={[0.09, 0.24, 0.09]} m={topMat} />
        <VB p={[0, -0.2, 0.03]} s={[0.09, 0.08, 0.09]} m={skin} />
      </group>
    </group>
  );

  return (
    <group ref={rootRef}>
      <group ref={bodyRef} position={[0, 0.55, 0]}>
        {/* Tos */}
        <VB p={[0, 0, 0]} s={[0.34, 0.18, 0.26]} m={bottomMat} cast />
        {/* Oyoqlar (tos pastidan) */}
        {leg(-0.09, hipL, kneeL, ankleL)}
        {leg(0.09, hipR, kneeR, ankleR)}

        {/* Yuqori tana */}
        <group ref={upperRef} position={[0, 0.09, 0]}>
          <VB p={[0, 0.22, 0]} s={[0.36, 0.4, 0.24]} m={topMat} cast />
          {arm(-0.23, shoL, elbowL)}
          {arm(0.23, shoR, elbowR)}
          <VB p={[0, 0.45, 0]} s={[0.1, 0.08, 0.1]} m={skin} />
          <group ref={headRef} position={[0, 0.62, 0]}>
            <VB s={[0.3, 0.3, 0.3]} m={skin} cast />
            {/* Yuz tafsilotlari (ko'z/burun/quloq/aksessuar) — faqat high LOD.
                Kichik yordamchilar (low) uchun ko'rinmaydi → tashlab ketamiz. */}
            {!lod && (
              <>
                {/* ko'zlar — eyesRef guruhда (y=0.025 markaz) → pirpiraganda joyida yumiladi */}
                <group ref={eyesRef} position={[0, 0.025, 0]}>
                  {[-0.07, 0.07].map((x) => (
                    <group key={x} position={[x, 0, -0.151]}>
                      <VB s={[0.05, 0.055, 0.02]} m={EYE_WHITE} cast={false} />
                      <VB
                        p={[0, 0, -0.012]}
                        s={[0.025, 0.03, 0.01]}
                        m={EYE_PUPIL}
                        cast={false}
                      />
                    </group>
                  ))}
                </group>
                <VB
                  p={[0, -0.03, -0.155]}
                  s={[0.04, 0.05, 0.03]}
                  m={skin}
                  cast={false}
                />
                {[-0.157, 0.157].map((x) => (
                  <VB
                    key={x}
                    p={[x, 0.0, 0.01]}
                    s={[0.03, 0.08, 0.08]}
                    m={skin}
                  />
                ))}
              </>
            )}
            <Hair style={s.hairStyle} color={s.hair} />
            {!lod && s.accessory && <Accessory type={s.accessory} />}
          </group>
        </group>
      </group>

      {/* Holat halqasi — geometriya ulashilgan, material status rangi bo'yicha keshlangan */}
      <mesh
        ref={ringRef}
        position={[0, 1.75, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
        geometry={RING_GEO}
        material={basicMat(STATUS_COLOR[status], {
          transparent: true,
          opacity: 0.9,
          side: THREE.DoubleSide,
        })}
      />
    </group>
  );
}
