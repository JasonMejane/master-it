import json
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from masterit.tagging.metadata.metadata_chain import call_service
from masterit.tagging.metadata.track_matching import strip_remaster_note
from masterit.tagging.metadata.types import (
    AlbumData,
    AlbumSearch,
    AlbumSource,
    AlbumTrackEntry,
    FoundAlbum,
    ProviderServices,
)

type FieldReader[Value] = Callable[[FoundAlbum], Value | None]


# Sources in the order each field is taken from.
@dataclass(frozen=True)
class AlbumSourceOrder:
    identity: Sequence[AlbumSource]
    year: Sequence[AlbumSource]
    genre: Sequence[AlbumSource]
    tracks: Sequence[AlbumSource]
    cover: Sequence[AlbumSource]


def fold_name(name: str) -> str:
    return unicodedata.normalize("NFC", name).strip().lower()


def get_album_key(search: AlbumSearch) -> str:
    return f"album-data:{json.dumps([fold_name(search.artist), fold_name(search.album)])}"


def make_folder_album(search: AlbumSearch) -> AlbumData:
    return AlbumData(search.album, search.artist, "", "", None, [], found=False)


def read_tracks(found: FoundAlbum) -> list[AlbumTrackEntry] | None:
    return found.tracks or None


def read_fitting_tracks(found: FoundAlbum, file_count: int | None) -> list[AlbumTrackEntry] | None:
    tracks = found.tracks
    return tracks if tracks is not None and len(tracks) == file_count else None


# One search per source and album, shared by every field that needs it.
class AlbumLookup:
    def __init__(self, search: AlbumSearch) -> None:
        self._search = search
        self._results: dict[AlbumSource, FoundAlbum | None] = {}

    def find_first[Value](
        self, sources: Sequence[AlbumSource], read: FieldReader[Value]
    ) -> Value | None:
        values = (self._read_from(source, read) for source in sources)
        return next((value for value in values if value is not None), None)

    def _read_from[Value](self, source: AlbumSource, read: FieldReader[Value]) -> Value | None:
        found = self._find(source)
        return None if found is None else read(found)

    def _find(self, source: AlbumSource) -> FoundAlbum | None:
        if source not in self._results:
            self._results[source] = call_service(lambda: source.find_album(self._search))
        return self._results[source]


class AlbumResolver:
    def __init__(self, order: AlbumSourceOrder, services: ProviderServices) -> None:
        self._order = order
        self._services = services

    @property
    def order(self) -> AlbumSourceOrder:
        return self._order

    # Sibling disc folders ask for the same album, so it is kept for the batch.
    def resolve(self, search: AlbumSearch, file_count: int | None = None) -> AlbumData:
        return self._services.cache.get_or_load(
            get_album_key(search), lambda: self._look_up(search, file_count)
        )

    def _look_up(self, search: AlbumSearch, file_count: int | None) -> AlbumData:
        lookup = AlbumLookup(search)
        identity = lookup.find_first(self._order.identity, lambda found: found)
        if identity is None:
            return make_folder_album(search)
        return self._collect(lookup, identity, file_count)

    def _collect(
        self, lookup: AlbumLookup, identity: FoundAlbum, file_count: int | None
    ) -> AlbumData:
        return AlbumData(
            strip_remaster_note(identity.album),
            identity.artist,
            lookup.find_first(self._order.year, lambda found: found.year or None) or "",
            lookup.find_first(self._order.genre, lambda found: found.genre or None) or "",
            self._find_cover(lookup),
            self._find_tracks(lookup, file_count),
            found=True,
        )

    # Editions differ in bonus tracks, so the one the folder holds comes first.
    def _find_tracks(self, lookup: AlbumLookup, file_count: int | None) -> list[AlbumTrackEntry]:
        sources = self._order.tracks
        fitting = lookup.find_first(sources, lambda found: read_fitting_tracks(found, file_count))
        if fitting is not None:
            return fitting
        return lookup.find_first(sources, read_tracks) or []

    def _find_cover(self, lookup: AlbumLookup) -> bytes | None:
        images = self._services.images
        return lookup.find_first(
            self._order.cover, lambda found: images.download_first(found.covers)
        )
