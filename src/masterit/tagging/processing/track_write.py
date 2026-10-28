from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from masterit.tagging.events import AutoTagStatus
from masterit.tagging.metadata.types import ExistingTags, TrackMetadata
from masterit.tagging.processing.write_policy import get_overwrite
from masterit.tagging.track_tags import TagWrite


class TagFiles(Protocol):
    def read(self, path: Path) -> ExistingTags: ...

    def read_cover(self, path: Path) -> bytes | None: ...

    def write(self, path: Path, tag_write: TagWrite) -> None: ...


@dataclass(frozen=True)
class TrackOutcome:
    status: AutoTagStatus
    reason: str = ""


def drop_stored_cover(
    files: TagFiles, path: Path, stored: ExistingTags, found: TrackMetadata
) -> TrackMetadata:
    if found.cover_data is None or not stored.has_cover:
        return found
    is_same = files.read_cover(path) == found.cover_data
    return replace(found, cover_data=None) if is_same else found


def write_found_metadata(
    files: TagFiles, path: Path, stored: ExistingTags, found: TrackMetadata
) -> TrackOutcome:
    changes = get_overwrite(stored, drop_stored_cover(files, path, stored, found))
    if changes is None:
        return TrackOutcome(AutoTagStatus.SKIPPED, "nothing new")
    files.write(path, changes)
    return TrackOutcome(AutoTagStatus.TAGGED)
