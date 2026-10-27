from masterit.tagging.metadata.providers.deezer_client import (
    DeezerClient,
    build_query,
    get_cover_requests,
)
from masterit.tagging.metadata.track_matching import is_same_name
from masterit.tagging.metadata.types import ProviderServices, TrackSearch
from masterit.tagging.web.json_fields import read_object, read_text
from masterit.tagging.web.json_response import JsonObject


def is_searched_album(album: JsonObject, search: TrackSearch) -> bool:
    artist = read_text(read_object(album, "artist"), "name")
    is_same_artist = not search.artist or is_same_name(artist, search.artist)
    return is_same_artist and is_same_name(read_text(album, "title"), search.album)


class DeezerCoverProvider:
    name = "Deezer"

    def __init__(self, client: DeezerClient, services: ProviderServices) -> None:
        self._client = client
        self._services = services

    def find_cover(self, search: TrackSearch) -> bytes | None:
        if not search.album:
            return None
        album = self._search_album(search)
        return self._services.images.download_first(get_cover_requests(album or {}))

    def _search_album(self, search: TrackSearch) -> JsonObject | None:
        albums = self._client.search_albums(build_query([search.artist, search.album]))
        return next((album for album in albums if is_searched_album(album, search)), None)
