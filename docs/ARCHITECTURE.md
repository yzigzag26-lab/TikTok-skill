# Architecture

## Deployment split
- **Vercel / Next.js**: web interface, URL validation, short API orchestration, optional Groq context note.
- **Media worker (separate service)**: Python FastAPI service under `worker/`, using yt-dlp, FFmpeg, Faster-Whisper, RapidOCR and OpenCV. It must not run as a long media job inside a Vercel Function.
- **Adapters**: REST API first; MCP stdio and remote Streamable HTTP planned over the same normalized core.

## Current service boundaries
The Next.js endpoint currently uses TikTok public oEmbed metadata. The Python worker independently retrieves and analyzes bounded media segments. The Vercel UI is not yet wired to the worker; callers use the worker REST endpoint with a server-side API key.

## Media safety invariants
1. Each media file is at most 10 MB.
2. Each processing segment is at most 90 seconds.
3. Validate TikTok hosts and HTTPS before fetching.
4. Worker must reject private IP destinations, unsafe redirects, arbitrary local paths and unsupported hosts.
5. Use bounded timeouts, temporary storage and cleanup.
6. Do not bypass private/login restrictions or platform protections.
7. Return unavailable/partial status instead of fabricating content.

## Next milestones
1. Add Python worker with job queue and object storage upload path.
2. Implement media retrieval with strict size/duration validation and sequential continuation tokens.
3. Add timestamped transcription, OCR, keyframes and optional music recognition.
4. Add authenticated REST and MCP adapters; test locally and in cloud.
