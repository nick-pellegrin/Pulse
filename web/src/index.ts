import { serve } from "bun";
import index from "./index.html";

const API_TARGET = "http://localhost:8000";

const server = serve({
  routes: {
    // Proxy API requests to the FastAPI backend (avoids CORS)
    "/api/*": async (req) => {
      const url = new URL(req.url);
      const target = `${API_TARGET}${url.pathname.replace(/^\/api/, "")}${url.search}`;
      return fetch(target, {
        method: req.method,
        headers: req.headers,
        body: req.body,
      });
    },

    // Serve index.html for all unmatched routes (SPA)
    "/*": index,
  },

  development: process.env.NODE_ENV !== "production" && {
    hmr: true,
    console: true,
  },
});

console.log(`Server running at ${server.url}`);
