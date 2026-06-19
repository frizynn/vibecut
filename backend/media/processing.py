"""Local media processing: silence detection (ffmpeg) and transcription (faster-whisper).

All functions here are synchronous and CPU-bound. Routes call them through a
thread pool so the event loop stays responsive. No external services or API
keys are required — everything runs on the host with ffmpeg + a local model.
"""

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from threading import Lock

from media.schema import (
    Caption,
    KeepSegment,
    SilenceInterval,
    TranscriptSegment,
)

logger = logging.getLogger(__name__)

# faster-whisper is imported lazily inside _get_model so the backend can start
# (and the silence-cut feature can work) even if the model wheel is unavailable.

_SILENCE_START_RE = re.compile(r"silence_start:\s*([0-9.]+)")
_SILENCE_END_RE = re.compile(r"silence_end:\s*([0-9.]+)")

# A reasonable default model: ~150 MB, runs comfortably on CPU with int8.
_DEFAULT_MODEL_SIZE = "base"
_MAX_CAPTION_CHARS = 42


class MediaProcessingError(RuntimeError):
    """Raised when ffmpeg/ffprobe fails or a model cannot be loaded."""


def _require_binary(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise MediaProcessingError(
            f"'{name}' was not found on PATH. Install ffmpeg to use media features."
        )
    return path


def probe_duration_seconds(input_path: str) -> float:
    """Return the media duration in seconds via ffprobe."""
    ffprobe = _require_binary("ffprobe")
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            input_path,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    raw = result.stdout.strip()
    try:
        return max(0.0, float(raw))
    except ValueError as exc:
        raise MediaProcessingError(
            f"Could not read media duration (ffprobe said: {result.stderr.strip()!r})"
        ) from exc


def detect_silences(
    input_path: str,
    noise_db: float = -30.0,
    min_silence_seconds: float = 0.5,
) -> list[SilenceInterval]:
    """Detect silent intervals using ffmpeg's silencedetect filter.

    noise_db: anything quieter than this (in dBFS) counts as silence.
    min_silence_seconds: ignore silences shorter than this.
    """
    ffmpeg = _require_binary("ffmpeg")
    filter_expr = f"silencedetect=noise={noise_db}dB:d={min_silence_seconds}"
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-nostats", "-i", input_path, "-af", filter_expr, "-f", "null", "-"],
        capture_output=True,
        text=True,
        check=False,
    )
    # silencedetect writes to stderr.
    stderr = result.stderr
    starts: list[float] = [float(m) for m in _SILENCE_START_RE.findall(stderr)]
    ends: list[float] = [float(m) for m in _SILENCE_END_RE.findall(stderr)]

    intervals: list[SilenceInterval] = []
    # Pair starts with the next end >= start. ffmpeg emits them in order, but a
    # trailing silence at EOF may have a start without an end.
    duration = probe_duration_seconds(input_path)
    for i, start in enumerate(starts):
        end = ends[i] if i < len(ends) else duration
        if end > start:
            intervals.append(SilenceInterval(start=round(start, 3), end=round(end, 3)))
    return intervals


def compute_keep_segments(
    duration: float,
    silences: list[SilenceInterval],
    padding_seconds: float = 0.1,
    min_keep_seconds: float = 0.2,
) -> tuple[list[KeepSegment], float]:
    """Invert silence intervals into the spans to KEEP.

    padding_seconds: leave a little breathing room around speech so cuts don't
    clip the first/last syllable.
    min_keep_seconds: drop kept spans shorter than this (avoids 1-frame slivers).

    Returns (keep_segments, removed_seconds).
    """
    if duration <= 0:
        return [], 0.0

    keeps: list[KeepSegment] = []
    cursor = 0.0
    for silence in sorted(silences, key=lambda s: s.start):
        # The silence shrinks by padding on each side so we keep a touch of it.
        silence_start = min(duration, silence.start + padding_seconds)
        silence_end = max(0.0, silence.end - padding_seconds)
        if silence_start > cursor:
            keeps.append(KeepSegment(start=round(cursor, 3), end=round(silence_start, 3)))
        cursor = max(cursor, silence_end)

    if cursor < duration:
        keeps.append(KeepSegment(start=round(cursor, 3), end=round(duration, 3)))

    kept = [k for k in keeps if (k.end - k.start) >= min_keep_seconds]
    kept_total = sum(k.end - k.start for k in kept)
    removed = max(0.0, duration - kept_total)
    return kept, round(removed, 3)


@dataclass
class _LoadedModel:
    size: str


_model_lock = Lock()


@lru_cache(maxsize=2)
def _get_model(model_size: str):  # type: ignore[no-untyped-def]
    """Load (and cache) a faster-whisper model. CPU + int8 by default."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:  # pragma: no cover - depends on install
        raise MediaProcessingError(
            "faster-whisper is not installed. Run `uv sync` in backend/."
        ) from exc

    logger.info("Loading faster-whisper model '%s' (cpu/int8)", model_size)
    return WhisperModel(model_size, device="cpu", compute_type="int8")


def transcribe(
    input_path: str,
    language: str | None = None,
    model_size: str = _DEFAULT_MODEL_SIZE,
) -> tuple[str, list[TranscriptSegment]]:
    """Transcribe audio/video to timed segments.

    Returns (detected_language, segments). Serialized behind a lock because a
    single CPU model instance is not safe to run concurrently.
    """
    with _model_lock:
        model = _get_model(model_size)
        segments_iter, info = model.transcribe(
            input_path,
            language=language,
            vad_filter=True,
            beam_size=5,
        )
        segments = [
            TranscriptSegment(
                start=round(float(seg.start), 3),
                end=round(float(seg.end), 3),
                text=seg.text.strip(),
            )
            for seg in segments_iter
            if seg.text.strip()
        ]
    return str(info.language), segments


def split_into_captions(
    segments: list[TranscriptSegment],
    max_chars: int = _MAX_CAPTION_CHARS,
) -> list[Caption]:
    """Break long segments into subtitle-sized chunks, distributing time evenly."""
    captions: list[Caption] = []
    for seg in segments:
        words = seg.text.split()
        if not words:
            continue

        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if len(candidate) > max_chars and current:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)

        span = max(0.001, seg.end - seg.start)
        total_chars = sum(len(line) for line in lines) or 1
        cursor = seg.start
        for line in lines:
            share = len(line) / total_chars
            end = min(seg.end, cursor + span * share)
            captions.append(
                Caption(start=round(cursor, 3), end=round(end, 3), text=line)
            )
            cursor = end
    return captions


def _format_srt_timestamp(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def segments_to_srt(segments: list[TranscriptSegment]) -> str:
    """Render transcript segments as an SRT subtitle file."""
    blocks: list[str] = []
    for index, seg in enumerate(segments, start=1):
        start = _format_srt_timestamp(seg.start)
        end = _format_srt_timestamp(seg.end)
        blocks.append(f"{index}\n{start} --> {end}\n{seg.text}\n")
    return "\n".join(blocks)
