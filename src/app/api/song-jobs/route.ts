import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const maxDuration = 10;

function config() {
  const url = process.env.WORKER_URL?.replace(/\/$/, "");
  const key = process.env.WORKER_API_KEY;
  if (!url || !key) throw new Error("Set WORKER_URL and WORKER_API_KEY in Vercel environment variables.");
  return { url, key };
}

export async function POST(req: NextRequest) {
  try {
    const { url, key } = config();
    const body = await req.json();
    if ((typeof body.url === "string") === (typeof body.cursor === "string")) {
      return NextResponse.json({ error: "Provide exactly one TikTok URL or continuation cursor." }, { status: 400 });
    }
    const upstream = await fetch(`${url}/v1/song-jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Worker-Key": key },
      body: JSON.stringify(body),
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
    const data = await upstream.json().catch(() => ({}));
    return NextResponse.json(data, { status: upstream.status });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "Could not start song identification." }, { status: 503 });
  }
}

export async function GET(req: NextRequest) {
  try {
    const { url, key } = config();
    const jobId = req.nextUrl.searchParams.get("jobId") || "";
    if (!/^[a-f0-9]{32}$/.test(jobId)) return NextResponse.json({ error: "A valid jobId is required." }, { status: 400 });
    const upstream = await fetch(`${url}/v1/song-jobs/${jobId}`, {
      headers: { "X-Worker-Key": key },
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
    const data = await upstream.json().catch(() => ({}));
    return NextResponse.json(data, { status: upstream.status });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "Could not read song-identification status." }, { status: 503 });
  }
}
