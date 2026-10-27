import urllib.parse
from typing import Any

import pytest

from masterit.tagging.metadata.providers.listenbrainz_client import (
    ListenBrainzClient,
    ListenBrainzCredentials,
)
from masterit.tagging.metadata.types import TrackSearch
from masterit.tagging.web.errors import ServiceError

from ...web.fakes import FakeClock, FakeTransport, make_json_response
from ..fakes import make_services

USER_AGENT = "MasterIt/1.0 (test@example.com)"
SEARCH = TrackSearch("Title", "Artist", "")


def make_client(payload: Any, status: int = 200, clock: FakeClock | None = None):
    transport = FakeTransport(lambda _request: make_json_response(payload, status))
    credentials = ListenBrainzCredentials("secret", USER_AGENT)
    return ListenBrainzClient(credentials, make_services(transport, clock)), transport


def test_looks_up_a_recording_with_its_metadata():
    client, transport = make_client({"recording_mbid": "id"})
    assert client.look_up(TrackSearch("Title", "Artist", "Album")) == {"recording_mbid": "id"}
    request = transport.requests[0]
    url = urllib.parse.urlsplit(request.url)
    assert url.path == "/1/metadata/lookup/"
    assert dict(urllib.parse.parse_qsl(url.query)) == {
        "artist_name": "Artist",
        "recording_name": "Title",
        "release_name": "Album",
        "metadata": "true",
        "inc": "artist tag release",
    }
    assert request.headers == {"Authorization": "Token secret", "User-Agent": USER_AGENT}


def test_leaves_out_an_unknown_album():
    client, transport = make_client({"recording_mbid": "id"})
    client.look_up(SEARCH)
    assert "release_name" not in transport.requests[0].url


@pytest.mark.parametrize("payload", [{}, {"recording_mbid": ""}, {"recording_mbid": 7}])
def test_returns_none_when_nothing_matches(payload: Any):
    client, _transport = make_client(payload)
    assert client.look_up(SEARCH) is None


def test_reports_http_failures():
    client, _transport = make_client({"error": "Server error"}, 500)
    with pytest.raises(ServiceError, match="ListenBrainz request failed: HTTP 500"):
        client.look_up(SEARCH)


def test_points_at_the_token_when_it_is_rejected():
    client, _transport = make_client({"error": "Invalid authorization token."}, 401)
    with pytest.raises(ServiceError, match="ListenBrainz rejected the token"):
        client.look_up(SEARCH)


def test_spaces_requests_one_second_apart():
    clock = FakeClock()
    client, _transport = make_client({}, clock=clock)
    client.look_up(SEARCH)
    client.look_up(TrackSearch("Other", "Artist"))
    assert clock.sleeps == [1.0]


def test_looks_up_each_search_once_per_batch():
    client, transport = make_client({"recording_mbid": "id"})
    client.look_up(SEARCH)
    assert client.look_up(TrackSearch("Title", "Artist", "")) == {"recording_mbid": "id"}
    client.look_up(TrackSearch("Other", "Artist"))
    assert len(transport.requests) == 2


def test_looks_up_with_half_an_emoji():
    client, transport = make_client({})
    client.look_up(TrackSearch("Song \ud83d", "Artist"))
    assert "recording_name=Song+%EF%BF%BD" in transport.requests[0].url
