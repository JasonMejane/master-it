import pytest

from masterit.tagging.metadata.providers.deezer_client import DeezerClient
from masterit.tagging.metadata.providers.deezer_cover import DeezerCoverProvider
from masterit.tagging.metadata.types import TrackSearch
from masterit.tagging.web.errors import ServiceError
from masterit.tagging.web.transport import HttpResponse

from ...web.fakes import FakeTransport, FakeWeb
from ..fakes import make_services
from .deezer_fakes import DEEZER_COVER_XL, make_deezer_services, make_deezer_web

SEARCH = TrackSearch("One More Time", "Daft Punk", "Discovery")
LOOKALIKE = {
    "title": "Discovery",
    "artist": {"name": "Data Punk"},
    "cover_xl": "https://cdn.deezer.test/lookalike.jpg",
}
SEARCHED_ALBUM = {
    "title": "Discovery",
    "artist": {"name": "Daft Punk"},
    "cover_xl": DEEZER_COVER_XL,
}


def find_deezer_cover(web: FakeWeb, search: TrackSearch = SEARCH) -> bytes | None:
    services = make_deezer_services(web)
    return DeezerCoverProvider(DeezerClient(services), services).find_cover(search)


def test_downloads_the_cover_of_the_searched_album():
    web = make_deezer_web({"/search/album": {"data": [LOOKALIKE, SEARCHED_ALBUM]}})
    assert find_deezer_cover(web) == b"image /1000x1000.jpg"
    assert web.requested == ["/search/album?q=Daft+Punk+Discovery&limit=5", "/1000x1000.jpg"]


def test_accepts_any_artist_when_none_is_searched():
    web = make_deezer_web({"/search/album": {"data": [LOOKALIKE]}})
    cover = find_deezer_cover(web, TrackSearch("One More Time", "", "Discovery"))
    assert cover == b"image /lookalike.jpg"


def test_skips_the_search_without_an_album():
    web = make_deezer_web({})
    assert find_deezer_cover(web, TrackSearch("One More Time", "Daft Punk", "")) is None
    assert web.requested == []


def test_returns_none_when_no_album_matches():
    web = make_deezer_web({"/search/album": {"data": [LOOKALIKE]}})
    assert find_deezer_cover(web) is None


def test_lets_a_failed_search_reach_the_chain():
    services = make_services(FakeTransport(lambda _request: HttpResponse(500, {}, b"")))
    provider = DeezerCoverProvider(DeezerClient(services), services)
    with pytest.raises(ServiceError, match="HTTP 500"):
        provider.find_cover(SEARCH)
