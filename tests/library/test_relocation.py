import errno
import io
import shutil
from pathlib import Path
from typing import BinaryIO

import pytest

from masterit.library.destinations import make_move_destination, make_rename_destination
from masterit.library.relocation import (
    Relocation,
    RelocationOutcome,
    RelocationPlan,
    RelocationProblem,
    apply_relocation_plan,
    make_relocation_plan,
    remove_emptied_folders,
    replace_relocated_paths,
)
from masterit.library.rename_rules import AddPrefix, RemoveText, RenameRule, SetName


def make_rename_plan(paths: list[Path], rule: RenameRule) -> RelocationPlan:
    return make_relocation_plan(paths, make_rename_destination(rule))


def make_files(root: Path, *names: str) -> list[Path]:
    paths = [root / name for name in names]
    for path in paths:
        path.touch()
    return paths


def test_plan_renames_stem_and_keeps_extension(tmp_path: Path):
    [song] = make_files(tmp_path, "Song (Official Video).mp3")
    plan = make_rename_plan([song], RemoveText("Official Video"))
    assert plan.entries == (Relocation(song, tmp_path / "Song.mp3"),)


def test_plan_skips_unchanged_files(tmp_path: Path):
    files = make_files(tmp_path, "Song.mp3")
    assert make_rename_plan(files, RemoveText("absent")).entries == ()


@pytest.mark.parametrize(
    ("new_name", "problem"),
    [
        ("  ", RelocationProblem.EMPTY_NAME),
        ("a/b", RelocationProblem.INVALID_NAME),
        ("a\0b", RelocationProblem.INVALID_NAME),
        (".", RelocationProblem.INVALID_NAME),
        (".hidden", RelocationProblem.INVALID_NAME),
        ("a:b", RelocationProblem.INVALID_NAME),
        ('a"b', RelocationProblem.INVALID_NAME),
        ("why?", RelocationProblem.INVALID_NAME),
        ("tab\there", RelocationProblem.INVALID_NAME),
    ],
)
def test_plan_flags_invalid_names(tmp_path: Path, new_name: str, problem: RelocationProblem):
    [song] = make_files(tmp_path, "Song.mp3")
    [entry] = make_rename_plan([song], SetName(new_name)).entries
    assert entry.problem == problem
    assert not entry.is_valid


def test_plan_flags_existing_target(tmp_path: Path):
    song, _ = make_files(tmp_path, "Song.mp3", "Other.mp3")
    [entry] = make_rename_plan([song], SetName("Other")).entries
    assert entry.problem == RelocationProblem.TARGET_EXISTS


def test_plan_flags_duplicate_targets(tmp_path: Path):
    files = make_files(tmp_path, "A Song.mp3", "B Song.mp3")
    plan = make_rename_plan(files, SetName("Song"))
    assert [entry.problem for entry in plan.entries] == [RelocationProblem.DUPLICATE_TARGET] * 2


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
    outcomes = apply_relocation_plan(plan)
    assert outcomes == [RelocationOutcome(song, tmp_path / "X Song.mp3")]
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "Other.mp3",
        "X Other.mp3",
        "X Song.mp3",
    ]


def test_apply_refuses_target_created_after_planning(tmp_path: Path):
    [song] = make_files(tmp_path, "Song.mp3")
    plan = make_rename_plan([song], SetName("New"))
    (tmp_path / "New.mp3").write_text("keep me")
    [outcome] = apply_relocation_plan(plan)
    assert outcome.error == RelocationProblem.TARGET_EXISTS
    assert (tmp_path / "New.mp3").read_text() == "keep me"


def test_apply_reports_os_errors(tmp_path: Path):
    [song] = make_files(tmp_path, "Song.mp3")
    plan = make_rename_plan([song], SetName("New"))
    song.unlink()
    [outcome] = apply_relocation_plan(plan)
    assert outcome.error is not None
    assert not outcome.succeeded


def test_replace_relocated_paths_keeps_order_and_ignores_failures(tmp_path: Path):
    a, b, c = (tmp_path / name for name in ("a.mp3", "b.mp3", "c.mp3"))
    outcomes = [
        RelocationOutcome(a, tmp_path / "A.mp3"),
        RelocationOutcome(b, tmp_path / "B.mp3", "denied"),
    ]
    assert replace_relocated_paths([a, b, c], outcomes) == [tmp_path / "A.mp3", b, c]


def make_move_plan(paths: list[Path], folder: Path) -> RelocationPlan:
    return make_relocation_plan(paths, make_move_destination(folder))


def test_move_creates_destination_folder(tmp_path: Path):
    [song] = make_files(tmp_path, "Song.mp3")
    song.write_text("audio")
    outcomes = apply_relocation_plan(make_move_plan([song], tmp_path / "new" / "folder"))
    assert outcomes == [RelocationOutcome(song, tmp_path / "new/folder/Song.mp3")]
    assert (tmp_path / "new/folder/Song.mp3").read_text() == "audio"
    assert not song.exists()


def test_move_flattens_and_flags_same_names_from_different_folders(tmp_path: Path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    files = make_files(tmp_path, "a/Song.mp3", "b/Song.mp3", "b/Other.mp3")
    plan = make_move_plan(files, tmp_path / "dest")
    assert [entry.problem for entry in plan.entries] == [
        RelocationProblem.DUPLICATE_TARGET,
        RelocationProblem.DUPLICATE_TARGET,
        None,
    ]


def test_move_flags_existing_file_at_destination(tmp_path: Path):
    (tmp_path / "dest").mkdir()
    song, _ = make_files(tmp_path, "Song.mp3", "dest/Song.mp3")
    [entry] = make_move_plan([song], tmp_path / "dest").entries
    assert entry.problem == RelocationProblem.TARGET_EXISTS


def test_move_to_same_folder_is_skipped(tmp_path: Path):
    files = make_files(tmp_path, "Song.mp3")
    assert make_move_plan(files, tmp_path).entries == ()


def fail_rename_across_devices(self: Path, target: Path) -> Path:
    raise OSError(errno.EXDEV, "Invalid cross-device link")


def test_move_across_devices_copies_then_deletes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    [song] = make_files(tmp_path, "Song.mp3")
    song.write_text("audio")
    monkeypatch.setattr(Path, "rename", fail_rename_across_devices)
    [outcome] = apply_relocation_plan(make_move_plan([song], tmp_path / "dest"))
    assert outcome.succeeded
    assert (tmp_path / "dest/Song.mp3").read_text() == "audio"
    assert not song.exists()


def test_failed_copy_across_devices_keeps_source_and_removes_partial_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    [song] = make_files(tmp_path, "Song.mp3")

    def copy_partially(source: BinaryIO, target: BinaryIO) -> None:
        target.write(b"partial")
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(Path, "rename", fail_rename_across_devices)
    monkeypatch.setattr(shutil, "copyfileobj", copy_partially)
    [outcome] = apply_relocation_plan(make_move_plan([song], tmp_path / "dest"))
    assert not outcome.succeeded
    assert song.exists()
    assert not (tmp_path / "dest/Song.mp3").exists()


def test_other_rename_errors_are_not_retried_as_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    [song] = make_files(tmp_path, "Song.mp3")

    def deny(self: Path, target: Path) -> Path:
        raise PermissionError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(Path, "rename", deny)
    [outcome] = apply_relocation_plan(make_move_plan([song], tmp_path / "dest"))
    assert outcome.error is not None and "Permission denied" in outcome.error
    assert not (tmp_path / "dest/Song.mp3").exists()


def test_emptied_source_folders_are_removed_up_to_boundary(tmp_path: Path):
    (tmp_path / "list/disc").mkdir(parents=True)
    [song] = make_files(tmp_path, "list/disc/Song.mp3")
    outcomes = apply_relocation_plan(make_move_plan([song], tmp_path / "dest"))
    remove_emptied_folders(outcomes, tmp_path, protect_nothing)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["dest"]


def test_folders_with_remaining_files_are_kept(tmp_path: Path):
    (tmp_path / "list").mkdir()
    song, _ = make_files(tmp_path, "list/Song.mp3", "list/cover.jpg")
    outcomes = apply_relocation_plan(make_move_plan([song], tmp_path / "dest"))
    remove_emptied_folders(outcomes, tmp_path, protect_nothing)
    assert (tmp_path / "list/cover.jpg").exists()


def test_boundary_and_outside_folders_are_never_removed(tmp_path: Path):
    (tmp_path / "root").mkdir()
    (tmp_path / "outside").mkdir()
    files = make_files(tmp_path, "root/Song.mp3", "outside/Other.mp3")
    outcomes = apply_relocation_plan(make_move_plan(files, tmp_path / "dest"))
    remove_emptied_folders(outcomes, tmp_path / "root", protect_nothing)
    assert (tmp_path / "root").is_dir()
    assert (tmp_path / "outside").is_dir()


def test_failed_moves_do_not_trigger_folder_removal(tmp_path: Path):
    folder = tmp_path / "list"
    folder.mkdir()
    outcome = RelocationOutcome(folder / "Gone.mp3", tmp_path / "Gone.mp3", "missing")
    remove_emptied_folders([outcome], tmp_path, protect_nothing)
    assert folder.is_dir()


def test_folder_removal_stops_when_rmdir_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    folder = tmp_path / "list"
    folder.mkdir()

    def deny(self: Path) -> None:
        raise PermissionError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(Path, "rmdir", deny)
    remove_emptied_folders(
        [RelocationOutcome(folder / "Song.mp3", tmp_path / "Song.mp3")], tmp_path, protect_nothing
    )
    assert folder.is_dir()


def protect_nothing(folder: Path) -> bool:
    return False


def test_failed_source_delete_after_copy_removes_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    [song] = make_files(tmp_path, "Song.mp3")
    original_unlink = Path.unlink

    def deny_source_unlink(self: Path, missing_ok: bool = False) -> None:
        if self == song:
            raise PermissionError(errno.EACCES, "Permission denied")
        original_unlink(self, missing_ok)

    monkeypatch.setattr(Path, "rename", fail_rename_across_devices)
    monkeypatch.setattr(Path, "unlink", deny_source_unlink)
    [outcome] = apply_relocation_plan(make_move_plan([song], tmp_path / "dest"))
    assert not outcome.succeeded
    assert song.exists()
    assert not (tmp_path / "dest/Song.mp3").exists()


def test_copy_never_overwrites_file_appearing_after_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    [song] = make_files(tmp_path, "Song.mp3")
    plan = make_move_plan([song], tmp_path / "dest")
    monkeypatch.setattr(Path, "rename", fail_rename_across_devices)
    monkeypatch.setattr("masterit.library.relocation.is_taken", never_taken)
    (tmp_path / "dest").mkdir()
    (tmp_path / "dest/Song.mp3").write_text("someone else's")
    [outcome] = apply_relocation_plan(plan)
    assert not outcome.succeeded
    assert (tmp_path / "dest/Song.mp3").read_text() == "someone else's"
    assert song.exists()


def test_metadata_copy_failure_does_not_fail_move(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    [song] = make_files(tmp_path, "Song.mp3")
    song.write_text("audio")

    def deny_copystat(source: Path, target: Path) -> None:
        raise PermissionError(errno.EPERM, "Operation not permitted")

    monkeypatch.setattr(Path, "rename", fail_rename_across_devices)
    monkeypatch.setattr(shutil, "copystat", deny_copystat)
    [outcome] = apply_relocation_plan(make_move_plan([song], tmp_path / "dest"))
    assert outcome.succeeded
    assert (tmp_path / "dest/Song.mp3").read_text() == "audio"


def test_protected_folders_are_never_removed(tmp_path: Path):
    (tmp_path / "downloads/list").mkdir(parents=True)
    [song] = make_files(tmp_path, "downloads/list/Song.mp3")
    outcomes = apply_relocation_plan(make_move_plan([song], tmp_path / "dest"))
    remove_emptied_folders(outcomes, tmp_path, lambda folder: folder.name == "downloads")
    assert (tmp_path / "downloads").is_dir()
    assert not (tmp_path / "downloads/list").exists()


def test_cleanup_compares_resolved_paths(tmp_path: Path):
    (tmp_path / "real/list").mkdir(parents=True)
    (tmp_path / "link").symlink_to(tmp_path / "real")
    [song] = make_files(tmp_path, "real/list/Song.mp3")
    outcomes = apply_relocation_plan(make_move_plan([song], tmp_path / "dest"))
    remove_emptied_folders(outcomes, tmp_path / "link", protect_nothing)
    assert not (tmp_path / "real/list").exists()
    assert (tmp_path / "real").is_dir()


def never_taken(source: Path, target: Path) -> bool:
    return False


class FailingCloseFile(io.BytesIO):
    def close(self) -> None:
        if not self.closed:
            super().close()
            raise OSError(errno.EIO, "Input/output error")


def test_error_when_closing_copy_removes_partial_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    [song] = make_files(tmp_path, "Song.mp3")
    original_open = Path.open

    def open_with_failing_close(self: Path, mode: str = "r", *args: object) -> object:
        if mode != "xb":
            return original_open(self, mode)
        original_open(self, "xb").close()
        return FailingCloseFile()

    monkeypatch.setattr(Path, "rename", fail_rename_across_devices)
    monkeypatch.setattr(Path, "open", open_with_failing_close)
    [outcome] = apply_relocation_plan(make_move_plan([song], tmp_path / "dest"))
    assert not outcome.succeeded
    assert song.exists()
    assert not (tmp_path / "dest/Song.mp3").exists()


def test_copy_is_kept_when_source_vanished_meanwhile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    [song] = make_files(tmp_path, "Song.mp3")
    original_unlink = Path.unlink

    def vanish(self: Path, missing_ok: bool = False) -> None:
        if self == song:
            original_unlink(self)
            raise FileNotFoundError(errno.ENOENT, "No such file or directory")
        original_unlink(self, missing_ok)

    monkeypatch.setattr(Path, "rename", fail_rename_across_devices)
    monkeypatch.setattr(Path, "unlink", vanish)
    apply_relocation_plan(make_move_plan([song], tmp_path / "dest"))
    assert (tmp_path / "dest/Song.mp3").exists()


def test_failed_copy_removal_keeps_original_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    [song] = make_files(tmp_path, "Song.mp3")

    def deny_all_unlinks(self: Path, missing_ok: bool = False) -> None:
        message = "Permission denied" if self == song else "Device busy"
        raise PermissionError(errno.EACCES, message)

    monkeypatch.setattr(Path, "rename", fail_rename_across_devices)
    monkeypatch.setattr(Path, "unlink", deny_all_unlinks)
    [outcome] = apply_relocation_plan(make_move_plan([song], tmp_path / "dest"))
    assert outcome.error is not None and "Permission denied" in outcome.error
