import pytest

from masterit.tagging.metadata.providers.deezer_client import (
    DeezerClient,
    build_query,
    get_cover_requests,
)
from masterit.tagging.web.errors import ServiceError
from masterit.tagging.web.images import ImageRequest
from masterit.tagging.web.transport import HttpResponse

from ...web.fakes import FakeClock, FakeTransport
from ..fakes import make_services
from .deezer_fakes import make_deezer_client, make_deezer_web


def test_searches_tracks_and_albums_with_a_free_text_query():
    web = make_deezer_web(
        {"/search": {"data": [{"id": 1}]}, "/search/album": {"data": [{"id": 2}]}}
    )
    client = make_deezer_client(web)
    assert client.search_tracks("Daft Punk One") == [{"id": 1}]
    assert client.search_albums("Daft Punk Disco") == [{"id": 2}]
    assert web.requested == [
        "/search?q=Daft+Punk+One&limit=5",
        "/search/album?q=Daft+Punk+Disco&limit=5",
    ]


def test_returns_no_results_when_the_list_is_missing_or_odd():
    web = make_deezer_web({"/search": {}, "/search/album": {"data": [{"id": 1}, "noise"]}})
    client = make_deezer_client(web)
    assert client.search_tracks("Title") == []
    assert client.search_albums("Title") == [{"id": 1}, {}]


def test_loads_each_album_its_tracks_artist_searches_and_albums_once_per_batch():
    web = make_deezer_web(
        {
            "/album/7": {"id": 7, "title": "Album"},
            "/album/7/tracks": {"data": [{"id": 1, "track_position": 3}]},
            "/search/artist": {"data": [{"id": 4, "name": "Band"}]},
            "/artist/4/albums": {"data": [{"id": 7}]},
        }
    )
    client = make_deezer_client(web)
    for _ in range(2):
        assert client.get_album(7) == {"id": 7, "title": "Album"}
        assert client.get_album_tracks(7) == [{"id": 1, "track_position": 3}]
        assert client.search_artists("Band") == [{"id": 4, "name": "Band"}]
        assert client.get_artist_albums(4) == [{"id": 7}]
    assert web.requested == [
        "/album/7",
        "/album/7/tracks?limit=1000",
        "/search/artist?q=Band&limit=5",
        "/artist/4/albums?limit=200",
    ]


@pytest.mark.parametrize(
    ("error", "message"),
    [
        ({"type": "DataException", "message": "no data"}, "Deezer error: no data"),
        ({}, "Deezer error: unknown"),
        ("quota", "Deezer error: unknown"),
        ([], "Deezer error: unknown"),
    ],
)
def test_turns_error_payloads_into_failures(error: object, message: str):
    client = make_deezer_client(make_deezer_web({"/album/0": {"error": error}}))
    with pytest.raises(ServiceError, match=message):
        client.get_album(0)


@pytest.mark.parametrize("error", [None, False, 0, ""])
def test_ignores_empty_error_values(error: object):
    client = make_deezer_client(make_deezer_web({"/album/0": {"id": 0, "error": error}}))
    assert client.get_album(0)["id"] == 0


def test_reports_http_failures():
    transport = FakeTransport(lambda _request: HttpResponse(503, {}, b""))
    with pytest.raises(ServiceError, match="Deezer request failed: HTTP 503"):
        DeezerClient(make_services(transport)).search_tracks("Title")


def test_spaces_requests_half_a_second_apart():
    clock = FakeClock()
    client = make_deezer_client(make_deezer_web({}), clock)
    client.search_tracks("first")
    client.search_albums("second")
    assert clock.sleeps == [0.5]


def test_cover_requests_prefer_the_largest_cover_and_skip_missing_sizes():
    both = {"cover_xl": "https://xl", "cover_big": "https://big"}
    assert get_cover_requests(both) == [ImageRequest("https://xl"), ImageRequest("https://big")]
    assert get_cover_requests({"cover_big": "https://big"}) == [ImageRequest("https://big")]
    assert get_cover_requests({}) == []
    odd_xl = {"cover_xl": 5, "cover_big": "https://big"}
    assert get_cover_requests(odd_xl) == [ImageRequest("https://big")]


def test_query_joins_the_known_search_terms():
    assert build_query(["", "Title"]) == "Title"
    assert build_query(["Artist", "Title"]) == "Artist Title"


def test_searches_with_half_an_emoji():
    web = make_deezer_web({})
    make_deezer_client(web).search_tracks("Song \ud83d")
    assert web.requested == ["/search?q=Song+%EF%BF%BD&limit=5"]
