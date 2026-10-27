from dataclasses import dataclass, field
from typing import Protocol

from masterit.tagging.web.batch_cache import BatchCache
from masterit.tagging.web.images import ImageCache, ImageRequest
from masterit.tagging.web.rate_limiter import Clock


@dataclass(frozen=True)
class TrackInfo:
    title: str = ""
    artist: str = ""
    album: str = ""
    year: str = ""


@dataclass(frozen=True)
class TrackExtras:
    genre: str | None = None
    album_artist: str | None = None
    track_number: int | None = None
    track_count: int | None = None
    disc_number: int | None = None
    disc_count: int | None = None


@dataclass(frozen=True)
class TrackMetadata:
    info: TrackInfo
    extras: TrackExtras = field(default_factory=TrackExtras)
    cover_data: bytes | None = None


@dataclass(frozen=True)
class ExistingTags:
    info: TrackInfo = field(default_factory=TrackInfo)
    extras: TrackExtras = field(default_factory=TrackExtras)
    has_cover: bool = False


@dataclass(frozen=True)
class TrackSearch:
    title: str
    artist: str = ""
    album: str = ""


@dataclass(frozen=True)
class AlbumSearch:
    artist: str
    album: str


# Like tags, the track count is per disc.
@dataclass(frozen=True)
class AlbumTrackEntry:
    title: str
    track_number: int
    track_count: int
    disc_number: int
    disc_count: int
    artist: str = ""


# The album as the service spells it, with what else the service knows.
@dataclass(frozen=True)
class FoundAlbum:
    album: str
    artist: str
    year: str = ""
    genre: str = ""
    covers: list[ImageRequest] = field(default_factory=list[ImageRequest])
    tracks: list[AlbumTrackEntry] | None = None


# What every track of an album shares; found is false when only the folder named it.
@dataclass(frozen=True)
class AlbumData:
    album: str
    artist: str
    year: str
    genre: str
    cover: bytes | None
    tracks: list[AlbumTrackEntry]
    found: bool


class AlbumFinder(Protocol):
    def resolve(self, search: AlbumSearch, file_count: int | None = None) -> AlbumData: ...


class AlbumSource(Protocol):
    @property
    def name(self) -> str: ...

    def find_album(self, search: AlbumSearch) -> FoundAlbum | None: ...


# details: the year or an extra is still missing.
@dataclass(frozen=True)
class ProviderNeeds:
    cover: bool
    details: bool


class MetadataProvider(Protocol):
    @property
    def name(self) -> str: ...

    def find_metadata(self, search: TrackSearch, needs: ProviderNeeds) -> TrackMetadata | None: ...


class CoverProvider(Protocol):
    @property
    def name(self) -> str: ...

    def find_cover(self, search: TrackSearch) -> bytes | None: ...


@dataclass(frozen=True)
class ProviderServices:
    clock: Clock
    images: ImageCache
    cache: BatchCache
