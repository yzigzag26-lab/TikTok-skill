import os
import subprocess
import tempfile
from pathlib import Path
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError, download_range_func
from .config import MAX_MEDIA_BYTES, DOWNLOAD_TIMEOUT_SECONDS

class MediaUnavailable(RuntimeError):
    pass

class MediaLimitExceeded(RuntimeError):
    pass

def _make_progress_hook():
    seen = {}
    def hook(data):
        filename = str(data.get("filename") or data.get("tmpfilename") or "media") + "#" + str(data.get("fragment_index") or 0)
        downloaded = int(data.get("downloaded_bytes") or 0)
        seen[filename] = max(seen.get(filename, 0), downloaded)
        if sum(seen.values()) > MAX_MEDIA_BYTES:
            raise DownloadError("Media transfer exceeded the configured safety bound.")
    return hook

def inspect_video(url: str) -> dict:
    options = {
        "quiet": True, "no_warnings": True, "skip_download": True,
        "noplaylist": True, "socket_timeout": 12, "retries": 1,
        "extractor_retries": 1, "ignoreerrors": False,
    }
    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
        if not info:
            raise MediaUnavailable("TikTok did not provide video metadata.")
        duration = float(info.get("duration") or 0)
        if duration <= 0:
            raise MediaUnavailable("Video duration is unavailable; cannot safely segment it.")
        return {"duration": duration, "title": info.get("title"), "uploader": info.get("uploader") or info.get("channel"), "id": info.get("id"), "webpage_url": info.get("webpage_url") or url}
    except MediaUnavailable:
        raise
    except Exception as exc:
        raise MediaUnavailable("TikTok media metadata could not be retrieved. The video may be private, unavailable, or blocked by the platform.") from exc

def download_segment(url: str, start: float, end: float, workdir: str) -> Path:
    output = Path(workdir) / "segment.%(ext)s"
    options = {
        "quiet": True, "no_warnings": True, "noplaylist": True,
        "format": "best[height<=720]/best",
        "outtmpl": str(output),
        "merge_output_format": "mp4",
        "download_ranges": download_range_func(None, [(start, end)]),
        "force_keyframes_at_cuts": True,
        "progress_hooks": [_make_progress_hook()],
        "socket_timeout": 12, "retries": 1, "fragment_retries": 1,
        "concurrent_fragment_downloads": 1,
        "overwrites": True,
    }
    try:
        with YoutubeDL(options) as ydl:
            ydl.download([url])
    except Exception as exc:
        if "safety bound" in str(exc).lower():
            raise MediaLimitExceeded("Download was stopped because the transfer exceeded the safe media bound.") from exc
        raise MediaUnavailable("TikTok could not provide this video segment. No access restrictions were bypassed.") from exc
    candidates = [p for p in Path(workdir).glob("segment.*") if p.is_file() and p.suffix not in {".part", ".ytdl"}]
    if not candidates:
        raise MediaUnavailable("The requested segment could not be downloaded.")
    path = max(candidates, key=lambda p: p.stat().st_size)
    size = path.stat().st_size
    if size <= 0:
        raise MediaUnavailable("TikTok returned an empty media segment.")
    if size > MAX_MEDIA_BYTES:
        path.unlink(missing_ok=True)
        raise MediaLimitExceeded(f"The 90-second segment is {size} bytes, above the 10 MB limit. It was discarded.")
    return path

def probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        check=True, capture_output=True, text=True, timeout=10,
    )
    return float(result.stdout.strip())
