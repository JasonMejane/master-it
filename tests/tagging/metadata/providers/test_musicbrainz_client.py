import itertools
import urllib.parse
from collections.abc import Callable

import pytest

from masterit.tagging.metadata.providers.musicbrainz_client import (
    MusicBrainzClient,
    get_musicbrainz_artist,
)
from masterit.tagging.metadata.types import AlbumSearch, TrackSearch
from masterit.tagging.web.errors import ServiceError, ServiceTimeoutError
from masterit.tagging.web.images import ImageRequest
from masterit.tagging.web.transport import HttpRequest, HttpResponse

from ...web.fakes import FakeClock, FakeTransport, make_json_response
from ..fakes import make_services

USER_AGENT = "MasterIt/1.0 (test@example.com)"
SEARCH = TrackSearch("Title", "Artist", "Album")

type Step = Callable[[], HttpResponse]


def answer_recordings() -> HttpResponse:
    return make_json_response({"recordings": [{"title": "Retried title"}]})


def make_unavailable(retry_after: str | None = None) -> Step:
    headers = {} if retry_after is None else {"retry-after": retry_after}
    return lambda: HttpResponse(503, headers, b"busy")


def time_out() -> HttpResponse:
    raise ServiceTimeoutError()


class ScriptedService:
    def __init__(self, steps: list[Step], clock: FakeClock | None = None) -> None:
        self.steps = steps
        self.clock = clock or FakeClock()
        self.started_at: list[float] = []
        self.transport = FakeTransport(self._answer)
        self.client = MusicBrainzClient(USER_AGENT, make_services(self.transport, self.clock))

    def _answer(self, _request: HttpRequest) -> HttpResponse:
        self.started_at.append(self.clock.now())
        return self.steps[len(self.started_at) - 1]()

    def get_query(self, index: int) -> dict[str, str]:
        url = urllib.parse.urlsplit(self.transport.requests[index].url)
        return dict(urllib.parse.parse_qsl(url.query))

    def get_path(self, index: int) -> str:
        return urllib.parse.urlsplit(self.transport.requests[index].url).path


def test_searches_recordings_by_title_artist_and_album():
    service = ScriptedService([answer_recordings])
    assert service.client.search_recordings(SEARCH) == [{"title": "Retried title"}]
    assert service.get_path(0) == "/ws/2/recording"
    assert service.get_query(0) == {
        "query": 'recording:"Title" AND artist:"Artist" AND release:"Album"',
        "fmt": "json",
        "limit": "1",
    }
    assert service.transport.requests[0].headers == {"User-Agent": USER_AGENT}


def test_leaves_unknown_artist_and_album_out_of_the_search():
    service = ScriptedService([answer_recordings])
    service.client.search_recordings(TrackSearch("Title"))
    assert service.get_query(0)["query"] == 'recording:"Title"'


def test_escapes_backslashes_and_quotes_in_search_terms():
    service = ScriptedService([answer_recordings])
    service.client.search_recordings(TrackSearch('a\\b"c\\'))
    assert service.get_query(0)["query"] == r'recording:"a\\b\"c\\"'


def test_returns_no_recordings_when_the_list_is_missing():
    service = ScriptedService([lambda: make_json_response({})])
    assert service.client.search_recordings(SEARCH) == []


def test_retries_once_after_the_retry_after_delay():
    service = ScriptedService([make_unavailable("5"), answer_recordings])
    assert service.client.search_recordings(SEARCH)[0]["title"] == "Retried title"
    assert len(service.started_at) == 2
    assert service.clock.sleeps == [5.0]


def test_waits_three_seconds_without_a_retry_after_header():
    service = ScriptedService([make_unavailable(), answer_recordings])
    service.client.search_recordings(SEARCH)
    assert service.clock.sleeps == [3.0, pytest.approx(0.5)]


def test_rate_limits_the_retry():
    service = ScriptedService([make_unavailable("0"), answer_recordings])
    service.client.search_recordings(SEARCH)
    assert service.clock.sleeps == [3.5]


def test_starts_requests_at_least_three_and_a_half_seconds_apart():
    empty: Step = lambda: make_json_response({})  # noqa: E731
    service = ScriptedService([empty, time_out, empty, empty])
    service.client.search_recordings(SEARCH)
    service.client.search_recordings(TrackSearch("Other", "Artist", "Album"))
    service.client.search_release_groups(AlbumSearch("Artist", "Album"))
    gaps = [later - earlier for earlier, later in itertools.pairwise(service.started_at)]
    assert len(service.started_at) == 4
    assert all(gap >= 3.5 for gap in gaps)


def test_gives_up_after_a_second_unavailable_response():
    service = ScriptedService([make_unavailable("0"), make_unavailable("0"), answer_recordings])
    with pytest.raises(ServiceError, match="MusicBrainz request failed: HTTP 503"):
        service.client.search_recordings(SEARCH)
    assert len(service.started_at) == 2


def test_does_not_retry_other_http_errors():
    service = ScriptedService([lambda: HttpResponse(500, {}, b""), answer_recordings])
    with pytest.raises(ServiceError):
        service.client.search_recordings(SEARCH)
    assert len(service.started_at) == 1


def test_retries_once_after_a_timeout():
    service = ScriptedService([time_out, answer_recordings])
    assert service.client.search_recordings(SEARCH)[0]["title"] == "Retried title"
    assert len(service.started_at) == 2


def test_gives_up_after_a_second_timeout():
    service = ScriptedService([time_out, time_out])
    with pytest.raises(ServiceTimeoutError):
        service.client.search_recordings(SEARCH)
    assert len(service.started_at) == 2


def test_loads_each_release_once_per_batch():
    release = {"id": "release-id", "title": "The Wall"}
    service = ScriptedService([lambda: make_json_response(release)])
    service.client.get_release("release-id")
    assert service.client.get_release("release-id") == release
    assert len(service.started_at) == 1
    assert service.get_path(0) == "/ws/2/release/release-id"
    assert service.get_query(0) == {
        "inc": "recordings release-groups artist-credits",
        "fmt": "json",
    }


def test_searches_each_recording_once_per_batch():
    service = ScriptedService([answer_recordings, answer_recordings])
    service.client.search_recordings(SEARCH)
    assert service.client.search_recordings(TrackSearch("Title", "Artist", "Album"))
    service.client.search_recordings(TrackSearch("Other", "Artist", "Album"))
    assert len(service.started_at) == 2


def test_searches_release_groups_by_album_and_artist():
    groups = make_json_response({"release-groups": [{"title": "Discovery"}]})
    service = ScriptedService([lambda: groups, lambda: make_json_response({})])
    album_search = AlbumSearch("Daft Punk", 'Dis"covery')
    assert service.client.search_release_groups(album_search) == [{"title": "Discovery"}]
    assert service.client.search_release_groups(album_search) == []
    assert service.get_path(0) == "/ws/2/release-group"
    assert service.get_query(0) == {
        "query": 'releasegroup:"Dis\\"covery" AND artist:"Daft Punk"',
        "fmt": "json",
        "limit": "5",
    }


def test_builds_cover_art_archive_requests_with_its_user_agent():
    client = ScriptedService([]).client
    assert client.get_cover_request("release id") == ImageRequest(
        "https://coverartarchive.org/release/release%20id/front-500", {"User-Agent": USER_AGENT}
    )
    assert client.get_cover_request("id", "123").url.endswith("/id/123-500")
    assert client.get_release_group_cover_request("group id", 1200) == ImageRequest(
        "https://coverartarchive.org/release-group/group%20id/front-1200",
        {"User-Agent": USER_AGENT},
    )


def test_joins_the_credited_names():
    credits = [
        {"name": "Daft Punk", "joinphrase": " feat. "},
        {"artist": {"name": "Pharrell Williams"}},
    ]
    assert get_musicbrainz_artist(credits) == "Daft Punk feat. Pharrell Williams"
    assert get_musicbrainz_artist([{}]) == ""
    assert get_musicbrainz_artist([]) == ""


def test_searches_and_loads_releases_with_half_an_emoji():
    service = ScriptedService([answer_recordings, lambda: make_json_response({})])
    service.client.search_recordings(TrackSearch("Song \ud83d"))
    service.client.get_release("id\ud83d")
    assert service.get_query(0)["query"] == 'recording:"Song \ufffd"'
    assert service.get_path(1) == "/ws/2/release/id%EF%BF%BD"
