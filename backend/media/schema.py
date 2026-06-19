from pydantic import BaseModel, ConfigDict, Field


class BaseSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")


class TranscriptSegment(BaseSchema):
    start: float = Field(description="Segment start time in seconds")
    end: float = Field(description="Segment end time in seconds")
    text: str = Field(description="Transcribed text for the segment")


class Caption(BaseSchema):
    """A short, timeline-ready subtitle chunk derived from the transcript."""

    start: float = Field(description="Caption start time in seconds")
    end: float = Field(description="Caption end time in seconds")
    text: str = Field(description="Caption text (already length-limited)")


class TranscribeResponse(BaseSchema):
    language: str = Field(description="Detected (or forced) language code")
    duration: float = Field(description="Media duration in seconds")
    segments: list[TranscriptSegment] = Field(
        description="Raw transcript segments as returned by the model"
    )
    captions: list[Caption] = Field(
        description="Subtitle-sized chunks ready to drop on the timeline as text clips"
    )
    srt: str = Field(description="Full transcript as an SRT subtitle file")


class SilenceInterval(BaseSchema):
    start: float = Field(description="Silence start time in seconds")
    end: float = Field(description="Silence end time in seconds")


class KeepSegment(BaseSchema):
    """A span of the source that should be KEPT after removing silences."""

    start: float = Field(description="Keep-segment start time in seconds")
    end: float = Field(description="Keep-segment end time in seconds")


class CutSilencesResponse(BaseSchema):
    duration: float = Field(description="Media duration in seconds")
    silences: list[SilenceInterval] = Field(
        description="Detected silent intervals in the source"
    )
    keep_segments: list[KeepSegment] = Field(
        description="Non-silent spans to keep, in order — the edited cut"
    )
    removed_seconds: float = Field(
        description="Total seconds of silence removed by the keep plan"
    )
