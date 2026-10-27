import urllib.parse
from typing import Any

import pytest

from masterit.tagging.metadata.providers.musicbrainz import MusicBrainzProvider
from masterit.tagging.metadata.providers.musicbrainz_client import MusicBrainzClient
from masterit.tagging.metadata.types import (
    ProviderNeeds,
    TrackExtras,
    TrackInfo,
    TrackMetadata,
    TrackSearch,
)
from masterit.tagging.web.errors import ServiceError
from masterit.tagging.web.transport import HttpResponse

from ...web.fakes import FakeTransport, FakeWeb
from ..fakes import make_services

SEARCH = TrackSearch("Title", "Artist", "")
COVER_NEEDS = ProviderNeeds(cover=True, details=True)
DETAIL_NEEDS = ProviderNeeds(cover=False, details=True)
SEARCHED_RECORDING: dict[str, Any] = {"title": "Title", "artist-credit": [{"name": "Artist"}]}


def make_web(recordings: list[dict[str, Any]]) -> FakeWeb:
    return FakeWeb("musicbrainz.org", {"/ws/2/recording": {"recordings": recordings}})


def find(web: FakeWeb, search: TrackSearch, needs: ProviderNeeds) -> TrackMetadata | None:
    services = make_services(web.transport)
    client = MusicBrainzClient("MasterIt/1.0 (test@example.com)", services)
    return MusicBrainzProvider(client, services).find_metadata(search, needs)


def get_requested_hosts(web: FakeWeb) -> list[str]:
    return [urllib.parse.urlsplit(request.url).netloc for request in web.transport.requests]


def test_takes_info_from_the_first_recording():
    recording = {
        "title": "Found",
        "artist-credit": [{"name": "A", "joinphrase": " & "}, {"artist": {"name": "B"}}],
        "first-release-date": "1979-11-30",
        "releases": [{"id": "release", "title": "Album", "date": "1984"}],
    }
    metadata = find(make_web([recording]), TrackSearch("Found", "A & B"), DETAIL_NEEDS)
    assert metadata is not None
    assert metadata.info == TrackInfo("Found", "A & B", "Album", "1979")


def test_falls_back_to_the_release_date_for_the_year():
    recording = {**SEARCHED_RECORDING, "releases": [{"title": "Album", "date": "1984-02"}]}
    metadata = find(make_web([recording]), SEARCH, DETAIL_NEEDS)
    assert metadata is not None
    assert metadata.info.year == "1984"


def test_downloads_the_first_release_cover():
    web = make_web([{**SEARCHED_RECORDING, "releases": [{"id": "release"}]}])
    metadata = find(web, SEARCH, COVER_NEEDS)
    assert metadata is not None
    assert metadata.cover_data == b"image /release/release/front-500"
    assert get_requested_hosts(web) == ["musicbrainz.org", "coverartarchive.org"]


def test_skips_the_cover_download_when_no_cover_is_needed():
    web = make_web([{**SEARCHED_RECORDING, "releases": [{"id": "release"}]}])
    metadata = find(web, SEARCH, DETAIL_NEEDS)
    assert metadata is not None
    assert metadata.cover_data is None
    assert get_requested_hosts(web) == ["musicbrainz.org"]


def test_returns_none_for_another_song():
    karaoke = {"title": "Title (Karaoke Version)", "artist-credit": [{"name": "Artist"}]}
    assert find(make_web([karaoke]), SEARCH, COVER_NEEDS) is None


def test_rejects_a_recording_released_only_by_another_artist():
    release = {"id": "cover-ep", "title": "Undercover", "artist-credit": [{"name": "Tribute Band"}]}
    recording = {**SEARCHED_RECORDING, "releases": [release]}
    assert find(make_web([recording]), SEARCH, COVER_NEEDS) is None


def test_takes_the_album_and_cover_of_the_searched_release():
    releases = [
        {"id": "single", "title": "Title"},
        {"id": "tribute", "title": "Album", "artist-credit": [{"name": "Tribute Band"}]},
        {"id": "album", "title": "Album", "artist-credit": [{"name": "Artist"}]},
    ]
    web = make_web([{**SEARCHED_RECORDING, "releases": releases}])
    metadata = find(web, TrackSearch("Title", "Artist", "Album"), COVER_NEEDS)
    assert metadata is not None
    assert metadata.info.album == "Album"
    assert web.transport.requests[-1].url == "https://coverartarchive.org/release/album/front-500"


def test_leaves_out_the_album_and_cover_of_another_release():
    web = make_web([{**SEARCHED_RECORDING, "releases": [{"id": "single", "title": "Title"}]}])
    metadata = find(web, TrackSearch("Title", "Artist", "Album"), COVER_NEEDS)
    assert metadata is not None
    assert (metadata.info.album, metadata.cover_data) == ("", None)
    assert get_requested_hosts(web) == ["musicbrainz.org"]


def test_takes_a_recording_without_releases_with_no_album():
    metadata = find(make_web([SEARCHED_RECORDING]), SEARCH, COVER_NEEDS)
    assert metadata == TrackMetadata(TrackInfo("Title", "Artist", "", ""), TrackExtras(), None)


def test_returns_none_when_nothing_is_found():
    assert find(make_web([]), SEARCH, COVER_NEEDS) is None


def test_lets_a_failed_search_reach_the_chain():
    services = make_services(FakeTransport(lambda _request: HttpResponse(500, {}, b"")))
    provider = MusicBrainzProvider(MusicBrainzClient("UA", services), services)
    with pytest.raises(ServiceError, match="HTTP 500"):
        provider.find_metadata(SEARCH, DETAIL_NEEDS)
