// vite.config.ts
import { defineConfig } from "file:///Users/ddt/work/projects/ai_agent/aos-platform/node_modules/.pnpm/vitest@2.1.9_jsdom@25.0.1/node_modules/vitest/dist/config.js";
import react from "file:///Users/ddt/work/projects/ai_agent/aos-platform/node_modules/.pnpm/@vitejs+plugin-react@4.7.0_vite@5.4.21/node_modules/@vitejs/plugin-react/dist/index.js";
import path from "node:path";
import { fileURLToPath } from "node:url";
var __vite_injected_original_import_meta_url = "file:///Users/ddt/work/projects/ai_agent/aos-platform/apps/web/vite.config.ts";
var root = path.dirname(fileURLToPath(__vite_injected_original_import_meta_url));
var apiProxyTarget = process.env.VITE_AOS_API_PROXY_TARGET?.trim() || "http://127.0.0.1:8080";
var vite_config_default = defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@aos/ontology-sdk": path.resolve(root, "../../packages/ontology-sdk/src/index.ts")
    }
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: apiProxyTarget,
        changeOrigin: true,
        rewrite: (requestPath) => requestPath.replace(/^\/api/, "")
      }
    }
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          "vendor-react": ["react", "react-dom"],
          "vendor-router": ["react-router-dom"]
        }
      }
    }
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"]
  }
});
export {
  vite_config_default as default
};
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsidml0ZS5jb25maWcudHMiXSwKICAic291cmNlc0NvbnRlbnQiOiBbImNvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9kaXJuYW1lID0gXCIvVXNlcnMvZGR0L3dvcmsvcHJvamVjdHMvYWlfYWdlbnQvYW9zLXBsYXRmb3JtL2FwcHMvd2ViXCI7Y29uc3QgX192aXRlX2luamVjdGVkX29yaWdpbmFsX2ZpbGVuYW1lID0gXCIvVXNlcnMvZGR0L3dvcmsvcHJvamVjdHMvYWlfYWdlbnQvYW9zLXBsYXRmb3JtL2FwcHMvd2ViL3ZpdGUuY29uZmlnLnRzXCI7Y29uc3QgX192aXRlX2luamVjdGVkX29yaWdpbmFsX2ltcG9ydF9tZXRhX3VybCA9IFwiZmlsZTovLy9Vc2Vycy9kZHQvd29yay9wcm9qZWN0cy9haV9hZ2VudC9hb3MtcGxhdGZvcm0vYXBwcy93ZWIvdml0ZS5jb25maWcudHNcIjtpbXBvcnQgeyBkZWZpbmVDb25maWcgfSBmcm9tIFwidml0ZXN0L2NvbmZpZ1wiO1xuaW1wb3J0IHJlYWN0IGZyb20gXCJAdml0ZWpzL3BsdWdpbi1yZWFjdFwiO1xuaW1wb3J0IHBhdGggZnJvbSBcIm5vZGU6cGF0aFwiO1xuaW1wb3J0IHsgZmlsZVVSTFRvUGF0aCB9IGZyb20gXCJub2RlOnVybFwiO1xuXG5jb25zdCByb290ID0gcGF0aC5kaXJuYW1lKGZpbGVVUkxUb1BhdGgoaW1wb3J0Lm1ldGEudXJsKSk7XG5jb25zdCBhcGlQcm94eVRhcmdldCA9IHByb2Nlc3MuZW52LlZJVEVfQU9TX0FQSV9QUk9YWV9UQVJHRVQ/LnRyaW0oKSB8fCBcImh0dHA6Ly8xMjcuMC4wLjE6ODA4MFwiO1xuXG5leHBvcnQgZGVmYXVsdCBkZWZpbmVDb25maWcoe1xuICBwbHVnaW5zOiBbcmVhY3QoKV0sXG4gIHJlc29sdmU6IHtcbiAgICBhbGlhczoge1xuICAgICAgXCJAYW9zL29udG9sb2d5LXNka1wiOiBwYXRoLnJlc29sdmUocm9vdCwgXCIuLi8uLi9wYWNrYWdlcy9vbnRvbG9neS1zZGsvc3JjL2luZGV4LnRzXCIpLFxuICAgIH0sXG4gIH0sXG4gIHNlcnZlcjoge1xuICAgIHBvcnQ6IDUxNzMsXG4gICAgcHJveHk6IHtcbiAgICAgIFwiL2FwaVwiOiB7XG4gICAgICAgIHRhcmdldDogYXBpUHJveHlUYXJnZXQsXG4gICAgICAgIGNoYW5nZU9yaWdpbjogdHJ1ZSxcbiAgICAgICAgcmV3cml0ZTogKHJlcXVlc3RQYXRoKSA9PiByZXF1ZXN0UGF0aC5yZXBsYWNlKC9eXFwvYXBpLywgXCJcIiksXG4gICAgICB9LFxuICAgIH0sXG4gIH0sXG4gIGJ1aWxkOiB7XG4gICAgcm9sbHVwT3B0aW9uczoge1xuICAgICAgb3V0cHV0OiB7XG4gICAgICAgIG1hbnVhbENodW5rczoge1xuICAgICAgICAgIFwidmVuZG9yLXJlYWN0XCI6IFtcInJlYWN0XCIsIFwicmVhY3QtZG9tXCJdLFxuICAgICAgICAgIFwidmVuZG9yLXJvdXRlclwiOiBbXCJyZWFjdC1yb3V0ZXItZG9tXCJdLFxuICAgICAgICB9LFxuICAgICAgfSxcbiAgICB9LFxuICB9LFxuICB0ZXN0OiB7XG4gICAgZW52aXJvbm1lbnQ6IFwianNkb21cIixcbiAgICBpbmNsdWRlOiBbXCJzcmMvKiovKi50ZXN0LnRzXCIsIFwic3JjLyoqLyoudGVzdC50c3hcIl0sXG4gIH0sXG59KTtcbiJdLAogICJtYXBwaW5ncyI6ICI7QUFBdVYsU0FBUyxvQkFBb0I7QUFDcFgsT0FBTyxXQUFXO0FBQ2xCLE9BQU8sVUFBVTtBQUNqQixTQUFTLHFCQUFxQjtBQUh3TCxJQUFNLDJDQUEyQztBQUt2USxJQUFNLE9BQU8sS0FBSyxRQUFRLGNBQWMsd0NBQWUsQ0FBQztBQUN4RCxJQUFNLGlCQUFpQixRQUFRLElBQUksMkJBQTJCLEtBQUssS0FBSztBQUV4RSxJQUFPLHNCQUFRLGFBQWE7QUFBQSxFQUMxQixTQUFTLENBQUMsTUFBTSxDQUFDO0FBQUEsRUFDakIsU0FBUztBQUFBLElBQ1AsT0FBTztBQUFBLE1BQ0wscUJBQXFCLEtBQUssUUFBUSxNQUFNLDBDQUEwQztBQUFBLElBQ3BGO0FBQUEsRUFDRjtBQUFBLEVBQ0EsUUFBUTtBQUFBLElBQ04sTUFBTTtBQUFBLElBQ04sT0FBTztBQUFBLE1BQ0wsUUFBUTtBQUFBLFFBQ04sUUFBUTtBQUFBLFFBQ1IsY0FBYztBQUFBLFFBQ2QsU0FBUyxDQUFDLGdCQUFnQixZQUFZLFFBQVEsVUFBVSxFQUFFO0FBQUEsTUFDNUQ7QUFBQSxJQUNGO0FBQUEsRUFDRjtBQUFBLEVBQ0EsT0FBTztBQUFBLElBQ0wsZUFBZTtBQUFBLE1BQ2IsUUFBUTtBQUFBLFFBQ04sY0FBYztBQUFBLFVBQ1osZ0JBQWdCLENBQUMsU0FBUyxXQUFXO0FBQUEsVUFDckMsaUJBQWlCLENBQUMsa0JBQWtCO0FBQUEsUUFDdEM7QUFBQSxNQUNGO0FBQUEsSUFDRjtBQUFBLEVBQ0Y7QUFBQSxFQUNBLE1BQU07QUFBQSxJQUNKLGFBQWE7QUFBQSxJQUNiLFNBQVMsQ0FBQyxvQkFBb0IsbUJBQW1CO0FBQUEsRUFDbkQ7QUFDRixDQUFDOyIsCiAgIm5hbWVzIjogW10KfQo=
