import * as THREE from "three";

// ── Ulashilgan geometriya + material keshi ───────────────────
// Muammo (M0 baseline): har <boxGeometry>/<meshStandardMaterial> YANGI obyekt
// yaratardi — 20 agentda 2118 geometriya + 2119 material. Bu yerdagi keshlar
// bir xillarni bitta obyektga jamlaydi (ko'rinish o'zgarmaydi, xotira/holat
// keskin kamayadi). Foydalanish: <mesh geometry={UNIT_BOX} material={stdMat(..)}
// scale={[w,h,d]} /> — bola sifatida <geometry>/<material> qo'ymaymiz.

/** Birlik kub (1×1×1) — mesh.scale bilan istalgan o'lchamga. Barcha qutilar shu. */
export const UNIT_BOX = new THREE.BoxGeometry(1, 1, 1);

/** Contact-shadow tekislik + yumshoq radial material (agent ostidа yerga bog'lash
 *  soyasi). Material LAZY yaratiladi (canvas faqat brauzerда, birinchi chaqiruvда). */
export const SHADOW_PLANE = new THREE.PlaneGeometry(1, 1);
let _shadowMat: THREE.MeshBasicMaterial | null = null;
export function contactShadowMat(): THREE.MeshBasicMaterial {
  if (_shadowMat) return _shadowMat;
  const cv = document.createElement("canvas");
  cv.width = cv.height = 64;
  const ctx = cv.getContext("2d")!;
  const g = ctx.createRadialGradient(32, 32, 2, 32, 32, 32);
  g.addColorStop(0, "rgba(0,0,0,0.4)");
  g.addColorStop(0.55, "rgba(0,0,0,0.2)");
  g.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 64, 64);
  _shadowMat = new THREE.MeshBasicMaterial({
    map: new THREE.CanvasTexture(cv),
    transparent: true,
    depthWrite: false,
  });
  return _shadowMat;
}

const stdCache = new Map<string, THREE.MeshStandardMaterial>();
const basicCache = new Map<string, THREE.MeshBasicMaterial>();
const cylCache = new Map<string, THREE.CylinderGeometry>();
const coneCache = new Map<string, THREE.ConeGeometry>();
const sphereCache = new Map<string, THREE.SphereGeometry>();

export interface StdOpts {
  roughness?: number;
  metalness?: number;
  emissive?: string;
  emissiveIntensity?: number;
  transparent?: boolean;
  opacity?: number;
}

/** Keshlangan MeshStandardMaterial (rang + parametrlar bo'yicha). */
export function stdMat(
  color: string,
  o: StdOpts = {},
): THREE.MeshStandardMaterial {
  const rough = o.roughness ?? 1;
  const metal = o.metalness ?? 0;
  const key = `${color}|${rough}|${metal}|${o.emissive ?? ""}|${o.emissiveIntensity ?? 1}|${o.transparent ? 1 : 0}|${o.opacity ?? 1}`;
  let m = stdCache.get(key);
  if (!m) {
    m = new THREE.MeshStandardMaterial({
      color,
      roughness: rough,
      metalness: metal,
    });
    if (o.emissive) {
      m.emissive = new THREE.Color(o.emissive);
      m.emissiveIntensity = o.emissiveIntensity ?? 1;
    }
    if (o.transparent) {
      m.transparent = true;
      m.opacity = o.opacity ?? 1;
    }
    stdCache.set(key, m);
  }
  return m;
}

export interface BasicOpts {
  transparent?: boolean;
  opacity?: number;
  blending?: THREE.Blending;
  side?: THREE.Side;
  toneMapped?: boolean;
}

/** Keshlangan MeshBasicMaterial (ekran/halo/halqa uchun). */
export function basicMat(
  color: string,
  o: BasicOpts = {},
): THREE.MeshBasicMaterial {
  const key = `${color}|${o.transparent ? 1 : 0}|${o.opacity ?? 1}|${o.blending ?? ""}|${o.side ?? ""}|${o.toneMapped === false ? 0 : 1}`;
  let m = basicCache.get(key);
  if (!m) {
    m = new THREE.MeshBasicMaterial({ color });
    if (o.transparent) {
      m.transparent = true;
      m.opacity = o.opacity ?? 1;
    }
    if (o.blending != null) m.blending = o.blending;
    if (o.side != null) m.side = o.side;
    if (o.toneMapped === false) m.toneMapped = false;
    basicCache.set(key, m);
  }
  return m;
}

/** Keshlangan silindr geometriyasi (radiuslar farq qilishi mumkin — kalitlab). */
export function cyl(
  rt: number,
  rb: number,
  h: number,
  seg = 8,
): THREE.CylinderGeometry {
  const key = `${rt}|${rb}|${h}|${seg}`;
  let g = cylCache.get(key);
  if (!g) {
    g = new THREE.CylinderGeometry(rt, rb, h, seg);
    cylCache.set(key, g);
  }
  return g;
}

export function cone(r: number, h: number, seg = 5): THREE.ConeGeometry {
  const key = `${r}|${h}|${seg}`;
  let g = coneCache.get(key);
  if (!g) {
    g = new THREE.ConeGeometry(r, h, seg);
    coneCache.set(key, g);
  }
  return g;
}

export function sphere(r: number, w = 8, h = 8): THREE.SphereGeometry {
  const key = `${r}|${w}|${h}`;
  let g = sphereCache.get(key);
  if (!g) {
    g = new THREE.SphereGeometry(r, w, h);
    sphereCache.set(key, g);
  }
  return g;
}
