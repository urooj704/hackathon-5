/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false,          // strict mode doubles renders in dev — off for speed
  swcMinify: true,                 // SWC minifier (faster than Babel)
  compress: true,
  poweredByHeader: false,
  async rewrites() {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    return [
      {
        source: '/api/backend/:path*',
        destination: `${apiBase}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
