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
import { cuentaCorta } from "../adaptador";
import { duracion, recortar } from "@/components/oficina/logica";
import { useSettings } from "../settings";

// ── Agent character (adapted from Agent Office 3D, MIT) ──
// Sits at the desk while working; when idle walks around the office through
// the doors. Resting agents (19, you are away) stay in the break room.
// Labels: project, account and short state; more data on hover; click opens
// the agent detail of /oficina. No emojis: badges are short texts.

const SPEED = 1.7;
// Ota→yordamchi bog'lovchi chiziq (sub-agent "daraxti" shoxi). Sariq — "yollandi"
// hodisasi bilan bir xil rang. Yorug'lik hisoblanmaydi (basic) → tekin.
const LINK_MAT = basicMat("#ffd60a", { transparent: true, opacity: 0.55 });

function AgentAvatar({ agent }: { agent: AgentView }) {
  const seat = seatFor(agent.seatIndex);
  const preset = characterFor(agent.role, agent.seatIndex, agent.id);
  const cuenta = cuentaCorta(agent.cuenta);
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

  // O'tirish nuqtasi (stul markazi — har qanday yo'nalishga mos, collision chetda)
  const sit = useRef<WP>({ ...sitPoint(seat) });

  const group = useRef<THREE.Group>(null);
  const pos = useRef<WP>({ ...sit.current });
  const path = useRef<WP[]>([]);
  const curNode = useRef(nearestNode(sit.current.x, sit.current.z)); // joriy graf tuguni
  const pendingNode = useRef<string | null>(null);
  const pause = useRef(0);
  const seated = useRef(true);
  const movingRef = useRef(false);
  const prevDesired = useRef(true);
  const stuck = useRef(0);
  const speedRef = useRef(0); // haqiqiy yurish tezligi (oyoq sirg'anmasin uchun)
  const firstIdleTrip = useRef(false); // ishdan endi bo'shadi → tanaffusga
  const statusRef = useRef(agent.status);
  statusRef.current = agent.status;
  const restingRef = useRef(agent.resting);
  restingRef.current = agent.resting;
  // ── Ijtimoiy hayot (uchrashuv) ──
  const reportT = useRef(0); // presence bildirish throttle
  const seekCd = useRef(3 + Math.random() * 4); // keyingi izlashgacha
  const metAt = useRef(0); // gather nuqtasiga yetgan payt (0 = yetmagan)
  const [emote, setEmote] = useState<"" | "charla">("");
  const emoteRef = useRef<"" | "charla">("");
  useEffect(() => () => unreport(agent.id), [agent.id]); // ketganda reyestrдан chiqar

  useFrame((_, delta) => {
    const dt = Math.min(delta, 0.05);
    const g = group.current;
    if (!g) return;
    // Sozlamalarni HAR FREYM store'dan o'qiymiz (reaktiv obuna emas — o'zgarish
    // darhol ta'sir qiladi, lekin qayta render qilinmaydi).
    const cfg = useSettings.getState();
    // Sayr o'chirilgan bo'lsa — bo'sh agent ham stolida qoladi.
    const desiredSit = statusRef.current !== "idle" || !cfg.wander;
    const p = pos.current;

    // Uchrashuvlar o'chirilgan bo'lsa — boshlanganini ham tozalaymiz (yarim
    // yo'lda qotib qolmasin) va yangisini izlamaymiz.
    if (!cfg.social && meetingOf(agent.id)) {
      clearMeeting(agent.id);
      metAt.current = 0;
    }

    // Rejim o'zgarsa — joriy tugunga yetib qayta rejalaymiz (uzoq aylanmasin)
    if (desiredSit !== prevDesired.current) {
      prevDesired.current = desiredSit;
      if (!desiredSit) firstIdleTrip.current = true; // ishni tugatdi → tanaffus
      if (desiredSit) {
        clearMeeting(agent.id);
        metAt.current = 0;
      } // task keldi → uchrashuvni tashla
      if (path.current.length > 1) {
        path.current = path.current.slice(0, 1);
        pendingNode.current = null;
      }
    }

    // Ijtimoiy izlash — HAR freym (sayr davomida ham). Cooldown tugagach bo'sh
    // sherik topilsa, joriy yo'lni tashlab hub'ga yo'naladi (keyingi freym
    // meet-tarmog'i boshqaradi). Aks holda tez-tez qayta urinadi.
    if (!desiredSit && cfg.social && !meetingOf(agent.id)) {
      if (seekCd.current > 0) seekCd.current -= dt;
      else {
        const m = seekMeeting(agent.id, p.x, p.z, performance.now() / 1000);
        if (m) {
          path.current = [];
          pendingNode.current = null;
        } else seekCd.current = 1.2 + Math.random(); // sherik hali yo'q — birozdan keyin
      }
    }
    // Uchrashuv bor, lekin sayr yo'lida (sherik — o'z yo'lini tozalamagan) —
    // joriy qirrani tugatib hub'ga qayta yo'naltiramiz (uzoq sayr qilmasin).
    {
      const cm = meetingOf(agent.id);
      if (
        cm &&
        metAt.current === 0 &&
        pendingNode.current !== cm.point &&
        path.current.length > 1
      ) {
        path.current = path.current.slice(0, 1);
        pendingNode.current = null;
      }
    }

    // Yo'l tugagan — keyingi maqsad. HAR DOIM graf tugunidan (curNode) yo'l
    // olamiz → yo'llar faqat eshiklardan o'tadi, devor/mebeldan emas.
    if (path.current.length === 0) {
      const atSeat =
        Math.hypot(p.x - sit.current.x, p.z - sit.current.z) < 0.25;
      if (desiredSit) {
        if (atSeat) {
          seated.current = true;
        } else {
          const target = nearestNode(sit.current.x, sit.current.z);
          const route = pathBetween(curNode.current, target);
          // Yo'l topilmasa — to'g'ridan-to'g'ri stulga (o'z stoli ochiq maydonda).
          path.current = route.length ? [...route, sit.current] : [sit.current];
          pendingNode.current = route.length ? target : null;
        }
      } else {
        seated.current = false;
        const now = performance.now() / 1000;
        const meet = meetingOf(agent.id);
        if (!meet && metAt.current) metAt.current = 0; // uchrashuv tashqaridan tozalandi
        if (meet) {
          // ── Uchrashuv: O'Z joyimga (spot) boraman; ikkovimiz yetgach ~6s
          //    suhbat, keyin tarqaymiz. Sherik ketsa — kutmaymiz. ──
          const spot = meetSpot(meet);
          const partner = presenceOf(meet.partner);
          const bothHere =
            metAt.current > 0 && partner != null && partner.metAt > 0;
          const chatSince = bothHere
            ? Math.max(metAt.current, partner!.metAt)
            : 0;
          const chatDone = bothHere && now - chatSince > 6;
          const partnerGone =
            partner == null || meetingOf(meet.partner) == null; // yurib turган bo'lsam ham bekor qilaman (R2)
          if (now > meet.until || chatDone || partnerGone) {
            clearMeeting(agent.id);
            metAt.current = 0;
            seekCd.current = 18 + Math.random() * 20; // yaqinда qayta uchrashmasin
            pause.current = 0.4 + Math.random();
          } else if (Math.hypot(p.x - spot.x, p.z - spot.z) < 0.32) {
            if (metAt.current === 0) metAt.current = now; // joyimga yetdim (sherikni kutaman)
          } else if (
            Math.hypot(p.x - NODES[meet.point].x, p.z - NODES[meet.point].z) <
            1.3
          ) {
            // hub'ga yetdim — oxirgi qadamni O'Z joyimga to'g'ri yuraman
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
          const target =
            firstIdleTrip.current || restingRef.current
              ? breakRoom()
              : idleDestination(agent.role);
          firstIdleTrip.current = false;
          const route = pathBetween(curNode.current, target);
          if (route.length === 0) {
            // Yetib bo'lmaydi — joyimizni qayta aniqlab, biroz kutamiz.
            curNode.current = nearestNode(p.x, p.z);
            pause.current = 0.6 + Math.random();
          } else {
            path.current = route;
            pendingNode.current = target;
          }
        }
      }
    }

    // Harakat — faqat yo'l nuqtalari orasida (graf qirralari devor kesmaydi)
    let moving = false;
    if (path.current.length > 0) {
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
          if (!desiredSit)
            pause.current = restingRef.current
              ? 12 + Math.random() * 10
              : 1.5 + Math.random() * 4;
        }
      } else {
        // QATTIQ to'qnashuv — devor/mebeldan o'tmaydi, sirg'anadi
        const mvx = (dx / dist) * SPEED * dt;
        const mvz = (dz / dist) * SPEED * dt;
        const res = slide(p.x, p.z, mvx, mvz, 0.16);
        // Agent-agent collision — bir-birini ustidan arvohdek o'tmaydi. O'q
        // bo'yicha: agar YANGI joy boshqa agentга tegsa (va hozir tegmayotgan
        // bo'lsak) — o'sha o'q bo'yicha turamiz. (Ichida qolsa — chiqishga ruxsat.)
        const SEP = 0.42;
        let fx = res.x,
          fz = res.z;
        if (
          blockedByAgent(agent.id, fx, p.z, SEP) &&
          !blockedByAgent(agent.id, p.x, p.z, SEP)
        )
          fx = p.x;
        if (
          blockedByAgent(agent.id, fx, fz, SEP) &&
          !blockedByAgent(agent.id, fx, p.z, SEP)
        )
          fz = p.z;
        const moved = Math.hypot(fx - p.x, fz - p.z);
        p.x = fx;
        p.z = fz;
        moving = true;
        speedRef.current = moved / Math.max(dt, 0.001); // m/s — qadam fazasi uchun
        g.rotation.y = dampAngle(g.rotation.y, Math.atan2(-dx, -dz), 10, dt);
        // Tiqilib qolsa — bu nuqtani tashlab, qayta rejalaymiz
        if (moved < SPEED * dt * 0.25) {
          stuck.current += dt;
          if (stuck.current > 0.8) {
            path.current.shift();
            stuck.current = 0;
            if (path.current.length === 0) {
              // Yetib BORMADIK — shuning uchun joriy tugunni HAQIQIY joydan
              // olamiz (pendingNode'ni ishlatsak, graf bo'yicha yolg'on joyda
              // turgan bo'lardik va keyingi yo'l ham noto'g'ri chiqardi).
              curNode.current = nearestNode(p.x, p.z);
              pendingNode.current = null;
              if (!desiredSit) pause.current = 1 + Math.random() * 3;
            }
          }
        } else {
          stuck.current = 0;
        }
      }
    }
    movingRef.current = moving;
    if (!moving) speedRef.current *= Math.max(0, 1 - dt * 6); // to'xtaganda so'nadi

    if (seated.current) g.rotation.y = dampAngle(g.rotation.y, seat.ry, 8, dt);
    g.position.x = p.x;
    g.position.z = p.z;

    // ── Uchrashuv: joyimga yetsam SHERIKKA qarayman; IKKOVIMIZ yetsa gaplashamiz.
    //    Emote FAQAT ikkovi ham yetganда (yolg'iz o'zidan emote yo'q). ──
    const mNow = meetingOf(agent.id);
    const partnerNow = mNow ? presenceOf(mNow.partner) : undefined;
    if (mNow && metAt.current > 0) {
      // Sherik kelgan bo'lsa unga, aks holda hub markaziga (kutish yo'nalishi) qaray
      const tx = partnerNow ? partnerNow.x : NODES[mNow.point].x;
      const tz = partnerNow ? partnerNow.z : NODES[mNow.point].z;
      const dx = tx - p.x,
        dz = tz - p.z;
      if (Math.hypot(dx, dz) > 0.05)
        g.rotation.y = dampAngle(g.rotation.y, Math.atan2(-dx, -dz), 6, dt);
      const bothHere = partnerNow != null && partnerNow.metAt > 0;
      if (bothHere) {
        const since = Math.max(metAt.current, partnerNow!.metAt);
        const el = performance.now() / 1000 - since;
        // both arrived: they chat (badge "Charlando")
        const e = el >= 0 ? "charla" : "";
        if (emoteRef.current !== e) {
          emoteRef.current = e;
          setEmote(e);
        }
      } else if (emoteRef.current !== "") {
        emoteRef.current = "";
        setEmote(""); // sherik hali yo'q — jim kutamiz
      }
    } else if (emoteRef.current !== "") {
      emoteRef.current = "";
      setEmote("");
    }

    // Presence reyestri (throttled ~5/s) — metAt bilan (sherik yetganimni bilsin)
    reportT.current -= dt;
    if (reportT.current <= 0) {
      reportT.current = 0.2;
      report(agent.id, p.x, p.z, statusRef.current === "idle", metAt.current);
    }
  });

  // Single badge (priority in emotes.ts). Stacked layers over the head:
  // label → wait bubble → helper bubble → badge; each one above the previous.
  const face = emoteFor({
    meeting: emote,
    status: agent.status,
    stuck: agent.stuck,
    hot,
    timed,
  });
  const espera = agent.permission
    ? t("burbuja.permiso")
    : agent.question
      ? t("burbuja.pregunta")
      : "";
  // Labels of neighbouring desks are staggered so they do not overlap.
  const escalon = (agent.seatIndex % 3) * 0.75;
  const labelTop = (selected ? 2.7 : 2.28) + escalon;
  const permY = labelTop + 0.3;
  const hireY = (espera ? permY : labelTop) + 0.34;
  const faceY = (hiring ? hireY : espera ? permY : labelTop) + 0.36;
  const ahora = Date.now();

  return (
    <group
      ref={group}
      position={[sit.current.x, 0, sit.current.z]}
      onClick={(e) => {
        e.stopPropagation();
        select(agent.id);
      }}
      onPointerOver={(e) => {
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

      {/* Waiting for a program or an upload (15, 16) */}
      {agent.background && (
        <Html
          portal={capaEtiquetas}
          zIndexRange={[60, 20]}
          position={[0.6, 1.55, 0]}
          center
          style={{ pointerEvents: "none" }}
        >
          <div style={{ ...CAJA, fontSize: 10.5, borderStyle: "dashed" }}>
            {t("burbuja.segundoPlano")}
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

      {/* Waiting for you: permission (13) or answer (14) */}
      {espera && (
        <Html
          portal={capaEtiquetas}
          zIndexRange={[60, 20]}
          position={[0, permY, 0]}
          center
          style={{ pointerEvents: "none" }}
        >
          <div
            style={{
              ...CAJA,
              background: "#111",
              color: "#fff",
              borderColor: "#111",
              fontSize: 12,
              fontWeight: 700,
            }}
          >
            {espera}
          </div>
        </Html>
      )}

      {/* Label: project · account and short state */}
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
              borderColor: color,
              fontSize: 11,
            }}
          >
            <span
              style={{
                width: 7,
                height: 7,
                background: color,
                flexShrink: 0,
              }}
            />
            <span style={{ fontWeight: 700 }}>{titulo}</span>
            {cuenta && <span style={{ color: "#555" }}>{cuenta}</span>}
            <span style={{ color: "#555" }}>
              · {t(`estado.${agent.status}`)}
            </span>
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
              maxWidth: 280,
              whiteSpace: "normal",
              textAlign: "left",
              fontSize: 12,
            }}
          >
            <div style={{ fontWeight: 700 }}>
              {titulo}
              {cuenta ? ` · ${cuenta}` : ""}
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
                <b>{t("detalle.pregunta")}:</b>{" "}
                {recortar(agent.preguntaPendiente, 180)}
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
