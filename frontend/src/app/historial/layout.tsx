import type { Metadata } from "next";
import { plexMono, plexSans } from "../fuentes";

export const metadata: Metadata = {
  title: "Historial del agente",
  description: "Todos los turnos de un agente, del más reciente al más antiguo",
};

export default function HistorialLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <div
      className={`${plexSans.variable} ${plexMono.variable}`}
      style={{
        background: "#ffffff",
        minHeight: "100dvh",
        colorScheme: "light",
      }}
    >
      {children}
    </div>
  );
}
