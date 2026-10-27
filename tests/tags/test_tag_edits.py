from pathlib import Path

import pytest

from masterit.tags.fields import TagField
from masterit.tags.tag_edits import (
    TagOutcome,
    find_tag_problem,
    merge_tag_values,
    write_tag_edits,
)

from .fakes import FakeTagStore


@pytest.mark.parametrize("year", ["", "2024", "2024-05", "2024-05-17"])
def test_valid_years_have_no_problem(year: str):
    assert find_tag_problem({TagField.YEAR: year}) is None


@pytest.mark.parametrize("year", ["24", "2024/05", "abcd", "2024-5"])
def test_invalid_year_is_refused(year: str):
    assert find_tag_problem({TagField.YEAR: year}) == "Year must look like 2024 or 2024-05-17."


@pytest.mark.parametrize("track", ["", "3", "3/12", "9999/9999"])
def test_valid_tracks_have_no_problem(track: str):
    assert find_tag_problem({TagField.TRACK: track}) is None


@pytest.mark.parametrize(
    "track", ["three", "3/", "/12", "-1", "99999", "1/12345", "0", "012", "3/0"]
)
def test_invalid_track_is_refused(track: str):
    assert find_tag_problem({TagField.TRACK: track}) == "Track must look like 3 or 3/12."


def test_free_text_fields_accept_anything():
    assert find_tag_problem({TagField.TITLE: "Anything / at all?"}) is None


def test_merge_keeps_common_values_and_marks_mixed_ones():
    merged = merge_tag_values(
        [
            {TagField.ARTIST: "Artist", TagField.TITLE: "One"},
            {TagField.ARTIST: "Artist", TagField.TITLE: "Two"},
        ]
    )
    assert merged[TagField.ARTIST] == "Artist"
    assert merged[TagField.TITLE] is None
    assert merged[TagField.ALBUM] == ""


def test_merge_of_nothing_is_empty():
    assert set(merge_tag_values([]).values()) == {""}


def test_write_applies_edits():
    store = FakeTagStore()
    outcome = write_tag_edits(Path("/a.mp3"), {TagField.GENRE: "Rock"}, store)
    assert outcome == TagOutcome(Path("/a.mp3"))
    assert outcome.succeeded
    assert store.tags == {Path("/a.mp3"): {TagField.GENRE: "Rock"}}


def test_write_reports_failure():
    store = FakeTagStore(failing={Path("/a.mp3")})
    outcome = write_tag_edits(Path("/a.mp3"), {TagField.GENRE: "Rock"}, store)
    assert outcome == TagOutcome(Path("/a.mp3"), "read-only")
    assert not outcome.succeeded
