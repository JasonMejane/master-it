from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ItemRef:
    item_id: str
    title: str


@dataclass(frozen=True)
class ItemQueued:
    source_url: str
    item: ItemRef


@dataclass(frozen=True)
class ItemProgress:
    source_url: str
    item: ItemRef
    percent: float


@dataclass(frozen=True)
class ItemCompleted:
    source_url: str
    item: ItemRef
    file_path: Path
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ItemFailed:
    source_url: str
    item: ItemRef | None
    message: str


@dataclass(frozen=True)
class ItemSkipped:
    source_url: str
    item: ItemRef | None


@dataclass(frozen=True)
class LinkStarted:
    """yt-dlp took the link: from now on, skipping the whole link is too late."""

    source_url: str
    item: None = None


type DownloadEvent = (
    ItemQueued | ItemProgress | ItemCompleted | ItemFailed | ItemSkipped | LinkStarted
)
type EventHandler = Callable[[DownloadEvent], None]
