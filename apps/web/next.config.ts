import type { NextConfig } from "next";

// Proxy /api/* to the FastAPI backend so the browser only ever talks to the web origin.
// This keeps the session cookie first-party (third-party cookies are blocked by default
// in modern browsers), which is what makes cross-service auth work in production.
const apiOrigin = process.env.API_ORIGIN ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiOrigin}/:path*` }];
  },
};

export default nextConfig;
