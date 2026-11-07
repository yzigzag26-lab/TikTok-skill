import { createHmac, randomUUID } from "node:crypto";
import { NextResponse } from "next/server";

export const runtime = "nodejs";

export async function POST() {
  const workerUrl = process.env.WORKER_URL?.replace(/\/$/, "");
  const secret = process.env.CURSOR_SECRET;
  if (!workerUrl || !secret) {
    return NextResponse.json({ error: "Video uploads are not configured yet. Set WORKER_URL and CURSOR_SECRET on the Vercel server." }, { status: 503 });
  }
  const payload = Buffer.from(JSON.stringify({
    purpose: "upload",
    exp: Math.floor(Date.now() / 1000) + 5 * 60,
    nonce: randomUUID(),
  })).toString("base64url");
  const signature = createHmac("sha256", secret).update(payload).digest("hex");
  return NextResponse.json({ uploadUrl: `${workerUrl}/v1/upload`, uploadToken: `${payload}.${signature}` });
}
