import urllib.parse
from typing import Any

from masterit.tagging.metadata.providers.discogs_album import DiscogsAlbumSource
from masterit.tagging.metadata.providers.discogs_client import DiscogsClient, DiscogsCredentials
from masterit.tagging.metadata.types import AlbumSearch, AlbumTrackEntry, FoundAlbum
from masterit.tagging.web.transport import HttpRequest, HttpResponse

from ...web.fakes import FakeTransport, make_json_response
from ..fakes import make_services
from .discogs_fakes import DISCOGS_COVER

SEARCH = AlbumSearch("Daft Punk", "discovery")
DISCOVERY: dict[str, Any] = {
    "title": "Discovery",
    "artists": [{"name": "Daft Punk (2)"}],
    "images": [{"type": "primary", "uri": DISCOGS_COVER}],
}


class FakeDiscogs:
    def __init__(self, results: dict[str, list[dict[str, Any]]], albums: dict[str, Any]) -> None:
        self.results = results
        self.albums = albums
        self.transport = FakeTransport(self._respond)
        services = make_services(self.transport)
        self.source = DiscogsAlbumSource(
            DiscogsClient(DiscogsCredentials("key", "secret"), services)
        )

    def _respond(self, request: HttpRequest) -> HttpResponse:
        url = urllib.parse.urlsplit(request.url)
        if url.path != "/database/search":
            return make_json_response(self.albums.get(url.path, {}))
        kind = dict(urllib.parse.parse_qsl(url.query))["type"]
        return make_json_response({"results": self.results.get(kind, [])})

    @property
    def requested(self) -> list[str]:
        return [urllib.parse.urlsplit(request.url).path for request in self.transport.requests]


def find_master(album: dict[str, Any]) -> FoundAlbum | None:
    return FakeDiscogs({"master": [{"id": 8}]}, {"/masters/8": album}).source.find_album(SEARCH)


def test_gives_the_master_of_the_searched_album_and_its_cover():
    discogs = FakeDiscogs({"master": [{"id": 8}]}, {"/masters/8": DISCOVERY})
    found = discogs.source.find_album(SEARCH)
    assert found is not None
    assert (found.album, [cover.url for cover in found.covers]) == ("Discovery", [DISCOGS_COVER])
    query = dict(
        urllib.parse.parse_qsl(urllib.parse.urlsplit(discogs.transport.requests[0].url).query)
    )
    assert (query["release_title"], query["artist"], "track" in query) == (
        "discovery",
        "Daft Punk",
        False,
    )


def test_falls_back_to_releases_without_a_master():
    discogs = FakeDiscogs({"release": [{"id": 3}]}, {"/releases/3": {**DISCOVERY, "year": 2021}})
    found = discogs.source.find_album(SEARCH)
    assert found is not None
    assert found.year == ""
    assert discogs.requested == ["/database/search", "/database/search", "/releases/3"]


def test_skips_another_album_and_may_have_no_cover():
    homework = {**DISCOVERY, "title": "Homework", "images": None}
    discogs = FakeDiscogs(
        {"master": [{"id": 8}], "release": [{"id": 8}]},
        {"/masters/8": homework, "/releases/8": {**DISCOVERY, "images": []}},
    )
    assert discogs.source.find_album(SEARCH) == FoundAlbum("Discovery", "Daft Punk", tracks=[])
    assert FakeDiscogs({}, {}).source.find_album(SEARCH) is None


def test_gives_the_master_artist_year_genre_and_tracklist():
    tracklist = [
        {"position": "1", "title": "One More Time"},
        {"position": "", "type_": "heading", "title": "Bonus"},
        {"position": "2", "title": "Aerodynamic"},
    ]
    found = find_master(
        {**DISCOVERY, "year": 2001, "genres": ["Electronic"], "tracklist": tracklist}
    )
    assert found is not None
    assert (found.artist, found.year, found.genre) == ("Daft Punk", "2001", "Electronic")
    assert found.tracks == [
        AlbumTrackEntry("One More Time", 1, 2, 1, 1, "Daft Punk"),
        AlbumTrackEntry("Aerodynamic", 2, 2, 1, 1, "Daft Punk"),
    ]


def test_places_an_index_track_as_one_song_with_its_artist():
    tracklist = [
        {"position": "1", "title": "Intro", "artists": [{"name": "Guest"}]},
        {
            "position": "2",
            "type_": "index",
            "title": "Suite",
            "sub_tracks": [{"position": "2a"}, {"position": "2b"}],
        },
    ]
    found = find_master({**DISCOVERY, "tracklist": tracklist})
    assert found is not None
    assert [(entry.title, entry.artist, entry.track_number) for entry in found.tracks or []] == [
        ("Intro", "Guest", 1),
        ("Suite", "Daft Punk", 2),
    ]


def test_gives_no_tracklist_when_a_song_has_no_place():
    found = find_master(
        {
            **DISCOVERY,
            "tracklist": [{"position": "1", "title": "One"}, {"position": "B1", "title": "Two"}],
        }
    )
    assert found is not None
    assert found.tracks == []


def test_skips_songs_of_an_unknown_type():
    tracklist = [
        {"position": "1", "title": "One"},
        {"position": "B1", "type_": None, "title": "Two"},
    ]
    found = find_master({**DISCOVERY, "tracklist": tracklist})
    assert found is not None
    assert [entry.title for entry in found.tracks or []] == ["One"]
