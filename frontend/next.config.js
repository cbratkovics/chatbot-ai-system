/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  trailingSlash: true,
  images: { unoptimized: true },
  eslint: {
    ignoreDuringBuilds: true, // npm run lint is a separate release gate.
  },
};

// The public build must never inherit a previous hosted-chat deployment's settings.
if (process.env.NODE_ENV === 'production' &&
    (process.env.NEXT_PUBLIC_API_URL || process.env.NEXT_PUBLIC_WS_URL)) {
  throw new Error('Static export needs no backend. Remove NEXT_PUBLIC_API_URL and NEXT_PUBLIC_WS_URL before building.');
}

module.exports = nextConfig;
