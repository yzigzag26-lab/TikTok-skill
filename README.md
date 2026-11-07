# TikTok Intelligence Skill

Evidence-first TikTok link analysis for AI agents.

This repository currently contains a **Vercel-ready Next.js MVP**:
- Responsive analysis workspace.
- Strict HTTPS TikTok hostname validation.
- Public TikTok oEmbed metadata retrieval.
- Optional Groq context note using metadata only.
- JSON report with explicit evidence limitations.
- Agent skill instructions and architecture documentation.

## Important current scope

The repository now includes a separate Python media worker under `worker/`. It retrieves public TikTok segments, enforces a 10 MiB media-file cap and a strict 90-second segment cap, and extracts timestamped speech, OCR and keyframes. Each request processes one segment and returns a signed continuation cursor when more accessible video remains. See [worker/README.md](worker/README.md).

The worker is a separate service, not a Vercel Function. Its runtime and model performance still need deployment verification. Music identification is not implemented yet.

## Deploy to Vercel

1. Import `https://github.com/yzigzag26-lab/TikTok-skill` into Vercel.
2. Framework preset: **Next.js**.
3. Add `GROQ_API_KEY` only if you want the optional metadata-based context note.
4. Optionally set `GROQ_MODEL` (default: `llama-3.3-70b-versatile`).
5. Deploy.

No environment variables are required for the metadata-only flow.

## Local development

Requires Node.js 20.9+.

```bash
npm install
npm run dev
```

Open http://localhost:3000.

## API

`POST /api/analyze`

```json
{ "url": "https://www.tiktok.com/@creator/video/1234567890", "notes": "Optional research question" }
```

The endpoint returns metadata, optional constrained context, limitations and next steps. It does not claim the video was watched.

## Python media worker

Deploy the worker separately using the root Render Blueprint (`render.yaml`) or build `worker/Dockerfile`. The service exposes authenticated `POST /v1/analyze`; pass either a TikTok URL to start or the returned `next_cursor` to continue. Full deployment steps, environment variables and curl examples are in [worker/README.md](worker/README.md).

## Remaining milestones

- Add a durable job queue and job-status API for slow cloud inference.
- Connect the Vercel UI to the worker through a server-side authenticated orchestration layer.
- Add music recognition and MCP stdio / Streamable HTTP adapters.
- Run end-to-end tests against accessible public sample videos and verify deployment resource usage.
