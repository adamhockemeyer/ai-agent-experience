/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Add experimental features for Next.js 15
  experimental: {

  },
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  output: 'standalone',
};

export default nextConfig;
