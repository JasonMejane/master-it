from pathlib import Path

import pytest

from masterit.library.destinations import Destination
from masterit.library.library_layout import make_layout_destination, make_safe_name
from masterit.library.relocation import RelocationProblem, make_relocation_plan
from masterit.tags.fields import TagField, Tags

ROOT = Path("/library")
SONG = Path("/downloads/x.mp3")


def make_destination(tags: Tags, source: Path = SONG) -> Destination:
    return make_layout_destination(ROOT, lambda path: tags)(source)


def test_file_goes_to_artist_folder_named_artist_dash_title():
    tags = {TagField.ARTIST: "Queen", TagField.TITLE: "Mustapha"}
    assert make_destination(tags) == Destination(ROOT / "Queen", "Queen - Mustapha.mp3")


@pytest.mark.parametrize(
    ("text", "safe"),
    [
        ("AC/DC", "AC-DC"),
        ("What?", "What-"),
        ('a\\b:c*d"e<f>g|h', "a-b-c-d-e-f-g-h"),
        ("  .38 Special ", "38 Special"),
        (". x", "x"),
        ("Mr. ", "Mr"),
        ("Tab\there", "Tab-here"),
    ],
)
def test_names_are_made_safe(text: str, safe: str):
    assert make_safe_name(text) == safe


@pytest.mark.parametrize(
    "tags",
    [
        {TagField.TITLE: "Mustapha"},
        {TagField.ARTIST: "Queen"},
        {TagField.ARTIST: "...", TagField.TITLE: "Mustapha"},
    ],
)
def test_missing_artist_or_title_is_a_problem(tags: Tags):
    destination = make_destination(tags)
    assert destination.problem == RelocationProblem.MISSING_TAGS
    assert destination.path == SONG


def test_plan_lists_file_without_tags_as_skipped():
    plan = make_relocation_plan([SONG], make_layout_destination(ROOT, lambda path: {}))
    assert [(entry.source, entry.problem) for entry in plan.entries] == [
        (SONG, RelocationProblem.MISSING_TAGS)
    ]
    assert plan.valid_entries == []


def test_file_already_in_place_is_left_out_of_plan():
    source = ROOT / "Queen" / "Queen - Mustapha.mp3"
    tags = {TagField.ARTIST: "Queen", TagField.TITLE: "Mustapha"}
    plan = make_relocation_plan([source], make_layout_destination(ROOT, lambda path: tags))
    assert plan.entries == ()


@pytest.mark.parametrize(
    ("text", "safe"), [("Con", "Con_"), ("nul", "nul_"), ("COM1", "COM1_"), ("Conan", "Conan")]
)
def test_reserved_windows_names_get_a_suffix(text: str, safe: str):
    assert make_safe_name(text) == safe


def test_reserved_name_is_checked_without_extension():
    tags = {TagField.ARTIST: "Aux", TagField.TITLE: "x"}
    assert make_destination(tags) == Destination(ROOT / "Aux_", "Aux_ - x.mp3")


def test_long_names_fit_255_bytes():
    tags = {TagField.ARTIST: "é" * 200, TagField.TITLE: "t" * 300}
    destination = make_destination(tags)
    assert len(destination.folder.name.encode()) <= 255
    assert len(destination.file_name.encode()) <= 255
    assert destination.file_name.endswith(".mp3")
    assert destination.folder.name.startswith("é")


def test_long_artist_keeps_the_title():
    tags = {TagField.ARTIST: "a" * 300, TagField.TITLE: "Title"}
    destination = make_destination(tags)
    assert destination.file_name.endswith(" - Title.mp3")
    assert len(destination.file_name.encode()) <= 255
