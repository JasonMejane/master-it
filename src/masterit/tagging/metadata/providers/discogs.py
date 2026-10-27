import re
from collections.abc import Callable
from dataclasses import dataclass, replace

from masterit.tagging.metadata.providers.discogs_client import DiscogsAlbumKind, DiscogsClient
from masterit.tagging.metadata.track_matching import (
    FoundRelease,
    FoundTrack,
    is_same_release,
    is_same_track,
    is_various_artists,
)
from masterit.tagging.metadata.track_metadata import make_optional_count, make_optional_text
from masterit.tagging.metadata.types import (
    ProviderNeeds,
    ProviderServices,
    TrackExtras,
    TrackInfo,
    TrackMetadata,
    TrackSearch,
)
from masterit.tagging.web.json_fields import read_int, read_list, read_objects, read_text
from masterit.tagging.web.json_response import JsonObject


@dataclass(frozen=True)
class DiscogsMatch:
    kind: DiscogsAlbumKind
    album: JsonObject
    track: JsonObject
    is_release: bool


@dataclass(frozen=True)
class TrackPosition:
    disc: int
    track: int


# "3", "1-3", "CD1-3" or "2.03"; vinyl sides ("A1") give no track number.
# JavaScript folds the long s into "s" but no other non-ASCII letter into "cd" or "disc".
NUMBERED_POSITION = re.compile(r"(?:(?ai:cd|di[s\u017f]c)?\s*([0-9]+)\s*[-.]\s*)?([0-9]+)")
# Discogs tells namesakes apart with "(2)".
ARTIST_NAME_MARKS = re.compile(r"\s*\([0-9]+\)\Z")
DISCOGS_VARIOUS_ARTISTS = "Various"
ALBUM_KINDS: tuple[DiscogsAlbumKind, ...] = ("master", "release")
# Headings and indexes split the tracklist without being songs.
SONGS_BY_TYPE: dict[str | None, Callable[[JsonObject], list[JsonObject]]] = {
    "track": lambda track: [track],
    "index": lambda track: read_objects(track, "sub_tracks"),
}


def get_artist_name(artist: JsonObject) -> str:
    return ARTIST_NAME_MARKS.sub("", read_text(artist, "name") or "")


def format_join(artist: JsonObject) -> str:
    joined = (read_text(artist, "join") or "").strip()
    return ", " if joined == "," else f" {joined} "


def get_credit(artists: list[JsonObject]) -> str:
    credit = "".join(f"{get_artist_name(artist)}{format_join(artist)}" for artist in artists)
    return re.sub(r"\s+", " ", credit).strip()


def get_album_artist(album: JsonObject) -> str:
    credit = get_credit(read_objects(album, "artists"))
    return "Various Artists" if credit == DISCOGS_VARIOUS_ARTISTS else credit


def get_track_artist(track: JsonObject, album: JsonObject) -> str:
    return get_credit(read_objects(track, "artists")) or get_album_artist(album)


def get_track_songs(track: JsonObject) -> list[JsonObject]:
    kind = read_text(track, "type_") if "type_" in track else "track"
    get_songs_of_type = SONGS_BY_TYPE.get(kind)
    return get_songs_of_type(track) if get_songs_of_type else []


def get_songs(album: JsonObject) -> list[JsonObject]:
    return [song for track in read_objects(album, "tracklist") for song in get_track_songs(track)]


def find_song(album: JsonObject, search: TrackSearch) -> JsonObject | None:
    return next(
        (
            song
            for song in get_songs(album)
            if is_same_track(
                FoundTrack(read_text(song, "title"), get_track_artist(song, album)), search
            )
        ),
        None,
    )


# Without an album to look for, the top result is often a compilation.
def is_guessed_compilation(album: JsonObject, searched_album: str) -> bool:
    return not searched_album and is_various_artists(get_album_artist(album))


def is_searched_release(album: JsonObject, track: JsonObject, searched_album: str) -> bool:
    release = FoundRelease(
        read_text(album, "title"), get_album_artist(album), get_track_artist(track, album)
    )
    is_release = is_same_release(release, searched_album)
    return is_release and not is_guessed_compilation(album, searched_album)


def parse_position(position: str | None) -> TrackPosition | None:
    match = NUMBERED_POSITION.fullmatch((position or "").strip())
    if match is None:
        return None
    return TrackPosition(int(match.group(1) or "1"), int(match.group(2)))


def get_positions(album: JsonObject) -> list[TrackPosition]:
    positions = (parse_position(read_text(song, "position")) for song in get_songs(album))
    return [position for position in positions if position is not None]


# Like tags, the track count is per disc.
def get_position_extras(album: JsonObject, track: JsonObject) -> TrackExtras:
    position = parse_position(read_text(track, "position"))
    if position is None:
        return TrackExtras()
    positions = get_positions(album)
    disc_tracks = [other for other in positions if other.disc == position.disc]
    return TrackExtras(
        track_number=make_optional_count(position.track),
        track_count=make_optional_count(len(disc_tracks)),
        disc_number=make_optional_count(position.disc),
        disc_count=make_optional_count(max(other.disc for other in positions)),
    )


def read_first_genre(album: JsonObject) -> str | None:
    genres = read_list(album, "genres")
    first = genres[0] if genres else None
    return make_optional_text(first) if isinstance(first, str) else None


def get_extras(match: DiscogsMatch) -> TrackExtras:
    if not match.is_release:
        return TrackExtras(genre=read_first_genre(match.album))
    positions = get_position_extras(match.album, match.track)
    album_artist = make_optional_text(get_album_artist(match.album))
    return replace(positions, genre=read_first_genre(match.album), album_artist=album_artist)


# Only a master's year is the album's first; a release can be a reissue.
def get_year(match: DiscogsMatch) -> str:
    year = read_int(match.album, "year")
    is_original = match.kind == "master" and match.is_release
    return str(year) if is_original and year else ""


def get_cover_url(album: JsonObject) -> str | None:
    images = read_objects(album, "images")
    primary = next((image for image in images if read_text(image, "type") == "primary"), None)
    chosen = primary or (images[0] if images else None)
    return read_text(chosen, "uri") if chosen else None


def get_info(match: DiscogsMatch) -> TrackInfo:
    album = read_text(match.album, "title") if match.is_release else ""
    return TrackInfo(
        read_text(match.track, "title") or "",
        get_track_artist(match.track, match.album),
        album or "",
        get_year(match),
    )


def match_song(
    kind: DiscogsAlbumKind, album: JsonObject, search: TrackSearch
) -> DiscogsMatch | None:
    track = find_song(album, search)
    if track is None:
        return None
    return DiscogsMatch(kind, album, track, is_searched_release(album, track, search.album))


# Finds the song in the tracklist of the album Discogs ranks first.
class DiscogsTrackFinder:
    def __init__(self, client: DiscogsClient, services: ProviderServices) -> None:
        self._client = client
        self._services = services

    def find(self, search: TrackSearch, needs: ProviderNeeds) -> TrackMetadata | None:
        if not (needs.cover or needs.details):
            return None
        match = self._find_match(search)
        if match is None:
            return None
        return TrackMetadata(
            get_info(match), get_extras(match), self._find_cover(match, needs.cover)
        )

    def _find_match(self, search: TrackSearch) -> DiscogsMatch | None:
        matches = (self._find_match_of_kind(kind, search) for kind in ALBUM_KINDS)
        return next((match for match in matches if match is not None), None)

    def _find_match_of_kind(
        self, kind: DiscogsAlbumKind, search: TrackSearch
    ) -> DiscogsMatch | None:
        results = self._client.search_albums(kind, search)
        album_id = read_int(results[0], "id") if results else None
        if album_id is None:
            return None
        return match_song(kind, self._client.get_album(kind, album_id), search)

    def _find_cover(self, match: DiscogsMatch, is_wanted: bool) -> bytes | None:
        url = get_cover_url(match.album) if is_wanted and match.is_release else None
        if not url:
            return None
        return self._services.images.download_first([self._client.get_cover_request(url)])


# First in the chain: it confirms the album of the folder or tags and its tracklist.
class DiscogsAlbumProvider:
    name = "Discogs"

    def __init__(self, finder: DiscogsTrackFinder) -> None:
        self._finder = finder

    def find_metadata(self, search: TrackSearch, needs: ProviderNeeds) -> TrackMetadata | None:
        return self._finder.find(search, needs) if search.album else None


# Later in the chain, for songs whose album is still unknown.
class DiscogsProvider:
    name = "Discogs"

    def __init__(self, finder: DiscogsTrackFinder) -> None:
        self._finder = finder

    def find_metadata(self, search: TrackSearch, needs: ProviderNeeds) -> TrackMetadata | None:
        return None if search.album else self._finder.find(search, needs)
