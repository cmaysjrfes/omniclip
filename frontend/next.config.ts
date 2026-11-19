import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  images: { unoptimized: true }, // thumbnails are presigned S3 URLs
};

export default nextConfig;
