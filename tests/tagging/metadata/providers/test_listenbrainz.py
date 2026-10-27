import urllib.parse
from typing import Any

import pytest

from masterit.tagging.metadata.providers.listenbrainz import ListenBrainzProvider
from masterit.tagging.metadata.providers.listenbrainz_client import (
    ListenBrainzClient,
    ListenBrainzCredentials,
)
from masterit.tagging.metadata.providers.musicbrainz_client import MusicBrainzClient
from masterit.tagging.metadata.types import (
    ProviderNeeds,
    TrackExtras,
    TrackInfo,
    TrackMetadata,
    TrackSearch,
)
from masterit.tagging.web.errors import ServiceError
from masterit.tagging.web.transport import HttpRequest, HttpResponse

from ...web.fakes import FakeTransport, make_image_response, make_json_response
from ..fakes import make_services

SEARCH = TrackSearch("Comfortably Numb", "Pink Floyd", "")
COVER_NEEDS = ProviderNeeds(cover=True, details=True)
DETAIL_NEEDS = ProviderNeeds(cover=False, details=True)
NO_NEEDS = ProviderNeeds(cover=False, details=False)
LOOKUP_MATCH: dict[str, Any] = {
    "recording_mbid": "numb",
    "recording_name": "Comfortably Numb",
    "artist_credit_name": "Pink Floyd",
    "release_mbid": "wall-1984",
    "release_name": "The Wall",
    "metadata": {
        "release": {
            "album_artist_name": "Pink Floyd",
            "caa_id": 42,
            "caa_release_mbid": "wall-art",
        },
        "tag": {"release_group": [{"tag": "progressive rock", "count": 22, "genre_mbid": "g"}]},
    },
}
WALL_RELEASE: dict[str, Any] = {
    "release-group": {"first-release-date": "1984-09"},
    "media": [
        {"position": 1, "track-count": 13, "tracks": []},
        {
            "position": 2,
            "track-count": 13,
            "tracks": [
                {"position": 6, "recording": {"id": "numb", "first-release-date": "1979-11-30"}}
            ],
        },
    ],
}
GENRE_ONLY = TrackExtras(genre="Progressive Rock")


class FakeServices:
    def __init__(self, match: Any = None, release_status: int = 200) -> None:
        self.match = LOOKUP_MATCH if match is None else match
        self.release_status = release_status
        self.requested: list[str] = []
        self.transport = FakeTransport(self._respond)

    def _respond(self, request: HttpRequest) -> HttpResponse:
        url = urllib.parse.urlsplit(request.url)
        self.requested.append(f"{url.hostname}{url.path}")
        if url.hostname == "api.listenbrainz.org":
            return make_json_response(self.match)
        if url.hostname == "musicbrainz.org":
            return make_json_response(WALL_RELEASE, self.release_status)
        return make_image_response(b"cover")


def find(
    services: FakeServices, needs: ProviderNeeds, search: TrackSearch = SEARCH
) -> TrackMetadata | None:
    provider_services = make_services(services.transport)
    user_agent = "MasterIt/1.0 (test@example.com)"
    provider = ListenBrainzProvider(
        ListenBrainzClient(ListenBrainzCredentials("secret", user_agent), provider_services),
        MusicBrainzClient(user_agent, provider_services),
        provider_services,
    )
    return provider.find_metadata(search, needs)


def test_fills_info_extras_and_cover_of_the_matched_release():
    services = FakeServices()
    assert find(services, COVER_NEEDS) == TrackMetadata(
        TrackInfo("Comfortably Numb", "Pink Floyd", "The Wall", "1979"),
        TrackExtras("Progressive Rock", "Pink Floyd", 6, 13, 2, 2),
        b"cover",
    )
    assert services.requested == [
        "api.listenbrainz.org/1/metadata/lookup/",
        "musicbrainz.org/ws/2/release/wall-1984",
        "coverartarchive.org/release/wall-art/42-500",
    ]


def test_skips_musicbrainz_and_the_cover_when_not_needed():
    services = FakeServices()
    metadata = find(services, NO_NEEDS)
    assert metadata == TrackMetadata(
        TrackInfo("Comfortably Numb", "Pink Floyd", "The Wall", ""),
        TrackExtras(genre="Progressive Rock", album_artist="Pink Floyd"),
    )
    assert len(services.requested) == 1


def test_needs_an_artist_to_look_up():
    services = FakeServices()
    assert find(services, COVER_NEEDS, TrackSearch("Comfortably Numb")) is None
    assert services.requested == []


def test_returns_none_when_nothing_matches():
    assert find(FakeServices({}), COVER_NEEDS) is None


def test_returns_none_for_another_song():
    assert find(FakeServices({**LOOKUP_MATCH, "recording_name": "Crazy Love"}), COVER_NEEDS) is None


def test_accepts_a_corrected_typo():
    metadata = find(FakeServices(), DETAIL_NEEDS, TrackSearch("Comfortaby Numb", "Pink Floyd"))
    assert metadata is not None
    assert metadata.info.title == "Comfortably Numb"


def test_takes_only_the_genre_from_another_release():
    services = FakeServices()
    metadata = find(services, COVER_NEEDS, TrackSearch("Comfortably Numb", "Pink Floyd", "Echoes"))
    assert metadata == TrackMetadata(TrackInfo("Comfortably Numb", "Pink Floyd"), GENRE_ONLY)
    assert len(services.requested) == 1


def test_rejects_a_release_by_another_artist():
    release = {**LOOKUP_MATCH["metadata"]["release"], "album_artist_name": "Stringdusters"}
    match = {**LOOKUP_MATCH, "metadata": {**LOOKUP_MATCH["metadata"], "release": release}}
    services = FakeServices(match)
    assert find(services, COVER_NEEDS) == TrackMetadata(
        TrackInfo("Comfortably Numb", "Pink Floyd"), GENRE_ONLY
    )
    assert len(services.requested) == 1


@pytest.mark.parametrize(
    "release",
    [{}, {"caa_id": 0, "caa_release_mbid": "art"}, {"caa_id": 42, "caa_release_mbid": ""}],
)
def test_skips_the_cover_without_cover_art_archive_art(release: dict[str, Any]):
    services = FakeServices({**LOOKUP_MATCH, "metadata": {"release": release}})
    metadata = find(services, ProviderNeeds(cover=True, details=False))
    assert metadata is not None
    assert metadata.cover_data is None
    assert len(services.requested) == 1


def test_skips_musicbrainz_without_a_release_id():
    match = {key: value for key, value in LOOKUP_MATCH.items() if key != "release_mbid"}
    services = FakeServices(match)
    metadata = find(services, DETAIL_NEEDS)
    assert metadata is not None
    assert metadata.info.year == ""
    assert len(services.requested) == 1


def test_lets_a_failed_lookup_reach_the_chain():
    transport = FakeTransport(lambda _request: HttpResponse(401, {}, b""))
    services = FakeServices()
    services.transport = transport
    with pytest.raises(ServiceError, match="ListenBrainz rejected the token"):
        find(services, COVER_NEEDS)


def test_keeps_the_match_when_the_release_lookup_fails():
    metadata = find(FakeServices(release_status=500), DETAIL_NEEDS)
    assert metadata == TrackMetadata(
        TrackInfo("Comfortably Numb", "Pink Floyd", "The Wall", ""),
        TrackExtras(genre="Progressive Rock", album_artist="Pink Floyd"),
    )
