import logging
import os
import shutil
import tempfile
from urllib.parse import urlparse
from urllib.request import urlopen

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from auth.routes import get_current_user
from auth.schema import SessionUser
from media.processing import (
    MediaProcessingError,
    compute_keep_segments,
    detect_silences,
    probe_duration_seconds,
    segments_to_srt,
    split_into_captions,
    transcribe,
)
from media.schema import CutSilencesResponse, TranscribeResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/media", tags=["media"])

# Cap to keep a single CPU transcription bounded. Tune once we have load data.
_MAX_UPLOAD_BYTES = 1024 * 1024 * 1024  # 1 GB
_DOWNLOAD_CHUNK = 1024 * 1024


def _materialize_to_tempfile(
    upload: UploadFile | None, media_url: str | None
) -> str:
    """Write the incoming media (uploaded file or remote URL) to a temp file.

    Returns the temp file path; caller is responsible for deleting it.
    """
    if upload is None and not media_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either a 'file' upload or a 'media_url'.",
        )

    suffix = ""
    if upload is not None and upload.filename:
        suffix = os.path.splitext(upload.filename)[1]
    elif media_url:
        suffix = os.path.splitext(urlparse(media_url).path)[1]

    fd, path = tempfile.mkstemp(suffix=suffix, prefix="vibecut_media_")
    written = 0
    try:
        with os.fdopen(fd, "wb") as dst:
            if upload is not None:
                while chunk := upload.file.read(_DOWNLOAD_CHUNK):
                    written += len(chunk)
                    if written > _MAX_UPLOAD_BYTES:
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail="Media file exceeds the 1 GB limit.",
                        )
                    dst.write(chunk)
            else:
                assert media_url is not None
                parsed = urlparse(media_url)
                if parsed.scheme not in ("http", "https"):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="media_url must be an http(s) URL.",
                    )
                with urlopen(media_url) as response:  # noqa: S310 - scheme checked above
                    while chunk := response.read(_DOWNLOAD_CHUNK):
                        written += len(chunk)
                        if written > _MAX_UPLOAD_BYTES:
                            raise HTTPException(
                                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                                detail="Media file exceeds the 1 GB limit.",
                            )
                        dst.write(chunk)
    except HTTPException:
        os.unlink(path)
        raise
    except OSError as exc:
        os.unlink(path)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not fetch media: {exc}",
        ) from exc

    if written == 0:
        os.unlink(path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Empty media input."
        )
    return path


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_media(
    file: UploadFile | None = File(default=None),
    media_url: str | None = Form(default=None),
    language: str | None = Form(default=None),
    model_size: str = Form(default="base"),
    max_caption_chars: int = Form(default=42, ge=10, le=120),
    user: SessionUser = Depends(get_current_user),
) -> TranscribeResponse:
    """Transcribe a clip locally and return SRT + timeline-ready caption chunks."""
    path = _materialize_to_tempfile(file, media_url)
    try:
        duration = await run_in_threadpool(probe_duration_seconds, path)
        detected_language, segments = await run_in_threadpool(
            transcribe, path, language, model_size
        )
        captions = split_into_captions(segments, max_caption_chars)
        srt = segments_to_srt(segments)
    except MediaProcessingError as exc:
        logger.warning("Transcription failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    finally:
        if os.path.exists(path):
            os.unlink(path)

    return TranscribeResponse(
        language=detected_language,
        duration=duration,
        segments=segments,
        captions=captions,
        srt=srt,
    )


@router.post("/cut-silences", response_model=CutSilencesResponse)
async def cut_silences(
    file: UploadFile | None = File(default=None),
    media_url: str | None = Form(default=None),
    noise_db: float = Form(default=-30.0),
    min_silence_seconds: float = Form(default=0.5, gt=0.0),
    padding_seconds: float = Form(default=0.1, ge=0.0),
    min_keep_seconds: float = Form(default=0.2, ge=0.0),
    user: SessionUser = Depends(get_current_user),
) -> CutSilencesResponse:
    """Detect silences and return the spans to keep (the de-silenced cut plan)."""
    path = _materialize_to_tempfile(file, media_url)
    try:
        duration = await run_in_threadpool(probe_duration_seconds, path)
        silences = await run_in_threadpool(
            detect_silences, path, noise_db, min_silence_seconds
        )
        keep_segments, removed = compute_keep_segments(
            duration, silences, padding_seconds, min_keep_seconds
        )
    except MediaProcessingError as exc:
        logger.warning("Silence detection failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    finally:
        if os.path.exists(path):
            os.unlink(path)

    return CutSilencesResponse(
        duration=duration,
        silences=silences,
        keep_segments=keep_segments,
        removed_seconds=removed,
    )
