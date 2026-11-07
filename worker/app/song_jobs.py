import threading
import uuid
import tempfile
from fastapi import HTTPException
from .security import validate_tiktok_url, UnsafeSource
from .cursors import decode_cursor, encode_cursor, InvalidCursor
from .media import inspect_video, download_segment, probe_duration, MediaUnavailable, MediaLimitExceeded
from .music import identify_songs
from .config import MAX_SEGMENT_SECONDS

_LOCK = threading.Lock()
_JOBS: dict[str, dict] = {}

def create_job(url: str | None, cursor: str | None) -> str:
    if bool(url) == bool(cursor):
        raise ValueError("Provide exactly one TikTok URL or continuation cursor.")
    if cursor:
        source_url, offset = decode_cursor(cursor)
    else:
        source_url, offset = validate_tiktok_url(url), 0.0
    job_id = uuid.uuid4().hex
    with _LOCK:
        _JOBS[job_id] = {"id":job_id,"status":"queued","result":None,"error":None}
    return job_id, source_url, offset

def run_job(job_id: str, source_url: str, offset: float) -> None:
    with _LOCK:
        if job_id not in _JOBS:
            return
        _JOBS[job_id]["status"] = "processing"
    try:
        info = inspect_video(source_url)
        duration = float(info["duration"])
        if offset >= duration:
            result = {"status":"complete","source_url":source_url,"song_recognition":{"status":"no_more_segments","matches":[]},"next_cursor":None,"message":"The end of the accessible video has been reached."}
        else:
            end = min(offset + MAX_SEGMENT_SECONDS, duration)
            with tempfile.TemporaryDirectory(prefix="tiktok-song-") as tmp:
                media = download_segment(source_url, offset, end, tmp)
                actual = probe_duration(media)
                if actual > MAX_SEGMENT_SECONDS:
                    raise MediaLimitExceeded("Downloaded segment exceeded the strict 90-second limit.")
                recognition = identify_songs(media, actual, offset)
                next_offset = min(offset + actual, duration)
                cursor = encode_cursor(source_url, next_offset) if next_offset + 0.5 < duration else None
                result = {
                    "status":"partial" if cursor else "complete",
                    "source_url":source_url,
                    "video":{"title":info.get("title"),"creator":info.get("uploader"),"duration_seconds":duration},
                    "segment":{"start_seconds":round(offset,3),"end_seconds":round(next_offset,3),"duration_seconds":round(actual,3),"file_bytes":media.stat().st_size},
                    "song_recognition":recognition,
                    "next_cursor":cursor,
                    "limitations":["Recognition samples up to three 12-second windows in this 90-second segment.","A missing match does not prove the audio contains no music. TikTok may restrict access to later segments."]
                }
        with _LOCK:
            _JOBS[job_id]["status"] = "complete"
            _JOBS[job_id]["result"] = result
    except (UnsafeSource, InvalidCursor, MediaUnavailable, MediaLimitExceeded, ValueError) as exc:
        with _LOCK:
            _JOBS[job_id]["status"] = "failed"
            _JOBS[job_id]["error"] = str(exc)
    except Exception:
        with _LOCK:
            _JOBS[job_id]["status"] = "failed"
            _JOBS[job_id]["error"] = "Song identification failed unexpectedly. Check worker logs."

def get_job(job_id: str) -> dict | None:
    with _LOCK:
        job = _JOBS.get(job_id)
        return dict(job) if job else None
