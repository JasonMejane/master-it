from pathlib import Path

import pytest

from masterit.library.rename_plan import (
    RenameEntry,
    RenameOutcome,
    RenameProblem,
    apply_rename_plan,
    make_rename_plan,
    replace_renamed_paths,
)
from masterit.library.rename_rules import AddPrefix, RemoveText, SetName


def make_files(root: Path, *names: str) -> list[Path]:
    paths = [root / name for name in names]
    for path in paths:
        path.touch()
    return paths


def test_plan_renames_stem_and_keeps_extension(tmp_path: Path):
    [song] = make_files(tmp_path, "Song (Official Video).mp3")
    plan = make_rename_plan([song], RemoveText("Official Video"))
    assert plan.entries == (RenameEntry(song, tmp_path / "Song.mp3"),)


def test_plan_skips_unchanged_files(tmp_path: Path):
    files = make_files(tmp_path, "Song.mp3")
    assert make_rename_plan(files, RemoveText("absent")).entries == ()


@pytest.mark.parametrize(
    ("new_name", "problem"),
    [
        ("  ", RenameProblem.EMPTY_NAME),
        ("a/b", RenameProblem.INVALID_NAME),
        ("a\0b", RenameProblem.INVALID_NAME),
        (".", RenameProblem.INVALID_NAME),
        (".hidden", RenameProblem.INVALID_NAME),
        ("a:b", RenameProblem.INVALID_NAME),
        ('a"b', RenameProblem.INVALID_NAME),
        ("why?", RenameProblem.INVALID_NAME),
        ("tab\there", RenameProblem.INVALID_NAME),
    ],
)
def test_plan_flags_invalid_names(tmp_path: Path, new_name: str, problem: RenameProblem):
    [song] = make_files(tmp_path, "Song.mp3")
    [entry] = make_rename_plan([song], SetName(new_name)).entries
    assert entry.problem == problem
    assert not entry.is_valid


def test_plan_flags_existing_target(tmp_path: Path):
    song, _ = make_files(tmp_path, "Song.mp3", "Other.mp3")
    [entry] = make_rename_plan([song], SetName("Other")).entries
    assert entry.problem == RenameProblem.TARGET_EXISTS


def test_plan_flags_duplicate_targets(tmp_path: Path):
    files = make_files(tmp_path, "A Song.mp3", "B Song.mp3")
    plan = make_rename_plan(files, SetName("Song"))
    assert [entry.problem for entry in plan.entries] == [RenameProblem.DUPLICATE_TARGET] * 2


def test_same_name_in_other_extension_is_no_conflict(tmp_path: Path):
    files = make_files(tmp_path, "A.mp3", "A.flac")
    plan = make_rename_plan(files, AddPrefix("X "))
    assert all(entry.is_valid for entry in plan.entries)


def test_case_only_rename_is_valid(tmp_path: Path):
    [song] = make_files(tmp_path, "song.mp3")
    [entry] = make_rename_plan([song], SetName("Song")).entries
    assert entry.is_valid


def test_apply_renames_only_valid_entries(tmp_path: Path):
    song, other, _ = make_files(tmp_path, "Song.mp3", "Other.mp3", "X Other.mp3")
    plan = make_rename_plan([song, other], AddPrefix("X "))
    outcomes = apply_rename_plan(plan)
    assert outcomes == [RenameOutcome(song, tmp_path / "X Song.mp3")]
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "Other.mp3",
        "X Other.mp3",
        "X Song.mp3",
    ]


def test_apply_refuses_target_created_after_planning(tmp_path: Path):
    [song] = make_files(tmp_path, "Song.mp3")
    plan = make_rename_plan([song], SetName("New"))
    (tmp_path / "New.mp3").write_text("keep me")
    [outcome] = apply_rename_plan(plan)
    assert outcome.error == RenameProblem.TARGET_EXISTS
    assert (tmp_path / "New.mp3").read_text() == "keep me"


def test_apply_reports_os_errors(tmp_path: Path):
    [song] = make_files(tmp_path, "Song.mp3")
    plan = make_rename_plan([song], SetName("New"))
    song.unlink()
    [outcome] = apply_rename_plan(plan)
    assert outcome.error is not None
    assert not outcome.succeeded


def test_replace_renamed_paths_keeps_order_and_ignores_failures(tmp_path: Path):
    a, b, c = (tmp_path / name for name in ("a.mp3", "b.mp3", "c.mp3"))
    outcomes = [
        RenameOutcome(a, tmp_path / "A.mp3"),
        RenameOutcome(b, tmp_path / "B.mp3", "denied"),
    ]
    assert replace_renamed_paths([a, b, c], outcomes) == [tmp_path / "A.mp3", b, c]
