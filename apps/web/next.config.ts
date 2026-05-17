import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Required for Docker standalone output
  output: "standalone",

  // Security headers applied to all routes
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-eval' 'unsafe-inline'",
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' data: blob: https:",
              `connect-src 'self' ${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}`,
            ].join("; "),
          },
        ],
      },
    ];
  },

  // Optimize images
  images: {
    formats: ["image/avif", "image/webp"],
    minimumCacheTTL: 3600,
  },
};

export default nextConfig;
