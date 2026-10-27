from dataclasses import dataclass

from masterit.tagging.metadata.types import ProviderServices, TrackSearch
from masterit.tagging.web.errors import ServiceError
from masterit.tagging.web.json_fields import read_text
from masterit.tagging.web.json_response import JsonObject, read_json
from masterit.tagging.web.rate_limiter import RateLimiter
from masterit.tagging.web.transport import HttpRequest, HttpResponse
from masterit.tagging.web.url_text import encode_query

LOOKUP_URL = "https://api.listenbrainz.org/1/metadata/lookup/"
LISTENBRAINZ_REQUEST_INTERVAL = 1.0
UNAUTHORIZED = 401


@dataclass(frozen=True)
class ListenBrainzCredentials:
    token: str
    user_agent: str


def build_lookup_url(search: TrackSearch) -> str:
    album = {"release_name": search.album} if search.album else {}
    params = {
        "artist_name": search.artist,
        "recording_name": search.title,
        **album,
        "metadata": "true",
        "inc": "artist tag release",
    }
    return f"{LOOKUP_URL}?{encode_query(params)}"


def read_lookup_response(response: HttpResponse) -> JsonObject:
    if response.status == UNAUTHORIZED:
        raise ServiceError("ListenBrainz rejected the token: check it in the settings.")
    return read_json(response, "ListenBrainz")


# No match is an empty object rather than an HTTP error.
def get_match(payload: JsonObject) -> JsonObject | None:
    return payload if read_text(payload, "recording_mbid") else None


class ListenBrainzClient:
    def __init__(self, credentials: ListenBrainzCredentials, services: ProviderServices) -> None:
        self._credentials = credentials
        self._services = services
        self._limiter = RateLimiter(LISTENBRAINZ_REQUEST_INTERVAL, services.clock)

    def look_up(self, search: TrackSearch) -> JsonObject | None:
        url = build_lookup_url(search)
        payload = self._services.cache.get_or_load(
            f"listenbrainz:lookup:{url}", lambda: self._request(url)
        )
        return get_match(payload)

    def _request(self, url: str) -> JsonObject:
        headers = {
            "Authorization": f"Token {self._credentials.token}",
            "User-Agent": self._credentials.user_agent,
        }
        request = HttpRequest(url, headers)
        return self._limiter.run(
            lambda: read_lookup_response(self._services.transport.send(request))
        )
