import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'photos.zillowstatic.com',
      },
    ],
  },
  // 允许在服务器开发模式下通过 IP 访问
  allowedDevOrigins: ['194.163.181.119'],
};

export default nextConfig;
