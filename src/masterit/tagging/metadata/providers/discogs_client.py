from dataclasses import dataclass
from typing import Literal

from masterit.tagging.metadata.types import ProviderServices, TrackSearch
from masterit.tagging.web.images import ImageRequest
from masterit.tagging.web.json_fields import read_objects
from masterit.tagging.web.json_response import JsonObject, read_json
from masterit.tagging.web.rate_limiter import RateLimiter
from masterit.tagging.web.transport import HttpRequest
from masterit.tagging.web.url_text import encode_query

# A master groups every edition of an album and carries its original year.
type DiscogsAlbumKind = Literal["master", "release"]

DISCOGS_API_URL = "https://api.discogs.com/"
# Discogs allows 60 authenticated requests per minute.
DISCOGS_REQUEST_INTERVAL = 1.0
USER_AGENT = "MasterIt/1.0"
SEARCH_LIMIT = "1"
ALBUM_PATHS: dict[DiscogsAlbumKind, str] = {"master": "masters", "release": "releases"}


@dataclass(frozen=True)
class DiscogsCredentials:
    key: str
    secret: str


# A known album is searched without the title, so its tracks share one cached search.
def build_search_url(kind: DiscogsAlbumKind, search: TrackSearch) -> str:
    params = {
        "type": kind,
        "artist": search.artist,
        "track": "" if search.album else search.title,
        "release_title": search.album,
        "per_page": SEARCH_LIMIT,
    }
    filled = {name: value for name, value in params.items() if value}
    return f"{DISCOGS_API_URL}database/search?{encode_query(filled)}"


# Consumer key and secret authenticate without a user, which searches need.
class DiscogsClient:
    def __init__(self, credentials: DiscogsCredentials, services: ProviderServices) -> None:
        self._services = services
        self._headers = {
            "User-Agent": USER_AGENT,
            "Authorization": f"Discogs key={credentials.key}, secret={credentials.secret}",
        }
        self._limiter = RateLimiter(DISCOGS_REQUEST_INTERVAL, services.clock)

    def search_albums(self, kind: DiscogsAlbumKind, search: TrackSearch) -> list[JsonObject]:
        return read_objects(self._request(build_search_url(kind, search)), "results")

    def get_album(self, kind: DiscogsAlbumKind, album_id: int) -> JsonObject:
        return self._request(f"{DISCOGS_API_URL}{ALBUM_PATHS[kind]}/{album_id}")

    def get_cover_request(self, url: str) -> ImageRequest:
        return ImageRequest(url, {"User-Agent": USER_AGENT})

    def _request(self, url: str) -> JsonObject:
        return self._services.cache.get_or_load(f"discogs:{url}", lambda: self._fetch_json(url))

    def _fetch_json(self, url: str) -> JsonObject:
        request = HttpRequest(url, self._headers)
        return self._limiter.run(
            lambda: read_json(self._services.transport.send(request), "Discogs")
        )
