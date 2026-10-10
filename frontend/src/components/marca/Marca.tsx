/**
 * Demo Org account mark: the isotype (small, labels and desks) or the full logo
 * (only where there is room, e.g. the agent detail). The personal account has
 * no mark. "Demo Org" as text only in the alt and the tooltip.
 */

import Image from "next/image";

const ISOTIPO = { src: "/logos/isotipo-demo.png", ancho: 131, alto: 119 };
const LOGO = { src: "/logos/logo-demo.png", ancho: 377, alto: 132 };

export function Isotipo({ alto = 16 }: { alto?: number }) {
  return (
    <Image
      src={ISOTIPO.src}
      alt="Demo Org"
      title="Demo Org"
      width={Math.round((alto * ISOTIPO.ancho) / ISOTIPO.alto)}
      height={alto}
      unoptimized
      style={{
        display: "inline-block",
        verticalAlign: "middle",
        flexShrink: 0,
      }}
    />
  );
}

export function LogoDemoOrg({ alto = 28 }: { alto?: number }) {
  return (
    <Image
      src={LOGO.src}
      alt="Demo Org"
      title="Demo Org"
      width={Math.round((alto * LOGO.ancho) / LOGO.alto)}
      height={alto}
      unoptimized
      style={{
        display: "inline-block",
        verticalAlign: "middle",
        flexShrink: 0,
      }}
    />
  );
}

/** Isotype for the Demo Org account; nothing for the personal one. */
export function MarcaCuenta({
  cuenta,
  alto = 16,
}: {
  cuenta: string | null;
  alto?: number;
}) {
  return cuenta === "demo" ? <Isotipo alto={alto} /> : null;
}
