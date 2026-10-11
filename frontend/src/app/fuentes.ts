import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";

/** IBM Plex Sans and Mono of the office pages (the variables go on a wrapper). */
export const plexSans = IBM_Plex_Sans({
  variable: "--font-plex-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});
