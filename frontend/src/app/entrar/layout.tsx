import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";

const plexSans = IBM_Plex_Sans({
  variable: "--font-plex-sans",
  subsets: ["latin"],
  weight: ["400", "600", "700"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "600"],
});

export const metadata: Metadata = {
  title: "Entrar · Oficina de agentes",
  description: "Inicio de sesión de la oficina de agentes",
};

export default function EntrarLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className={`${plexSans.variable} ${plexMono.variable}`}>
      {children}
    </div>
  );
}
