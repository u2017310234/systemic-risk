/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    optimizePackageImports: ["echarts", "zod"]
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "Link", value: '</data/latest.json>; rel="alternate"; type="application/json", </llms.txt>; rel="llms-txt"' }
        ]
      },
      {
        source: "/data/:path*",
        headers: [
          { key: "Access-Control-Allow-Origin", value: "*" },
          { key: "Access-Control-Allow-Methods", value: "GET, HEAD, OPTIONS" },
          { key: "Access-Control-Allow-Headers", value: "Content-Type, If-None-Match" },
          { key: "Vary", value: "Origin" }
        ]
      },
      { source: "/data/latest.json", headers: [{ key: "Cache-Control", value: "max-age=0, must-revalidate" }] },
      { source: "/data/manifest.json", headers: [{ key: "Cache-Control", value: "max-age=0, must-revalidate" }] },
      { source: "/data/:path*", headers: [{ key: "Cache-Control", value: "public, max-age=3600" }] }
    ];
  }
};

export default nextConfig;
