from dataclasses import dataclass, field
from pathlib import Path

from masterit.tagging.metadata.types import (
    AlbumData,
    AlbumSearch,
    ExistingTags,
    TrackMetadata,
    TrackSearch,
)
from masterit.tagging.track_tags import TagWrite
from masterit.tags.tag_store import TagError


@dataclass
class FakeTagFiles:
    stored: dict[Path, ExistingTags] = field(default_factory=dict[Path, ExistingTags])
    covers: dict[Path, bytes] = field(default_factory=dict[Path, bytes])
    writes: list[tuple[Path, TagWrite]] = field(default_factory=list[tuple[Path, TagWrite]])

    def read(self, path: Path) -> ExistingTags:
        if path not in self.stored:
            raise TagError(f"Tags not supported for {path.name}")
        return self.stored[path]

    def read_cover(self, path: Path) -> bytes | None:
        return self.covers.get(path)

    def write(self, path: Path, tag_write: TagWrite) -> None:
        self.writes.append((path, tag_write))


@dataclass
class FakeTrackFinder:
    results: list[TrackMetadata | None]
    calls: list[tuple[TrackSearch, ExistingTags, bool]] = field(
        default_factory=list[tuple[TrackSearch, ExistingTags, bool]]
    )
    clears: int = 0

    def find(
        self, search: TrackSearch, existing: ExistingTags, replace_cover: bool = False
    ) -> TrackMetadata | None:
        self.calls.append((search, existing, replace_cover))
        return self.results.pop(0) if self.results else None

    def clear_cache(self) -> None:
        self.clears += 1


@dataclass
class FakeAlbumFinder:
    album: AlbumData | Exception
    searches: list[tuple[AlbumSearch, int | None]] = field(
        default_factory=list[tuple[AlbumSearch, int | None]]
    )

    def resolve(self, search: AlbumSearch, file_count: int | None = None) -> AlbumData:
        self.searches.append((search, file_count))
        if isinstance(self.album, Exception):
            raise self.album
        return self.album
