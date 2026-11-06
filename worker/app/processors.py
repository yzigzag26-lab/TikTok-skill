import base64
import io
import subprocess
from pathlib import Path
import cv2
from PIL import Image
from faster_whisper import WhisperModel
from rapidocr_onnxruntime import RapidOCR
from .config import WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE, MAX_OCR_FRAMES, MAX_KEYFRAMES

_whisper = None
_ocr = None

def get_whisper():
    global _whisper
    if _whisper is None:
        _whisper = WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE_TYPE, cpu_threads=2)
    return _whisper

def get_ocr():
    global _ocr
    if _ocr is None:
        _ocr = RapidOCR()
    return _ocr

def extract_audio(video_path: Path, workdir: str) -> Path:
    audio = Path(workdir) / "audio.wav"
    subprocess.run(
        ["ffmpeg", "-nostdin", "-y", "-i", str(video_path), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(audio)],
        check=True, capture_output=True, timeout=30,
    )
    return audio

def transcribe(video_path: Path, workdir: str, offset: float) -> list[dict]:
    audio = extract_audio(video_path, workdir)
    model = get_whisper()
    segments, info = model.transcribe(str(audio), beam_size=1, vad_filter=True, word_timestamps=False)
    rows = []
    for seg in segments:
        text = seg.text.strip()
        if text:
            rows.append({"start": round(offset + float(seg.start), 3), "end": round(offset + float(seg.end), 3), "text": text})
    return rows

def extract_frames(video_path: Path, offset: float) -> tuple[list[dict], list[dict]]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError("FFmpeg/OpenCV could not open the downloaded segment.")
    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = frame_count / fps if fps > 0 else 0
    if duration <= 0:
        capture.release()
        return [], []
    sample_count = min(MAX_OCR_FRAMES, max(1, int(duration // 3) + 1))
    times = sorted(set(min(duration, i * max(duration / sample_count, 0.5)) for i in range(sample_count)))
    ocr = get_ocr()
    texts, keyframes = [], []
    keyframe_indexes = set(round(i * (len(times)-1) / max(1, MAX_KEYFRAMES-1)) for i in range(min(MAX_KEYFRAMES, len(times))))
    for index, seconds in enumerate(times):
        capture.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
        ok, frame = capture.read()
        if not ok:
            continue
        absolute = round(offset + seconds, 3)
        result, _ = ocr(frame)
        found = []
        for item in result or []:
            try:
                text = str(item[1]).strip()
                score = float(item[2])
                if text and score >= 0.35:
                    found.append({"text": text, "confidence": round(score, 3)})
            except (IndexError, TypeError, ValueError):
                continue
        if found:
            texts.append({"timestamp": absolute, "items": found})
        if index in keyframe_indexes:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(rgb)
            image.thumbnail((480, 480))
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=62, optimize=True)
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
            keyframes.append({"timestamp": absolute, "mime_type": "image/jpeg", "image_base64": encoded})
    capture.release()
    return texts, keyframes
