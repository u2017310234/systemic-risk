/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    optimizePackageImports: ["echarts", "zod"]
  }
};

export default nextConfig;
