import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const maxDuration = 60;

export async function POST(req: NextRequest) {
  const workerUrl = process.env.WORKER_URL?.replace(/\/$/, "");
  const workerKey = process.env.WORKER_API_KEY;
  if (!workerUrl || !workerKey) {
    return NextResponse.json({ error: "The media worker is not configured." }, { status: 503 });
  }
  try {
    const body = await req.json();
    if (typeof body.cursor !== "string" || body.cursor.length > 4096) {
      return NextResponse.json({ error: "A valid continuation cursor is required." }, { status: 400 });
    }
    const upstream = await fetch(`${workerUrl}/v1/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Worker-Key": workerKey },
      body: JSON.stringify({ cursor: body.cursor }),
      cache: "no-store",
      signal: AbortSignal.timeout(55_000),
    });
    const data = await upstream.json().catch(() => ({}));
    return NextResponse.json(data, { status: upstream.status });
  } catch {
    return NextResponse.json({ error: "The media worker could not continue this segment. The cursor may have expired or the worker may be unavailable." }, { status: 502 });
  }
}
