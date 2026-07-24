import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@aos/ontology-sdk": path.resolve(root, "../../packages/ontology-sdk/src/index.ts"),
    },
  },
  server: { port: 5173 },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.ts"],
  },
});
