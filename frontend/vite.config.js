import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      "/analyze": "http://localhost:8000",
      "/knowledge-base": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
  test: {
    environment: "happy-dom",
    globals: true,
    setupFiles: "./src/test/setup.js",
  },
});
