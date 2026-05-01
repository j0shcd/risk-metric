import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: "./src/test-setup.js",
    globals: true,
    pool: "threads",
    fileParallelism: false,
    maxWorkers: 1,
  },
});
