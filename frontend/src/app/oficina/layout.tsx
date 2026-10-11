import type { Metadata } from "next";
import { plexMono, plexSans } from "../fuentes";

export const metadata: Metadata = {
  title: "Oficina de agentes",
  description:
    "Estado de los agentes de Claude Code, agrupado por urgencia o por proyecto",
};

export default function OficinaLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className={`${plexSans.variable} ${plexMono.variable}`}>
      {children}
    </div>
  );
}
