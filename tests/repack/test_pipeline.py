from pathlib import Path

import pytest

from masterit.library.library_layout import AlbumTarget
from masterit.library.relocation import RelocationOutcome, RelocationProblem
from masterit.repack.pipeline import find_album_problem, make_repack_plan, make_suggested_album
from masterit.tagging.paths.album_plan import find_album_folder
from masterit.tags.fields import TagField, Tags

ROOT = Path("/library")
JAZZ = AlbumTarget("Queen", "Jazz")
ARTIST_SEPARATOR_PROBLEM = 'The artist cannot contain " - ", "\u2013" or "\u2014".'
ALBUM_FOLDER = ROOT / "Queen" / "Queen - Jazz"
DOWNLOADED = Path("/downloads/Queen - Mustapha.mp3")
IN_PLACE = ALBUM_FOLDER / "Queen - Bicycle.opus"
UNTAGGED = Path("/downloads/unknown.mp3")
TAGS = {
    DOWNLOADED: {TagField.ARTIST: "Queen", TagField.TITLE: "Mustapha"},
    IN_PLACE: {TagField.ARTIST: "Queen", TagField.TITLE: "Bicycle"},
}


def read_tags(path: Path) -> Tags:
    return TAGS.get(path, {})


def test_plan_moves_files_into_album_folder_and_keeps_files_in_place():
    plan = make_repack_plan([DOWNLOADED, IN_PLACE, UNTAGGED], ROOT, JAZZ, read_tags)
    moves = [(entry.source, entry.target, entry.problem) for entry in plan.moves.entries]
    assert moves == [
        (DOWNLOADED, ALBUM_FOLDER / "Queen - Mustapha.mp3", None),
        (UNTAGGED, UNTAGGED, RelocationProblem.MISSING_TITLE),
    ]
    assert plan.in_place == (IN_PLACE,)


def test_files_to_tag_are_files_in_place_and_moved_targets():
    plan = make_repack_plan([DOWNLOADED, IN_PLACE], ROOT, JAZZ, read_tags)
    target = ALBUM_FOLDER / "Queen - Mustapha.mp3"
    outcomes = [
        RelocationOutcome(DOWNLOADED, target),
        RelocationOutcome(Path("/downloads/b.mp3"), ROOT / "b.mp3", "disk full"),
    ]
    assert plan.get_files_to_tag(outcomes) == [IN_PLACE, target]


@pytest.mark.parametrize(
    ("tags", "suggested"),
    [
        (
            [{TagField.ARTIST: "Queen", TagField.ALBUM: "Jazz"}] * 2,
            AlbumTarget("Queen", "Jazz"),
        ),
        (
            [
                {TagField.ALBUM_ARTIST: "Queen", TagField.ARTIST: "A", TagField.ALBUM: "Jazz"},
                {TagField.ALBUM_ARTIST: "Queen", TagField.ARTIST: "B", TagField.ALBUM: "Live"},
            ],
            AlbumTarget("Queen", ""),
        ),
        (
            [
                {TagField.ALBUM_ARTIST: "Queen", TagField.ARTIST: "Queen feat. X"},
                {TagField.ARTIST: "Queen"},
            ],
            AlbumTarget("Queen", ""),
        ),
        ([{TagField.ARTIST: "A"}, {TagField.ARTIST: "B"}], AlbumTarget("", "")),
        ([{TagField.ARTIST: "A"}, {}], AlbumTarget("", "")),
    ],
)
def test_suggested_album_uses_values_shared_by_all_files(tags: list[Tags], suggested: AlbumTarget):
    paths = [Path(f"/downloads/{index}.mp3") for index in range(len(tags))]
    tags_by_path = dict(zip(paths, tags, strict=True))
    assert make_suggested_album(paths, tags_by_path.__getitem__) == suggested


def test_repacked_file_is_found_as_album_track_by_the_tagger():
    plan = make_repack_plan([DOWNLOADED], ROOT, JAZZ, read_tags)
    album = find_album_folder(plan.moves.entries[0].target)
    assert album is not None
    assert (album.folder, album.artist, album.album) == (ALBUM_FOLDER, "Queen", "Jazz")


@pytest.mark.parametrize(
    ("target", "problem"),
    [
        (AlbumTarget("Queen", "Jazz"), ""),
        (AlbumTarget("AC-DC", "Jazz"), ""),
        (AlbumTarget(" ", "Jazz"), "Enter an artist and an album."),
        (AlbumTarget("Queen", "..."), "Enter an artist and an album."),
        (AlbumTarget("A - B", "Jazz"), ARTIST_SEPARATOR_PROBLEM),
        (AlbumTarget("A\u2013B", "Jazz"), ARTIST_SEPARATOR_PROBLEM),
        (AlbumTarget("A \u2014 B", "Jazz"), ARTIST_SEPARATOR_PROBLEM),
        (AlbumTarget("A / B", "Jazz"), ARTIST_SEPARATOR_PROBLEM),
        (AlbumTarget("A -", "Jazz"), ARTIST_SEPARATOR_PROBLEM),
        (AlbumTarget("A\t-\tB", "Jazz"), ""),
        (AlbumTarget("a" * 118 + " - b", "Jazz"), ARTIST_SEPARATOR_PROBLEM),
    ],
)
def test_album_problem_explains_unusable_targets(target: AlbumTarget, problem: str):
    assert find_album_problem(target) == problem
