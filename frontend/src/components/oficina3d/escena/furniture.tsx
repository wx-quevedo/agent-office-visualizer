import type { JSX } from "react";
import { defMueble, huella, MUEBLES, type DefMueble } from "../muebles";
import {
  Bookshelf,
  CoffeeTable,
  EmptyDesk,
  MeetingTable,
  Plant,
  Sofa,
  StandingLamp,
} from "./OfficeDecor";

// ── Placeable furniture drawings (adapted from Agent Office 3D, MIT) ──
// Types, names and sizes live in ../muebles.ts (no three.js, testable).

export interface FurnitureDef extends DefMueble {
  render: () => JSX.Element;
}

const DIBUJOS: Record<string, () => JSX.Element> = {
  plant: () => <Plant p={[0, 0, 0]} scale={1.1} />,
  desk: () => <EmptyDesk p={[0, 0, 0]} />,
  sofa: () => <Sofa p={[0, 0, 0]} />,
  coffee: () => <CoffeeTable p={[0, 0, 0]} />,
  meeting: () => <MeetingTable p={[0, 0, 0]} r={0.9} />,
  shelf: () => <Bookshelf p={[0, 0, 0]} />,
  lamp: () => <StandingLamp p={[0, 0, 0]} />,
};

export const CATALOGO: FurnitureDef[] = MUEBLES.map((m) => ({
  ...m,
  render: DIBUJOS[m.type],
}));

export function furnitureDef(type: string): FurnitureDef | undefined {
  const d = defMueble(type);
  return d && DIBUJOS[type] ? { ...d, render: DIBUJOS[type] } : undefined;
}

/** Rotated AABB half sizes of a placed item (collision). */
export function footprint(
  type: string,
  ry: number,
): { hx: number; hz: number } {
  return huella(type, ry);
}
