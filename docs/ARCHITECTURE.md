# Architecture

## Deployment split
- **Vercel / Next.js**: web interface, URL validation, short API orchestration, optional Groq context note.
- **Media worker (separate service)**: future Python service for FFmpeg, yt-dlp-compatible public retrieval, lightweight transcription, OCR and keyframes. It must not run as a long media job inside a Vercel Function.
- **Adapters**: REST API first; MCP stdio and remote Streamable HTTP planned over the same normalized core.

## Current MVP boundary
The current endpoint uses TikTok public oEmbed. It does not retrieve the actual video file. No transcript, OCR, audio fingerprint or keyframes are returned yet. Groq is optional and receives only public metadata plus the user's research question.

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
