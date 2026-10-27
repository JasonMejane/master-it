import urllib.parse
from collections.abc import Callable
from typing import Any

import pytest

from masterit.tagging.metadata.providers.lastfm import LastFmProvider, remove_artist_prefix
from masterit.tagging.metadata.types import ProviderNeeds, TrackInfo, TrackMetadata, TrackSearch
from masterit.tagging.web.errors import ServiceError
from masterit.tagging.web.transport import HttpRequest, HttpResponse

from ...web.fakes import FakeClock, FakeTransport, make_image_response, make_json_response
from ..fakes import make_services

SEARCH = TrackSearch("Title", "Artist", "")
COVER_NEEDS = ProviderNeeds(cover=True, details=True)
DETAIL_NEEDS = ProviderNeeds(cover=False, details=True)

type Answer = Callable[[], HttpResponse]


def answer_search(track: Any) -> Answer:
    return lambda: make_json_response({"results": {"trackmatches": {"track": track}}})


def answer_info(track: Any) -> Answer:
    return lambda: make_json_response({"track": track} if track is not None else {})


def serve_cover(_request: HttpRequest) -> HttpResponse:
    return make_image_response(b"cover")


class FakeLastFm:
    def __init__(
        self,
        search: Answer,
        info: Answer,
        clock: FakeClock | None = None,
        cover: Callable[[HttpRequest], HttpResponse] = serve_cover,
    ) -> None:
        self.answers = {"track.search": search, "track.getInfo": info}
        self.cover = cover
        self.clock = clock or FakeClock()
        self.transport = FakeTransport(self._respond)
        self.provider = LastFmProvider("key", make_services(self.transport, self.clock))

    def _respond(self, request: HttpRequest) -> HttpResponse:
        url = urllib.parse.urlsplit(request.url)
        if url.hostname != "ws.audioscrobbler.com":
            return self.cover(request)
        return self.answers[self.get_params(request)["method"]]()

    @staticmethod
    def get_params(request: HttpRequest) -> dict[str, str]:
        return dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(request.url).query))

    @property
    def methods(self) -> list[str]:
        return [
            self.get_params(request).get("method", "image") for request in self.transport.requests
        ]

    def find(
        self, search: TrackSearch = SEARCH, needs: ProviderNeeds = DETAIL_NEEDS
    ) -> TrackMetadata | None:
        return self.provider.find_metadata(search, needs)


COVER_ALBUM = {"title": "Album", "image": [{"size": "large", "#text": "https://images.test/a.jpg"}]}


def test_skips_the_cover_download_when_no_cover_is_needed():
    lastfm = FakeLastFm(answer_search({"name": "Title"}), answer_info({"album": COVER_ALBUM}))
    metadata = lastfm.find()
    assert metadata is not None
    assert (metadata.info.album, metadata.cover_data) == ("Album", None)
    assert "image" not in lastfm.methods


def test_spaces_api_requests_but_not_the_cover_download():
    lastfm = FakeLastFm(answer_search({"name": "Title"}), answer_info({"album": COVER_ALBUM}))
    metadata = lastfm.find(TrackSearch("Title"), COVER_NEEDS)
    assert metadata is not None
    assert metadata.cover_data == b"cover"
    assert lastfm.methods == ["track.search", "track.getInfo", "image"]
    assert lastfm.clock.sleeps == [2.0]


def test_caps_large_covers_and_skips_the_default_image():
    album = {
        "title": "Album",
        "image": [
            {"size": "small", "#text": "https://images.test/small.jpg"},
            {"size": "large", "#text": "https://images.test/2a96cbd8b46e442fc41c2b86b821562f.png"},
            {"size": "medium", "#text": "https://images.test/medium.jpg"},
        ],
    }
    lastfm = FakeLastFm(answer_search({"name": "Title"}), answer_info({"album": album}))
    lastfm.find(TrackSearch("Title"), COVER_NEEDS)
    covers = lastfm.transport.requests[2:]
    assert [request.url for request in covers] == ["https://images.test/medium.jpg"]
    big = FakeLastFm(answer_search({"name": "Title"}), answer_info({"album": COVER_ALBUM}))
    big.find(TrackSearch("Title"), COVER_NEEDS)
    assert big.transport.requests[2].byte_limit == 500 * 1024


def test_returns_none_when_nothing_matches():
    lastfm = FakeLastFm(answer_search([]), answer_info(None))
    assert lastfm.find(TrackSearch("Title"), COVER_NEEDS) is None


def test_reads_the_first_match_from_a_result_list_with_a_plain_artist():
    matches = [
        {"name": "Plain Artist: Song", "artist": "Plain Artist"},
        {"name": "Other", "artist": "X"},
    ]
    lastfm = FakeLastFm(
        answer_search(matches), answer_info({"album": {"title": "Album", "year": "1999"}})
    )
    metadata = lastfm.find(TrackSearch("Song"))
    assert metadata is not None
    assert metadata.info == TrackInfo("Song", "Plain Artist", "Album", "1999")
    search_params, info_params = (
        lastfm.get_params(request) for request in lastfm.transport.requests
    )
    assert search_params == {
        "method": "track.search",
        "track": "Song",
        "api_key": "key",
        "format": "json",
        "limit": "1",
    }
    assert (info_params["track"], info_params["artist"], info_params["autocorrect"]) == (
        "Song",
        "Plain Artist",
        "1",
    )


def test_takes_the_year_from_the_album_date():
    album = {"title": "Album", "date": "18 October 2004, 00:00"}
    lastfm = FakeLastFm(answer_search({"name": "Title"}), answer_info({"album": album}))
    metadata = lastfm.find(TrackSearch("Title"))
    assert metadata is not None
    assert metadata.info.year == "2004"


@pytest.mark.parametrize(
    ("found", "title"),
    [("Abbaesque", "Abbaesque"), ("ABBA - Waterloo", "Waterloo"), ("Abba: Waterloo", "Waterloo")],
)
def test_removes_only_a_repeated_artist_prefix(found: str, title: str):
    lastfm = FakeLastFm(answer_search({"name": found, "artist": "Abba"}), answer_info(None))
    metadata = lastfm.find(TrackSearch(title, "Abba"))
    assert metadata is not None
    assert metadata.info.title == title


def test_throws_a_failed_search():
    lastfm = FakeLastFm(lambda: HttpResponse(500, {}, b""), lambda: HttpResponse(500, {}, b""))
    with pytest.raises(ServiceError, match=r"Last\.fm request failed: HTTP 500"):
        lastfm.find(SEARCH, COVER_NEEDS)
    assert lastfm.methods == ["track.getInfo", "track.search"]


def make_info_lastfm(track: Any) -> FakeLastFm:
    return FakeLastFm(answer_search({"name": "Title", "artist": "The Artist"}), answer_info(track))


def test_asks_track_info_directly_when_the_artist_is_known():
    lastfm = make_info_lastfm(
        {
            "name": "Title (Remastered)",
            "artist": {"name": "The Artist"},
            "album": {"title": "Album", "year": "2001"},
        }
    )
    metadata = lastfm.find()
    assert metadata is not None
    assert metadata.info == TrackInfo("Title (Remastered)", "The Artist", "Album", "2001")
    assert lastfm.methods == ["track.getInfo"]
    params = lastfm.get_params(lastfm.transport.requests[0])
    assert (params["artist"], params["track"]) == ("Artist", "Title")


@pytest.mark.parametrize(
    "track",
    [
        {"album": {"title": "Album"}},
        {"name": "Title", "artist": {"name": "Artist"}},
        {"name": "Other Song", "artist": {"name": "Artist"}, "album": {"title": "Other Album"}},
    ],
)
def test_falls_back_to_track_search_when_the_direct_hit_does_not_do(track: dict[str, Any]):
    lastfm = make_info_lastfm(track)
    metadata = lastfm.find()
    assert metadata is not None
    assert metadata.info.title == "Title"
    assert lastfm.methods == ["track.getInfo", "track.search", "track.getInfo"]


def test_strips_a_repeated_artist_from_the_title_it_asks_directly():
    lastfm = make_info_lastfm({"name": "Title", "album": {"title": "Album"}})
    lastfm.find(TrackSearch("Artist - Title", "Artist"))
    assert lastfm.get_params(lastfm.transport.requests[0])["track"] == "Title"


def test_does_not_ask_track_info_twice_for_the_same_track():
    lastfm = FakeLastFm(
        answer_search({"name": "Title", "artist": "Artist"}), answer_info({"name": "Title"})
    )
    metadata = lastfm.find()
    assert metadata is not None
    assert metadata.info.title == "Title"
    assert lastfm.methods == ["track.getInfo", "track.search"]


def test_falls_back_spaced_when_the_direct_lookup_fails():
    calls: list[str] = []

    def answer_info_once_failed() -> HttpResponse:
        calls.append("info")
        if len(calls) == 1:
            return HttpResponse(500, {}, b"")
        return make_json_response({"track": {"album": {"title": "Album"}}})

    lastfm = FakeLastFm(
        answer_search({"name": "Title", "artist": "The Artist"}), answer_info_once_failed
    )
    metadata = lastfm.find()
    assert metadata is not None
    assert metadata.info.album == "Album"
    assert lastfm.clock.sleeps == [2.0, 2.0]


def test_keeps_the_match_when_the_track_info_fails():
    lastfm = FakeLastFm(
        answer_search({"name": "Title", "artist": "Band"}), lambda: HttpResponse(500, {}, b"")
    )
    metadata = lastfm.find(TrackSearch("Title"))
    assert metadata == TrackMetadata(TrackInfo("Title", "Band", "", ""))


def test_returns_none_without_track_details_when_the_search_finds_another_song():
    lastfm = FakeLastFm(answer_search({"name": "Other Song", "artist": "Band"}), answer_info(None))
    assert lastfm.find(TrackSearch("Title")) is None
    assert lastfm.methods == ["track.search"]


def test_keeps_no_album_from_a_direct_hit_that_is_another_song():
    lastfm = FakeLastFm(
        answer_search({"name": "Title", "artist": "Artist"}),
        answer_info({"name": "Other Song", "album": {"title": "Other"}}),
    )
    metadata = lastfm.find()
    assert metadata is not None
    assert (metadata.info.title, metadata.info.album) == ("Title", "")
    assert len(lastfm.transport.requests) == 2


@pytest.mark.parametrize("matches", [[None, {"name": "Title"}], {}])
def test_an_empty_first_match_is_no_match(matches: Any):
    lastfm = FakeLastFm(answer_search(matches), answer_info(None))
    assert lastfm.find(TrackSearch("Title")) is None
    assert lastfm.methods == ["track.search"]


def test_drops_the_matched_artist_from_a_search_title_without_artist():
    lastfm = FakeLastFm(answer_search({"name": "Title", "artist": "A"}), answer_info(None))
    metadata = lastfm.find(TrackSearch("A - Title"))
    assert metadata is not None
    assert (metadata.info.title, metadata.info.artist) == ("Title", "A")


def test_keeps_an_empty_album_year_over_its_date():
    album = {"title": "Album", "year": "", "date": "2004"}
    lastfm = FakeLastFm(answer_search({"name": "Title"}), answer_info({"album": album}))
    metadata = lastfm.find(TrackSearch("Title"))
    assert metadata is not None
    assert metadata.info.year == ""


def test_tries_cover_sizes_from_large_to_small_and_caps_only_large():
    sizes = ["small", "large", "medium"]
    images = [{"size": size, "#text": f"https://images.test/{size}.jpg"} for size in sizes]

    def fail_large(request: HttpRequest) -> HttpResponse:
        return HttpResponse(404, {}, b"") if "large" in request.url else serve_cover(request)

    info = answer_info({"album": {"title": "A", "image": images}})
    lastfm = FakeLastFm(answer_search({"name": "Title"}), info, cover=fail_large)
    metadata = lastfm.find(TrackSearch("Title"), COVER_NEEDS)
    assert metadata is not None
    assert metadata.cover_data == b"cover"
    covers = lastfm.transport.requests[2:]
    assert [request.url.rsplit("/", 1)[1] for request in covers] == ["large.jpg", "medium.jpg"]
    assert [request.byte_limit for request in covers] == [500 * 1024, float("inf")]


def test_searches_with_the_known_artist():
    lastfm = FakeLastFm(answer_search({"name": "Title", "artist": "Artist"}), answer_info({}))
    lastfm.find()
    search_request = lastfm.transport.requests[1]
    assert lastfm.get_params(search_request)["artist"] == "Artist"


@pytest.mark.parametrize(
    ("title", "artist", "stripped"),
    [(" - Title", "", " - Title"), ("Abba - Waterloo  ", "Abba", "Waterloo")],
)
def test_strips_artist_prefixes_only_with_an_artist_and_trims_the_rest(
    title: str, artist: str, stripped: str
):
    assert remove_artist_prefix(title, artist) == stripped
