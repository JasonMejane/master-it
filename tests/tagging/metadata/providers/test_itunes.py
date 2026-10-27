import urllib.parse
from typing import Any

import pytest

from masterit.tagging.metadata.providers.itunes import ItunesProvider
from masterit.tagging.metadata.types import (
    ProviderNeeds,
    TrackExtras,
    TrackInfo,
    TrackMetadata,
    TrackSearch,
)
from masterit.tagging.web.errors import ServiceError
from masterit.tagging.web.transport import HttpRequest, HttpResponse

from ...web.fakes import FakeClock, FakeTransport, FakeWeb, make_json_response
from ..fakes import make_services

COVER_NEEDS = ProviderNeeds(cover=True, details=True)
DETAIL_NEEDS = ProviderNeeds(cover=False, details=True)
RELEASE: dict[str, Any] = {
    "trackName": "Title",
    "collectionName": "Back in Black",
    "releaseDate": "1980-07-25T07:00:00Z",
    "primaryGenreName": "Hard Rock",
    "collectionArtistName": "AC/DC",
    "trackNumber": 6,
    "trackCount": 10,
    "discNumber": 1,
    "discCount": 1,
}
WITH_ARTWORK = {**RELEASE, "artworkUrl100": "https://artwork.test/cover.jpg"}


def make_web(track: dict[str, Any] | None) -> FakeWeb:
    return FakeWeb("itunes.apple.com", {"/search": {"results": [] if track is None else [track]}})


def find(
    web: FakeWeb,
    search: TrackSearch,
    needs: ProviderNeeds = DETAIL_NEEDS,
    clock: FakeClock | None = None,
) -> TrackMetadata | None:
    return ItunesProvider(make_services(web.transport, clock)).find_metadata(search, needs)


def find_extras(
    album: str, track: dict[str, Any] = RELEASE, artist: str = ""
) -> TrackExtras | None:
    metadata = find(make_web(track), TrackSearch("Title", artist, album))
    return None if metadata is None else metadata.extras


def get_hosts(web: FakeWeb) -> list[str]:
    return [urllib.parse.urlsplit(request.url).netloc for request in web.transport.requests]


def test_searches_songs_by_artist_title_and_album():
    web = make_web(None)
    find(web, TrackSearch("Title", "AC/DC", "Back in Black"))
    query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(web.transport.requests[0].url).query))
    assert query == {
        "term": "AC/DC Title Back in Black",
        "country": "US",
        "entity": "song",
        "limit": "1",
    }


def test_takes_info_and_release_extras_when_the_album_matches():
    metadata = find(make_web(RELEASE), TrackSearch("Title", "", " back in black "))
    assert metadata == TrackMetadata(
        TrackInfo("Title", "", "Back in Black", "1980"),
        TrackExtras("Hard Rock", "AC/DC", 6, 10, 1, 1),
    )


def test_takes_release_extras_when_no_album_is_known():
    extras = find_extras("")
    assert extras is not None
    assert extras.track_number == 6


def test_keeps_only_the_genre_from_a_release_by_another_artist():
    tribute = {**RELEASE, "artistName": "AC/DC", "collectionArtistName": "Tribute Band"}
    assert find_extras("", tribute, "AC/DC") == TrackExtras(genre="Hard Rock")


def test_leaves_out_the_album_of_another_release():
    metadata = find(
        make_web({**RELEASE, "artistName": "AC/DC"}), TrackSearch("Title", "AC/DC", "Greatest Hits")
    )
    assert metadata is not None
    assert metadata.info.album == ""


def test_keeps_only_the_genre_when_the_album_differs():
    assert find_extras("Greatest Hits") == TrackExtras(genre="Hard Rock")


def test_leaves_out_extras_itunes_does_not_provide():
    assert find_extras("", {"trackName": "Title"}) == TrackExtras()


@pytest.mark.parametrize(
    ("track", "artist"),
    [
        ({**RELEASE, "trackName": "Other song"}, ""),
        ({**RELEASE, "artistName": "Karaoke Band"}, "AC/DC"),
        ({**RELEASE, "trackName": "Title (Karaoke Version)"}, ""),
        ({**RELEASE, "trackName": "Title (Live)", "artistName": "AC/DC"}, "AC/DC"),
    ],
)
def test_ignores_other_songs_and_versions(track: dict[str, Any], artist: str):
    assert find_extras("", track, artist) is None


def test_matches_names_loosely():
    remaster = {**RELEASE, "trackName": "TITLE (Remastered 2009)", "artistName": "AC-DC"}
    featured = {**RELEASE, "trackName": "Title [feat. Jay-Z]", "artistName": "Beyoncé"}
    assert find_extras("", remaster, "ac/dc") is not None
    assert find_extras("", featured, "Beyonce") is not None


def test_returns_none_without_results():
    assert find(make_web(None), TrackSearch("Title")) is None


def test_downloads_the_artwork_of_the_searched_song_and_release():
    metadata = find(make_web(WITH_ARTWORK), TrackSearch("Title", "", "Back in Black"), COVER_NEEDS)
    assert metadata is not None
    assert metadata.cover_data == b"image /cover.jpg"


def test_skips_the_artwork_when_no_cover_is_needed_or_from_another_release():
    for album, needs in (("", DETAIL_NEEDS), ("Greatest Hits", COVER_NEEDS)):
        web = make_web(WITH_ARTWORK)
        metadata = find(web, TrackSearch("Title", "", album), needs)
        assert metadata is not None
        assert metadata.cover_data is None
        assert get_hosts(web) == ["itunes.apple.com"]


def test_downloads_no_artwork_for_a_different_song():
    web = make_web({**WITH_ARTWORK, "trackName": "Title (Karaoke)"})
    assert find(web, TrackSearch("Title"), COVER_NEEDS) is None
    assert get_hosts(web) == ["itunes.apple.com"]


def test_spaces_searches_four_seconds_apart():
    clock = FakeClock()
    web = make_web(None)
    provider = ItunesProvider(make_services(web.transport, clock))
    provider.find_metadata(TrackSearch("title", "artist"), COVER_NEEDS)
    provider.find_metadata(TrackSearch("title", "artist"), COVER_NEEDS)
    assert clock.sleeps == [4.0]


def test_lets_a_failed_search_reach_the_chain():
    services = make_services(FakeTransport(lambda _request: HttpResponse(500, {}, b"")))
    with pytest.raises(ServiceError, match="iTunes Search request failed: HTTP 500"):
        ItunesProvider(services).find_metadata(TrackSearch("Title"), DETAIL_NEEDS)


def test_keeps_the_metadata_when_the_artwork_download_fails():
    def answer(request: HttpRequest) -> HttpResponse:
        if "itunes.apple.com" in request.url:
            return make_json_response({"results": [WITH_ARTWORK]})
        return HttpResponse(404, {}, b"")

    provider = ItunesProvider(make_services(FakeTransport(answer)))
    metadata = provider.find_metadata(TrackSearch("Title", "", "Back in Black"), COVER_NEEDS)
    assert metadata is not None
    assert (metadata.info.title, metadata.cover_data) == ("Title", None)
