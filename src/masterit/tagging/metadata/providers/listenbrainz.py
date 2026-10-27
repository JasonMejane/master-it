from dataclasses import dataclass, fields, replace

from masterit.tagging.metadata.providers.listenbrainz_client import ListenBrainzClient
from masterit.tagging.metadata.providers.listenbrainz_genre import pick_genre
from masterit.tagging.metadata.providers.musicbrainz_client import MusicBrainzClient
from masterit.tagging.metadata.providers.musicbrainz_release import (
    get_first_release_year,
    get_track_position_extras,
)
from masterit.tagging.metadata.track_matching import (
    FoundRelease,
    FoundTrack,
    is_same_release,
    is_same_track,
)
from masterit.tagging.metadata.track_metadata import make_optional_text
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
class ReleaseDetails:
    year: str
    extras: TrackExtras


@dataclass(frozen=True)
class ReleaseNeeds:
    is_release: bool
    cover: bool
    details: bool


NO_DETAILS = ReleaseDetails("", TrackExtras())


def get_release(match: JsonObject) -> JsonObject:
    return read_object(read_object(match, "metadata"), "release")


def is_searched_match(match: JsonObject, search: TrackSearch) -> bool:
    found = FoundTrack(read_text(match, "recording_name"), read_text(match, "artist_credit_name"))
    return is_same_track(found, search)


# Year, numbers, album artist and cover from another release would be wrong.
def get_release_needs(match: JsonObject, search: TrackSearch, needs: ProviderNeeds) -> ReleaseNeeds:
    release = FoundRelease(
        read_text(match, "release_name"),
        read_text(get_release(match), "album_artist_name"),
        read_text(match, "artist_credit_name"),
    )
    is_release = is_same_release(release, search.album)
    return ReleaseNeeds(is_release, needs.cover and is_release, needs.details and is_release)


def get_match_info(match: JsonObject, year: str, is_release: bool) -> TrackInfo:
    album = read_text(match, "release_name") if is_release else ""
    return TrackInfo(
        read_text(match, "recording_name") or "",
        read_text(match, "artist_credit_name") or "",
        album or "",
        year,
    )


def get_match_extras(match: JsonObject, is_release: bool) -> TrackExtras:
    album_artist = make_optional_text(read_text(get_release(match), "album_artist_name"))
    genre = pick_genre(read_object(read_object(match, "metadata"), "tag"))
    return TrackExtras(genre=genre, album_artist=album_artist if is_release else None)


def overlay_extras(base: TrackExtras, top: TrackExtras) -> TrackExtras:
    known = {field.name: getattr(top, field.name) for field in fields(top)}
    return replace(base, **{name: value for name, value in known.items() if value is not None})


def get_cover_art(release: JsonObject) -> tuple[str, int] | None:
    release_id = read_text(release, "caa_release_mbid")
    image_id = read_int(release, "caa_id")
    return (release_id, image_id) if release_id and image_id else None


# Its year needs a release lookup, so MusicBrainz gives the first release year.
class ListenBrainzProvider:
    name = "ListenBrainz"

    def __init__(
        self,
        listenbrainz: ListenBrainzClient,
        musicbrainz: MusicBrainzClient,
        services: ProviderServices,
    ) -> None:
        self._listenbrainz = listenbrainz
        self._musicbrainz = musicbrainz
        self._services = services

    def find_metadata(self, search: TrackSearch, needs: ProviderNeeds) -> TrackMetadata | None:
        match = self._find_match(search)
        if match is None:
            return None
        release_needs = get_release_needs(match, search, needs)
        details = self._find_release_details(match, release_needs.details)
        extras = overlay_extras(get_match_extras(match, release_needs.is_release), details.extras)
        info = get_match_info(match, details.year, release_needs.is_release)
        return TrackMetadata(info, extras, self._find_cover(match, release_needs.cover))

    def _find_match(self, search: TrackSearch) -> JsonObject | None:
        if not search.artist:
            return None
        match = self._listenbrainz.look_up(search)
        return match if match and is_searched_match(match, search) else None

    def _find_release_details(self, match: JsonObject, needs_details: bool) -> ReleaseDetails:
        release_id = read_text(match, "release_mbid")
        if not needs_details or not release_id:
            return NO_DETAILS
        return self._load_release_details(release_id, read_text(match, "recording_mbid") or "")

    # The match stands, so a failed release lookup only costs its details.
    def _load_release_details(self, release_id: str, recording_id: str) -> ReleaseDetails:
        try:
            release = self._musicbrainz.get_release(release_id)
        except ServiceError:
            return NO_DETAILS
        return ReleaseDetails(
            get_first_release_year(release, recording_id),
            get_track_position_extras(release, recording_id),
        )

    def _find_cover(self, match: JsonObject, is_wanted: bool) -> bytes | None:
        cover_art = get_cover_art(get_release(match))
        if not is_wanted or cover_art is None:
            return None
        release_id, image_id = cover_art
        request = self._musicbrainz.get_cover_request(release_id, str(image_id))
        return self._services.images.download_first([request])
