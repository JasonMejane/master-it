from masterit.tagging.metadata.types import AlbumSearch, ProviderServices, TrackSearch
from masterit.tagging.web.errors import ServiceTimeoutError
from masterit.tagging.web.images import ImageRequest
from masterit.tagging.web.json_fields import read_object, read_objects, read_text
from masterit.tagging.web.json_response import JsonObject, get_retry_after_delay, read_json
from masterit.tagging.web.rate_limiter import RateLimiter
from masterit.tagging.web.transport import HttpRequest, HttpResponse
from masterit.tagging.web.url_text import encode_path_part, encode_query

MUSICBRAINZ_BASE = "https://musicbrainz.org/ws/2/"
COVER_ART_ARCHIVE_BASE = "https://coverartarchive.org/release/"
COVER_ART_ARCHIVE_GROUP_BASE = "https://coverartarchive.org/release-group/"
RELEASE_GROUP_SEARCH_LIMIT = "5"
# MusicBrainz allows one request per second, yet 2 s and 3 s spacing still drew 503s.
MUSICBRAINZ_REQUEST_INTERVAL = 3.5
SERVICE_UNAVAILABLE = 503
DEFAULT_RETRY_DELAY = 3.0
MAX_RETRY_DELAY = 10.0
RELEASE_INCLUDES = "recordings release-groups artist-credits"


def get_credit_name(credit: JsonObject) -> str:
    name = read_text(credit, "name")
    return name if name is not None else read_text(read_object(credit, "artist"), "name") or ""


def get_musicbrainz_artist(credits: list[JsonObject]) -> str:
    names = (
        f"{get_credit_name(credit)}{read_text(credit, 'joinphrase') or ''}" for credit in credits
    )
    return "".join(names).strip()


def build_search_term(field: str, value: str) -> str:
    escaped = value.replace('"', '\\"')
    return f'{field}:"{escaped}"'


def build_musicbrainz_url(path: str, params: dict[str, str]) -> str:
    return f"{MUSICBRAINZ_BASE}{path}?{encode_query(params)}"


def build_recording_search_url(search: TrackSearch) -> str:
    terms = [
        build_search_term("recording", search.title),
        *([build_search_term("artist", search.artist)] if search.artist else []),
        *([build_search_term("release", search.album)] if search.album else []),
    ]
    params = {"query": " AND ".join(terms), "fmt": "json", "limit": "1"}
    return build_musicbrainz_url("recording", params)


def build_release_group_search_url(search: AlbumSearch) -> str:
    terms = [
        build_search_term("releasegroup", search.album),
        build_search_term("artist", search.artist),
    ]
    params = {"query": " AND ".join(terms), "fmt": "json", "limit": RELEASE_GROUP_SEARCH_LIMIT}
    return build_musicbrainz_url("release-group", params)


def build_release_url(release_id: str) -> str:
    params = {"inc": RELEASE_INCLUDES, "fmt": "json"}
    return build_musicbrainz_url(f"release/{encode_path_part(release_id)}", params)


class MusicBrainzClient:
    def __init__(self, user_agent: str, services: ProviderServices) -> None:
        self._user_agent = user_agent
        self._services = services
        self._limiter = RateLimiter(MUSICBRAINZ_REQUEST_INTERVAL, services.clock)

    def search_recordings(self, search: TrackSearch) -> list[JsonObject]:
        url = build_recording_search_url(search)
        data = self._services.cache.get_or_load(
            f"musicbrainz:search:{url}", lambda: self._request_json(url)
        )
        return read_objects(data, "recordings")

    def search_release_groups(self, search: AlbumSearch) -> list[JsonObject]:
        data = self._request_json(build_release_group_search_url(search))
        return read_objects(data, "release-groups")

    def get_release(self, release_id: str) -> JsonObject:
        return self._services.cache.get_or_load(
            f"musicbrainz:release:{release_id}",
            lambda: self._request_json(build_release_url(release_id)),
        )

    def get_cover_request(self, release_id: str, image: str = "front") -> ImageRequest:
        url = f"{COVER_ART_ARCHIVE_BASE}{encode_path_part(release_id)}/{image}-500"
        return ImageRequest(url, {"User-Agent": self._user_agent})

    def get_release_group_cover_request(self, group_id: str, size: int) -> ImageRequest:
        url = f"{COVER_ART_ARCHIVE_GROUP_BASE}{encode_path_part(group_id)}/front-{size}"
        return ImageRequest(url, {"User-Agent": self._user_agent})

    def _request_json(self, url: str) -> JsonObject:
        return read_json(self._fetch_with_retry(url), "MusicBrainz")

    def _fetch_with_retry(self, url: str) -> HttpResponse:
        response = self._fetch_retrying_timeout(url)
        if response.status != SERVICE_UNAVAILABLE:
            return response
        delay = get_retry_after_delay(response, DEFAULT_RETRY_DELAY, MAX_RETRY_DELAY)
        if delay > 0:
            self._services.clock.sleep(delay)
        return self._schedule_fetch(url)

    # MusicBrainz sometimes stalls on a request it answers at once when asked again.
    def _fetch_retrying_timeout(self, url: str) -> HttpResponse:
        try:
            return self._schedule_fetch(url)
        except ServiceTimeoutError:
            return self._schedule_fetch(url)

    def _schedule_fetch(self, url: str) -> HttpResponse:
        request = HttpRequest(url, {"User-Agent": self._user_agent})
        return self._limiter.run(lambda: self._services.transport.send(request))
