from typing import Any

import pytest

from masterit.tagging.metadata.providers.musicbrainz_album import MusicBrainzAlbumSource
from masterit.tagging.metadata.providers.musicbrainz_client import MusicBrainzClient
from masterit.tagging.metadata.types import AlbumSearch, FoundAlbum

from ...web.fakes import FakeTransport, make_json_response
from ..fakes import make_services

SEARCH = AlbumSearch("Daft Punk", "discovery")


def find_album(groups: list[dict[str, Any]]) -> FoundAlbum | None:
    transport = FakeTransport(lambda _request: make_json_response({"release-groups": groups}))
    client = MusicBrainzClient("MasterIt/1.0", make_services(transport))
    return MusicBrainzAlbumSource(client).find_album(SEARCH)


def test_gives_the_searched_release_group_and_its_covers():
    found = find_album(
        [
            {"id": "other", "title": "Discovery", "artist-credit": [{"name": "Data Punk"}]},
            {"id": "group", "title": "Discovery", "artist-credit": [{"name": "Daft Punk"}]},
        ]
    )
    assert found is not None
    assert found.album == "Discovery"
    assert [cover.url for cover in found.covers] == [
        "https://coverartarchive.org/release-group/group/front-1200",
        "https://coverartarchive.org/release-group/group/front-500",
    ]


def test_finds_nothing_without_the_same_album():
    groups = [{"id": "live", "title": "Alive 2007", "artist-credit": [{"name": "Daft Punk"}]}]
    assert find_album(groups) is None


@pytest.mark.parametrize("group_id", [None, ""])
def test_gives_no_cover_for_a_release_group_without_an_id(group_id: str | None):
    group = {"id": group_id, "title": "Discovery", "artist-credit": [{"name": "Daft Punk"}]}
    assert find_album([group]) == FoundAlbum("Discovery", "Daft Punk")


def test_gives_the_artist_and_first_release_year():
    group = {
        "id": "group",
        "title": "Discovery",
        "artist-credit": [{"name": "Daft Punk"}],
        "first-release-date": "2001-03-07",
    }
    found = find_album([group])
    assert found is not None
    assert (found.artist, found.year) == ("Daft Punk", "2001")
