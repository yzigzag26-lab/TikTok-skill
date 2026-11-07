# Python media and song-recognition worker

This service retrieves accessible public TikTok media and identifies music using AudD. It is separate from Vercel.

## Song identification API

All endpoints require `X-Worker-Key`.

Start a job:

```bash
curl -X POST "$WORKER_URL/v1/song-jobs" \
  -H "Content-Type: application/json" \
  -H "X-Worker-Key: $WORKER_API_KEY" \
  -d '{"url":"https://www.tiktok.com/@creator/video/1234567890"}'
```

Poll the returned job ID:

```bash
curl "$WORKER_URL/v1/song-jobs/JOB_ID" \
  -H "X-Worker-Key: $WORKER_API_KEY"
```

When the result contains `next_cursor`, start another job with that cursor only when the user asks to continue:

```bash
curl -X POST "$WORKER_URL/v1/song-jobs" \
  -H "Content-Type: application/json" \
  -H "X-Worker-Key: $WORKER_API_KEY" \
  -d '{"cursor":"PASTE_NEXT_CURSOR"}'
```

Each job processes one segment, no longer than 90 seconds. The signed cursor is bound to the original TikTok URL and expires after six hours.

## Recognition strategy

- Extracts three separate 12-second MP3 samples at approximately 0, 30 and 60 seconds into each segment.
- Sends each sample to AudD's standard recognition endpoint.
- Deduplicates repeated artist/title matches and returns the sample timestamp, provider metadata and available song links.
- Does not manufacture confidence percentages: the standard AudD response does not reliably provide a numeric match score.
- Returns `not_configured` when `AUDD_API_TOKEN` is missing and `no_match` when sampled audio returns no recognized song.

A provider match is a candidate, not a guarantee. Short, noisy, remixed, sped-up or voice-over-heavy clips can fail to match or return an incorrect result. Later segments may contain a different song and are only processed after explicit continuation.

## Limits

- Downloaded media file: maximum 10,485,760 bytes (10 MiB).
- Segment duration: maximum 90 seconds.
- AudD standard recognition accepts short audio samples (the provider documents a 10 MB file limit and analyses up to about 12 seconds on its standard endpoint).
- This worker sends up to three provider requests per segment. Each request may count against the AudD plan.
- Temporary media is removed after each job.
- No browser cookies, account credentials, login bypass, private-video access or DRM circumvention.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| WORKER_API_KEY | required | Authenticates API callers |
| CURSOR_SECRET | required | Signs continuation cursors |
| AUDD_API_TOKEN | empty | AudD music-recognition token |
| MAX_MEDIA_BYTES | 10485760 | Hard cap; cannot exceed 10 MiB |
| MAX_SEGMENT_SECONDS | 90 | Hard cap; cannot exceed 90 seconds |
| WHISPER_MODEL | tiny | Used by the optional full evidence endpoint |
| WHISPER_DEVICE | cpu | Whisper inference device |
| WHISPER_COMPUTE_TYPE | int8 | Whisper CPU quantization |

## Deploy on Render

1. Create a Blueprint from the repository root and use `render.yaml`.
2. Set `AUDD_API_TOKEN` in the worker environment. It is intentionally not auto-generated.
3. Keep `WORKER_API_KEY` and `CURSOR_SECRET` secret.
4. Wait for deployment and verify `/health`.
5. In Vercel, set `WORKER_URL` and `WORKER_API_KEY` as server-only environment variables.

The free Render plan can sleep or run out of resources. Job state is in memory, so worker restarts lose in-flight jobs and continuation cursors remain usable only if their source can be fetched again. A larger instance or durable job storage is needed for production reliability.
