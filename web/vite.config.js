import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

export default defineConfig({
  plugins: [react()],
  // node_modules is a symlink to node_modules.nosync (iCloud workaround). Without
  // this, Vite serves raw CommonJS from the real path and dev mode fails to load.
  resolve: { preserveSymlinks: true },
  // Raw imports use query-suffixed IDs; allow their public evidence directory.
  server: { fs: { allow: [fileURLToPath(new URL("./", import.meta.url)),
    fileURLToPath(new URL("../docs/artifacts/target-readout-2026-11-10/", import.meta.url))] } },
  test: {
    include: ["src/**/*.test.{js,jsx,ts,tsx}"],
    exclude: ["node_modules/**", "node_modules.nosync/**", "node_modules 2/**", "dist/**"],
    environment: "jsdom",
    setupFiles: "./src/test-setup.js",
    globals: true,
    pool: "threads",
    fileParallelism: false,
    maxWorkers: 1,
  },
});
