import type { Metadata } from "next";
import { plexMono, plexSans } from "../fuentes";

export const metadata: Metadata = {
  title: "Dónde quedamos",
  description:
    "Dónde quedó cada proyecto: plan, prompts, lo último y lo siguiente",
};

export default function DondeLayout({
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
