# Architecture

## Deployment split
- **Vercel / Next.js**: responsive UI, public TikTok URL validation, oEmbed metadata lookup, and server-side proxy routes. Worker secrets never reach browser code.
- **Render / Python worker**: public media retrieval, bounded FFmpeg extraction, AudD music-recognition calls, asynchronous job status and signed continuation cursors.
- **AudD**: external music-recognition database. Its API token is stored only in the worker environment.
- **Connected AI agent**: performs wider video understanding and professional context; this skill returns source-backed song candidates and timestamps.

## Song-identification flow
1. User submits a public TikTok HTTPS URL.
2. The Next.js UI starts a song job through a server-side route.
3. Worker validates the TikTok host, retrieves at most one 90-second / 10 MiB segment and extracts up to three 12-second audio samples at offsets 0, 30 and 60 seconds.
4. Worker submits samples to AudD's standard recognition endpoint, deduplicates artist/title candidates and returns available metadata and song links.
5. UI polls the worker job status through Next.js.
6. If more video is accessible, a signed cursor is returned. The next segment is processed only after the user asks to continue.

## Media safety invariants
1. Every downloaded media file is capped at 10 MiB; transfer progress and final file size are checked.
2. Each processing segment is capped at 90 seconds and verified with ffprobe.
3. Only HTTPS TikTok hosts are accepted.
4. DNS results resolving to non-public IP addresses are rejected.
5. Use bounded timeouts and per-job temporary directories.
6. No cookies, login bypass, private-video access, DRM circumvention or video-upload fallback.
7. Return unavailable/no-match/partial states instead of fabricating a song.
8. Do not claim perfect accuracy or invent numeric confidence scores that the provider did not return.

## Job model and limitations
Song jobs are asynchronous FastAPI background tasks and their state is held in worker memory. A worker restart loses queued or in-progress job status. Production reliability requires a durable queue and shared job store. Render free instances may sleep and have limited resources.

## External provider requirements
- Set `AUDD_API_TOKEN` on Render.
- AudD standard recognition is sample-based; the worker sends up to three independent requests per 90-second segment.
- API quotas and billing are controlled by AudD and are not guaranteed free indefinitely.
- Set `WORKER_URL` and `WORKER_API_KEY` on Vercel. Both must remain server-side.
