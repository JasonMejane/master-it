from pathlib import Path

import pytest

from masterit.library.destinations import Destination
from masterit.library.library_layout import (
    AlbumTarget,
    make_album_destination,
    make_folder_artist,
    make_safe_name,
)
from masterit.library.relocation import RelocationProblem, make_relocation_plan
from masterit.tags.fields import TagField, Tags

ROOT = Path("/library")
SONG = Path("/downloads/x.mp3")
JAZZ = AlbumTarget("Queen", "Jazz")
JAZZ_FOLDER = ROOT / "Queen" / "Queen - Jazz"


def make_destination(tags: Tags, source: Path = SONG, target: AlbumTarget = JAZZ) -> Destination:
    return make_album_destination(ROOT, target, lambda path: tags)(source)


def test_file_goes_to_album_folder_named_artist_dash_title():
    tags = {TagField.ARTIST: "Freddie", TagField.TITLE: "Mustapha"}
    assert make_destination(tags) == Destination(JAZZ_FOLDER, "Queen - Mustapha.mp3")


@pytest.mark.parametrize(
    ("text", "safe"),
    [
        ("AC/DC", "AC-DC"),
        ("What?", "What_"),
        ("Why? Not: me", "Why_ Not- me"),
        ('a\\b:c*d"e<f>g|h', "a-b-c-d-e-f-g-h"),
        ("  .38 Special ", "38 Special"),
        (". x", "x"),
        ("Mr. ", "Mr"),
        ("Tab\there", "Tab-here"),
    ],
)
def test_names_are_made_safe(text: str, safe: str):
    assert make_safe_name(text) == safe


@pytest.mark.parametrize("tags", [{}, {TagField.ARTIST: "Queen", TagField.TITLE: "..."}])
def test_missing_title_is_a_problem(tags: Tags):
    destination = make_destination(tags)
    assert destination.problem == RelocationProblem.MISSING_TITLE
    assert destination.path == SONG


def test_plan_lists_file_without_tags_as_skipped():
    plan = make_relocation_plan([SONG], make_album_destination(ROOT, JAZZ, lambda path: {}))
    assert [(entry.source, entry.problem) for entry in plan.entries] == [
        (SONG, RelocationProblem.MISSING_TITLE)
    ]
    assert plan.valid_entries == []


def test_file_already_in_place_is_left_out_of_plan():
    source = JAZZ_FOLDER / "Queen - Mustapha.mp3"
    tags = {TagField.TITLE: "Mustapha"}
    plan = make_relocation_plan([source], make_album_destination(ROOT, JAZZ, lambda path: tags))
    assert plan.entries == ()


@pytest.mark.parametrize(
    ("text", "safe"), [("Con", "Con_"), ("nul", "nul_"), ("COM1", "COM1_"), ("Conan", "Conan")]
)
def test_reserved_windows_names_get_a_suffix(text: str, safe: str):
    assert make_safe_name(text) == safe


def test_entered_names_are_made_safe():
    destination = make_destination({TagField.TITLE: "x"}, target=AlbumTarget("Aux", "A/B"))
    assert destination == Destination(ROOT / "Aux_" / "Aux_ - A-B", "Aux_ - x.mp3")


def test_long_names_fit_255_bytes():
    target = AlbumTarget("é" * 200, "b" * 300)
    destination = make_destination({TagField.TITLE: "t" * 300}, target=target)
    assert len(destination.folder.parent.name.encode()) <= 255
    assert len(destination.folder.name.encode()) <= 255
    assert len(destination.file_name.encode()) <= 255
    assert destination.file_name.endswith(".mp3")
    assert destination.folder.parent.name.startswith("é")
    assert destination.folder.name.startswith(f"{destination.folder.parent.name} - b")


def test_long_artist_keeps_the_album_and_matches_its_folder():
    destination = make_destination({TagField.TITLE: "x"}, target=AlbumTarget("a" * 300, "Jazz"))
    artist = destination.folder.parent.name
    assert destination.folder.name == f"{artist} - Jazz"
    assert destination.file_name == f"{artist} - x.mp3"


def test_long_artist_keeps_the_title():
    destination = make_destination({TagField.TITLE: "Title"}, target=AlbumTarget("a" * 300, "B"))
    assert destination.file_name.endswith(" - Title.mp3")
    assert len(destination.file_name.encode()) <= 255


def test_folder_artist_is_safe_and_cut_to_120_bytes():
    assert make_folder_artist(" AC/DC ") == "AC-DC"
    assert make_folder_artist("é" * 100) == "é" * 60
