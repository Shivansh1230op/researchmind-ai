import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  distDir: process.env.NEXT_DIST_DIR || ".next",
  output: "standalone",
  devIndicators: false,
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_STORAGE_BACKEND: process.env.VERCEL ? "vercel_blob" : "local",
  },
  // Same-origin API proxy for local use and hosted deployments.
  async rewrites() {
    if (process.env.VERCEL) return [];
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.API_PROXY_URL || "http://127.0.0.1:8000"}/:path*`,
      },
    ];
  },
};

export default nextConfig;
