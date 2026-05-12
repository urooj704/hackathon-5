/**
 * Public backend base URL for server-side API routes (no trailing slash).
 * Set BACKEND_URL or NEXT_PUBLIC_API_URL in Vercel / .env.local.
 */
const DEFAULT_BACKEND_PUBLIC_URL = 'https://ujjee-hackathon-5.hf.space';

export function getServerBackendUrl() {
  const raw =
    process.env.BACKEND_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    DEFAULT_BACKEND_PUBLIC_URL;
  return String(raw).replace(/\/$/, '');
}
