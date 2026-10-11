import type { Metadata } from "next";
import { plexMono, plexSans } from "../fuentes";

export const metadata: Metadata = {
  title: "Proyectos",
  description:
    "Proyectos creados desde la oficina: carpeta, orquestador y agentes de código",
};

export default function ProyectosLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <div
      className={`${plexSans.variable} ${plexMono.variable}`}
      style={{
        background: "#f4f5f7",
        minHeight: "100dvh",
        colorScheme: "light",
      }}
    >
      {children}
    </div>
  );
}
