from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class AutoTagStatus(StrEnum):
    TAGGED = "tagged"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class TaggingStarted:
    total: int


@dataclass(frozen=True)
class FileAutoTagged:
    path: Path
    status: AutoTagStatus
    reason: str = ""


@dataclass(frozen=True)
class TaggingFinished:
    tagged: int
    skipped: int
    failed: int
    unprocessed: int
    stopped: bool


@dataclass(frozen=True)
class TaggingFailed:
    message: str


@dataclass(frozen=True)
class TaggingStopped:
    """Cancelled before SoundTag could report a summary."""


type TaggerEvent = (
    TaggingStarted | FileAutoTagged | TaggingFinished | TaggingFailed | TaggingStopped
)
type TaggerEventHandler = Callable[[TaggerEvent], None]
