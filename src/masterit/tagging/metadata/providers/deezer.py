from dataclasses import dataclass, replace

from masterit.tagging.metadata.providers.deezer_client import (
    DeezerClient,
    build_query,
    get_cover_requests,
    get_deezer_genre,
)
from masterit.tagging.metadata.track_matching import (
    FoundRelease,
    FoundTrack,
    is_same_release,
    is_same_track,
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
from masterit.tagging.web.errors import ServiceError
from masterit.tagging.web.json_fields import read_int, read_object, read_text
from masterit.tagging.web.json_response import JsonObject


@dataclass(frozen=True)
class DeezerDetails:
    extras: TrackExtras
    is_release: bool


@dataclass(frozen=True)
class DetailsRequest:
    album_id: int
    track: JsonObject
    is_release: bool
    searched_album: str


def read_artist_name(item: JsonObject) -> str | None:
    return read_text(read_object(item, "artist"), "name")


def is_searched_track(track: JsonObject, search: TrackSearch) -> bool:
    return is_same_track(FoundTrack(read_text(track, "title"), read_artist_name(track)), search)


def is_searched_release(track: JsonObject, search: TrackSearch) -> bool:
    album_title = read_text(read_object(track, "album"), "title")
    return is_same_release(FoundRelease(album_title), search.album)


# Results can start with a karaoke version, or the song on another release.
def pick_track(tracks: list[JsonObject], search: TrackSearch) -> JsonObject | None:
    matches = [track for track in tracks if is_searched_track(track, search)]
    on_release = (track for track in matches if is_searched_release(track, search))
    return next(on_release, matches[0] if matches else None)


# Deezer dates are often those of a reissue, so the year is left to others.
def get_track_info(track: JsonObject, is_release: bool) -> TrackInfo:
    album = read_text(read_object(track, "album"), "title") if is_release else ""
    return TrackInfo(read_text(track, "title") or "", read_artist_name(track) or "", album or "")


def get_disc_count(tracks: list[JsonObject]) -> int:
    return max([0, *(read_int(track, "disk_number") or 0 for track in tracks)])


def find_position(tracks: list[JsonObject], track_id: int | None) -> JsonObject | None:
    if track_id is None:
        return None
    return next((track for track in tracks if read_int(track, "id") == track_id), None)


# nb_tracks counts every disc, while the track count is per disc.
def get_position_extras(tracks: list[JsonObject], track_id: int | None) -> TrackExtras:
    position = find_position(tracks, track_id)
    if position is None:
        return TrackExtras()
    disc = read_int(position, "disk_number")
    disc_tracks = [track for track in tracks if read_int(track, "disk_number") == disc]
    return TrackExtras(
        track_number=make_optional_count(read_int(position, "track_position")),
        track_count=make_optional_count(len(disc_tracks)),
        disc_number=make_optional_count(disc),
        disc_count=make_optional_count(get_disc_count(tracks)),
    )


# The search result has no album artist, so the album confirms the release.
def is_release_of_track(album: JsonObject, track: JsonObject, searched_album: str) -> bool:
    release = FoundRelease(
        read_text(album, "title"), read_artist_name(album), read_artist_name(track)
    )
    return is_same_release(release, searched_album)


def get_genre_details(album: JsonObject) -> DeezerDetails:
    return DeezerDetails(TrackExtras(genre=get_deezer_genre(album)), is_release=False)


class DeezerProvider:
    name = "Deezer"

    def __init__(self, client: DeezerClient, services: ProviderServices) -> None:
        self._client = client
        self._services = services

    def find_metadata(self, search: TrackSearch, needs: ProviderNeeds) -> TrackMetadata | None:
        query = build_query([search.artist, search.title])
        track = pick_track(self._client.search_tracks(query), search)
        if track is None:
            return None
        details = self._find_details(track, search, needs.details)
        cover = self._find_cover(track, needs.cover and details.is_release)
        return TrackMetadata(get_track_info(track, details.is_release), details.extras, cover)

    def _find_details(
        self, track: JsonObject, search: TrackSearch, needs_details: bool
    ) -> DeezerDetails:
        is_release = is_searched_release(track, search)
        album_id = read_int(read_object(track, "album"), "id")
        if not needs_details or album_id is None:
            return DeezerDetails(TrackExtras(), is_release)
        return self._load_details(DetailsRequest(album_id, track, is_release, search.album))

    # The track was found, so a failed album lookup only costs its details.
    def _load_details(self, request: DetailsRequest) -> DeezerDetails:
        try:
            return self._load_album_details(request)
        except ServiceError:
            return DeezerDetails(TrackExtras(), request.is_release)

    def _load_album_details(self, request: DetailsRequest) -> DeezerDetails:
        album = self._client.get_album(request.album_id)
        is_confirmed = request.is_release and is_release_of_track(
            album, request.track, request.searched_album
        )
        if not is_confirmed:
            return get_genre_details(album)
        return self._load_release_details(album, request)

    def _load_release_details(self, album: JsonObject, request: DetailsRequest) -> DeezerDetails:
        tracks = self._client.get_album_tracks(request.album_id)
        positions = get_position_extras(tracks, read_int(request.track, "id"))
        extras = replace(
            positions,
            genre=get_deezer_genre(album),
            album_artist=make_optional_text(read_artist_name(album)),
        )
        return DeezerDetails(extras, is_release=True)

    def _find_cover(self, track: JsonObject, is_wanted: bool) -> bytes | None:
        if not is_wanted:
            return None
        return self._services.images.download_first(get_cover_requests(read_object(track, "album")))
