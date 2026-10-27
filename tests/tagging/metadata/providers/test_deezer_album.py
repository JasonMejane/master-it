from typing import Any

import pytest

from masterit.tagging.metadata.providers.deezer_album import DeezerAlbumSource
from masterit.tagging.metadata.providers.deezer_client import DeezerClient
from masterit.tagging.metadata.types import AlbumSearch, AlbumTrackEntry, FoundAlbum
from masterit.tagging.web.images import ImageRequest
from masterit.tagging.web.transport import HttpRequest, HttpResponse

from ...web.fakes import FakeTransport, FakeWeb, make_json_response
from ..fakes import make_services
from .deezer_fakes import DEEZER_COVER_XL, make_deezer_services, make_deezer_web

SEARCH = AlbumSearch("Daft Punk", "discovery")
ACOUSTICA = AlbumSearch("Scorpions", "Acoustica")
DISCOVERY_RESULT = {"data": [{"id": 7, "title": "Discovery", "artist": {"name": "Daft Punk"}}]}


def make_source(web: FakeWeb) -> DeezerAlbumSource:
    services = make_deezer_services(web)
    return DeezerAlbumSource(DeezerClient(services))


def find_album(
    responses: dict[str, Any], search: AlbumSearch = SEARCH
) -> tuple[FoundAlbum | None, FakeWeb]:
    web = make_deezer_web(responses)
    return make_source(web).find_album(search), web


def test_gives_the_searched_album_as_deezer_spells_it():
    albums = [
        {"title": "Discovery", "artist": {"name": "Data Punk"}},
        {"title": "Discovery", "artist": {"name": "Daft Punk"}, "cover_xl": DEEZER_COVER_XL},
    ]
    found, web = find_album({"/search/album": {"data": albums}})
    assert found == FoundAlbum("Discovery", "Daft Punk", covers=[ImageRequest(DEEZER_COVER_XL)])
    assert web.requested == ["/search/album?q=Daft+Punk+discovery&limit=5"]


def test_finds_nothing_without_the_same_album():
    albums = [
        {"title": "Discovery (Deluxe)", "artist": {"name": "Daft Punk"}},
        {"artist": {"name": "Daft Punk"}},
    ]
    found, _web = find_album({"/search/album": {"data": albums}})
    assert found is None


def test_looks_through_the_artist_albums_when_the_album_search_misses():
    found, web = find_album(
        {
            "/search/artist": {
                "data": [{"id": 1, "name": "Scorpions Tribute"}, {"id": 7, "name": "Scorpions"}]
            },
            "/artist/7/albums": {
                "data": [
                    {"title": "MTV Unplugged"},
                    {"title": "Acoustica", "cover_xl": DEEZER_COVER_XL},
                ]
            },
        },
        ACOUSTICA,
    )
    assert found == FoundAlbum("Acoustica", "Scorpions", covers=[ImageRequest(DEEZER_COVER_XL)])
    assert web.requested == [
        "/search/album?q=Scorpions+Acoustica&limit=5",
        "/search/artist?q=Scorpions&limit=5",
        "/artist/7/albums?limit=200",
    ]


def test_finds_nothing_when_deezer_has_neither_the_artist_nor_the_album():
    found, web = find_album(
        {"/search/artist": {"data": [{"id": 1, "name": "Scorpions Tribute"}]}}, ACOUSTICA
    )
    assert found is None
    assert len(web.requested) == 2
    responses = {
        "/search/artist": {"data": [{"id": 7, "name": "Scorpions"}]},
        "/artist/7/albums": {"data": [{"title": "MTV Unplugged"}]},
    }
    assert find_album(responses, ACOUSTICA)[0] is None


def test_prefers_the_artist_named_exactly_over_a_collaboration():
    found, web = find_album(
        {
            "/search/artist": {
                "data": [{"id": 1, "name": "Scorpions & Friends"}, {"id": 7, "name": "Scorpions"}]
            },
            "/artist/7/albums": {"data": [{"title": "Acoustica"}]},
        },
        ACOUSTICA,
    )
    assert found is not None
    assert "/artist/7/albums?limit=200" in web.requested


def test_falls_back_to_an_artist_sharing_the_credit():
    responses = {
        "/search/artist": {"data": [{"id": 3, "name": "Scorpions & Friends"}]},
        "/artist/3/albums": {"data": [{"title": "Acoustica"}]},
    }
    found, _web = find_album(responses, ACOUSTICA)
    assert found is not None
    assert found.album == "Acoustica"


def test_does_not_list_the_albums_of_various_artists():
    found, web = find_album({}, AlbumSearch("Various Artists", "Hits 90"))
    assert found is None
    assert web.requested == ["/search/album?q=Various+Artists+Hits+90&limit=5"]


def test_searches_each_artist_and_lists_its_albums_once_per_batch():
    web = make_deezer_web(
        {
            "/search/artist": {"data": [{"name": "Scorpions"}, {"id": 7, "name": "Scorpions"}]},
            "/artist/7/albums": {"data": [{"title": "Acoustica"}]},
        }
    )
    source = make_source(web)
    source.find_album(ACOUSTICA)
    source.find_album(AlbumSearch("Scorpions", "Crazy World"))
    assert len([path for path in web.requested if not path.startswith("/search/album")]) == 2


def test_gives_the_genre_year_and_tracklist():
    found, web = find_album(
        {
            "/search/album": {
                "data": [{**DISCOVERY_RESULT["data"][0], "cover_xl": DEEZER_COVER_XL}]
            },
            "/album/7": {"genres": {"data": [{"name": "Electro"}]}, "release_date": "2001-03-12"},
            "/album/7/tracks": {
                "data": [
                    {"title": "One More Time", "track_position": 1, "disk_number": 1},
                    {"title": "Aerodynamic", "track_position": 2, "disk_number": 1},
                    {"title": "Unplaced"},
                ]
            },
        }
    )
    assert found == FoundAlbum(
        "Discovery",
        "Daft Punk",
        "2001",
        "Electro",
        [ImageRequest(DEEZER_COVER_XL)],
        [AlbumTrackEntry("One More Time", 1, 2, 1, 1), AlbumTrackEntry("Aerodynamic", 2, 2, 1, 1)],
    )
    assert len(web.requested) == 3


def test_keeps_the_album_when_its_details_cannot_be_read():
    found, _web = find_album(
        {"/search/album": DISCOVERY_RESULT, "/album/7": {"error": {"message": "quota"}}}
    )
    assert found == FoundAlbum("Discovery", "Daft Punk")


def test_reads_no_year_from_an_unknown_date_and_keeps_track_artists():
    found, _web = find_album(
        {
            "/search/album": DISCOVERY_RESULT,
            "/album/7": {"release_date": "0000-00-00"},
            "/album/7/tracks": {
                "data": [
                    {
                        "title": "Digital Love",
                        "artist": {"name": " Daft Punk "},
                        "track_position": 3,
                        "disk_number": 0,
                    }
                ]
            },
        }
    )
    assert found is not None
    assert found.year == ""
    assert found.tracks == [AlbumTrackEntry("Digital Love", 3, 1, 0, 0, "Daft Punk")]


def test_lets_bugs_in_album_details_through():
    def answer(request: HttpRequest) -> HttpResponse:
        if "/album/7" in request.url:
            raise TypeError("bug")
        return make_json_response(DISCOVERY_RESULT)

    services = make_services(FakeTransport(answer))
    with pytest.raises(TypeError, match="bug"):
        DeezerAlbumSource(DeezerClient(services)).find_album(SEARCH)
