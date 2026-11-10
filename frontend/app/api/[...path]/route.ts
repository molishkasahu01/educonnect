import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

function resolveBackendOrigin(): string | null {
  const raw = (process.env.BACKEND_URL || process.env.BACKEND_INTERNAL_URL || "").trim().replace(/\/$/, "");
  if (!raw) return null;
  if (raw.startsWith("http://") || raw.startsWith("https://")) return raw;
  return `https://${raw}`;
}

async function proxyRequest(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
): Promise<Response> {
  const origin = resolveBackendOrigin();
  if (!origin) {
    return Response.json(
      { detail: "BACKEND_URL is not configured on the frontend proxy." },
      { status: 500 }
    );
  }

  const { path } = await context.params;
  const search = request.nextUrl.search || "";
  const targetUrl = `${origin}/api/${path.join("/")}${search}`;

  const headers = new Headers();
  const forwardHeaders = ["authorization", "content-type", "accept"];
  for (const h of forwardHeaders) {
    const val = request.headers.get(h);
    if (val) headers.set(h, val);
  }

  const hasBody = !["GET", "HEAD"].includes(request.method.toUpperCase());
  const body = hasBody ? await request.arrayBuffer() : undefined;

  const upstream = await fetch(targetUrl, {
    method: request.method,
    headers,
    body,
    redirect: "manual",
  });

  const respHeaders = new Headers();
  for (const h of ["content-type", "content-disposition", "cache-control"]) {
    const val = upstream.headers.get(h);
    if (val) respHeaders.set(h, val);
  }

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: respHeaders,
  });
}

export const GET = proxyRequest;
export const POST = proxyRequest;
export const PUT = proxyRequest;
export const PATCH = proxyRequest;
export const DELETE = proxyRequest;
export const OPTIONS = proxyRequest;
