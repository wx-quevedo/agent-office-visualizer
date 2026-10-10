/**
 * Seats by project (Cabinas por proyecto, Estudio con jardín). Pure logic,
 * tested in tests/entornos.test.ts.
 *
 * Rules: an agent keeps its desk while it exists. A new agent sits in a group
 * (cabin, island) of its project when there is room; otherwise, if its project
 * already sits in the general group, there; otherwise its project gets a free
 * group of its own when it has enough agents (umbralPropio) and free groups
 * remain (reservaGeneral); otherwise the general group. A group belongs to its
 * project while it has agents (closed desks that are kept count too).
 */

import { GRUPO_GENERAL, type Agrupacion } from "./tipos";

export interface AsignacionGrupos {
  puestos: Record<string, number>;
  /** Owner of each used group: project name or GRUPO_GENERAL. */
  duenos: Record<number, string>;
}

export function asignarPorProyecto(
  prev: Record<string, number>,
  lista: Array<{ id: string; proyecto: string }>,
  duenosPrev: Record<number, string>,
  agr: Agrupacion,
): AsignacionGrupos {
  const puestos: Record<string, number> = {};
  const usados = new Map<number, Set<number>>(); // group → places in use
  const extras = new Set<number>(); // seats past the groups (general)
  const ocupar = (asiento: number) => {
    const { g, k } = agr.grupoDe(asiento);
    if (g >= agr.grupos) {
      extras.add(asiento);
      return;
    }
    if (!usados.has(g)) usados.set(g, new Set());
    usados.get(g)!.add(k);
  };
  for (const { id } of lista) {
    if (prev[id] !== undefined) {
      puestos[id] = prev[id];
      ocupar(prev[id]);
    }
  }

  // Owners: only groups that still have agents keep theirs.
  const duenos: Record<number, string> = {};
  for (const [g, dueno] of Object.entries(duenosPrev)) {
    if (usados.has(Number(g))) duenos[Number(g)] = dueno;
  }
  for (const { id, proyecto } of lista) {
    if (puestos[id] === undefined) continue;
    const { g } = agr.grupoDe(puestos[id]);
    if (g < agr.grupos && duenos[g] === undefined) duenos[g] = proyecto;
  }
  if (agr.generalFijo !== null) duenos[agr.generalFijo] = GRUPO_GENERAL;

  const cuenta: Record<string, number> = {};
  for (const { proyecto } of lista)
    cuenta[proyecto] = (cuenta[proyecto] ?? 0) + 1;
  // Projects that already have agents in the general group stay together there.
  const enGeneral = new Set<string>();
  for (const { id, proyecto } of lista) {
    if (puestos[id] === undefined) continue;
    const { g } = agr.grupoDe(puestos[id]);
    if (g >= agr.grupos || duenos[g] === GRUPO_GENERAL) enGeneral.add(proyecto);
  }

  const libreEn = (g: number): number | null => {
    const cap = agr.capacidad(g);
    const set = usados.get(g) ?? new Set<number>();
    for (let k = 0; k < cap; k++) if (!set.has(k)) return k;
    return null;
  };
  const gruposDe = (dueno: string) =>
    Array.from({ length: agr.grupos }, (_, g) => g).filter(
      (g) => duenos[g] === dueno,
    );
  const libres = () =>
    Array.from({ length: agr.grupos }, (_, g) => g).filter(
      (g) => duenos[g] === undefined,
    );
  const sentarEn = (gs: number[]): number | null => {
    for (const g of gs) {
      const k = libreEn(g);
      if (k !== null) return agr.asiento(g, k);
    }
    return null;
  };
  const reclamar = (dueno: string): number | null => {
    const g = libres()[0];
    if (g === undefined) return null;
    duenos[g] = dueno;
    return agr.asiento(g, 0);
  };

  // New agents, grouped by project (first appearance order).
  const orden = new Map<string, number>();
  lista.forEach(({ proyecto }, i) => {
    if (!orden.has(proyecto)) orden.set(proyecto, i);
  });
  const nuevos = lista
    .filter(({ id }) => puestos[id] === undefined)
    .sort((a, b) => orden.get(a.proyecto)! - orden.get(b.proyecto)!);

  for (const { id, proyecto } of nuevos) {
    let asiento = sentarEn(gruposDe(proyecto));
    if (asiento === null && enGeneral.has(proyecto))
      asiento = sentarEn(gruposDe(GRUPO_GENERAL));
    if (
      asiento === null &&
      cuenta[proyecto] >= agr.umbralPropio &&
      libres().length > agr.reservaGeneral
    )
      asiento = reclamar(proyecto);
    if (asiento === null) {
      asiento = sentarEn(gruposDe(GRUPO_GENERAL)) ?? reclamar(GRUPO_GENERAL);
      if (asiento !== null) enGeneral.add(proyecto);
    }
    // Everything taken: any free place, then extra desks past the groups.
    if (asiento === null)
      asiento = sentarEn(Array.from({ length: agr.grupos }, (_, g) => g));
    if (asiento === null) {
      let i = agr.asiento(agr.grupos, 0);
      while (extras.has(i)) i++;
      asiento = i;
      enGeneral.add(proyecto);
    }
    puestos[id] = asiento;
    ocupar(asiento);
  }
  return { puestos, duenos };
}
