import { Html } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { memo, useEffect, useRef, useState } from "react";
import * as THREE from "three";
import type { AgentView } from "../store";
import { useOffice } from "../store";
import { slide } from "./collision";
import {
  contextHot,
  EMOTE_MS,
  emoteFor,
  LONG_THINK_MS,
  type Distintivo,
} from "./emotes";
import {
  breakRoom,
  idleDestination,
  nearestNode,
  NODES,
  pathBetween,
  type WP,
} from "./nav";
import {
  blockedByAgent,
  clearMeeting,
  meetingOf,
  meetSpot,
  presenceOf,
  report,
  seekMeeting,
  unreport,
} from "./presence";
import { capaEtiquetas } from "./capaEtiquetas";
import PixelPerson from "./PixelPerson";
import {
  basicMat,
  contactShadowMat,
  SHADOW_PLANE,
  UNIT_BOX,
} from "./resources";
import {
  type CharSkin,
  characterFor,
  energyFor,
  seatFor,
  sitPoint,
  STATUS_COLOR,
} from "./roles";
import { t } from "../textos";
import { ENTRADA, PASILLO_SOFA, PUERTA } from "../comportamiento";
import { MarcaCuenta } from "@/components/marca/Marca";
import { duracion, recortar } from "@/components/oficina/logica";
import { useEditor } from "../editor";
import { useSettings } from "../settings";

// ── Agent character (adapted from Agent Office 3D, MIT) ──
// The behaviour layer (comportamiento.ts) says where it goes: its desk, a
// walk around the office, the break room sofa (19) or the entrance door (12,
// and closed agents walking out). New agents walk in from the door; on the
// first load they are placed directly. It stands up and sits down with an
// animation and never teleports. Poses: arm up (13), facing the camera (14),
// relaxed on the sofa (19). Labels say only what the posture does not show;
// more data on hover; click opens the agent detail of /oficina. No emojis.

const SPEED = 1.7;
// Ota→yordamchi bog'lovchi chiziq (sub-agent "daraxti" shoxi). Sariq — "yollandi"
// hodisasi bilan bir xil rang. Yorug'lik hisoblanmaydi (basic) → tekin.
const LINK_MAT = basicMat("#ffd60a", { transparent: true, opacity: 0.55 });

function AgentAvatar({ agent }: { agent: AgentView }) {
  const seat = seatFor(agent.seatIndex);
  const preset = characterFor(agent.role, agent.seatIndex, agent.id);
  const titulo = agent.customName || agent.folderName;
  const select = useOffice((s) => s.select);
  const hover = useOffice((s) => s.hover);
  const selected = useOffice((s) => s.hoveredId === agent.id);
  const showLabels = useSettings((s) => s.showLabels);
  const color = STATUS_COLOR[agent.status];

  // Sub-agent "yollash" pufagi — subagentlar soni oshganda qisqa vaqt ko'rinadi.
  const [hiring, setHiring] = useState(false);
  const prevSubs = useRef(agent.subagents.length);
  useEffect(() => {
    const inc = agent.subagents.length > prevSubs.current;
    prevSubs.current = agent.subagents.length;
    if (inc) setHiring(true);
  }, [agent.subagents.length]);
  // Yashirish taymeri — `hiring`ga bog'liq (soni o'zgarsa ham qotib qolmaydi).
  useEffect(() => {
    if (!hiring) return;
    const t = setTimeout(() => setHiring(false), 3500);
    return () => clearTimeout(t);
  }, [hiring]);

  // Yordamchilar — BARQAROR slot + chiqish animatsiyasi. Store ro'yxatidan
  // farqi: ketayotgan yordamchini darrov o'chirmay, kichrayib yo'qolgunча
  // saqlaymiz. Slot kalit bo'yicha barqaror — o'rtadagi ketsa qolganlari
  // SAKRAMAYDI (avvalgi index-asosli joylashuv bug'i).
  // Yorliq/turi yordamchi YARATILGANDA saqlanadi — ketayotganda (store'dan
  // o'chgach) ham nomi ko'rinib turadi, "Yordamchi"ga sakramaydi.
  const [helpers, setHelpers] = useState<
    {
      key: string;
      slot: number;
      leaving: boolean;
      label?: string;
      kind?: string;
    }[]
  >([]);
  const subSig = agent.subagents.map((s) => s.key).join(",");
  useEffect(() => {
    const active = agent.subagents;
    setHelpers((prev) => {
      const used = new Set<number>();
      const next = prev.map((h) => {
        used.add(h.slot);
        return active.some((s) => s.key === h.key)
          ? h.leaving
            ? { ...h, leaving: false }
            : h
          : { ...h, leaving: true };
      });
      for (const s of active) {
        if (!next.some((h) => h.key === s.key)) {
          let slot = 0;
          while (used.has(slot)) slot++;
          used.add(slot);
          next.push({
            key: s.key,
            slot,
            leaving: false,
            label: s.label,
            kind: s.kind,
          });
        }
      }
      return next;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subSig]);
  const removeHelper = (key: string) =>
    setHelpers((prev) => prev.filter((h) => h.key !== key));

  // ── Emotsiyalar (holatdan kelib chiqadi — o'ylab topilmaydi, emotes.ts'ga qarang) ──
  // Taymerli emotsiya: uzoq o'ylash · ishni tugatdi.
  const [timed, setTimed] = useState<Distintivo>("");
  const prevStatus = useRef(agent.status);
  useEffect(() => {
    const prev = prevStatus.current;
    prevStatus.current = agent.status;
    setTimed("");
    if (
      agent.status === "idle" &&
      (prev === "working" || prev === "thinking" || prev === "collab")
    ) {
      setTimed("listo"); // the turn ended
      const t = setTimeout(() => setTimed(""), EMOTE_MS.done);
      return () => clearTimeout(t);
    }
    if (agent.status === "thinking") {
      const t = setTimeout(() => setTimed("pensando"), LONG_THINK_MS); // long thinking
      return () => clearTimeout(t);
    }
  }, [agent.status]);

  // Kontekst 85% dan OSHGAN payt — qisqa ogohlantirish (doim turmaydi).
  const hotNow = contextHot(agent.inputTokens, agent.contextWindow);
  const [hot, setHot] = useState(false);
  const prevHot = useRef(hotNow);
  useEffect(() => {
    const was = prevHot.current;
    prevHot.current = hotNow;
    if (!hotNow || was) return;
    setHot(true);
    const t = setTimeout(() => setHot(false), EMOTE_MS.hot);
    return () => clearTimeout(t);
  }, [hotNow]);

  // Desk seat point (chair centre).
  const sit = useRef<WP>({ ...sitPoint(seat) });
  // Agents that appear after the first load walk in from the entrance door.
  const desdePuerta = useRef(agent.origen === "puerta");
  // First load while resting (19): already in the break room ("its place").
  const descansoInicial = useRef(
    !desdePuerta.current && agent.destino === "sofa" ? agent.descanso : null,
  );

  const group = useRef<THREE.Group>(null);
  const pos = useRef<WP>(
    desdePuerta.current
      ? { ...PUERTA }
      : descansoInicial.current
        ? { x: descansoInicial.current.x, z: descansoInicial.current.z }
        : { ...sit.current },
  );
  const path = useRef<WP[]>(desdePuerta.current ? [{ ...ENTRADA }] : []);
  const curNode = useRef(
    desdePuerta.current
      ? nearestNode(ENTRADA.x, ENTRADA.z)
      : descansoInicial.current
        ? "lounge_i"
        : nearestNode(sit.current.x, sit.current.z),
  );
  const pendingNode = useRef<string | null>(null);
  const pause = useRef(0);
  const seated = useRef(
    !desdePuerta.current && descansoInicial.current?.tipo !== "cerca",
  );
  const movingRef = useRef(false);
  const stuck = useRef(0);
  const speedRef = useRef(0); // real walking speed (feet do not slide)
  const firstIdleTrip = useRef(false); // just finished work → coffee break
  const statusRef = useRef(agent.status);
  statusRef.current = agent.status;
  // Behaviour layer (comportamiento.ts), read every frame without re-render.
  const destinoRef = useRef(agent.destino);
  destinoRef.current = agent.destino;
  const poseRef = useRef(agent.pose);
  poseRef.current = agent.pose;
  const descansoRef = useRef(agent.descanso);
  descansoRef.current = agent.descanso;
  const descansoAnterior = useRef(agent.descanso);
  const prevDestino = useRef(agent.destino);
  // Sitting on the sofa / gliding between the approach point and the seat
  // (no collision for that last step: the seat is inside the sofa box).
  const enSofa = useRef(descansoInicial.current?.tipo === "sofa");
  const deslizar = useRef<{ x: number; z: number; ry: number } | null>(null);
  // Standing up before walking away (no teleport, no instant stand-up).
  const levantarse = useRef(0);
  // Entrance / exit: scale 0→1 at the door, 1→0 when leaving.
  const escala = useRef(desdePuerta.current ? 0 : 1);
  const salio = useRef(false);
  const marcarSalido = useOffice((s) => s.marcarSalido);
  // ── Social life (idle agents meet) ──
  const reportT = useRef(0);
  const seekCd = useRef(3 + Math.random() * 4);
  const metAt = useRef(0);
  const [emote, setEmote] = useState<"" | "charla">("");
  const emoteRef = useRef<"" | "charla">("");
  useEffect(() => () => unreport(agent.id), [agent.id]);

  useFrame((state, delta) => {
    const dt = Math.min(delta, 0.05);
    const g = group.current;
    if (!g) return;
    const cfg = useSettings.getState();
    const destino = destinoRef.current;
    const pasear = destino === "pasear" && cfg.wander;
    const desiredSit =
      destino === "escritorio" || (destino === "pasear" && !cfg.wander);
    const p = pos.current;

    if ((!cfg.social || !pasear) && meetingOf(agent.id)) {
      clearMeeting(agent.id);
      metAt.current = 0;
    }

    // Destination changed: finish the current edge and plan again; stand up
    // first if seated (the pose animates, nobody teleports).
    if (destino !== prevDestino.current) {
      if (prevDestino.current === "escritorio" && destino === "pasear")
        firstIdleTrip.current = true;
      prevDestino.current = destino;
      clearMeeting(agent.id);
      metAt.current = 0;
      if (path.current.length > 1) {
        path.current = path.current.slice(0, 1);
        pendingNode.current = null;
      }
      if (seated.current && !enSofa.current && destino !== "escritorio") {
        seated.current = false;
        levantarse.current = 0.7;
      }
      if (enSofa.current && destino !== "sofa") {
        // get up from the sofa: back to its approach point
        const d = descansoAnterior.current;
        if (d) deslizar.current = { x: d.ax, z: d.az, ry: d.ry };
      }
    }
    if (destino === "sofa" && descansoRef.current)
      descansoAnterior.current = descansoRef.current;

    let moving = false;

    if (levantarse.current > 0) {
      levantarse.current -= dt;
    } else if (deslizar.current) {
      // Last step onto / off the sofa, without collision.
      const d = deslizar.current;
      const dx = d.x - p.x;
      const dz = d.z - p.z;
      const dist = Math.hypot(dx, dz);
      const paso = Math.min(dist, 0.9 * dt);
      if (dist > 0.02) {
        p.x += (dx / dist) * paso;
        p.z += (dz / dist) * paso;
      } else {
        deslizar.current = null;
        if (destino !== "sofa") {
          // Off the sofa: back through the corridor to the lounge node.
          enSofa.current = false;
          seated.current = false;
          path.current = [{ ...PASILLO_SOFA }];
          pendingNode.current = "lounge_i";
        }
      }
      g.rotation.y = dampAngle(g.rotation.y, d.ry, 6, dt);
    } else if (path.current.length === 0) {
      planear(dt, desiredSit, pasear);
    }

    // Walk along the path (graph edges never cross walls).
    if (
      !deslizar.current &&
      levantarse.current <= 0 &&
      path.current.length > 0
    ) {
      seated.current = false;
      const t = path.current[0];
      const dx = t.x - p.x;
      const dz = t.z - p.z;
      const dist = Math.hypot(dx, dz);
      if (dist < 0.1) {
        p.x = t.x;
        p.z = t.z;
        path.current.shift();
        if (path.current.length === 0) {
          curNode.current = pendingNode.current ?? nearestNode(p.x, p.z);
          pendingNode.current = null;
          if (pasear) pause.current = 1.5 + Math.random() * 4;
        }
      } else {
        const mvx = (dx / dist) * SPEED * dt;
        const mvz = (dz / dist) * SPEED * dt;
        // The door is inside the outer wall: no collision for that last step.
        const libre =
          Math.hypot(t.x - PUERTA.x, t.z - PUERTA.z) < 0.05 ||
          Math.hypot(p.x - PUERTA.x, p.z - PUERTA.z) < 1.2;
        const res = libre
          ? { x: p.x + mvx, z: p.z + mvz }
          : slide(p.x, p.z, mvx, mvz, 0.16);
        const SEP = 0.42;
        let fx = res.x,
          fz = res.z;
        if (
          !libre &&
          blockedByAgent(agent.id, fx, p.z, SEP) &&
          !blockedByAgent(agent.id, p.x, p.z, SEP)
        )
          fx = p.x;
        if (
          !libre &&
          blockedByAgent(agent.id, fx, fz, SEP) &&
          !blockedByAgent(agent.id, fx, p.z, SEP)
        )
          fz = p.z;
        const moved = Math.hypot(fx - p.x, fz - p.z);
        p.x = fx;
        p.z = fz;
        moving = true;
        speedRef.current = moved / Math.max(dt, 0.001);
        g.rotation.y = dampAngle(g.rotation.y, Math.atan2(-dx, -dz), 10, dt);
        if (moved < SPEED * dt * 0.25) {
          stuck.current += dt;
          if (stuck.current > 0.8) {
            path.current.shift();
            stuck.current = 0;
            if (path.current.length === 0) {
              curNode.current = nearestNode(p.x, p.z);
              pendingNode.current = null;
              if (pasear) pause.current = 1 + Math.random() * 3;
            }
          }
        } else {
          stuck.current = 0;
        }
      }
    }
    movingRef.current = moving;
    if (!moving) speedRef.current *= Math.max(0, 1 - dt * 6);

    // Facing while seated: the desk, or the camera when it asked you something.
    if (seated.current && !enSofa.current && !deslizar.current) {
      let ry = seat.ry;
      if (poseRef.current === "mirarCamara") {
        const c = state.camera.position;
        ry = Math.atan2(-(c.x - p.x), -(c.z - p.z));
      }
      g.rotation.y = dampAngle(g.rotation.y, ry, 4, dt);
    }
    // On the sofa: face where the sofa faces.
    if (enSofa.current && !deslizar.current && descansoRef.current) {
      g.rotation.y = dampAngle(g.rotation.y, descansoRef.current.ry, 4, dt);
    }
    // Standing near the sofa (no seat left): face the sofas.
    if (
      !moving &&
      destino === "sofa" &&
      descansoRef.current?.tipo === "cerca" &&
      path.current.length === 0
    ) {
      g.rotation.y = dampAngle(g.rotation.y, descansoRef.current.ry, 4, dt);
    }
    g.position.x = p.x;
    g.position.z = p.z;

    // Entrance (grow at the door) and exit (shrink at the door).
    const enPuerta = Math.hypot(p.x - PUERTA.x, p.z - PUERTA.z) < 0.15;
    const objetivo = destino === "salida" && enPuerta ? 0 : 1;
    escala.current += (objetivo - escala.current) * Math.min(1, dt * 5);
    g.scale.setScalar(Math.max(0.001, escala.current));
    if (objetivo === 0 && escala.current < 0.03 && !salio.current) {
      salio.current = true;
      marcarSalido(agent.id);
    }
    if (destino !== "salida") salio.current = false;

    // ── Meeting: face the partner; both arrived → "Charlando" badge. ──
    const mNow = meetingOf(agent.id);
    const partnerNow = mNow ? presenceOf(mNow.partner) : undefined;
    if (mNow && metAt.current > 0) {
      const tx = partnerNow ? partnerNow.x : NODES[mNow.point].x;
      const tz = partnerNow ? partnerNow.z : NODES[mNow.point].z;
      const dx = tx - p.x,
        dz = tz - p.z;
      if (Math.hypot(dx, dz) > 0.05)
        g.rotation.y = dampAngle(g.rotation.y, Math.atan2(-dx, -dz), 6, dt);
      const bothHere = partnerNow != null && partnerNow.metAt > 0;
      const e = bothHere ? "charla" : "";
      if (emoteRef.current !== e) {
        emoteRef.current = e;
        setEmote(e);
      }
    } else if (emoteRef.current !== "") {
      emoteRef.current = "";
      setEmote("");
    }

    reportT.current -= dt;
    if (reportT.current <= 0) {
      reportT.current = 0.2;
      report(agent.id, p.x, p.z, pasear, metAt.current);
    }
  });

  /** Path finished: choose the next one for the current destination. */
  function planear(dt: number, desiredSit: boolean, pasear: boolean): void {
    const p = pos.current;
    const destino = destinoRef.current;
    if (desiredSit) {
      enSofa.current = false;
      if (Math.hypot(p.x - sit.current.x, p.z - sit.current.z) < 0.25) {
        seated.current = true;
      } else {
        const target = nearestNode(sit.current.x, sit.current.z);
        const route = pathBetween(curNode.current, target);
        path.current = route.length ? [...route, sit.current] : [sit.current];
        pendingNode.current = route.length ? target : null;
      }
      return;
    }
    if (destino === "sofa") {
      const d = descansoRef.current;
      if (!d) return;
      if (enSofa.current) return; // already seated on the sofa
      if (Math.hypot(p.x - d.ax, p.z - d.az) < 0.25) {
        if (d.tipo === "sofa") {
          enSofa.current = true;
          seated.current = true;
          deslizar.current = { x: d.x, z: d.z, ry: d.ry };
        }
        return; // standing spot: stay
      }
      const route = pathBetween(curNode.current, "lounge_i");
      // Sofa seats are reached through the corridor (the coffee table is in the way).
      const via = d.tipo === "sofa" ? [{ ...PASILLO_SOFA }] : [];
      path.current = [...route, ...via, { x: d.ax, z: d.az }];
      pendingNode.current = "lounge_i";
      return;
    }
    if (destino === "salida") {
      if (Math.hypot(p.x - PUERTA.x, p.z - PUERTA.z) < 0.15) return; // at the door
      if (Math.hypot(p.x - ENTRADA.x, p.z - ENTRADA.z) < 0.25) {
        path.current = [{ ...PUERTA }];
        return;
      }
      const target = nearestNode(ENTRADA.x, ENTRADA.z);
      const route = pathBetween(curNode.current, target);
      path.current = [...route, { ...ENTRADA }, { ...PUERTA }];
      pendingNode.current = null;
      return;
    }
    // Free: walk around the office (original behaviour).
    seated.current = false;
    if (!pasear) return;
    const cfg = useSettings.getState();
    if (cfg.social && !meetingOf(agent.id)) {
      if (seekCd.current > 0) seekCd.current -= dt;
      else if (!seekMeeting(agent.id, p.x, p.z, performance.now() / 1000))
        seekCd.current = 1.2 + Math.random();
    }
    const now = performance.now() / 1000;
    const meet = meetingOf(agent.id);
    if (!meet && metAt.current) metAt.current = 0;
    if (meet) {
      const spot = meetSpot(meet);
      const partner = presenceOf(meet.partner);
      const bothHere =
        metAt.current > 0 && partner != null && partner.metAt > 0;
      const chatSince = bothHere ? Math.max(metAt.current, partner!.metAt) : 0;
      const chatDone = bothHere && now - chatSince > 6;
      const partnerGone = partner == null || meetingOf(meet.partner) == null;
      if (now > meet.until || chatDone || partnerGone) {
        clearMeeting(agent.id);
        metAt.current = 0;
        seekCd.current = 18 + Math.random() * 20;
        pause.current = 0.4 + Math.random();
      } else if (Math.hypot(p.x - spot.x, p.z - spot.z) < 0.32) {
        if (metAt.current === 0) metAt.current = now;
      } else if (
        Math.hypot(p.x - NODES[meet.point].x, p.z - NODES[meet.point].z) < 1.3
      ) {
        path.current = [spot];
        pendingNode.current = null;
      } else {
        const from = nearestNode(p.x, p.z);
        const route = pathBetween(from, meet.point);
        if (route.length === 0) {
          curNode.current = from;
          pause.current = 0.5;
        } else {
          path.current = route;
          curNode.current = from;
          pendingNode.current = meet.point;
        }
      }
    } else if (pause.current > 0) {
      pause.current -= dt;
    } else {
      const target = firstIdleTrip.current
        ? breakRoom()
        : idleDestination(agent.role);
      firstIdleTrip.current = false;
      const route = pathBetween(curNode.current, target);
      if (route.length === 0) {
        curNode.current = nearestNode(p.x, p.z);
        pause.current = 0.6 + Math.random();
      } else {
        path.current = route;
        pendingNode.current = target;
      }
    }
  }

  // Single badge (priority in emotes.ts). Stacked layers over the head:
  // label → question balloon → helper bubble → badge; each one above the previous.
  const face = emoteFor({
    meeting: emote,
    status: agent.status,
    stuck: agent.stuck,
    hot,
    timed,
  });
  const et = agent.etiqueta;
  const pregunta = agent.question ? agent.preguntaPendiente : null;
  // Labels of neighbouring desks are staggered so they do not overlap.
  const escalon =
    agent.destino === "sofa" && agent.descanso
      ? (agent.descanso.indice % 2) * 0.55
      : (agent.seatIndex % 3) * 0.75;
  const labelTop = (selected ? 2.7 : 2.28) + escalon;
  const globoY = labelTop + 0.45;
  const hireY = (pregunta ? globoY + 0.5 : labelTop) + 0.34;
  const faceY = (hiring ? hireY : pregunta ? globoY + 0.5 : labelTop) + 0.36;
  const ahora = Date.now();

  return (
    <group
      ref={group}
      position={[pos.current.x, 0, pos.current.z]}
      // While editing the office the agents stay visible but do not react
      // (the click goes on to the floor of the editor).
      onClick={(e) => {
        if (useEditor.getState().activo) return;
        e.stopPropagation();
        select(agent.id);
      }}
      onPointerOver={(e) => {
        if (useEditor.getState().activo) return;
        e.stopPropagation();
        hover(agent.id);
        document.body.style.cursor = "pointer";
      }}
      onPointerOut={() => {
        hover(null);
        document.body.style.cursor = "";
      }}
    >
      {/* Soft contact shadow */}
      <mesh
        geometry={SHADOW_PLANE}
        material={contactShadowMat()}
        position={[0, 0.04, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
        scale={[0.92, 0.92, 1]}
      />
      <PixelPerson
        skin={preset}
        status={agent.status}
        energy={energyFor(agent.role, agent.seatIndex)}
        getState={() => ({
          sit: seated.current,
          moving: movingRef.current,
          speed: speedRef.current,
          pose: enSofa.current
            ? "sofa"
            : seated.current && poseRef.current === "brazoAlzado"
              ? "brazoAlzado"
              : "normal",
        })}
      />

      {/* Parent → helper links on the floor */}
      {helpers
        .filter((h) => !h.leaving)
        .map((h) => {
          const s = helperSlot(h.slot);
          const len = Math.hypot(s.x, s.z);
          return (
            <mesh
              key={`link-${h.key}`}
              geometry={UNIT_BOX}
              material={LINK_MAT}
              position={[s.x / 2, 0.05, s.z / 2]}
              rotation={[0, Math.atan2(s.x, s.z), 0]}
              scale={[0.035, 0.01, len]}
            />
          );
        })}

      {/* Helpers (subagents): small characters next to the agent */}
      {helpers.map((h) => (
        <SubAgent
          key={h.key}
          skin={preset}
          slot={h.slot}
          leaving={h.leaving}
          label={h.kind || h.label}
          showLabel={selected && showLabels}
          onExited={() => removeHelper(h.key)}
        />
      ))}

      {/* Badge: short text in a box (no emojis) */}
      {face && (
        <Html
          portal={capaEtiquetas}
          zIndexRange={[60, 20]}
          position={[0, faceY, 0]}
          center
          style={{ pointerEvents: "none" }}
        >
          <div
            style={{
              ...CAJA,
              background: face === "error" ? "#111" : "#fff",
              color: face === "error" ? "#fff" : "#111",
              fontSize: 10.5,
              fontWeight: 700,
            }}
          >
            {t(`distintivo.${face}`)}
          </div>
        </Html>
      )}

      {/* "Called a helper" bubble, for a short time */}
      {hiring && (
        <Html
          portal={capaEtiquetas}
          zIndexRange={[60, 20]}
          position={[0, hireY, 0]}
          center
          style={{ pointerEvents: "none" }}
        >
          <div style={{ ...CAJA, fontSize: 11.5, fontWeight: 700 }}>
            {t("burbuja.ayudante")}
          </div>
        </Html>
      )}

      {/* 14: speech balloon with the pending question (full text on hover) */}
      {pregunta && !selected && (
        <Html
          portal={capaEtiquetas}
          zIndexRange={[60, 20]}
          position={[0, globoY, 0]}
          center
          style={{ pointerEvents: "none" }}
        >
          <div style={GLOBO}>
            {recortar(pregunta, 80)}
            <span style={COLA_BORDE} />
            <span style={COLA} />
          </div>
        </Html>
      )}

      {/* Label: only what the posture does not show (walking = free,
          seated = working). Demo Org account: isotype; personal: nothing. */}
      {showLabels && !selected && (
        <Html
          portal={capaEtiquetas}
          position={[0, 1.98 + escalon, 0]}
          center
          occlude={false}
          style={{ pointerEvents: "none" }}
          zIndexRange={[10, 0]}
        >
          <div
            style={{
              ...CAJA,
              display: "flex",
              alignItems: "center",
              gap: 5,
              fontSize: 11,
              ...(et.espera
                ? { borderWidth: 2, borderColor: "#111", fontWeight: 600 }
                : { borderColor: "#9a9a9a" }),
            }}
          >
            <MarcaCuenta cuenta={agent.cuenta} alto={14} />
            <span style={{ fontWeight: 700 }}>{et.proyecto}</span>
            {et.espera && <span>· {et.espera}</span>}
            {et.actividad && (
              <span style={{ color: "#555" }}>· {et.actividad}</span>
            )}
            {et.errores && (
              <span style={{ color: "#111", fontWeight: 700 }}>
                · {t("distintivo.conErrores")}
              </span>
            )}
          </div>
        </Html>
      )}

      {/* Hover: more data. A separate <Html> mounted on hover so it gets a
          high z-index (drei only recomputes it when something moves). */}
      {selected && (
        <Html
          portal={capaEtiquetas}
          position={[0, 1.98 + escalon, 0]}
          center
          occlude={false}
          style={{ pointerEvents: "none" }}
          zIndexRange={[1000, 900]}
        >
          <div
            style={{
              ...CAJA,
              borderLeftWidth: 4,
              borderLeftColor: color,
              padding: "6px 10px",
              minWidth: 180,
              maxWidth: 300,
              whiteSpace: "normal",
              textAlign: "left",
              fontSize: 12,
            }}
          >
            <div
              style={{
                fontWeight: 700,
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <MarcaCuenta cuenta={agent.cuenta} alto={16} />
              {titulo}
            </div>
            <div style={{ fontFamily: MONO, marginTop: 2 }}>
              {agent.estado.numero} · {agent.estado.nombre}
            </div>
            <div style={{ color: "#555", marginTop: 2 }}>
              {t("detalle.enEsteEstado")} {duracion(agent.estado.desde, ahora)}
            </div>
            {agent.lePide && (
              <div style={{ marginTop: 4 }}>
                <b>{t("detalle.pide")}:</b> {recortar(agent.lePide, 140)}
              </div>
            )}
            {agent.preguntaPendiente && (
              <div style={{ marginTop: 4 }}>
                <b>{t("detalle.pregunta")}:</b> {agent.preguntaPendiente}
              </div>
            )}
            <div style={{ color: "#555", marginTop: 4, fontSize: 11 }}>
              {t("detalle.clic")}
            </div>
          </div>
        </Html>
      )}
    </group>
  );
}

/** Speech balloon (14): white box with a tail pointing to the head. */
const GLOBO: React.CSSProperties = {
  position: "relative",
  width: 230,
  padding: "6px 9px",
  background: "#fff",
  color: "#111",
  border: "2px solid #111",
  borderRadius: 10,
  fontFamily: "var(--font-plex-sans), system-ui, sans-serif",
  fontSize: 11.5,
  lineHeight: 1.3,
  whiteSpace: "normal",
  boxShadow: "0 2px 6px rgba(0,0,0,0.25)",
};
const COLA_BORDE: React.CSSProperties = {
  position: "absolute",
  left: "50%",
  bottom: -10,
  marginLeft: -9,
  width: 0,
  height: 0,
  borderLeft: "9px solid transparent",
  borderRight: "9px solid transparent",
  borderTop: "10px solid #111",
};
const COLA: React.CSSProperties = {
  position: "absolute",
  left: "50%",
  bottom: -6,
  marginLeft: -6,
  width: 0,
  height: 0,
  borderLeft: "6px solid transparent",
  borderRight: "6px solid transparent",
  borderTop: "7px solid #fff",
};

const MONO = "var(--font-plex-mono), 'Courier New', monospace";
/** Light boxes like /oficina: white, greys and black. */
const CAJA: React.CSSProperties = {
  padding: "2px 7px",
  background: "rgba(255,255,255,0.95)",
  color: "#111",
  borderWidth: 1,
  borderStyle: "solid",
  borderColor: "#555",
  fontFamily: "var(--font-plex-sans), system-ui, sans-serif",
  whiteSpace: "nowrap",
  boxShadow: "0 1px 4px rgba(0,0,0,0.25)",
};

// Sub-agent — parent yonidagi KICHIK yordamchi. Kirganda noldan "pop"
// (easeOutBack) bilan kattalashadi, ketganda kichrayib yo'qoladi (leaving),
// so'ng onExited orqali ro'yxatдан chiqadi. Joyi `slot` bo'yicha barqaror.
const SUB_TARGET = 0.5;
/** Yordamchi joyi — slot bo'yicha BARQAROR (o'rtadagi ketsa qolganlari sakramaydi). */
export function helperSlot(slot: number): { x: number; z: number } {
  return { x: 0.9 + (slot % 2) * 0.62, z: 0.45 - Math.floor(slot / 2) * 0.62 };
}
function SubAgent({
  skin,
  slot,
  leaving,
  label,
  showLabel,
  onExited,
}: {
  skin: CharSkin;
  slot: number;
  leaving: boolean;
  label?: string;
  showLabel: boolean;
  onExited: () => void;
}) {
  const g = useRef<THREE.Group>(null);
  const grow = useRef(0);
  const shrink = useRef(0);
  const done = useRef(false);
  const { x: px, z: pz } = helperSlot(slot);
  useFrame((_, delta) => {
    const gg = g.current;
    if (!gg) return;
    if (leaving) {
      shrink.current = Math.min(1, shrink.current + delta * 4.5); // ~0.22s
      const e = 1 - shrink.current * shrink.current; // easeInQuad → 1..0
      gg.scale.setScalar(Math.max(0.0001, SUB_TARGET * e));
      if (shrink.current >= 1 && !done.current) {
        done.current = true;
        onExited();
      }
      return;
    }
    if (grow.current < 1) {
      grow.current = Math.min(1, grow.current + delta * 3.2); // ~0.3s
      const x = grow.current,
        c1 = 1.70158,
        c3 = c1 + 1;
      gg.scale.setScalar(
        SUB_TARGET * (1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2)),
      ); // easeOutBack
    }
  });
  return (
    <group ref={g} position={[px, 0, pz]} scale={0.001}>
      <PixelPerson skin={skin} status="working" pose="stand" detail="low" />
      {/* Yorliq — sub-agentning HAQIQIY turi/vazifasi (Task tool'idan). Bo'lmasa
          umumiy "Yordamchi" (o'ylab topilgan nom yozilmaydi).
          Guruh 0.5ga kichraytirilgan → lokal 6.4 ≈ 3.2m: otaning TANLANGAN (baland)
          yorlig'idan ham yuqorida. Har slot +1.4 lokal ≈ +0.7m — yozuvlar
          bir-birining ustiga tushmaydi. */}
      {showLabel && (
        <Html
          portal={capaEtiquetas}
          position={[0, 6.4 + slot * 1.4, 0]}
          center
          style={{ pointerEvents: "none" }}
          zIndexRange={[60, 20]}
        >
          <div
            style={{
              ...CAJA,
              maxWidth: 160,
              fontSize: 9.5,
              fontWeight: 700,
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {label || t("ayudante")}
          </div>
        </Html>
      )}
    </group>
  );
}

function dampAngle(cur: number, target: number, l: number, dt: number): number {
  let d = target - cur;
  while (d > Math.PI) d -= Math.PI * 2;
  while (d < -Math.PI) d += Math.PI * 2;
  return cur + d * (1 - Math.exp(-l * dt));
}

// memo — store o'zgarmagan agent obyekt ref'ini saqlaydi, shuning uchun boshqa
// agent yangilanganda bu personaj qayta render bo'lmaydi (ko'p agentda muhim).
export default memo(AgentAvatar);
