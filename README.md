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

This MVP does **not** download or inspect video media. Timestamped transcription, OCR, keyframes, music recognition, 90-second segment continuation and the 10 MB per-file enforcement belong to the separate media worker milestone. The UI and skill documentation state this boundary rather than inventing media evidence.

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

## Planned next phase

Implement a separate Python media worker for bounded public/authorized media retrieval, strict 10 MB file and 90-second segment limits, sequential continuation, timestamped transcription, OCR, keyframes and audio/music identification. Add REST/MCP adapters over the normalized evidence schema.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [skills/tiktok-reader/SKILL.md](skills/tiktok-reader/SKILL.md).
