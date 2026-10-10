"use client";

/**
 * The 3D office (adapted from App.tsx of Agent Office 3D, MIT): isometric
 * camera, building, layout furniture, desks and agents. Without their HUD,
 * first-person view, cost sampling, conflict links or furniture editor.
 */

import { OrbitControls, OrthographicCamera } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useRef, useState } from "react";
import { ACESFilmicToneMapping, SRGBColorSpace } from "three";
import { useLayout } from "./distribucion";
import { useEditor } from "./editor";
import AgentAvatar from "./escena/AgentAvatar";
import { capaEtiquetas } from "./escena/capaEtiquetas";
import { setActiveSeats, setPlacedRects } from "./escena/collision";
import { footprint } from "./escena/furniture";
import PlacedFurniture from "./escena/PlacedFurniture";
import Room from "./escena/Room";
import { cantidadPuestosBase } from "./escena/roles";
import { activarEntorno } from "./entornos/activo";
import { DecoracionEntorno, PuestoUsuario } from "./entornos/decoracion";
import { mirarHacia, sitPoint } from "./entornos/tipos";
import { updateFrustum } from "./escena/visibility";
import Workstation from "./escena/Workstation";
import { dprFor, shadowEvery, useSettings } from "./settings";
import { useOffice } from "./store";

// The shadow map is refreshed every few frames, not every frame: agents move
// slowly, and redrawing the whole scene into the shadow pass was the main stutter.
function ShadowThrottle({ every }: { every: number }) {
  const gl = useThree((s) => s.gl);
  const f = useRef(0);
  useEffect(() => {
    gl.shadowMap.autoUpdate = false;
    gl.shadowMap.needsUpdate = true;
  }, [gl]);
  useFrame((state) => {
    updateFrustum(state.camera); // culling used by every agent
    if (f.current++ % every === 0) gl.shadowMap.needsUpdate = true;
  });
  return null;
}

/**
 * `vertical`: phones in portrait. The camera looks along the long side of the
 * office so it fits the narrow screen.
 */
export default function Escena3D({
  zoom = 20,
  vertical = false,
  centro = [0, 0],
}: {
  zoom?: number;
  vertical?: boolean;
  /** Point of the floor the camera looks at (x, z). */
  centro?: [number, number];
}) {
  const [cx, cz] = centro;
  const order = useOffice((s) => s.order);
  const agents = useOffice((s) => s.agents);
  const cerrados = useOffice((s) => s.cerrados);
  const presente = useOffice((s) => s.presente);
  // Active environment (from the saved layout): its building, desks, paths.
  const clave = useLayout((s) => s.entorno);
  const ent = activarEntorno(clave);
  const SEAT_COUNT = cantidadPuestosBase();
  const hover = useOffice((s) => s.hover);
  const quality = useSettings((s) => s.quality);
  const shadows = useSettings((s) => s.shadows);
  // Dragging a piece in the editor: the camera does not move.
  const arrastrando = useEditor((s) => s.arrastrando) !== null;
  // Labels go into a fixed layer; agents are drawn once it exists.
  const [capaLista, setCapaLista] = useState(false);
  const capa = (el: HTMLDivElement | null) => {
    if (el && capaEtiquetas.current !== el) {
      capaEtiquetas.current = el;
      setCapaLista(true);
    }
  };

  // Desks drawn: the base ones of the environment, the used ones (agents and
  // closed desks that are kept) and the empty ones the environment adds next
  // to them (the rest of a cabin or an island).
  const ocupados = [
    ...order
      .map((id) => agents[id]?.seatIndex)
      .filter((i): i is number => typeof i === "number"),
    ...cerrados.map((c) => c.seatIndex),
  ];
  const seatKey = [...ocupados].sort((a, b) => a - b).join(",");
  const dibujados = [
    ...new Set([
      ...Array.from({ length: SEAT_COUNT }, (_, i) => i),
      ...ocupados,
      ...(ent.puestosVisibles?.(ocupados) ?? []),
    ]),
  ].sort((a, b) => a - b);
  // Collision: every drawn desk.
  useEffect(() => {
    setActiveSeats(dibujados);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seatKey, clave]);

  // Layout furniture collision (characters do not walk through it).
  const placed = useLayout((s) => s.items);
  useEffect(() => {
    setPlacedRects(
      placed.map((it) => {
        const f = footprint(it.type, it.ry);
        return {
          x0: it.x - f.hx,
          x1: it.x + f.hx,
          z0: it.z - f.hz,
          z1: it.z + f.hz,
        };
      }),
    );
  }, [placed]);

  // Desk details of the environment: project nameplate, light while the
  // agent waits for you, chair turned while it queues at the counter.
  const extrasPuesto = (a: (typeof agents)[string] | undefined) => {
    if (!a) return {};
    const espera = a.permission || a.question;
    const giro = (() => {
      // Estudio: the chair turns towards your desk while it waits.
      if (!ent.girarHaciaTi || !espera) return 0;
      const p = ent.puesto(a.seatIndex);
      const s = sitPoint(p);
      return mirarHacia(s.x, s.z, ent.tuPuesto.x, ent.tuPuesto.z) - p.ry;
    })();
    return {
      placa: ent.placaNombre ? a.folderName : undefined,
      resaltado: ent.resaltarEspera && espera,
      sillaGirada: a.destino === "fila",
      giroSilla: giro,
      luzSilla: !!ent.girarHaciaTi && espera,
    };
  };

  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <Canvas
        shadows={shadows}
        dpr={dprFor(quality)}
        gl={{
          antialias: quality === "high",
          powerPreference: "high-performance",
          toneMapping: ACESFilmicToneMapping,
          outputColorSpace: SRGBColorSpace,
        }}
        onPointerMissed={() => hover(null)}
      >
        {shadows && <ShadowThrottle every={shadowEvery(quality)} />}
        {!shadows && <FrustumOnly />}
        <OrthographicCamera
          key={vertical ? "vertical" : "iso"}
          makeDefault
          position={vertical ? [46 + cx, 36, 6 + cz] : [34 + cx, 27, 34 + cz]}
          zoom={zoom}
          near={-300}
          far={800}
        />
        <OrbitControls
          makeDefault
          enabled={!arrastrando}
          target={[cx, 0.8, cz]}
          enablePan
          minZoom={8}
          maxZoom={70}
          maxPolarAngle={Math.PI * 0.44}
          minPolarAngle={Math.PI * 0.18}
        />
        {/* Everything below remounts when the environment changes: agents
            appear directly at their places. */}
        <group key={clave}>
          <Room
            mode="iso"
            ancho={ent.tamano.ancho}
            fondo={ent.tamano.fondo}
            piso={ent.pisoCentral}
          />
          <DecoracionEntorno clave={clave} entorno={ent} />
          <PuestoUsuario puesto={ent.tuPuesto} presente={presente} />
          <PlacedFurniture />
          {dibujados.map((i) => {
            const occ = order
              .map((id) => agents[id])
              .find((a) => a && a.seatIndex === i);
            const cerrado = occ
              ? undefined
              : cerrados.find((c) => c.seatIndex === i);
            return (
              <Workstation
                key={`seat-${i}`}
                seatIndex={i}
                agent={occ}
                cerrado={cerrado}
                {...extrasPuesto(occ)}
              />
            );
          })}
          {capaLista &&
            order.map((id) => {
              const a = agents[id];
              return a ? <AgentAvatar key={`av-${id}`} agent={a} /> : null;
            })}
        </group>
      </Canvas>
      <div
        ref={capa}
        style={{
          position: "absolute",
          inset: 0,
          pointerEvents: "none",
          overflow: "hidden",
        }}
      />
    </div>
  );
}

/** Without shadows the frustum (used for culling) still needs updating. */
function FrustumOnly() {
  useFrame((state) => updateFrustum(state.camera));
  return null;
}
