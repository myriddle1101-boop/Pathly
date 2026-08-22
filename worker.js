/**
 * Cloudflare edge entry point for the Pathly pilot.
 * Static learner UI is served from Assets. API calls are proxied to Railway so
 * the browser keeps one same-origin HttpOnly session cookie.
 */
export default {
  async fetch(request, env) {
    const incoming = new URL(request.url);
    if (incoming.pathname.startsWith("/api/")) {
      if (!env.PATHLY_BACKEND_ORIGIN) {
        return new Response("Pathly backend is not configured", { status: 503 });
      }
      const backend = new URL(env.PATHLY_BACKEND_ORIGIN);
      const target = new URL(incoming.pathname + incoming.search, backend);
      const headers = new Headers(request.headers);
      headers.set("Origin", backend.origin);
      headers.delete("Host");
      headers.delete("Content-Length");
      return fetch(target, {
        method: request.method,
        headers,
        body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
        redirect: "manual",
      });
    }

    if (incoming.pathname === "/") incoming.pathname = "/index.html";
    return env.ASSETS.fetch(new Request(incoming.toString(), request));
  },
};
