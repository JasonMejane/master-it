from masterit.tagging.metadata.album_tracklist import TrackPlace, build_tracklist
from masterit.tagging.metadata.providers.discogs import (
    ALBUM_KINDS,
    get_album_artist,
    get_cover_url,
    get_track_artist,
    parse_position,
    read_first_genre,
)
from masterit.tagging.metadata.providers.discogs_client import DiscogsAlbumKind, DiscogsClient
from masterit.tagging.metadata.track_matching import FoundAlbumName, is_searched_album
from masterit.tagging.metadata.types import AlbumSearch, AlbumTrackEntry, FoundAlbum, TrackSearch
from masterit.tagging.web.json_fields import read_int, read_objects, read_text
from masterit.tagging.web.json_response import JsonObject

ALBUM_SONG_TYPES = ("track", "index")


def is_searched(album: JsonObject, search: AlbumSearch) -> bool:
    return is_searched_album(
        FoundAlbumName(read_text(album, "title"), get_album_artist(album)), search
    )


# An index is one song of the album, whatever its parts.
def is_album_song(song: JsonObject) -> bool:
    kind = read_text(song, "type_") if "type_" in song else "track"
    return kind in ALBUM_SONG_TYPES


def place_song(song: JsonObject, album: JsonObject) -> TrackPlace | None:
    position = parse_position(read_text(song, "position"))
    if position is None:
        return None
    title = read_text(song, "title") or ""
    return TrackPlace(title, position.disc, position.track, get_track_artist(song, album))


# Vinyl sides ("A1") give no place; a partial tracklist would misnumber the rest.
def get_tracklist(album: JsonObject) -> list[AlbumTrackEntry]:
    songs = [song for song in read_objects(album, "tracklist") if is_album_song(song)]
    places = [place_song(song, album) for song in songs]
    placed = [place for place in places if place is not None]
    return build_tracklist(placed) if len(placed) == len(places) else []


# Only a master's year is the album's first; a release can be a reissue.
def get_year(kind: DiscogsAlbumKind, album: JsonObject) -> str:
    year = read_int(album, "year")
    return str(year) if kind == "master" and year else ""


# Discogs ranks the album first, so only its top result is checked.
class DiscogsAlbumSource:
    name = "Discogs"

    def __init__(self, client: DiscogsClient) -> None:
        self._client = client

    def find_album(self, search: AlbumSearch) -> FoundAlbum | None:
        albums = (self._find_album_of_kind(kind, search) for kind in ALBUM_KINDS)
        return next((album for album in albums if album is not None), None)

    def _find_album_of_kind(self, kind: DiscogsAlbumKind, search: AlbumSearch) -> FoundAlbum | None:
        results = self._client.search_albums(kind, TrackSearch("", search.artist, search.album))
        album_id = read_int(results[0], "id") if results else None
        if album_id is None:
            return None
        album = self._client.get_album(kind, album_id)
        return self._describe_album(kind, album) if is_searched(album, search) else None

    def _describe_album(self, kind: DiscogsAlbumKind, album: JsonObject) -> FoundAlbum:
        cover_url = get_cover_url(album)
        return FoundAlbum(
            read_text(album, "title") or "",
            get_album_artist(album),
            get_year(kind, album),
            read_first_genre(album) or "",
            [self._client.get_cover_request(cover_url)] if cover_url else [],
            get_tracklist(album),
        )
