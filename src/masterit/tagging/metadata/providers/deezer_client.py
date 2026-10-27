import urllib.parse

from masterit.tagging.metadata.track_metadata import make_optional_text
from masterit.tagging.metadata.types import ProviderServices
from masterit.tagging.web.errors import ServiceError
from masterit.tagging.web.images import ImageRequest
from masterit.tagging.web.json_fields import read_object, read_objects, read_text
from masterit.tagging.web.json_response import JsonObject, read_json
from masterit.tagging.web.rate_limiter import RateLimiter
from masterit.tagging.web.transport import HttpRequest

DEEZER_API_URL = "https://api.deezer.com/"
DEEZER_REQUEST_INTERVAL = 0.5
SEARCH_LIMIT = "5"
ALBUM_TRACKS_LIMIT = "1000"
ARTIST_ALBUMS_LIMIT = "200"
COVER_SIZES = ("cover_xl", "cover_big")


def build_deezer_url(path: str, params: dict[str, str]) -> str:
    query = f"?{urllib.parse.urlencode(params)}" if params else ""
    return f"{DEEZER_API_URL}{path}{query}"


def build_query(parts: list[str]) -> str:
    return " ".join(part for part in parts if part)


def get_deezer_genre(album: JsonObject) -> str | None:
    genres = read_objects(read_object(album, "genres"), "data")
    return make_optional_text(read_text(genres[0], "name")) if genres else None


def get_cover_requests(album: JsonObject) -> list[ImageRequest]:
    urls = (read_text(album, size) for size in COVER_SIZES)
    return [ImageRequest(url) for url in urls if url is not None]


# JavaScript objects are truthy even when empty, so "error": {} is still an error.
def is_reported_error(error: object) -> bool:
    return isinstance(error, dict | list) or bool(error)


# Deezer reports failures with HTTP 200 and an error object.
def ensure_no_deezer_error(payload: JsonObject) -> None:
    if not is_reported_error(payload.get("error")):
        return
    message = read_object(payload, "error").get("message")
    raise ServiceError(f"Deezer error: {'unknown' if message is None else message}")


class DeezerClient:
    def __init__(self, services: ProviderServices) -> None:
        self._services = services
        self._limiter = RateLimiter(DEEZER_REQUEST_INTERVAL, services.clock)

    def search_tracks(self, query: str) -> list[JsonObject]:
        return self._request_list("search", {"q": query, "limit": SEARCH_LIMIT})

    def search_albums(self, query: str) -> list[JsonObject]:
        return self._request_list("search/album", {"q": query, "limit": SEARCH_LIMIT})

    def search_artists(self, name: str) -> list[JsonObject]:
        params = {"q": name, "limit": SEARCH_LIMIT}
        return self._services.cache.get_or_load(
            f"deezer:artists:{name}", lambda: self._request_list("search/artist", params)
        )

    def get_artist_albums(self, artist_id: int) -> list[JsonObject]:
        path = f"artist/{artist_id}/albums"
        return self._services.cache.get_or_load(
            f"deezer:artist-albums:{artist_id}",
            lambda: self._request_list(path, {"limit": ARTIST_ALBUMS_LIMIT}),
        )

    def get_album(self, album_id: int) -> JsonObject:
        return self._services.cache.get_or_load(
            f"deezer:album:{album_id}", lambda: self._request(f"album/{album_id}", {})
        )

    def get_album_tracks(self, album_id: int) -> list[JsonObject]:
        path = f"album/{album_id}/tracks"
        return self._services.cache.get_or_load(
            f"deezer:album-tracks:{album_id}",
            lambda: self._request_list(path, {"limit": ALBUM_TRACKS_LIMIT}),
        )

    def _request_list(self, path: str, params: dict[str, str]) -> list[JsonObject]:
        return read_objects(self._request(path, params), "data")

    def _request(self, path: str, params: dict[str, str]) -> JsonObject:
        request = HttpRequest(build_deezer_url(path, params))
        payload = self._limiter.run(
            lambda: read_json(self._services.transport.send(request), "Deezer")
        )
        ensure_no_deezer_error(payload)
        return payload
