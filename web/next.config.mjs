/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static files only: regwatch serves them from the Python package with no Node at run time.
  output: "export",
  // Each page becomes a folder with an index.html, which the local server resolves.
  trailingSlash: true,
  images: { unoptimized: true },
  poweredByHeader: false,
  productionBrowserSourceMaps: false,
  devIndicators: false,
  // A fixed id, so building the same source twice gives the same files.
  generateBuildId: async () => "regwatch",
};

export default nextConfig;
