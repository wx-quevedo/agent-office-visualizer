import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Extra dev hosts (for example a Tailscale IP), comma separated in ALLOWED_DEV_ORIGINS.
  allowedDevOrigins: (process.env.ALLOWED_DEV_ORIGINS ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean),
  // Enable static export for production builds
  output: "export",
  // Disable image optimization (not supported in static export)
  images: {
    unoptimized: true,
  },
  // StrictMode stays off as before (it was turned off for the removed Pixi
  // view). Turning it on needs a check of the 3D scene's double mount first.
  reactStrictMode: false,
};

export default nextConfig;
