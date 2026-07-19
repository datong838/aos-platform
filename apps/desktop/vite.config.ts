import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const webSrc = path.resolve(__dirname, "../web/src");
const ontologySdkSrc = path.resolve(__dirname, "../../packages/ontology-sdk/src/index.ts");
const reactPkg = path.resolve(__dirname, "node_modules/react");
const reactDomPkg = path.resolve(__dirname, "node_modules/react-dom");

// @ts-expect-error process is a nodejs global
const host = process.env.TAURI_DEV_HOST;

export default defineConfig(async () => ({
  plugins: [react()],
  resolve: {
    alias: {
      "@aos-web": webSrc,
      "@aos/ontology-sdk": ontologySdkSrc,
      react: reactPkg,
      "react-dom": reactDomPkg,
    },
    dedupe: ["react", "react-dom", "react-router-dom"],
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    host: host || false,
    fs: {
      allow: [path.resolve(__dirname, "..")],
    },
    hmr: host
      ? {
          protocol: "ws",
          host,
          port: 1421,
        }
      : undefined,
    watch: {
      ignored: ["**/src-tauri/**"],
    },
  },
}));
