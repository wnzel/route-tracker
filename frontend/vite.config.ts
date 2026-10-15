/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // In Docker the API is the "web" service; running Vite on the host, it's localhost.
    proxy: { "/api": process.env.API_PROXY_TARGET ?? "http://localhost:8000" },
    // File change events don't cross a Windows bind mount into the container, so poll instead.
    watch: process.env.VITE_USE_POLLING ? { usePolling: true, interval: 300 } : undefined,
  },
  test: {
    environment: "node",
  },
});
