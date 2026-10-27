from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TrackSearchTerms:
    title: str
    artist: str = ""
    album: str = ""


@dataclass(frozen=True)
class FolderSearchTerms:
    artist: str = ""
    album: str = ""


# From ".../<Artist>/<Artist> - <Title>" or ".../<Artist> - <Album>/<Artist> - <Title>".
@dataclass(frozen=True)
class LibraryPathTerms:
    title: str
    artist: str
    album: str


# ".../<Artist>/<Artist> - <Album>[ - CD<n>]/", disc folders such as "CD1" included.
@dataclass(frozen=True)
class AlbumFolder:
    folder: Path
    artist: str
    album: str
    disc: int | None


@dataclass(frozen=True)
class AlbumTrack:
    path: Path
    disc: int | None


# Sibling disc folders ("Album - CD1", "Album - CD2") are units of their own,
# so the album lookup must be shared by artist and album.
@dataclass(frozen=True)
class AlbumUnit:
    folder: Path
    artist: str
    album: str
    tracks: list[AlbumTrack]


# Albums are tagged as a whole; singles one file at a time.
@dataclass(frozen=True)
class TrackPlan:
    albums: list[AlbumUnit]
    singles: list[Path]
