import urllib.parse
from typing import Any

import pytest

from masterit.tagging.metadata.providers.youtube import YouTubeCoverProvider
from masterit.tagging.metadata.types import TrackSearch
from masterit.tagging.web.errors import ServiceError
from masterit.tagging.web.transport import HttpRequest, HttpResponse

from ...web.fakes import FakeTransport, FakeWeb, make_json_response
from ..fakes import make_services

SEARCH = TrackSearch("Title", "Artist", "")


def make_web(response: Any) -> FakeWeb:
    return FakeWeb("www.googleapis.com", {"/youtube/v3/search": response})


def find_cover(web: FakeWeb) -> bytes | None:
    return YouTubeCoverProvider("key", make_services(web.transport)).find_cover(SEARCH)


def make_response(thumbnails: dict[str, Any]) -> dict[str, Any]:
    return {"items": [{"snippet": {"thumbnails": thumbnails}}]}


def test_downloads_the_largest_available_thumbnail():
    web = make_web(
        make_response(
            {
                "default": {"url": "https://i.ytimg.test/default.jpg"},
                "high": {"url": "https://i.ytimg.test/high.jpg"},
            }
        )
    )
    assert find_cover(web) == b"image /high.jpg"
    query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(web.transport.requests[0].url).query))
    assert query == {
        "part": "snippet",
        "type": "video",
        "maxResults": "1",
        "q": "Artist Title",
        "key": "key",
    }


@pytest.mark.parametrize(
    ("thumbnails", "expected"),
    [
        (
            {
                "standard": {"url": "https://i.ytimg.test/standard.jpg"},
                "maxres": {"url": "https://i.ytimg.test/maxres.jpg"},
            },
            "https://i.ytimg.test/maxres.jpg",
        ),
        (
            {
                "high": {"url": "https://i.ytimg.test/high.jpg"},
                "standard": {"url": "https://i.ytimg.test/standard.jpg"},
            },
            "https://i.ytimg.test/standard.jpg",
        ),
        (
            {"maxres": {"url": ""}, "high": {"url": "https://i.ytimg.test/high.jpg"}},
            "https://i.ytimg.test/high.jpg",
        ),
    ],
)
def test_prefers_maxres_then_standard_thumbnails(thumbnails: dict[str, Any], expected: str):
    web = make_web(make_response(thumbnails))
    find_cover(web)
    assert web.transport.requests[1].url == expected


NO_THUMBNAILS: list[dict[str, Any]] = [{}, {"items": []}, {"items": [{"snippet": {}}]}]


@pytest.mark.parametrize("response", NO_THUMBNAILS)
def test_returns_none_when_no_video_has_a_thumbnail(response: dict[str, Any]):
    web = make_web(response)
    assert find_cover(web) is None
    assert len(web.transport.requests) == 1


def test_lets_a_failed_search_reach_the_chain():
    services = make_services(FakeTransport(lambda _request: HttpResponse(403, {}, b"")))
    with pytest.raises(ServiceError, match="YouTube Data API request failed: HTTP 403"):
        YouTubeCoverProvider("key", services).find_cover(SEARCH)


def test_lets_a_failed_thumbnail_download_reach_the_chain():
    thumbnails = {"high": {"url": "https://i.ytimg.test/high.jpg"}}

    def answer(request: HttpRequest) -> HttpResponse:
        if "googleapis" in request.url:
            return make_json_response(make_response(thumbnails))
        return HttpResponse(404, {}, b"")

    services = make_services(FakeTransport(answer))
    with pytest.raises(ServiceError, match="HTTP 404"):
        YouTubeCoverProvider("key", services).find_cover(SEARCH)
