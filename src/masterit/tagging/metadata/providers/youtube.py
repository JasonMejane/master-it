from masterit.tagging.metadata.types import ProviderServices, TrackSearch
from masterit.tagging.web.images import ImageRequest
from masterit.tagging.web.json_fields import read_object, read_objects, read_text
from masterit.tagging.web.json_response import JsonObject, read_json
from masterit.tagging.web.transport import HttpRequest
from masterit.tagging.web.url_text import encode_query

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
THUMBNAIL_SIZES = ("maxres", "standard", "high", "medium", "default")


def build_youtube_search_url(search: TrackSearch, api_key: str) -> str:
    query = " ".join(part for part in (search.artist, search.title) if part)
    params = {"part": "snippet", "type": "video", "maxResults": "1", "q": query, "key": api_key}
    return f"{YOUTUBE_SEARCH_URL}?{encode_query(params)}"


def get_best_thumbnail_url(data: JsonObject) -> str | None:
    items = read_objects(data, "items")
    snippet = read_object(items[0], "snippet") if items else {}
    thumbnails = read_object(snippet, "thumbnails")
    urls = (read_text(read_object(thumbnails, size), "url") for size in THUMBNAIL_SIZES)
    return next((url for url in urls if url), None)


# The thumbnail may be a video still rather than the album art, so it comes last.
class YouTubeCoverProvider:
    name = "YouTube"

    def __init__(self, api_key: str, services: ProviderServices) -> None:
        self._api_key = api_key
        self._services = services

    def find_cover(self, search: TrackSearch) -> bytes | None:
        request = HttpRequest(build_youtube_search_url(search, self._api_key))
        data = read_json(self._services.transport.send(request), "YouTube Data API")
        url = get_best_thumbnail_url(data)
        return self._services.images.download(ImageRequest(url)) if url else None
