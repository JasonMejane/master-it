from collections.abc import Callable
from dataclasses import replace

from masterit.tagging.metadata.album_tracklist import TrackPlace, build_tracklist
from masterit.tagging.metadata.providers.deezer_client import (
    DeezerClient,
    build_query,
    get_cover_requests,
    get_deezer_genre,
)
from masterit.tagging.metadata.track_matching import (
    FoundAlbumName,
    is_same_artist,
    is_same_artist_name,
    is_searched_album,
    is_various_credit,
)
from masterit.tagging.metadata.track_metadata import extract_year
from masterit.tagging.metadata.types import AlbumSearch, AlbumTrackEntry, FoundAlbum
from masterit.tagging.web.errors import ServiceError
from masterit.tagging.web.json_fields import read_int, read_object, read_text
from masterit.tagging.web.json_response import JsonObject

type ArtistCheck = Callable[[str | None, str], bool]


def read_artist_name(item: JsonObject) -> str | None:
    return read_text(read_object(item, "artist"), "name")


def is_searched(album: JsonObject, search: AlbumSearch) -> bool:
    return is_searched_album(
        FoundAlbumName(read_text(album, "title"), read_artist_name(album)), search
    )


def find_artist_by(artists: list[JsonObject], name: str, is_same: ArtistCheck) -> JsonObject | None:
    return next(
        (
            artist
            for artist in artists
            if read_int(artist, "id") is not None and is_same(read_text(artist, "name"), name)
        ),
        None,
    )


# Deezer may rank a collaboration ("Scorpions & Friends") above the artist itself.
def find_searched_artist(artists: list[JsonObject], name: str) -> JsonObject | None:
    exact = find_artist_by(artists, name, is_same_artist_name)
    return exact if exact is not None else find_artist_by(artists, name, is_same_artist)


def describe_album(album: JsonObject) -> FoundAlbum:
    return FoundAlbum(
        read_text(album, "title") or "",
        read_artist_name(album) or "",
        covers=get_cover_requests(album),
    )


def place_track(track: JsonObject) -> TrackPlace:
    disc = read_int(track, "disk_number")
    return TrackPlace(
        read_text(track, "title") or "",
        1 if disc is None else disc,
        read_int(track, "track_position") or 0,
        (read_artist_name(track) or "").strip(),
    )


def get_tracklist(tracks: list[JsonObject]) -> list[AlbumTrackEntry]:
    return build_tracklist(
        [place_track(track) for track in tracks if read_int(track, "track_position")]
    )


# Deezer dates what it does not know "0000-00-00".
def get_release_year(album: JsonObject) -> str:
    year = extract_year(read_text(album, "release_date"))
    return year if year and int(year) > 0 else ""


class DeezerAlbumSource:
    name = "Deezer"

    def __init__(self, client: DeezerClient) -> None:
        self._client = client

    def find_album(self, search: AlbumSearch) -> FoundAlbum | None:
        album = self._search_album(search)
        if album is None:
            album = self._find_artist_album(search)
        return None if album is None else self._describe_with_details(album)

    def _describe_with_details(self, album: JsonObject) -> FoundAlbum:
        album_id = read_int(album, "id")
        found = describe_album(album)
        return found if album_id is None else self._add_details(found, album_id)

    # The search already named the album, which a failed detail must not undo.
    def _add_details(self, found: FoundAlbum, album_id: int) -> FoundAlbum:
        try:
            album = self._client.get_album(album_id)
            tracks = self._client.get_album_tracks(album_id)
        except ServiceError:
            return found
        genre = get_deezer_genre(album) or ""
        return replace(
            found, year=get_release_year(album), genre=genre, tracks=get_tracklist(tracks)
        )

    def _search_album(self, search: AlbumSearch) -> JsonObject | None:
        albums = self._client.search_albums(build_query([search.artist, search.album]))
        return next((album for album in albums if is_searched(album, search)), None)

    # The album search misses albums that the artist's own list holds.
    def _find_artist_album(self, search: AlbumSearch) -> JsonObject | None:
        artist = self._search_artist(search)
        artist_id = read_int(artist or {}, "id")
        if artist is None or artist_id is None:
            return None
        albums = (
            {**album, "artist": artist} for album in self._client.get_artist_albums(artist_id)
        )
        return next((album for album in albums if is_searched(album, search)), None)

    # Various artists have too many albums for their list to be searched.
    def _search_artist(self, search: AlbumSearch) -> JsonObject | None:
        if is_various_credit(search.artist):
            return None
        return find_searched_artist(self._client.search_artists(search.artist), search.artist)
