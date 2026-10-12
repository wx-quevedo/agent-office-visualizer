import type { Metadata } from "next";
import { plexMono, plexSans } from "../fuentes";

export const metadata: Metadata = {
  title: "Ajustes",
  description:
    "Reglas de la casa y comandos seguros que usan todos los proyectos",
};

export default function AjustesLayout({
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
