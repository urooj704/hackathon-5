/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false,
  swcMinify: true,
  compress: true,
  poweredByHeader: false,
  // ESLint errors should not block production builds
  eslint: {
    ignoreDuringBuilds: true,
  },
};

module.exports = nextConfig;
