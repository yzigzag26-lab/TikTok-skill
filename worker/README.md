# Python media worker

This service runs outside Vercel. It accepts a public TikTok URL or a signed continuation cursor and processes exactly one bounded segment per request.

## Endpoints

- `GET /health` — health and configured hard limits.
- `POST /v1/analyze` — retrieve and analyze one segment.

All analysis requests require `X-Worker-Key`.

Start a new analysis:

```bash
curl -X POST "$WORKER_URL/v1/analyze" \
  -H "Content-Type: application/json" \
  -H "X-Worker-Key: $WORKER_API_KEY" \
  -d '{"url":"https://www.tiktok.com/@creator/video/1234567890"}'
```

Continue only when the response contains `next_cursor`:

```bash
curl -X POST "$WORKER_URL/v1/analyze" \
  -H "Content-Type: application/json" \
  -H "X-Worker-Key: $WORKER_API_KEY" \
  -d '{"cursor":"PASTE_NEXT_CURSOR"}'
```

A cursor is HMAC-signed, bound to the original TikTok URL, and expires after six hours. A request may contain either `url` or `cursor`, never both.

## Hard limits and processing

- Maximum source media file: 10,485,760 bytes (10 MiB).
- Maximum requested segment: 90 seconds.
- A download progress hook monitors bytes across downloaded media fragments and aborts when the transfer exceeds the cap. The completed output is checked again on disk.
- ffprobe checks the actual segment duration before transcription or OCR. Files over either limit are discarded.
- yt-dlp is used without browser cookies or login credentials. Private/login-walled content is not supported.
- Temporary files are created in a per-request temporary directory and deleted automatically.
- Speech recognition uses Faster-Whisper (tiny/int8 by default).
- OCR uses RapidOCR on at most 30 sampled frames.
- Up to six resized JPEG keyframes are returned as base64 data with absolute timestamps.
- Transcript and OCR timestamps are relative to the original video timeline.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| WORKER_API_KEY | required | API authentication |
| CURSOR_SECRET | required | HMAC signing of continuation cursors |
| MAX_MEDIA_BYTES | 10485760 | Hard cap; cannot be configured above 10 MiB |
| MAX_SEGMENT_SECONDS | 90 | Hard cap; cannot be configured above 90 seconds |
| WHISPER_MODEL | tiny | Faster-Whisper model |
| WHISPER_DEVICE | cpu | Inference device |
| WHISPER_COMPUTE_TYPE | int8 | CPU quantization |

## Deploy on Render

1. In Render, create a new Blueprint from this repository and select the root `render.yaml`.
2. Render creates the worker service from `worker/Dockerfile`.
3. Set `WORKER_API_KEY` and `CURSOR_SECRET` to long random values if not auto-generated.
4. Wait for the build and call `/health`.
5. Save the service URL and API key as server-only environment variables in any trusted caller. Never expose the worker key in browser JavaScript.

The blueprint uses Render's free plan as a starting point. Free instances can sleep and have constrained RAM/CPU; model initialization or OCR/transcription may be slow or run out of memory. If this happens, use a larger worker instance or move speech recognition to a managed inference API. The free plan is a deployment experiment, not a performance guarantee.

## Important constraints

TikTok may block or change public media retrieval. The worker does not bypass login, private-video permissions, DRM, or other access controls. If retrieval fails, the API returns an explicit unavailable error. No transcript, OCR or keyframe content is fabricated.

The current worker does not identify music, and it does not yet use a durable job queue. One HTTP request processes one segment synchronously. For longer cloud jobs, the next architecture step is a queue + job-status endpoint so client connections do not need to remain open.
