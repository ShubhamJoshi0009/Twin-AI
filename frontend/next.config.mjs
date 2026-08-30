/** @type {import('next').NextConfig} */
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  // Pin the tracing/output root to this frontend directory. Without it Next
  // infers the workspace root from the closest lockfile and can pick a stray
  // package-lock.json outside the repo, breaking `next build`/standalone.
  outputFileTracingRoot: __dirname,
  // Hide the floating Next.js dev-tools logo (bottom-left) in dev mode.
  devIndicators: false,
};

export default nextConfig;
