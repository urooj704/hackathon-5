/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false,          // strict mode doubles renders in dev — off for speed
  swcMinify: true,                 // SWC minifier (faster than Babel)
  compress: true,
  poweredByHeader: false,
  async rewrites() {
    return [
      {
        source: '/api/backend/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
