/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false,
  swcMinify: true,
  compress: true,
  poweredByHeader: false,
  async rewrites() {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    return {
      beforeFiles: [
        {
          source: '/api/backend/:path*',
          destination: `${apiBase}/:path*`,
        },
      ],
    };
  },
};

module.exports = nextConfig;
