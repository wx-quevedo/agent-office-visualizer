import * as THREE from "three";

// ── Umumiy ko'rinish-frustumi (perf culling) ─────────────────────────
// Har freym BIR marta yangilanadi (App'da), keyin har agent/o'simlik o'zining
// KOSMETIK useFrame'ini ekrandan tashqarida bo'lsa o'tkazib yuboradi. Bu faqat
// vizual animatsiyaga taalluqli — HARAKAT/navigatsiya bunga bog'liq EMAS.
// Iso (ortho) ham FPV (perspective) uchun ham to'g'ri ishlaydi.

const _frustum = new THREE.Frustum();
const _mat = new THREE.Matrix4();
const _sphere = new THREE.Sphere(new THREE.Vector3(), 1.4); // agent gabariti + zaxira
const _v = new THREE.Vector3();
let _ready = false;

export function updateFrustum(camera: THREE.Camera): void {
  _mat.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse);
  _frustum.setFromProjectionMatrix(_mat);
  _ready = true;
}

/** (x,y,z) atrofidagi ~1.4 radiusli shar frustumга tegadimi? Tayyor bo'lmasa true. */
export function visiblePoint(x: number, y: number, z: number): boolean {
  if (!_ready) return true;
  _sphere.center.set(x, y, z);
  return _frustum.intersectsSphere(_sphere);
}

/** Obyekt (agent guruhi) ko'rinадими? Dunyo-pozitsiyasidan (y=0.9 markaz). */
export function visibleObject(obj: THREE.Object3D): boolean {
  if (!_ready) return true;
  obj.getWorldPosition(_v);
  _sphere.center.set(_v.x, 0.9, _v.z);
  return _frustum.intersectsSphere(_sphere);
}
