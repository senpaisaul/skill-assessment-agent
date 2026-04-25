/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Backend URL exposed to the browser. Defaults to localhost:8000 for dev.
  env: {
    NEXT_PUBLIC_BACKEND_URL: process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000",
  },
};

export default nextConfig;
