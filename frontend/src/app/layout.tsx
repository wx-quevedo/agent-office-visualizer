import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import GuardaSesion from "@/components/acceso/GuardaSesion";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Oficina de agentes",
  description: "Los agentes de Claude Code de Washington, en una oficina en vivo",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
        suppressHydrationWarning
      >
        <GuardaSesion />
        {children}
      </body>
    </html>
  );
}
