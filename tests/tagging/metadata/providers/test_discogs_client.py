import urllib.parse

import pytest

from masterit.tagging.metadata.providers.discogs_client import DiscogsClient, DiscogsCredentials
from masterit.tagging.metadata.types import TrackSearch
from masterit.tagging.web.errors import ServiceError
from masterit.tagging.web.transport import HttpResponse

from ...web.fakes import FakeTransport
from ..fakes import make_services
from .discogs_fakes import make_discogs_client, make_discogs_web

DIGITAL_LOVE = TrackSearch("Digital Love", "Daft Punk", "Discovery")


def get_query(url: str) -> dict[str, str]:
    return dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))


def test_searches_a_known_album_by_artist_and_album_only_with_its_consumer_key():
    web = make_discogs_web({"/database/search": {"results": [{"id": 3}]}})
    assert make_discogs_client(web).search_albums("master", DIGITAL_LOVE) == [{"id": 3}]
    request = web.transport.requests[0]
    assert get_query(request.url) == {
        "type": "master",
        "artist": "Daft Punk",
        "release_title": "Discovery",
        "per_page": "1",
    }
    assert request.headers == {
        "User-Agent": "MasterIt/1.0",
        "Authorization": "Discogs key=consumer-key, secret=consumer-secret",
    }


def test_leaves_out_an_unknown_album_and_caches_repeated_requests():
    web = make_discogs_web({"/releases/5": {"id": 5, "title": "Discovery"}})
    client = make_discogs_client(web)
    search = TrackSearch("Digital Love", "Daft Punk", "")
    client.search_albums("release", search)
    client.search_albums("release", search)
    client.get_album("release", 5)
    assert client.get_album("release", 5)["title"] == "Discovery"
    assert len(web.requested) == 2
    assert get_query(web.transport.requests[0].url)["track"] == "Digital Love"
    assert "release_title" not in get_query(web.transport.requests[0].url)
    assert web.requested[1] == "/releases/5"


def test_reads_masters_from_their_own_path():
    web = make_discogs_web({"/masters/8": {"id": 8}})
    make_discogs_client(web).get_album("master", 8)
    assert web.requested == ["/masters/8"]


def test_turns_http_errors_into_service_errors():
    services = make_services(FakeTransport(lambda _request: HttpResponse(429, {}, b"")))
    client = DiscogsClient(DiscogsCredentials("key", "secret"), services)
    with pytest.raises(ServiceError, match="HTTP 429"):
        client.get_album("master", 1)


def test_asks_for_covers_with_its_user_agent():
    request = make_discogs_client(make_discogs_web({})).get_cover_request("https://i.test/a.jpg")
    assert (request.url, request.headers) == (
        "https://i.test/a.jpg",
        {"User-Agent": "MasterIt/1.0"},
    )


def test_searches_every_track_of_an_album_once():
    web = make_discogs_web({})
    client = make_discogs_client(web)
    client.search_albums("master", DIGITAL_LOVE)
    client.search_albums("master", TrackSearch("Aerodynamic", "Daft Punk", "Discovery"))
    assert len(web.requested) == 1
