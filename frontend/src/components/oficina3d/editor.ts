import { create } from "zustand";
import { bloqueos, type Bloqueo } from "./caminos";
import {
  distribucionActual,
  guardarDistribucion,
  useLayout,
  type Distribucion,
  type PlacedItem,
} from "./distribucion";
import { LIMITE_X, LIMITE_Z } from "./muebles";
import { temaPorClave } from "./temas";

// ── Office editor (adapted from layoutStore of Agent Office 3D, MIT) ──
// Edits the live layout (useLayout) so the scene shows every change; a photo
// taken when entering is restored by "Cancelar". Grid of 0.5 m, rotation in
// 45° steps, undo/redo of 50 steps. Saving goes to the backend of this copy
// and is refused while a piece blocks a path or a desk (caminos.ts).

export const CUADRICULA = 0.5;
const MAX_HISTORIA = 50;

export const ajustar = (v: number, limite: number): number =>
  Math.max(-limite, Math.min(limite, Math.round(v / CUADRICULA) * CUADRICULA));

let contador = 0;
const nuevoId = () => `m${Date.now().toString(36)}${(contador++).toString(36)}`;

type Foto = Distribucion;

interface EditorState {
  activo: boolean;
  /** Furniture type to place with the next click on the floor. */
  paleta: string | null;
  seleccion: string | null;
  arrastrando: string | null;
  inicioArrastre: Foto | null;
  original: Foto | null;
  pasado: Foto[];
  futuro: Foto[];
  guardando: boolean;
  mensaje: string | null;

  entrar(): void;
  cancelar(): void;
  guardar(): Promise<boolean>;
  elegirPaleta(type: string | null): void;
  seleccionar(id: string | null): void;
  colocar(x: number, z: number): void;
  empezarArrastre(id: string): void;
  arrastrar(x: number, z: number): void;
  terminarArrastre(): void;
  rotar(id?: string): void;
  borrar(id?: string): void;
  aplicarTema(key: string): void;
  importar(d: Distribucion): void;
  deshacer(): void;
  rehacer(): void;
}

function aplicar(f: Foto): void {
  useLayout.getState().cargar(f);
}

export const useEditor = create<EditorState>()((set, get) => {
  /** Applies a change and records the previous state for undo. */
  const cambiar = (f: Foto) => {
    const antes = distribucionActual();
    set((s) => ({
      pasado: [...s.pasado, antes].slice(-MAX_HISTORIA),
      futuro: [],
      mensaje: null,
    }));
    aplicar(f);
  };
  const conItems = (items: PlacedItem[]): Foto => ({
    ...distribucionActual(),
    items,
  });

  return {
    activo: false,
    paleta: null,
    seleccion: null,
    arrastrando: null,
    inicioArrastre: null,
    original: null,
    pasado: [],
    futuro: [],
    guardando: false,
    mensaje: null,

    entrar() {
      set({
        activo: true,
        original: distribucionActual(),
        pasado: [],
        futuro: [],
        paleta: null,
        seleccion: null,
        mensaje: null,
      });
    },
    cancelar() {
      const o = get().original;
      if (o) aplicar(o);
      set({
        activo: false,
        original: null,
        paleta: null,
        seleccion: null,
        arrastrando: null,
        mensaje: null,
      });
    },
    async guardar() {
      const d = distribucionActual();
      if (bloqueos(d.items).length > 0) {
        set({
          mensaje:
            "Hay muebles que tapan un camino o un escritorio: muévelos antes de guardar.",
        });
        return false;
      }
      set({ guardando: true, mensaje: null });
      const error = await guardarDistribucion(d);
      if (error) {
        set({ guardando: false, mensaje: error });
        return false;
      }
      useLayout.setState({ origen: "guardada" });
      set({
        guardando: false,
        activo: false,
        original: null,
        paleta: null,
        seleccion: null,
      });
      return true;
    },
    elegirPaleta(type) {
      set({ paleta: type, seleccion: null });
    },
    seleccionar(id) {
      set({ seleccion: id, paleta: null });
    },
    colocar(x, z) {
      const type = get().paleta;
      if (!type) return;
      const it: PlacedItem = {
        id: nuevoId(),
        type,
        x: ajustar(x, LIMITE_X),
        z: ajustar(z, LIMITE_Z),
        ry: 0,
      };
      cambiar(conItems([...useLayout.getState().items, it]));
      set({ seleccion: it.id });
    },
    empezarArrastre(id) {
      set({
        arrastrando: id,
        seleccion: id,
        paleta: null,
        inicioArrastre: distribucionActual(),
      });
    },
    arrastrar(x, z) {
      const id = get().arrastrando;
      if (!id) return;
      const items = useLayout
        .getState()
        .items.map((it) =>
          it.id === id
            ? { ...it, x: ajustar(x, LIMITE_X), z: ajustar(z, LIMITE_Z) }
            : it,
        );
      aplicar(conItems(items)); // no history while dragging
    },
    terminarArrastre() {
      const { arrastrando, inicioArrastre } = get();
      set({ arrastrando: null, inicioArrastre: null });
      if (!arrastrando || !inicioArrastre) return;
      const antes = inicioArrastre.items.find((it) => it.id === arrastrando);
      const ahora = useLayout
        .getState()
        .items.find((it) => it.id === arrastrando);
      if (antes && ahora && (antes.x !== ahora.x || antes.z !== ahora.z)) {
        set((s) => ({
          pasado: [...s.pasado, inicioArrastre].slice(-MAX_HISTORIA),
          futuro: [],
          mensaje: null,
        }));
      }
    },
    rotar(id) {
      const objetivo = id ?? get().seleccion;
      if (!objetivo) return;
      const paso = Math.PI / 4;
      cambiar(
        conItems(
          useLayout
            .getState()
            .items.map((it) =>
              it.id === objetivo
                ? { ...it, ry: ((Math.round(it.ry / paso) + 1) % 8) * paso }
                : it,
            ),
        ),
      );
    },
    borrar(id) {
      const objetivo = id ?? get().seleccion;
      if (!objetivo) return;
      cambiar(
        conItems(useLayout.getState().items.filter((it) => it.id !== objetivo)),
      );
      set({ seleccion: null });
    },
    aplicarTema(key) {
      const t = temaPorClave(key);
      cambiar({
        ...distribucionActual(),
        tema: t.key,
        floorColor: t.floor,
        wallColor: t.wall,
      });
    },
    importar(d) {
      cambiar({ ...d, version: 1 });
      set({
        seleccion: null,
        mensaje: "Distribución importada: revisa y presiona Guardar.",
      });
    },
    deshacer() {
      const { pasado } = get();
      if (!pasado.length) return;
      const previo = pasado[pasado.length - 1];
      set((s) => ({
        pasado: s.pasado.slice(0, -1),
        futuro: [distribucionActual(), ...s.futuro].slice(0, MAX_HISTORIA),
        seleccion: null,
      }));
      aplicar(previo);
    },
    rehacer() {
      const { futuro } = get();
      if (!futuro.length) return;
      const siguiente = futuro[0];
      set((s) => ({
        futuro: s.futuro.slice(1),
        pasado: [...s.pasado, distribucionActual()].slice(-MAX_HISTORIA),
        seleccion: null,
      }));
      aplicar(siguiente);
    },
  };
});

/** Blocking pieces of the current layout (for the panel and the red rings). */
export function bloqueosActuales(items: PlacedItem[]): Bloqueo[] {
  return bloqueos(items);
}
