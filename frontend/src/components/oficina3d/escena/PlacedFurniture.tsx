import { useEffect, useMemo } from "react";
import { bloqueos } from "../caminos";
import { useLayout } from "../distribucion";
import { useEditor } from "../editor";
import { furnitureDef } from "./furniture";

// ── Placed furniture and the editor on the floor (adapted from Agent Office 3D, MIT) ──
// Edit mode: a click on the floor places the chosen piece, a piece is dragged
// on the 0.5 m grid, the selected one has a dark ring, and a piece that blocks
// a path or a desk has a red ring.

const ANILLO_SELECCION = "#111111";
const ANILLO_BLOQUEO = "#d33a2c";

export default function PlacedFurniture() {
  const items = useLayout((s) => s.items);
  const activo = useEditor((s) => s.activo);
  const seleccion = useEditor((s) => s.seleccion);
  const paleta = useEditor((s) => s.paleta);
  const arrastrando = useEditor((s) => s.arrastrando);
  const tapan = useMemo(
    () =>
      activo ? new Set(bloqueos(items).map((b) => b.id)) : new Set<string>(),
    [activo, items],
  );

  // The drag ends wherever the button is released (also outside the floor).
  useEffect(() => {
    if (!arrastrando) return;
    const soltar = () => useEditor.getState().terminarArrastre();
    window.addEventListener("pointerup", soltar);
    return () => window.removeEventListener("pointerup", soltar);
  }, [arrastrando]);

  return (
    <group>
      {activo && (
        <>
          <gridHelper
            args={[46, 92, "#9a9a9a", "#c8c8c8"]}
            position={[0, 0.035, 0]}
          />
          <mesh
            rotation={[-Math.PI / 2, 0, 0]}
            position={[0, 0.004, 0]}
            onClick={(e) => {
              e.stopPropagation();
              const ed = useEditor.getState();
              if (ed.arrastrando) return;
              if (ed.paleta) ed.colocar(e.point.x, e.point.z);
              else ed.seleccionar(null);
            }}
            onPointerMove={(e) => {
              if (useEditor.getState().arrastrando) {
                e.stopPropagation();
                useEditor.getState().arrastrar(e.point.x, e.point.z);
              }
            }}
          >
            <planeGeometry args={[46, 32]} />
            <meshBasicMaterial transparent opacity={0} depthWrite={false} />
          </mesh>
        </>
      )}

      {items.map((it) => {
        const def = furnitureDef(it.type);
        if (!def) return null;
        const sel = activo && seleccion === it.id;
        const tapa = tapan.has(it.id);
        const rad = Math.max(def.hx, def.hz);
        return (
          <group
            key={it.id}
            position={[it.x, 0, it.z]}
            rotation={[0, it.ry, 0]}
            onPointerDown={
              activo && !paleta
                ? (e) => {
                    e.stopPropagation();
                    useEditor.getState().empezarArrastre(it.id);
                  }
                : undefined
            }
          >
            {def.render()}
            {(sel || tapa) && (
              <mesh position={[0, 0.03, 0]} rotation={[-Math.PI / 2, 0, 0]}>
                <ringGeometry
                  args={[rad + 0.14, rad + (sel ? 0.32 : 0.24), 32]}
                />
                <meshBasicMaterial
                  color={tapa ? ANILLO_BLOQUEO : ANILLO_SELECCION}
                  transparent
                  opacity={0.95}
                />
              </mesh>
            )}
          </group>
        );
      })}
    </group>
  );
}
