import os
import tempfile
import threading
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Header, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from .config import WORKER_API_KEY, CURSOR_SECRET, MAX_MEDIA_BYTES, MAX_SEGMENT_SECONDS, MAX_REQUEST_BYTES
from .security import validate_tiktok_url, require_worker_key, UnsafeSource
from .cursors import encode_cursor, decode_cursor, InvalidCursor
from .media import inspect_video, download_segment, probe_duration, MediaUnavailable, MediaLimitExceeded
from .processors import transcribe, extract_frames
from .music import identify_songs
from .song_jobs import create_job, run_job, get_job, WorkerBusy

app = FastAPI(title="TikTok Intelligence Media Worker", version="0.2.0")

class AnalyzeRequest(BaseModel):
    url: Optional[str] = Field(default=None, max_length=2048)
    cursor: Optional[str] = Field(default=None, max_length=4096)

class SongJobRequest(BaseModel):
    url: Optional[str] = Field(default=None, max_length=2048)
    cursor: Optional[str] = Field(default=None, max_length=4096)

@app.get("/health")
def health():
    return {"ok": True, "service": "tiktok-intelligence-worker", "max_media_bytes": MAX_MEDIA_BYTES, "max_segment_seconds": MAX_SEGMENT_SECONDS}

PROCESS_LOCK = threading.Lock()

@app.post("/v1/analyze")
def analyze(payload: AnalyzeRequest, request: Request, x_worker_key: Optional[str] = Header(default=None)):
    if not PROCESS_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="Worker is busy processing another segment. Retry shortly.")
    try:
        return _analyze(payload, request, x_worker_key)
    finally:
        PROCESS_LOCK.release()

def _analyze(payload: AnalyzeRequest, request: Request, x_worker_key: Optional[str] = None):
    if not WORKER_API_KEY:
        raise HTTPException(status_code=503, detail="WORKER_API_KEY is not configured.")
    require_worker_key(x_worker_key, WORKER_API_KEY)
    if int(request.headers.get("content-length", "0") or "0") > MAX_REQUEST_BYTES:
        raise HTTPException(status_code=413, detail="Request body is too large.")
    if not CURSOR_SECRET:
        raise HTTPException(status_code=503, detail="CURSOR_SECRET is not configured.")
    try:
        if payload.cursor:
            if payload.url:
                raise HTTPException(status_code=400, detail="Send either url or cursor, not both.")
            raw_url, start = decode_cursor(payload.cursor)
        elif payload.url:
            raw_url, start = payload.url, 0.0
        else:
            raise HTTPException(status_code=400, detail="A TikTok URL or continuation cursor is required.")
        safe_url = validate_tiktok_url(raw_url)
        info = inspect_video(safe_url)
        duration = float(info["duration"])
        if start >= duration:
            return {"status": "complete", "source_url": safe_url, "video": info, "segment": None, "next_cursor": None, "message": "The end of the accessible video has been reached."}
        segment_end = min(start + MAX_SEGMENT_SECONDS, duration)
        with tempfile.TemporaryDirectory(prefix="tiktok-intel-") as tmp:
            media = download_segment(safe_url, start, segment_end, tmp)
            if media.stat().st_size > MAX_MEDIA_BYTES:
                raise MediaLimitExceeded("Downloaded segment exceeded the 10 MB hard limit and was discarded.")
            actual_duration = probe_duration(media)
            if actual_duration > MAX_SEGMENT_SECONDS:
                raise MediaLimitExceeded("Downloaded media exceeded the strict 90-second segment limit and was discarded.")
            transcript = transcribe(media, tmp, start)
            on_screen_text, keyframes = extract_frames(media, start)
            song_recognition = identify_songs(media, actual_duration, start)
            next_offset = min(start + actual_duration, duration)
            next_cursor = encode_cursor(safe_url, next_offset) if next_offset + 0.5 < duration else None
            return {
                "status": "partial" if next_cursor else "complete",
                "source_url": safe_url,
                "video": {"title": info.get("title"), "creator": info.get("uploader"), "duration_seconds": duration},
                "segment": {"start_seconds": round(start, 3), "end_seconds": round(next_offset, 3), "duration_seconds": round(actual_duration, 3), "file_bytes": media.stat().st_size, "max_file_bytes": MAX_MEDIA_BYTES, "max_segment_seconds": MAX_SEGMENT_SECONDS},
                "transcript": transcript,
                "on_screen_text": on_screen_text,
                "keyframes": keyframes,
                "song_recognition": song_recognition,
                "next_cursor": next_cursor,
                "continuation": "Send next_cursor to POST /v1/analyze to process the next accessible segment. Each request processes at most one 90-second segment.",
                "limitations": ["Only public TikTok videos accessible without login or restriction bypass are supported.", "OCR and speech recognition are machine-generated and may contain errors.", "Song recognition depends on the optional AudD provider and may return no match for short, noisy, remixed or heavily processed audio."]
            }
    except UnsafeSource as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except InvalidCursor as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MediaLimitExceeded as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except MediaUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Media processing failed. Check worker logs for the internal error.") from exc

@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": "Internal worker error."})


@app.post("/v1/song-jobs")
def start_song_job(payload: SongJobRequest, background_tasks: BackgroundTasks, x_worker_key: Optional[str] = Header(default=None)):
    if not WORKER_API_KEY:
        raise HTTPException(status_code=503, detail="WORKER_API_KEY is not configured.")
    require_worker_key(x_worker_key, WORKER_API_KEY)
    try:
        job_id, source_url, offset = create_job(payload.url, payload.cursor)
    except WorkerBusy as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except (UnsafeSource, InvalidCursor, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    background_tasks.add_task(run_job, job_id, source_url, offset)
    return {"job_id": job_id, "status": "queued", "poll": f"/v1/song-jobs/{job_id}"}

@app.get("/v1/song-jobs/{job_id}")
def read_song_job(job_id: str, x_worker_key: Optional[str] = Header(default=None)):
    if not WORKER_API_KEY:
        raise HTTPException(status_code=503, detail="WORKER_API_KEY is not configured.")
    require_worker_key(x_worker_key, WORKER_API_KEY)
    if len(job_id) != 32 or not job_id.isalnum():
        raise HTTPException(status_code=400, detail="Invalid job ID.")
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Song-identification job not found. The worker may have restarted.")
    return job
