import { useEffect, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import type * as THREE from "three";
import { useLayout } from "../distribucion";
import type { CameraMode } from "../store";
import { useDaylight } from "./daylight";

// ── Ofis xonasi — dollhouse (yopiq bino, iso'da near-devorlar yashirin) ──
export const ROOM = { W: 46, D: 32, WH: 3.4 };

// Rangni och/to'q qilish (mavzu devorlari uchun).
function shade(hex: string, amt: number): string {
  const n = parseInt(hex.replace("#", ""), 16);
  const cl = (v: number) => Math.max(0, Math.min(255, v));
  const r = cl(((n >> 16) & 255) + amt),
    g = cl(((n >> 8) & 255) + amt),
    b = cl((n & 255) + amt);
  return "#" + ((1 << 24) | (r << 16) | (g << 8) | b).toString(16).slice(1);
}

// Kun/tun yorug'ligi — parametrlar useDaylight store'dan, real soatдан ~30s'da
// yangilanadi (soat sekin o'zgargani uchun snap sezilmaydi). Fon rangi ham shundan.
function Daylight() {
  const params = useDaylight((s) => s.params);
  const refresh = useDaylight((s) => s.refresh);
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 30000);
    return () => clearInterval(t);
  }, [refresh]);
  return (
    <>
      <color attach="background" args={[params.sky]} />
      <ambientLight intensity={params.ambient} />
      <hemisphereLight args={["#ffffff", "#c9c2b2", params.hemi]} />
      <directionalLight
        position={[12, 20, 8]}
        intensity={params.dirI}
        color={params.dir}
        castShadow
        shadow-mapSize={[1024, 1024]}
        shadow-camera-left={-24}
        shadow-camera-right={24}
        shadow-camera-top={18}
        shadow-camera-bottom={-18}
        shadow-radius={4}
        shadow-normalBias={0.02}
        shadow-bias={-0.0002}
      />
      {/* Iliq qaytaruvchi nur (pol/devordan aks — CG "yassi" ko'rinishni yumshatadi) */}
      <directionalLight
        position={[-10, 6, -8]}
        intensity={params.dirI * 0.2}
        color="#ffe6c4"
      />
    </>
  );
}

// ── Dinamik devor shaffofligi (Sims/Habbo "dollhouse cutaway") ──────
// Kvadrat bino: 4 perimetr devor. Iso kamera aylanadi — QAYSI 2 devor kamera
// bilan ofis o'rtasi orasida qolsa (ya'ni bizga TASHQI yuzi qaragan), o'shalar
// shaffof bo'ladi (ichi ko'rinsin). Qolgan 2 devorning ICHKI yuzi bizga
// qaragani uchun ular QATTIQ fon bo'lib turadi. FPV'da hammasi zich.
const GHOST = 0.16; // ochiq (near) devor shaffofligi
const SOLID = 1.0; // yopiq (far) devor
// Shift butun ichkini QOPLAYDI — shuning uchun devor GHOST'idan pastroq (aks
// holda butun ofis xira ko'rinardi). Faqat "yopiq bino" hissi + lampalar joyi.
const CEIL_GHOST = 0.28;
const FADE = 7; // silliq o'tish oralig'i (kamera koordinatasi bo'yicha)
function smoothstep(e0: number, e1: number, x: number): number {
  const t = Math.max(0, Math.min(1, (x - e0) / (e1 - e0)));
  return t * t * (3 - 2 * t);
}
// openCoord > 0 → devorning tashqi yuzi kameraga qaragan (near) → shaffof.
function applyWall(
  m: THREE.MeshStandardMaterial | null,
  openCoord: number,
): void {
  if (!m) return;
  const t = smoothstep(-FADE, FADE, openCoord);
  const op = SOLID + (GHOST - SOLID) * t;
  m.opacity = op;
  const tr = op < 0.985;
  if (m.transparent !== tr) {
    m.transparent = tr;
    m.needsUpdate = true;
  } // toggle → recompile
  m.depthWrite = op > 0.6; // qattiq bo'lsa chuqurlik yozadi (fon), shaffofда yo'q
}

export default function Room({
  mode,
  ancho = ROOM.W,
  fondo = ROOM.D,
  piso = { x0: -15, x1: 15, z0: -7, z1: 7 },
}: {
  mode: CameraMode;
  /** Room size of the active environment (Original: 46 × 32). */
  ancho?: number;
  fondo?: number;
  /** Area painted with the floor colour of the theme (Original: 30 × 14 in the centre). */
  piso?: { x0: number; x1: number; z0: number; z1: number };
}) {
  const W = ancho;
  const D = fondo;
  const { WH } = ROOM;
  const fpv = mode === "fpv";
  const floorColor = useLayout((s) => s.floorColor);
  const wallColor = useLayout((s) => s.wallColor);
  const wallMat = wallColor ?? "#dcd3c2";
  // Yon devorlar biroz to'qroq (chuqurlik hissi) — mavzu rangidan hosila.
  const sideWall = wallColor ? shade(wallColor, -10) : "#d2c9b7";

  const backM = useRef<THREE.MeshStandardMaterial>(null);
  const frontM = useRef<THREE.MeshStandardMaterial>(null);
  const leftM = useRef<THREE.MeshStandardMaterial>(null);
  const rightM = useRef<THREE.MeshStandardMaterial>(null);
  const ceilM = useRef<THREE.MeshStandardMaterial>(null);

  useFrame(({ camera }) => {
    if (fpv) {
      for (const r of [backM, frontM, leftM, rightM]) {
        const m = r.current;
        if (m) {
          m.opacity = 1;
          m.transparent = false;
          m.depthWrite = true;
        }
      }
      // FPV'da ichkаridan yuqoriga qaralganда shift QATTIQ ko'rinsin.
      if (ceilM.current) {
        ceilM.current.opacity = 1;
        ceilM.current.transparent = false;
        ceilM.current.depthWrite = true;
      }
      return;
    }
    // Shift — iso'da kamera DOIM undan yuqorida (tashqi yuzi bizga qaragan) →
    // devorlardagi "near" holat kabi hamisha GHOST. Shunda ofis yopiq bino'dek
    // ko'rinadi va lampalar shiftga o'rnashadi, lekin ichi baribir ko'rinadi.
    if (ceilM.current) {
      ceilM.current.opacity = CEIL_GHOST;
      ceilM.current.transparent = true;
      ceilM.current.depthWrite = false;
    }
    const cx = camera.position.x,
      cz = camera.position.z;
    // Devor FAQAT kamera uning TASHQARISIGA (±D/2 / ±W/2) o'tганда shaffof
    // bo'ladi (tashqi yuzi ko'ringanда). Aks holda ichki yuzi ko'rinadi → qattiq
    // fon. Chegara 0'da EMAS, devor pozitsiyasida — shu bois face-on ko'rinishда
    // uzoq devorlar to'g'ri qattiq qoladi.
    applyWall(backM.current, -(cz + D / 2)); // orqa (z=-D/2): kamera z<-D/2 → shaffof
    applyWall(frontM.current, cz - D / 2); // old  (z=+D/2): kamera z>+D/2 → shaffof
    applyWall(leftM.current, -(cx + W / 2)); // chap (x=-W/2): kamera x<-W/2 → shaffof
    applyWall(rightM.current, cx - W / 2); // o'ng (x=+W/2): kamera x>+W/2 → shaffof
  });

  return (
    <group>
      {/* Yorug'lik — kun/tun sikliga bog'liq (Daylight). Soya-kamerasi butun
          xonani qamraydi (x=±23, z=±16 dan tashqaridagi mebel ham soya beradi). */}
      <Daylight />

      {/* Pol — z-fight bo'lmasin uchun markaziy zona polygonOffset bilan */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[W, D]} />
        <meshStandardMaterial
          color="#e9e2d2"
          roughness={0.68}
          metalness={0.04}
        />
      </mesh>
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[(piso.x0 + piso.x1) / 2, 0.012, (piso.z0 + piso.z1) / 2]}
        receiveShadow
      >
        <planeGeometry args={[piso.x1 - piso.x0, piso.z1 - piso.z0]} />
        <meshStandardMaterial
          color={floorColor ?? "#d8c7a8"}
          roughness={0.6}
          metalness={0.05}
          polygonOffset
          polygonOffsetFactor={-1}
          polygonOffsetUnits={-1}
        />
      </mesh>

      {/* ── Perimetr devorlar (4 tomon) — dinamik shaffoflik useFrame'da ── */}
      <mesh position={[0, WH / 2, -D / 2]} receiveShadow>
        <boxGeometry args={[W, WH, 0.3]} />
        <meshStandardMaterial
          ref={backM}
          color={wallMat}
          roughness={1}
          transparent
          opacity={SOLID}
        />
      </mesh>
      <mesh position={[0, WH / 2, D / 2]} receiveShadow>
        <boxGeometry args={[W, WH, 0.3]} />
        <meshStandardMaterial
          ref={frontM}
          color={wallMat}
          roughness={1}
          transparent
          opacity={GHOST}
          depthWrite={false}
        />
      </mesh>
      <mesh position={[-W / 2, WH / 2, 0]} receiveShadow>
        <boxGeometry args={[0.3, WH, D]} />
        <meshStandardMaterial
          ref={leftM}
          color={sideWall}
          roughness={1}
          transparent
          opacity={SOLID}
        />
      </mesh>
      <mesh position={[W / 2, WH / 2, 0]} receiveShadow>
        <boxGeometry args={[0.3, WH, D]} />
        <meshStandardMaterial
          ref={rightM}
          color={sideWall}
          roughness={1}
          transparent
          opacity={GHOST}
          depthWrite={false}
        />
      </mesh>

      {/* Shift (tepa yuza) — devorlar kabi dollhouse: iso'da GHOST (ichini
          ko'rasiz), FPV'da qattiq. raycast=null → butun ichkini qoplasa ham
          agent/stol bosishlariga xalaqit bermaydi (bosish undan o'tib ketadi). */}
      <mesh
        position={[0, WH, 0]}
        rotation={[Math.PI / 2, 0, 0]}
        raycast={() => null}
      >
        <planeGeometry args={[W, D]} />
        <meshStandardMaterial
          ref={ceilM}
          color="#eae4d6"
          roughness={1}
          side={2}
          transparent
          opacity={CEIL_GHOST}
          depthWrite={false}
        />
      </mesh>
    </group>
  );
}
