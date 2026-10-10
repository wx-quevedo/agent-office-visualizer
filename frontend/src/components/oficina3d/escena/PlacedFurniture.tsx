import { useLayout } from "../distribucion";
import { furnitureDef } from "./furniture";

// ── Furniture from distribucion.json (adapted from Agent Office 3D, MIT) ──
// Read-only: the placement/drag editor is not ported yet.

export default function PlacedFurniture() {
  const items = useLayout((s) => s.items);
  return (
    <group>
      {items.map((it) => {
        const def = furnitureDef(it.type);
        if (!def) return null;
        return (
          <group
            key={it.id}
            position={[it.x, 0, it.z]}
            rotation={[0, it.ry, 0]}
          >
            {def.render()}
          </group>
        );
      })}
    </group>
  );
}
