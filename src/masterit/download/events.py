from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ItemRef:
    item_id: str
    title: str


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


type DownloadEvent = ItemProgress | ItemCompleted | ItemFailed
type EventHandler = Callable[[DownloadEvent], None]
