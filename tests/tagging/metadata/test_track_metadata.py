import pytest

from masterit.tagging.metadata.track_metadata import (
    build_provider_search,
    extract_year,
    fill_missing_extras,
    fill_missing_fields,
    get_changed_extras,
    get_first_filled,
    get_stale_extras,
    has_all_details,
    has_changed_fields,
    is_complete,
    make_optional_count,
    make_optional_text,
    merge_metadata,
)
from masterit.tagging.metadata.types import TrackExtras, TrackInfo, TrackMetadata, TrackSearch

COMPLETE_INFO = TrackInfo("Title", "Artist", "Album", "2024")
REQUIRED_EXTRAS = TrackExtras(genre="Rock", track_number=3)
ALL_EXTRAS = TrackExtras("Rock", "Artist", 3, 10, 1, 1)


def test_fill_missing_fields_keeps_known_fields_and_fills_blank_ones():
    info = TrackInfo("Known", " ", "", "1999")
    assert fill_missing_fields(info, COMPLETE_INFO) == TrackInfo("Known", "Artist", "Album", "1999")


def test_complete_needs_every_field_genre_track_number_and_cover():
    complete = TrackMetadata(COMPLETE_INFO, REQUIRED_EXTRAS, b"cover")
    assert is_complete(complete, has_existing_cover=False)
    assert not is_complete(TrackMetadata(COMPLETE_INFO, REQUIRED_EXTRAS), False)
    blank_year = TrackMetadata(TrackInfo("Title", "Artist", "Album", " "), REQUIRED_EXTRAS, b"c")
    assert not is_complete(blank_year, False)
    assert not is_complete(TrackMetadata(COMPLETE_INFO, TrackExtras(track_number=3), b"c"), False)
    assert not is_complete(TrackMetadata(COMPLETE_INFO, TrackExtras(genre="Rock"), b"c"), False)


def test_complete_counts_a_cover_already_in_the_file():
    assert is_complete(TrackMetadata(COMPLETE_INFO, REQUIRED_EXTRAS), has_existing_cover=True)


@pytest.mark.parametrize(
    ("extras", "candidate", "merged"),
    [
        (
            TrackExtras(genre="Known"),
            TrackExtras(genre="Other", track_number=4, disc_number=1),
            TrackExtras(genre="Known", track_number=4, disc_number=1),
        ),
        (
            TrackExtras(track_number=5),
            TrackExtras(track_number=6, track_count=12, disc_number=1, disc_count=3),
            TrackExtras(track_number=5, disc_number=1, disc_count=3),
        ),
        (TrackExtras(track_count=12), TrackExtras(track_count=9), TrackExtras(track_count=12)),
        (
            TrackExtras(track_count=12),
            TrackExtras(track_number=3, track_count=10),
            TrackExtras(track_count=12),
        ),
    ],
)
def test_fill_missing_extras_moves_positions_with_their_counts(
    extras: TrackExtras, candidate: TrackExtras, merged: TrackExtras
):
    assert fill_missing_extras(extras, candidate) == merged


def test_optional_text_trims_and_treats_blank_as_unknown():
    assert make_optional_text(" Rock ") == "Rock"
    assert make_optional_text("  ") is None
    assert make_optional_text(None) is None


def test_optional_count_treats_missing_and_non_positive_numbers_as_unknown():
    assert make_optional_count(3) == 3
    assert make_optional_count(0) is None
    assert make_optional_count(-1) is None
    assert make_optional_count(None) is None


@pytest.mark.parametrize(
    ("text", "year"),
    [
        ("18 October 2024, 12:00", "2024"),
        ("1997-01-01", "1997"),
        ("2024年", "2024"),
        ("12024", ""),
        ("unknown", ""),
        (None, ""),
    ],
)
def test_extract_year_reads_the_first_four_digit_year(text: str | None, year: str):
    assert extract_year(text) == year


def test_provider_search_prefers_found_title_and_artist_and_searched_album():
    search = TrackSearch("Query", "Query artist", "Folder album")
    found = TrackInfo("Found", " ", "Found album")
    assert build_provider_search(search, found) == TrackSearch(
        "Found", "Query artist", "Folder album"
    )
    bare = build_provider_search(TrackSearch("Query"), TrackInfo(album="Found album"))
    assert bare == TrackSearch("Query", "", "Found album")


def test_merge_fills_missing_fields_and_extras_and_keeps_the_first_cover():
    current = TrackMetadata(TrackInfo("Title", "Artist", "", "2024"), TrackExtras(genre="Rock"))
    candidate = TrackMetadata(
        TrackInfo("Title", "Artist", "Other", "2024"),
        TrackExtras(genre="Pop", track_number=2),
        b"first",
    )
    assert merge_metadata(current, candidate) == TrackMetadata(
        TrackInfo("Title", "Artist", "Other", "2024"),
        TrackExtras(genre="Rock", track_number=2),
        b"first",
    )
    with_cover = TrackMetadata(COMPLETE_INFO, cover_data=b"first")
    second = TrackMetadata(COMPLETE_INFO, cover_data=b"second")
    assert merge_metadata(with_cover, second).cover_data == b"first"


def test_first_filled_returns_the_first_non_empty_value():
    assert get_first_filled("", None, "second", "third") == "second"
    assert get_first_filled(None, "") == ""


def test_changed_fields_need_a_found_value_that_differs():
    existing = TrackInfo("Song", "Artist")
    assert has_changed_fields(existing, TrackInfo("Song", "Artist", "", "1999"))
    assert has_changed_fields(existing, TrackInfo("Other", "Artist"))
    assert not has_changed_fields(existing, TrackInfo("Song", ""))
    assert not has_changed_fields(existing, existing)


def test_changed_extras_keep_found_groups_that_differ():
    existing = TrackExtras(genre="Rock", track_number=1, track_count=9, disc_number=1)
    found = TrackExtras(genre="Rock", album_artist="VA", track_number=1, track_count=12)
    assert get_changed_extras(existing, found) == TrackExtras(
        album_artist="VA", track_number=1, track_count=12
    )
    rock = TrackExtras(genre="Rock")
    assert get_changed_extras(rock, rock) == TrackExtras()


def test_changed_extras_ignore_fields_the_service_did_not_find():
    stored = TrackExtras(track_number=5, track_count=12)
    assert get_changed_extras(stored, TrackExtras(track_number=5)) == TrackExtras()
    assert get_changed_extras(stored, TrackExtras(track_number=3)) == TrackExtras(track_number=3)


def test_stale_extras_name_stored_fields_a_changed_group_did_not_get():
    stored = TrackExtras(genre="Rock", track_number=5, track_count=12)
    assert get_stale_extras(stored, TrackExtras(track_number=3)) == ["track_count"]
    assert get_stale_extras(stored, TrackExtras(track_number=5)) == []
    assert get_stale_extras(stored, TrackExtras(genre="Pop")) == []


def test_all_details_need_a_year_and_every_extra_group_lead():
    assert has_all_details(TrackMetadata(COMPLETE_INFO, ALL_EXTRAS))
    no_year = TrackMetadata(TrackInfo("Title", "Artist", "Album", ""), ALL_EXTRAS)
    assert not has_all_details(no_year)
    assert not has_all_details(TrackMetadata(COMPLETE_INFO, REQUIRED_EXTRAS))


def test_an_empty_cover_still_counts_as_found():
    assert is_complete(TrackMetadata(COMPLETE_INFO, REQUIRED_EXTRAS, b""), has_existing_cover=False)


def test_merge_keeps_an_empty_cover_found_first():
    current = TrackMetadata(COMPLETE_INFO, cover_data=b"")
    candidate = TrackMetadata(COMPLETE_INFO, cover_data=b"x")
    assert merge_metadata(current, candidate).cover_data == b""
