from typing import Any

import pytest

from masterit.tagging.metadata.providers.deezer import DeezerProvider
from masterit.tagging.metadata.providers.deezer_client import DeezerClient
from masterit.tagging.metadata.types import (
    ProviderNeeds,
    TrackExtras,
    TrackInfo,
    TrackMetadata,
    TrackSearch,
)
from masterit.tagging.web.errors import ServiceError
from masterit.tagging.web.transport import HttpResponse

from ...web.fakes import FakeTransport, FakeWeb
from ..fakes import make_services
from .deezer_fakes import DEEZER_COVER_XL, make_deezer_services, make_deezer_web

SEARCH = TrackSearch("One More Time", "Daft Punk", "")
COVER_NEEDS = ProviderNeeds(cover=True, details=True)
DETAIL_NEEDS = ProviderNeeds(cover=False, details=True)
FOUND_TRACK: dict[str, Any] = {
    "id": 11,
    "title": "One More Time",
    "artist": {"name": "Daft Punk"},
    "album": {"id": 7, "title": "Discovery", "cover_xl": DEEZER_COVER_XL},
}
FOUND_ALBUM: dict[str, Any] = {
    "id": 7,
    "title": "Discovery",
    "release_date": "2001-03-07",
    "artist": {"name": "Daft Punk"},
    "genres": {"data": [{"name": "Electro"}]},
}
ALBUM_TRACKS = {
    "data": [
        {"id": 10, "track_position": 1, "disk_number": 1},
        {"id": 11, "track_position": 2, "disk_number": 1},
        {"id": 12, "track_position": 1, "disk_number": 2},
    ]
}
RESPONSES: dict[str, Any] = {
    "/search": {"data": [FOUND_TRACK]},
    "/album/7": FOUND_ALBUM,
    "/album/7/tracks": ALBUM_TRACKS,
}
DISCOVERY_INFO = TrackInfo("One More Time", "Daft Punk", "Discovery", "")
BARE_INFO = TrackInfo("One More Time", "Daft Punk", "", "")


def find_with_deezer(
    web: FakeWeb, needs: ProviderNeeds, search: TrackSearch = SEARCH
) -> TrackMetadata | None:
    services = make_deezer_services(web)
    return DeezerProvider(DeezerClient(services), services).find_metadata(search, needs)


def drop_key(payload: dict[str, Any], key: str) -> dict[str, Any]:
    return {name: value for name, value in payload.items() if name != key}


def test_fills_info_release_extras_and_the_largest_cover():
    web = make_deezer_web(RESPONSES)
    assert find_with_deezer(web, COVER_NEEDS) == TrackMetadata(
        DISCOVERY_INFO,
        TrackExtras("Electro", "Daft Punk", 2, 2, 1, 2),
        b"image /1000x1000.jpg",
    )
    assert web.requested == [
        "/search?q=Daft+Punk+One+More+Time&limit=5",
        "/album/7",
        "/album/7/tracks?limit=1000",
        "/1000x1000.jpg",
    ]


def test_skips_album_calls_and_the_cover_when_nothing_is_missing():
    web = make_deezer_web(RESPONSES)
    metadata = find_with_deezer(web, ProviderNeeds(cover=False, details=False))
    assert metadata == TrackMetadata(DISCOVERY_INFO)
    assert len(web.requested) == 1


def test_prefers_the_first_result_that_is_the_searched_track():
    karaoke = {**FOUND_TRACK, "id": 99, "title": "One More Time (Karaoke)"}
    web = make_deezer_web({**RESPONSES, "/search": {"data": [karaoke, FOUND_TRACK]}})
    metadata = find_with_deezer(web, DETAIL_NEEDS)
    assert metadata is not None
    assert (metadata.info.title, metadata.extras.track_number) == ("One More Time", 2)


def test_returns_none_when_no_result_is_the_searched_track():
    karaoke = {**FOUND_TRACK, "title": "One More Time (Karaoke)"}
    web = make_deezer_web({"/search": {"data": [karaoke]}})
    assert find_with_deezer(web, COVER_NEEDS) is None
    assert len(web.requested) == 1


def test_prefers_the_searched_track_on_the_searched_album():
    compilation = {
        **FOUND_TRACK,
        "album": {"id": 8, "title": "Greatest Hits", "cover_xl": "https://other"},
    }
    web = make_deezer_web({**RESPONSES, "/search": {"data": [compilation, FOUND_TRACK]}})
    metadata = find_with_deezer(
        web, COVER_NEEDS, TrackSearch("One More Time", "Daft Punk", "Discovery")
    )
    assert metadata is not None
    assert metadata.extras.track_number == 2
    assert metadata.cover_data == b"image /1000x1000.jpg"


def test_takes_only_the_genre_and_no_cover_from_another_release():
    web = make_deezer_web(RESPONSES)
    search = TrackSearch("One More Time", "Daft Punk", "Greatest Hits")
    assert find_with_deezer(web, COVER_NEEDS, search) == TrackMetadata(
        BARE_INFO, TrackExtras(genre="Electro")
    )
    assert web.requested == ["/search?q=Daft+Punk+One+More+Time&limit=5", "/album/7"]


def test_takes_only_the_genre_from_a_release_by_another_artist():
    tribute = {**FOUND_ALBUM, "artist": {"name": "Tribute Band"}}
    web = make_deezer_web({**RESPONSES, "/album/7": tribute})
    assert find_with_deezer(web, COVER_NEEDS) == TrackMetadata(
        BARE_INFO, TrackExtras(genre="Electro")
    )
    assert web.requested == ["/search?q=Daft+Punk+One+More+Time&limit=5", "/album/7"]


def test_leaves_out_positions_of_a_track_missing_from_the_album_list():
    web = make_deezer_web({**RESPONSES, "/album/7/tracks": {"data": []}})
    metadata = find_with_deezer(web, DETAIL_NEEDS)
    assert metadata is not None
    assert metadata.extras == TrackExtras(genre="Electro", album_artist="Daft Punk")


def test_leaves_out_positions_when_track_ids_are_unknown():
    web = make_deezer_web(
        {
            **RESPONSES,
            "/search": {"data": [drop_key(FOUND_TRACK, "id")]},
            "/album/7/tracks": {"data": [{"track_position": 1, "disk_number": 1}]},
        }
    )
    metadata = find_with_deezer(web, DETAIL_NEEDS)
    assert metadata is not None
    assert metadata.extras.track_number is None


def test_takes_no_details_from_a_track_without_an_album():
    web = make_deezer_web({"/search": {"data": [drop_key(FOUND_TRACK, "album")]}})
    assert find_with_deezer(web, COVER_NEEDS) == TrackMetadata(BARE_INFO)
    assert len(web.requested) == 1


def test_leaves_out_details_deezer_does_not_provide():
    web = make_deezer_web(
        {
            "/search": {"data": [drop_key(FOUND_TRACK, "artist")]},
            "/album/7": {"id": 7, "title": "Discovery"},
            "/album/7/tracks": {"data": [{"id": 11, "track_position": 2}]},
        }
    )
    metadata = find_with_deezer(web, DETAIL_NEEDS, TrackSearch("One More Time"))
    assert metadata is not None
    assert metadata.info.artist == ""
    assert metadata.extras == TrackExtras(track_number=2, track_count=1)


def test_returns_none_when_nothing_is_found():
    assert find_with_deezer(make_deezer_web({}), COVER_NEEDS) is None


def test_lets_a_failed_search_reach_the_chain():
    services = make_services(FakeTransport(lambda _request: HttpResponse(500, {}, b"")))
    provider = DeezerProvider(DeezerClient(services), services)
    with pytest.raises(ServiceError, match="HTTP 500"):
        provider.find_metadata(SEARCH, COVER_NEEDS)


def test_keeps_the_track_info_when_the_album_lookup_fails():
    web = make_deezer_web({**RESPONSES, "/album/7": {"error": {"message": "quota"}}})
    assert find_with_deezer(web, DETAIL_NEEDS) == TrackMetadata(DISCOVERY_INFO)


def test_reads_album_and_track_ids_of_zero():
    track = {**FOUND_TRACK, "id": 0, "album": {**FOUND_TRACK["album"], "id": 0}}
    web = make_deezer_web(
        {
            "/search": {"data": [track]},
            "/album/0": FOUND_ALBUM,
            "/album/0/tracks": {"data": [{"id": 0, "track_position": 4, "disk_number": 1}]},
        }
    )
    metadata = find_with_deezer(web, DETAIL_NEEDS)
    assert metadata is not None
    assert metadata.extras.track_number == 4
