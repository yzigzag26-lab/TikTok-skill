import io
import json
import subprocess
from pathlib import Path
import requests
from .config import AUDD_API_TOKEN

AUDD_ENDPOINT = "https://api.audd.io/"
SAMPLE_SECONDS = 12
SAMPLE_OFFSETS = (0, 30, 60)

def _extract_sample(video_path: Path, offset: float) -> bytes:
    output = io.BytesIO()
    result = subprocess.run(
        [
            "ffmpeg", "-nostdin", "-v", "error", "-ss", str(offset),
            "-i", str(video_path), "-t", str(SAMPLE_SECONDS), "-vn",
            "-ac", "1", "-ar", "22050", "-c:a", "libmp3lame", "-b:a", "96k",
            "-f", "mp3", "pipe:1",
        ],
        check=True, capture_output=True, timeout=20,
    )
    return result.stdout

def identify_songs(video_path: Path, segment_duration: float, absolute_offset: float = 0) -> dict:
    if not AUDD_API_TOKEN:
        return {
            "status": "not_configured",
            "matches": [],
            "attempts": 0,
            "message": "Song recognition is not configured. Set AUDD_API_TOKEN on the worker."
        }

    matches = []
    seen = set()
    attempts = []
    for local_offset in SAMPLE_OFFSETS:
        if local_offset >= segment_duration:
            continue
        sample = _extract_sample(video_path, local_offset)
        if len(sample) < 2048:
            attempts.append({"timestamp_seconds": round(absolute_offset + local_offset, 3), "status": "sample_too_short"})
            continue
        try:
            response = requests.post(
                AUDD_ENDPOINT,
                data={"api_token": AUDD_API_TOKEN, "return": "apple_music,spotify"},
                files={"file": (f"tiktok-audio-{local_offset}.mp3", sample, "audio/mpeg")},
                timeout=(5, 18),
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            attempts.append({"timestamp_seconds": round(absolute_offset + local_offset, 3), "status": "provider_error"})
            continue

        result = payload.get("result") if payload.get("status") == "success" else None
        if not result:
            attempts.append({"timestamp_seconds": round(absolute_offset + local_offset, 3), "status": "no_match"})
            continue

        artist = str(result.get("artist") or "").strip()
        title = str(result.get("title") or "").strip()
        if not artist and not title:
            attempts.append({"timestamp_seconds": round(absolute_offset + local_offset, 3), "status": "incomplete_match"})
            continue
        key = (artist.casefold(), title.casefold())
        attempts.append({"timestamp_seconds": round(absolute_offset + local_offset, 3), "status": "matched"})
        if key in seen:
            continue
        seen.add(key)
        matches.append({
            "title": title or None,
            "artist": artist or None,
            "album": result.get("album"),
            "release_date": result.get("release_date"),
            "label": result.get("label"),
            "timecode": result.get("timecode"),
            "song_link": result.get("song_link"),
            "apple_music": result.get("apple_music"),
            "spotify": result.get("spotify"),
            "matched_at_seconds": round(absolute_offset + local_offset, 3),
            "provider": "AudD",
            "match_type": "provider_identification",
        })

    return {
        "status": "matched" if matches else "no_match",
        "matches": matches,
        "attempts": attempts,
        "samples_checked": len(attempts),
        "message": "Song candidates were returned by AudD. Verify against the clip before treating a match as definitive." if matches else "No song was identified in the sampled audio. Try another segment if the track starts later or the audio is clearer."
    }
