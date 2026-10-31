import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { Plugin, ProxyOptions, ViteDevServer } from "vite";

const root = path.dirname(fileURLToPath(import.meta.url));
const apiProxyTarget = process.env.VITE_AOS_API_PROXY_TARGET?.trim() || "http://127.0.0.1:8080";
const renewalPrefix = "/api/v1/aip/budget-policy-renewal";

export function createBudgetRenewalTransport(target: string | undefined): {
  plugins: Plugin[];
  proxy: Record<string, ProxyOptions>;
} {
  // Deliberately accept one literal endpoint, without URL normalization or a default writer.
  const configured = target === "http://127.0.0.1:18462";
  const installBoundary = (server: Pick<ViteDevServer, "middlewares">) => {
    // Runs before Vite's generic proxy. Vite's bypass(false) forces a 404.
    server.middlewares.use((req, res, next) => {
      if (configured || !req.url?.startsWith(renewalPrefix)) return next();
      res.statusCode = 503;
      res.setHeader("content-type", "application/json; charset=utf-8");
      res.setHeader("cache-control", "no-store");
      res.end(JSON.stringify({ error: "BUDGET_RENEWAL_GATEWAY_UNAVAILABLE" }));
    });
  };
  return {
    plugins: [{
      name: "aos-budget-renewal-closed-boundary",
      configureServer: installBoundary,
      configurePreviewServer: installBoundary,
    }],
    proxy: configured ? {
      [renewalPrefix]: {
        target,
        changeOrigin: true,
        ws: false,
        rewrite: (requestPath) => requestPath.replace(/^\/api/, ""),
      },
    } : {},
  };
}

const renewalTransport = createBudgetRenewalTransport(process.env.AOS_BUDGET_RENEWAL_PROXY_TARGET);

export default defineConfig({
  plugins: [react(), ...renewalTransport.plugins],
  resolve: {
    alias: {
      "@aos/ontology-sdk": path.resolve(root, "../../packages/ontology-sdk/src/index.ts"),
    },
  },
  server: {
    hmr: process.env.VITE_AOS_HMR === "0" ? false : undefined,
    port: 5173,
    proxy: {
      ...renewalTransport.proxy,
      "/api": {
        target: apiProxyTarget,
        changeOrigin: true,
        rewrite: (requestPath) => requestPath.replace(/^\/api/, ""),
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          "vendor-react": ["react", "react-dom"],
          "vendor-router": ["react-router-dom"],
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
});
