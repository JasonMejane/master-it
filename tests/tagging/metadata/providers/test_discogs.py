import urllib.parse
from typing import Any

import pytest

from masterit.tagging.metadata.providers.discogs import (
    DiscogsAlbumProvider,
    DiscogsProvider,
    parse_position,
)
from masterit.tagging.metadata.types import (
    ProviderNeeds,
    TrackExtras,
    TrackInfo,
    TrackMetadata,
    TrackSearch,
)
from masterit.tagging.web.transport import HttpRequest, HttpResponse

from ...web.fakes import FakeTransport, FakeWeb, make_json_response
from .discogs_fakes import DISCOGS_COVER, make_discogs_web, make_finder, make_finder_on

ALBUM_SEARCH = TrackSearch("Digital Love", "Daft Punk", "Discovery")
SONG_SEARCH = TrackSearch("Digital Love", "Daft Punk", "")
COVER_NEEDS = ProviderNeeds(cover=True, details=True)
DETAIL_NEEDS = ProviderNeeds(cover=False, details=True)
DISCOVERY: dict[str, Any] = {
    "id": 8,
    "title": "Discovery",
    "year": 2001,
    "artists": [{"name": "Daft Punk", "join": ""}],
    "genres": ["Electronic", "Pop"],
    "images": [
        {"type": "secondary", "uri": "https://i.discogs.test/back.jpg"},
        {"type": "primary", "uri": DISCOGS_COVER},
    ],
    "tracklist": [
        {"position": "", "type_": "heading", "title": "Discovery"},
        {"position": "1-1", "type_": "track", "title": "One More Time"},
        {"position": "1-2", "type_": "track", "title": "Digital Love"},
        {"position": "2-1", "type_": "track", "title": "Bonus"},
    ],
}
MASTER_RESPONSES = {"/database/search": {"results": [{"id": 8}]}, "/masters/8": DISCOVERY}


def find_with(
    web: FakeWeb, search: TrackSearch = ALBUM_SEARCH, needs: ProviderNeeds = COVER_NEEDS
) -> TrackMetadata | None:
    return make_finder(web).find(search, needs)


def test_takes_the_song_year_genre_numbers_and_cover_of_a_master():
    assert find_with(make_discogs_web(MASTER_RESPONSES)) == TrackMetadata(
        TrackInfo("Digital Love", "Daft Punk", "Discovery", "2001"),
        TrackExtras("Electronic", "Daft Punk", 2, 2, 1, 2),
        b"image /cover.jpg",
    )


def test_searches_releases_when_no_master_has_the_song_without_their_year():
    tracklist = [{"position": "3", "title": "Digital Love"}]
    release = {**DISCOVERY, "id": 5, "year": 2021, "tracklist": tracklist}

    def answer_releases_only(request: HttpRequest) -> HttpResponse:
        if "/releases/5" in request.url:
            return make_json_response(release)
        results = [{"id": 5}] if "type=release" in request.url else []
        return make_json_response({"results": results})

    transport = FakeTransport(answer_releases_only)
    found = make_finder_on(transport).find(ALBUM_SEARCH, DETAIL_NEEDS)
    assert found == TrackMetadata(
        TrackInfo("Digital Love", "Daft Punk", "Discovery", ""),
        TrackExtras("Electronic", "Daft Punk", 3, 1, 1, 1),
    )
    kinds = [
        dict(urllib.parse.parse_qsl(request.url.split("?")[1]))["type"]
        for request in transport.requests[:2]
    ]
    assert kinds == ["master", "release"]
    assert len(transport.requests) == 3


def test_finds_nothing_when_the_album_lacks_the_song():
    search = TrackSearch("Around the World", "Daft Punk", "Discovery")
    assert find_with(make_discogs_web(MASTER_RESPONSES), search) is None


def test_finds_nothing_without_search_results():
    web = make_discogs_web({})
    assert find_with(web) is None
    assert len(web.requested) == 2


def test_keeps_only_the_song_from_another_album():
    search = TrackSearch("Digital Love", "Daft Punk", "Alive 2007")
    assert find_with(make_discogs_web(MASTER_RESPONSES), search) == TrackMetadata(
        TrackInfo("Digital Love", "Daft Punk"), TrackExtras(genre="Electronic")
    )


def test_reads_track_credits_vinyl_sides_and_various_artists():
    compilation = {
        "id": 9,
        "title": "Club Hits",
        "artists": [{"name": "Various"}],
        "tracklist": [
            {
                "position": "A1",
                "title": "Digital Love",
                "artists": [
                    {"name": "Daft Punk (2)", "join": "Feat."},
                    {"name": "DJ Falcon", "join": ""},
                ],
            }
        ],
    }
    web = make_discogs_web(
        {"/database/search": {"results": [{"id": 9}]}, "/masters/9": compilation}
    )
    search = TrackSearch("Digital Love", "Daft Punk", "Club Hits")
    assert find_with(web, search) == TrackMetadata(
        TrackInfo("Digital Love", "Daft Punk Feat. DJ Falcon", "Club Hits", ""),
        TrackExtras(album_artist="Various Artists"),
    )


def test_album_provider_only_searches_a_known_album():
    web = make_discogs_web({})
    provider = DiscogsAlbumProvider(make_finder(web))
    provider.find_metadata(SONG_SEARCH, COVER_NEEDS)
    assert web.requested == []
    provider.find_metadata(ALBUM_SEARCH, COVER_NEEDS)
    assert "release_title=Discovery" in web.transport.requests[0].url
    assert provider.name == "Discogs"


def test_song_provider_only_searches_without_a_known_album():
    web = make_discogs_web({})
    provider = DiscogsProvider(make_finder(web))
    provider.find_metadata(ALBUM_SEARCH, COVER_NEEDS)
    assert web.requested == []
    provider.find_metadata(SONG_SEARCH, COVER_NEEDS)
    assert "track=Digital+Love" in web.transport.requests[0].url
    assert provider.name == "Discogs"


def test_asks_nothing_when_neither_details_nor_a_cover_are_needed():
    web = make_discogs_web({})
    assert find_with(web, needs=ProviderNeeds(cover=False, details=False)) is None
    assert web.requested == []


def test_takes_no_compilation_as_the_album_of_a_song_without_one():
    compilation = {
        "id": 9,
        "title": "Club Hits",
        "year": 2004,
        "artists": [{"name": "Various"}],
        "tracklist": [
            {"position": "4", "title": "Digital Love", "artists": [{"name": "Daft Punk"}]}
        ],
    }
    web = make_discogs_web(
        {"/database/search": {"results": [{"id": 9}]}, "/masters/9": compilation}
    )
    assert find_with(web, SONG_SEARCH) == TrackMetadata(TrackInfo("Digital Love", "Daft Punk"))


def test_finds_songs_inside_an_index_track_and_spaced_positions():
    sub_tracks = [
        {"position": "CD 1 - 1", "type_": "track", "title": "Intro"},
        {"position": "CD 1 - 2", "type_": "track", "title": "Digital Love"},
    ]
    album = {
        **DISCOVERY,
        "tracklist": [{"type_": "index", "title": "Suite", "sub_tracks": sub_tracks}],
    }
    web = make_discogs_web({"/database/search": {"results": [{"id": 8}]}, "/masters/8": album})
    found = find_with(web)
    assert found is not None
    assert (found.extras.track_number, found.extras.track_count) == (2, 2)


def test_asks_discogs_once_per_album_for_its_tracks():
    web = make_discogs_web(MASTER_RESPONSES)
    finder = make_finder(web)
    finder.find(ALBUM_SEARCH, COVER_NEEDS)
    second = finder.find(TrackSearch("One More Time", "Daft Punk", "Discovery"), DETAIL_NEEDS)
    assert second is not None
    assert second.extras.track_number == 1
    api_paths = [path.split("?")[0] for path in web.requested if path != "/cover.jpg"]
    assert api_paths == ["/database/search", "/masters/8"]


def test_skips_the_cover_of_an_album_without_images():
    album = {key: value for key, value in DISCOVERY.items() if key != "images"}
    web = make_discogs_web({"/database/search": {"results": [{"id": 8}]}, "/masters/8": album})
    found = find_with(web)
    assert found is not None
    assert found.cover_data is None


def test_takes_the_first_image_without_a_primary_one():
    images = [{"type": "secondary", "uri": "https://i.discogs.test/back.jpg"}]
    album = {**DISCOVERY, "images": images}
    web = make_discogs_web({"/database/search": {"results": [{"id": 8}]}, "/masters/8": album})
    found = find_with(web)
    assert found is not None
    assert found.cover_data == b"image /back.jpg"


@pytest.mark.parametrize(
    ("position", "parsed"),
    [
        ("3", (1, 3)),
        ("1-3", (1, 3)),
        ("CD1-3", (1, 3)),
        ("2.03", (2, 3)),
        (" disc 2 - 4 ", (2, 4)),
        ("DI\u017fC1-2", (1, 2)),
    ],
)
def test_parses_numbered_positions(position: str, parsed: tuple[int, int]):
    found = parse_position(position)
    assert found is not None
    assert (found.disc, found.track) == parsed


@pytest.mark.parametrize("position", ["A1", "", None, "1-", "3a", "D\u0130SC1-2"])
def test_gives_no_position_for_vinyl_sides_or_odd_ones(position: str | None):
    assert parse_position(position) is None


def make_album_web(album: dict[str, Any], album_id: int = 8) -> FakeWeb:
    search = {"results": [{"id": album_id}]}
    return make_discogs_web({"/database/search": search, f"/masters/{album_id}": album})


def test_joins_credits_with_commas():
    track = {
        "position": "1",
        "title": "Digital Love",
        "artists": [{"name": "A", "join": ","}, {"name": "B"}],
    }
    found = find_with(
        make_album_web({**DISCOVERY, "tracklist": [track]}), TrackSearch("Digital Love", "A")
    )
    assert found is not None
    assert found.info.artist == "A, B"


def test_reads_no_genre_from_an_odd_first_genre():
    found = find_with(make_album_web({**DISCOVERY, "genres": [7, "Pop"]}))
    assert found is not None
    assert found.extras.genre is None


def test_stops_at_a_first_result_without_an_id():
    web = make_discogs_web(
        {"/database/search": {"results": [{}, {"id": 8}]}, "/masters/8": DISCOVERY}
    )
    assert find_with(web) is None
    assert all(path.startswith("/database/search") for path in web.requested)


def test_takes_no_cover_from_an_odd_first_image():
    images = ["x", {"uri": "https://i.discogs.test/back.jpg"}]
    found = find_with(make_album_web({**DISCOVERY, "images": images}))
    assert found is not None
    assert found.cover_data is None
