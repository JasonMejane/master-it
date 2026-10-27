import re
from dataclasses import dataclass, field
from typing import cast

from masterit.tagging.metadata.track_matching import FoundTrack, is_same_track
from masterit.tagging.metadata.track_metadata import extract_year
from masterit.tagging.metadata.types import (
    ProviderNeeds,
    ProviderServices,
    TrackExtras,
    TrackInfo,
    TrackMetadata,
    TrackSearch,
)
from masterit.tagging.web.errors import ServiceError
from masterit.tagging.web.images import ImageRequest
from masterit.tagging.web.json_fields import read_object, read_objects, read_text
from masterit.tagging.web.json_response import JsonObject, read_json
from masterit.tagging.web.rate_limiter import RateLimiter
from masterit.tagging.web.transport import HttpRequest
from masterit.tagging.web.url_text import encode_query

LASTFM_BASE = "https://ws.audioscrobbler.com/2.0/"
DEFAULT_COVER = "2a96cbd8b46e442fc41c2b86b821562f.png"
MAX_LARGE_COVER_BYTES = 500 * 1024
LASTFM_REQUEST_INTERVAL = 2.0
COVER_SIZES = ("large", "medium", "small")
TITLE_SEPARATOR = re.compile(r"^\s*[-\u2013\u2014:]\s*")


@dataclass(frozen=True)
class MatchedTrack:
    title: str
    artist: str


@dataclass(frozen=True)
class DirectLookup:
    asked: MatchedTrack | None = None
    track: JsonObject | None = None


@dataclass(frozen=True)
class LastFmMatch:
    matched: MatchedTrack
    album: JsonObject = field(default_factory=dict[str, object])


# One match comes as an object, several as a list; an empty one would match any search.
def get_first_match(data: JsonObject) -> JsonObject | None:
    trackmatches = read_object(read_object(data, "results"), "trackmatches")
    single = trackmatches.get("track")
    if isinstance(single, dict):
        return cast(JsonObject, single) or None
    matches = read_objects(trackmatches, "track")
    return (matches[0] or None) if matches else None


def get_artist_name(track: JsonObject) -> str:
    artist = track.get("artist")
    return (
        artist if isinstance(artist, str) else read_text(read_object(track, "artist"), "name") or ""
    )


def starts_with_artist(title: str, artist: str) -> bool:
    return bool(artist) and title[: len(artist)].lower() == artist.lower()


def remove_artist_prefix(title: str, artist: str) -> str:
    if not starts_with_artist(title, artist):
        return title
    remainder = title[len(artist) :]
    separator = TITLE_SEPARATOR.search(remainder)
    return remainder[separator.end() :].strip() if separator else title


def get_cover_url(images: list[JsonObject], size: str) -> str:
    sized = [image for image in images if read_text(image, "size") == size]
    return (read_text(sized[0], "#text") or "") if sized else ""


def get_cover_requests(album: JsonObject) -> list[ImageRequest]:
    images = read_objects(album, "image")
    sized_urls = ((size, get_cover_url(images, size)) for size in COVER_SIZES)
    return [
        ImageRequest(url, byte_limit=MAX_LARGE_COVER_BYTES if size == "large" else float("inf"))
        for size, url in sized_urls
        if url and not url.endswith(DEFAULT_COVER)
    ]


def get_matched_track(track: JsonObject, search: TrackSearch) -> MatchedTrack:
    artist = get_artist_name(track) or search.artist
    title = read_text(track, "name") or search.title
    return MatchedTrack(remove_artist_prefix(title, artist), artist)


# A scrobbled variant without an album is a worse match than what search finds.
def get_album_track(direct: DirectLookup) -> JsonObject | None:
    track = direct.track
    is_album_track = (
        track and read_text(track, "name") and read_text(read_object(track, "album"), "title")
    )
    return track if is_album_track else None


def is_searched_song(matched: MatchedTrack, search: TrackSearch) -> bool:
    title = remove_artist_prefix(search.title, search.artist or matched.artist)
    found = FoundTrack(matched.title, matched.artist)
    return is_same_track(found, TrackSearch(title, search.artist, search.album))


def get_searched_song(track: JsonObject | None, search: TrackSearch) -> LastFmMatch | None:
    if track is None:
        return None
    matched = get_matched_track(track, search)
    return (
        LastFmMatch(matched, read_object(track, "album"))
        if is_searched_song(matched, search)
        else None
    )


def get_album_info(match: LastFmMatch) -> TrackInfo:
    year = read_text(match.album, "year")
    album_year = year if year is not None else extract_year(read_text(match.album, "date"))
    return TrackInfo(
        match.matched.title, match.matched.artist, read_text(match.album, "title") or "", album_year
    )


class LastFmProvider:
    name = "Last.fm"

    def __init__(self, api_key: str, services: ProviderServices) -> None:
        self._api_key = api_key
        self._services = services
        self._limiter = RateLimiter(LASTFM_REQUEST_INTERVAL, services.clock)

    def find_metadata(self, search: TrackSearch, needs: ProviderNeeds) -> TrackMetadata | None:
        match = self._find_match(search)
        if match is None:
            return None
        cover = (
            self._services.images.download_first(get_cover_requests(match.album))
            if needs.cover
            else None
        )
        return TrackMetadata(get_album_info(match), TrackExtras(), cover)

    def _find_match(self, search: TrackSearch) -> LastFmMatch | None:
        direct = self._look_up_directly(search)
        found = get_searched_song(get_album_track(direct), search)
        return found or self._search_then_get_info(search, direct)

    # Saves the track.search request, which halves the Last.fm time per track.
    def _look_up_directly(self, search: TrackSearch) -> DirectLookup:
        if not search.artist:
            return DirectLookup()
        asked = MatchedTrack(remove_artist_prefix(search.title, search.artist), search.artist)
        track = self._get_track_info(asked)
        return DirectLookup(asked, track if get_searched_song(track, search) else None)

    def _search_then_get_info(
        self, search: TrackSearch, direct: DirectLookup
    ) -> LastFmMatch | None:
        found = get_searched_song(self._search_track(search), search)
        if found is None:
            return None
        is_asked = direct.asked == found.matched
        track = direct.track if is_asked else self._get_track_info(found.matched)
        return LastFmMatch(found.matched, read_object(track or {}, "album"))

    def _search_track(self, search: TrackSearch) -> JsonObject | None:
        params = {"method": "track.search", "track": search.title, "api_key": self._api_key}
        artist = {"artist": search.artist} if search.artist else {}
        return get_first_match(self._request({**params, "format": "json", "limit": "1", **artist}))

    # A failed lookup only costs the album: the song is found, or track.search still runs.
    def _get_track_info(self, matched: MatchedTrack) -> JsonObject | None:
        params = {
            "method": "track.getInfo",
            "artist": matched.artist,
            "track": matched.title,
            "api_key": self._api_key,
            "format": "json",
            "autocorrect": "1",
        }
        try:
            data = self._request(params)
        except ServiceError:
            return None
        return read_object(data, "track") or None

    def _request(self, params: dict[str, str]) -> JsonObject:
        request = HttpRequest(f"{LASTFM_BASE}?{encode_query(params)}")
        return self._limiter.run(
            lambda: read_json(self._services.transport.send(request), "Last.fm")
        )
