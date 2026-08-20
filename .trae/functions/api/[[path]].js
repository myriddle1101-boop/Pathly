// Cloudflare Pages same-origin API bridge.  The browser never needs the
// Railway URL, so its HttpOnly anonymous-session cookie stays on the Pages
// domain and Pathly's existing ownership checks remain effective.
export async function onRequest(context) {
  const backend = context.env.PATHLY_BACKEND_ORIGIN;
  if (!backend) return new Response("PATHLY_BACKEND_ORIGIN is not configured", { status: 503 });

  const incoming = new URL(context.request.url);
  const targetBase = new URL(backend);
  const target = new URL(incoming.pathname + incoming.search, targetBase);
  const headers = new Headers(context.request.headers);
  headers.set("Origin", targetBase.origin);
  headers.delete("Host");
  headers.delete("Content-Length");

  const response = await fetch(target, {
    method: context.request.method,
    headers,
    body: ["GET", "HEAD"].includes(context.request.method) ? undefined : context.request.body,
    redirect: "manual",
  });
  const responseHeaders = new Headers(response.headers);
  responseHeaders.delete("content-encoding");
  return new Response(response.body, { status: response.status, headers: responseHeaders });
}
