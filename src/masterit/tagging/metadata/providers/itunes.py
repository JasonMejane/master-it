from dataclasses import replace

from masterit.tagging.metadata.track_matching import (
    FoundRelease,
    FoundTrack,
    is_same_release,
    is_same_track,
)
from masterit.tagging.metadata.track_metadata import (
    extract_year,
    make_optional_count,
    make_optional_text,
)
from masterit.tagging.metadata.types import (
    ProviderNeeds,
    ProviderServices,
    TrackExtras,
    TrackInfo,
    TrackMetadata,
    TrackSearch,
)
from masterit.tagging.web.images import ImageRequest
from masterit.tagging.web.json_fields import read_int, read_objects, read_text
from masterit.tagging.web.json_response import JsonObject, read_json
from masterit.tagging.web.rate_limiter import RateLimiter
from masterit.tagging.web.transport import HttpRequest
from masterit.tagging.web.url_text import encode_query

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
# Apple's Search API allows about 20 requests per minute.
ITUNES_REQUEST_INTERVAL = 4.0


def build_itunes_search_url(search: TrackSearch) -> str:
    term = " ".join(part for part in (search.artist, search.title, search.album) if part)
    params = {"term": term, "country": "US", "entity": "song", "limit": "1"}
    return f"{ITUNES_SEARCH_URL}?{encode_query(params)}"


def get_track_info(track: JsonObject, is_release: bool) -> TrackInfo:
    album = read_text(track, "collectionName") if is_release else ""
    return TrackInfo(
        read_text(track, "trackName") or "",
        read_text(track, "artistName") or "",
        album or "",
        extract_year(read_text(track, "releaseDate")),
    )


def get_release_extras(track: JsonObject) -> TrackExtras:
    return TrackExtras(
        album_artist=make_optional_text(read_text(track, "collectionArtistName")),
        track_number=make_optional_count(read_int(track, "trackNumber")),
        track_count=make_optional_count(read_int(track, "trackCount")),
        disc_number=make_optional_count(read_int(track, "discNumber")),
        disc_count=make_optional_count(read_int(track, "discCount")),
    )


def get_extras(track: JsonObject, is_release: bool) -> TrackExtras:
    genre = make_optional_text(read_text(track, "primaryGenreName"))
    if not is_release:
        return TrackExtras(genre=genre)
    return replace(get_release_extras(track), genre=genre)


def is_searched_track(track: JsonObject, search: TrackSearch) -> bool:
    found = FoundTrack(read_text(track, "trackName"), read_text(track, "artistName"))
    return is_same_track(found, search)


def is_searched_release(track: JsonObject, search: TrackSearch) -> bool:
    release = FoundRelease(
        read_text(track, "collectionName"),
        read_text(track, "collectionArtistName"),
        read_text(track, "artistName"),
    )
    return is_same_release(release, search.album)


class ItunesProvider:
    name = "iTunes"

    def __init__(self, services: ProviderServices) -> None:
        self._services = services
        self._limiter = RateLimiter(ITUNES_REQUEST_INTERVAL, services.clock)

    def find_metadata(self, search: TrackSearch, needs: ProviderNeeds) -> TrackMetadata | None:
        track = self._search_track(search)
        if track is None:
            return None
        is_release = is_searched_release(track, search)
        cover = self._find_artwork(track, needs.cover and is_release)
        return TrackMetadata(
            get_track_info(track, is_release), get_extras(track, is_release), cover
        )

    def _search_track(self, search: TrackSearch) -> JsonObject | None:
        request = HttpRequest(build_itunes_search_url(search))
        data = self._limiter.run(
            lambda: read_json(self._services.transport.send(request), "iTunes Search")
        )
        results = read_objects(data, "results")
        return results[0] if results and is_searched_track(results[0], search) else None

    def _find_artwork(self, track: JsonObject, is_wanted: bool) -> bytes | None:
        url = read_text(track, "artworkUrl100") if is_wanted else None
        return self._services.images.download_first([ImageRequest(url)]) if url else None
