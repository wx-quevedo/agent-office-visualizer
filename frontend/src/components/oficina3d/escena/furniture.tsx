import type { JSX } from "react";
import {
  Bookshelf,
  CoffeeTable,
  EmptyDesk,
  MeetingTable,
  Plant,
  Sofa,
  StandingLamp,
} from "./OfficeDecor";

// ── Placeable furniture catalog (adapted from Agent Office 3D, MIT) ──
// Used by distribucion.json. The external JSON "packs" and the editor are not
// ported yet.

export interface FurnitureDef {
  type: string;
  label: string;
  /** Base half sizes (at ry=0), for the collision AABB. */
  hx: number;
  hz: number;
  render: () => JSX.Element;
}

const BUILTIN: FurnitureDef[] = [
  {
    type: "plant",
    label: "Planta",
    hx: 0.3,
    hz: 0.3,
    render: () => <Plant p={[0, 0, 0]} scale={1.1} />,
  },
  {
    type: "desk",
    label: "Escritorio",
    hx: 0.72,
    hz: 0.42,
    render: () => <EmptyDesk p={[0, 0, 0]} />,
  },
  {
    type: "sofa",
    label: "Sofá",
    hx: 1.12,
    hz: 0.48,
    render: () => <Sofa p={[0, 0, 0]} />,
  },
  {
    type: "coffee",
    label: "Mesa de centro",
    hx: 0.56,
    hz: 0.32,
    render: () => <CoffeeTable p={[0, 0, 0]} />,
  },
  {
    type: "meeting",
    label: "Mesa de reuniones",
    hx: 1.1,
    hz: 1.1,
    render: () => <MeetingTable p={[0, 0, 0]} r={0.9} />,
  },
  {
    type: "shelf",
    label: "Librero",
    hx: 0.62,
    hz: 0.2,
    render: () => <Bookshelf p={[0, 0, 0]} />,
  },
  {
    type: "lamp",
    label: "Lámpara",
    hx: 0.24,
    hz: 0.24,
    render: () => <StandingLamp p={[0, 0, 0]} />,
  },
];

const BY_TYPE: Record<string, FurnitureDef> = Object.fromEntries(
  BUILTIN.map((d) => [d.type, d]),
);

export function furnitureDef(type: string): FurnitureDef | undefined {
  return BY_TYPE[type];
}

/** Rotated AABB half sizes of a placed item (collision). */
export function footprint(
  type: string,
  ry: number,
): { hx: number; hz: number } {
  const d = furnitureDef(type);
  if (!d) return { hx: 0.3, hz: 0.3 };
  const c = Math.abs(Math.cos(ry));
  const s = Math.abs(Math.sin(ry));
  return { hx: d.hx * c + d.hz * s + 0.05, hz: d.hx * s + d.hz * c + 0.05 };
}
