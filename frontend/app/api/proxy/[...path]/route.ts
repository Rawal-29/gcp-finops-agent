/**
 * Same-origin proxy to the FastAPI service. Runs server-side only.
 *
 * The API is a private Cloud Run service, so every upstream request carries an
 * OIDC ID token minted from the metadata server (audience = API_URL). Locally
 * there is no metadata server; requests go out unauthenticated, matching the
 * API's dev mode. API_AUTH_KEY is also attached when set (GKE path).
 */
import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.API_URL ?? "http://localhost:8080";
const API_AUTH_KEY = process.env.API_AUTH_KEY ?? "";
const METADATA_ID_TOKEN_URL =
  "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity";

// Only the endpoints the dashboard actually uses are reachable through the proxy.
const ALLOWED_GET = new Set(["anomalies", "agent/runs", "evals", "health"]);
const ALLOWED_POST = new Set(["query"]);

let cachedToken: { value: string; expiresAt: number } | null = null;

async function getIdToken(): Promise<string | null> {
  if (API_URL.includes("localhost") || API_URL.includes("127.0.0.1")) return null;
  if (cachedToken && Date.now() < cachedToken.expiresAt) return cachedToken.value;
  try {
    const res = await fetch(
      `${METADATA_ID_TOKEN_URL}?audience=${encodeURIComponent(API_URL)}`,
      { headers: { "Metadata-Flavor": "Google" }, cache: "no-store" },
    );
    if (!res.ok) return null;
    const token = await res.text();
    // Tokens live ~1h; refresh early.
    cachedToken = { value: token, expiresAt: Date.now() + 50 * 60_000 };
    return token;
  } catch {
    return null; // no metadata server (local / docker-compose)
  }
}

async function upstreamHeaders(): Promise<Record<string, string>> {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  const token = await getIdToken();
  if (token) h["Authorization"] = `Bearer ${token}`;
  if (API_AUTH_KEY) h["X-API-Key"] = API_AUTH_KEY;
  return h;
}

async function forward(req: NextRequest, path: string, allowed: Set<string>) {
  if (!allowed.has(path)) {
    return NextResponse.json({ detail: "not found" }, { status: 404 });
  }
  const url = `${API_URL}/${path}${req.nextUrl.search}`;
  const res = await fetch(url, {
    method: req.method,
    headers: await upstreamHeaders(),
    body: req.method === "POST" ? await req.text() : undefined,
    cache: "no-store",
  });
  const body = await res.text();
  return new NextResponse(body, {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
  });
}

type Params = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, { params }: Params) {
  const { path } = await params;
  return forward(req, path.join("/"), ALLOWED_GET);
}

export async function POST(req: NextRequest, { params }: Params) {
  const { path } = await params;
  return forward(req, path.join("/"), ALLOWED_POST);
}
