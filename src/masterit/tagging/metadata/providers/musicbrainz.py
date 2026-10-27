from masterit.tagging.metadata.providers.musicbrainz_client import (
    MusicBrainzClient,
    get_musicbrainz_artist,
)
from masterit.tagging.metadata.track_matching import (
    FoundRelease,
    FoundTrack,
    is_same_release,
    is_same_track,
)
from masterit.tagging.metadata.track_metadata import extract_year
from masterit.tagging.metadata.types import (
    ProviderNeeds,
    ProviderServices,
    TrackExtras,
    TrackInfo,
    TrackMetadata,
    TrackSearch,
)
from masterit.tagging.web.json_fields import read_objects, read_text
from masterit.tagging.web.json_response import JsonObject


def get_credited_artist(item: JsonObject) -> str:
    return get_musicbrainz_artist(read_objects(item, "artist-credit"))


def get_credited_releases(recording: JsonObject) -> list[JsonObject]:
    track_artist = get_credited_artist(recording)
    return [
        release
        for release in read_objects(recording, "releases")
        if is_same_release(FoundRelease(None, get_credited_artist(release), track_artist), "")
    ]


# A recording only released by another artist is a mis-credited cover.
def is_released_by_artist(recording: JsonObject) -> bool:
    return not read_objects(recording, "releases") or bool(get_credited_releases(recording))


def get_searched_releases(recording: JsonObject, searched_album: str) -> list[JsonObject]:
    return [
        release
        for release in get_credited_releases(recording)
        if is_same_release(FoundRelease(read_text(release, "title")), searched_album)
    ]


def get_recording_year(recording: JsonObject, release: JsonObject) -> str:
    recording_year = extract_year(read_text(recording, "first-release-date"))
    return recording_year or extract_year(read_text(release, "date"))


def get_recording_info(recording: JsonObject, release: JsonObject) -> TrackInfo:
    return TrackInfo(
        read_text(recording, "title") or "",
        get_credited_artist(recording),
        read_text(release, "title") or "",
        get_recording_year(recording, release),
    )


def is_searched_recording(recording: JsonObject, search: TrackSearch) -> bool:
    found = FoundTrack(read_text(recording, "title"), get_credited_artist(recording))
    return is_same_track(found, search) and is_released_by_artist(recording)


class MusicBrainzProvider:
    name = "MusicBrainz"

    def __init__(self, client: MusicBrainzClient, services: ProviderServices) -> None:
        self._client = client
        self._services = services

    def find_metadata(self, search: TrackSearch, needs: ProviderNeeds) -> TrackMetadata | None:
        recording = self._search_recording(search)
        if recording is None:
            return None
        releases = get_searched_releases(recording, search.album)
        info = get_recording_info(recording, releases[0] if releases else {})
        cover = self._download_cover(releases) if needs.cover else None
        return TrackMetadata(info, TrackExtras(), cover)

    def _search_recording(self, search: TrackSearch) -> JsonObject | None:
        recordings = self._client.search_recordings(search)
        if not recordings or not is_searched_recording(recordings[0], search):
            return None
        return recordings[0]

    def _download_cover(self, releases: list[JsonObject]) -> bytes | None:
        requests = [
            self._client.get_cover_request(release_id)
            for release in releases
            if (release_id := read_text(release, "id"))
        ]
        return self._services.images.download_first(requests)
