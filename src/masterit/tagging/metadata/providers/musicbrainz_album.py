from masterit.tagging.metadata.providers.musicbrainz_client import (
    MusicBrainzClient,
    get_musicbrainz_artist,
)
from masterit.tagging.metadata.track_matching import FoundAlbumName, is_searched_album
from masterit.tagging.metadata.track_metadata import extract_year
from masterit.tagging.metadata.types import AlbumSearch, FoundAlbum
from masterit.tagging.web.images import ImageRequest
from masterit.tagging.web.json_fields import read_objects, read_text
from masterit.tagging.web.json_response import JsonObject

# Like Deezer's 1000 px artwork; the 500 px one when the archive has no larger.
COVER_SIZES = (1200, 500)


def get_group_artist(group: JsonObject) -> str:
    return get_musicbrainz_artist(read_objects(group, "artist-credit"))


def is_searched_group(group: JsonObject, search: AlbumSearch) -> bool:
    found = FoundAlbumName(read_text(group, "title"), get_group_artist(group))
    return is_searched_album(found, search)


class MusicBrainzAlbumSource:
    name = "MusicBrainz"

    def __init__(self, client: MusicBrainzClient) -> None:
        self._client = client

    def find_album(self, search: AlbumSearch) -> FoundAlbum | None:
        groups = self._client.search_release_groups(search)
        group = next((group for group in groups if is_searched_group(group, search)), None)
        return None if group is None else self._describe_album(group)

    def _get_cover_requests(self, group: JsonObject) -> list[ImageRequest]:
        group_id = read_text(group, "id")
        if not group_id:
            return []
        return [
            self._client.get_release_group_cover_request(group_id, size) for size in COVER_SIZES
        ]

    def _describe_album(self, group: JsonObject) -> FoundAlbum:
        return FoundAlbum(
            read_text(group, "title") or "",
            get_group_artist(group),
            extract_year(read_text(group, "first-release-date")),
            covers=self._get_cover_requests(group),
        )
