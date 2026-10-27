import threading
from pathlib import Path

import pytest
from PySide6.QtWidgets import QFileDialog, QWidget
from pytestqt.qtbot import QtBot

from masterit.gui import move_job
from masterit.gui.library_panel import LibraryPanel
from masterit.gui.move_action import make_download_protection
from masterit.library.relocation import RelocationOutcome, RelocationPlan

from .library_helpers import (
    choose,
    get_names,
    make_files,
    make_panel,
    open_folder,
    select_rows,
)


def start_move(
    qtbot: QtBot, panel: LibraryPanel, folder: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", choose(str(folder)))
    with qtbot.waitSignal(panel.work_finished, timeout=2000):
        panel.move_action.move_button.click()


def add_session_files(panel: LibraryPanel, root: Path, *names: str) -> list[Path]:
    paths = make_files(root, *names)
    for path in paths:
        panel.add_downloaded_file(path)
    return paths


def test_move_without_selection_asks_for_it(qtbot: QtBot):
    panel = make_panel(qtbot)
    panel.move_action.move_button.click()
    assert panel.status_label.text() == "Select files to move."


def test_cancelled_folder_choice_moves_nothing(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    panel = make_panel(qtbot)
    [song] = add_session_files(panel, tmp_path, "Song.mp3")
    select_rows(panel, 0)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", choose(""))
    panel.move_action.move_button.click()
    assert song.exists()


def test_declined_confirmation_moves_nothing(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    asked: list[tuple[int, Path]] = []

    def decline(parent: QWidget, plan: RelocationPlan, folder: Path) -> bool:
        asked.append((len(plan.entries), folder))
        return False

    panel = make_panel(qtbot, confirm_move=decline)
    [song] = add_session_files(panel, tmp_path, "Song.mp3")
    select_rows(panel, 0)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", choose(str(tmp_path / "dest")))
    panel.move_action.move_button.click()
    assert asked == [(1, tmp_path / "dest")]
    assert song.exists()


def test_confirmed_move_updates_session_and_cleans_download_folder(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    downloads = tmp_path / "downloads"
    panel = make_panel(qtbot, download_folder=downloads)
    add_session_files(panel, downloads, "list/A.mp3", "list/B.mp3", "C.mp3")
    select_rows(panel, 0, 1)
    start_move(qtbot, panel, tmp_path / "library", monkeypatch)
    assert sorted(path.name for path in (tmp_path / "library").iterdir()) == ["A.mp3", "B.mp3"]
    assert not (downloads / "list").exists()
    assert panel.table_model.get_files() == [
        tmp_path / "library/A.mp3",
        tmp_path / "library/B.mp3",
        downloads / "C.mp3",
    ]
    assert panel.status_label.text() == "2 moved, 0 skipped, 0 failed."


def test_move_out_of_opened_folder_removes_rows_and_emptied_subfolders(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    panel = make_panel(qtbot)
    make_files(tmp_path / "root", "list/A.mp3", "B.mp3")
    open_folder(panel, tmp_path / "root", monkeypatch)
    select_rows(panel, 1)
    start_move(qtbot, panel, tmp_path / "library", monkeypatch)
    assert get_names(panel) == ["B.mp3"]
    assert not (tmp_path / "root/list").exists()
    assert (tmp_path / "root").is_dir()


def test_move_into_subfolder_of_opened_folder_keeps_row(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    panel = make_panel(qtbot)
    make_files(tmp_path, "A.mp3")
    open_folder(panel, tmp_path, monkeypatch)
    select_rows(panel, 0)
    start_move(qtbot, panel, tmp_path / "sorted", monkeypatch)
    assert panel.table_model.get_files() == [tmp_path / "sorted/A.mp3"]


def test_skipped_files_are_counted(qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    panel = make_panel(qtbot)
    add_session_files(panel, tmp_path, "a/Song.mp3", "b/Song.mp3", "c/Other.mp3")
    select_rows(panel, 0, 1, 2)
    start_move(qtbot, panel, tmp_path / "library", monkeypatch)
    assert panel.status_label.text() == "1 moved, 2 skipped, 0 failed."


def test_actions_are_locked_and_progress_shown_while_moving(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    release = threading.Event()

    def relocate_slowly(source: Path, target: Path) -> RelocationOutcome:
        release.wait(5)
        return RelocationOutcome(source, target)

    monkeypatch.setattr(move_job, "relocate_file", relocate_slowly)
    panel = make_panel(qtbot)
    add_session_files(panel, tmp_path, "A.mp3")
    select_rows(panel, 0)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", choose(str(tmp_path / "dest")))
    panel.move_action.move_button.click()
    try:
        assert panel.is_busy
        assert panel.status_label.text() == "Moving 0/1\u2026"
        assert not panel.move_action.move_button.isEnabled()
        assert not panel.table_view.isEnabled()
    finally:
        with qtbot.waitSignal(panel.work_finished, timeout=2000):
            release.set()
    assert not panel.is_busy
    assert panel.move_action.move_button.isEnabled()
    assert panel.table_view.isEnabled()


def test_unexpected_error_is_shown(qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    def crash(source: Path, target: Path) -> RelocationOutcome:
        raise RuntimeError("boom")

    monkeypatch.setattr(move_job, "relocate_file", crash)
    panel = make_panel(qtbot)
    add_session_files(panel, tmp_path, "A.mp3")
    select_rows(panel, 0)
    start_move(qtbot, panel, tmp_path / "dest", monkeypatch)
    assert panel.status_label.text() == "Move stopped by an unexpected error: boom"


def test_download_folder_itself_is_never_removed(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    downloads = tmp_path / "Musique/YT_DL"
    panel = make_panel(qtbot, download_folder=downloads)
    make_files(downloads, "Song.mp3")
    open_folder(panel, tmp_path / "Musique", monkeypatch)
    select_rows(panel, 0)
    start_move(qtbot, panel, tmp_path / "library", monkeypatch)
    assert downloads.is_dir()


def test_download_subfolders_are_kept_while_downloading(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    downloads = tmp_path / "downloads"
    panel = make_panel(qtbot, download_folder=downloads, is_downloading=lambda: True)
    add_session_files(panel, downloads, "list/A.mp3")
    select_rows(panel, 0)
    start_move(qtbot, panel, tmp_path / "library", monkeypatch)
    assert (downloads / "list").is_dir()


def test_selection_is_read_after_folder_choice(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    panel = make_panel(qtbot)
    add_session_files(panel, tmp_path, "A.mp3", "B.mp3")
    select_rows(panel, 0)

    def choose_after_selecting_more(*args: object) -> str:
        select_rows(panel, 1)
        return str(tmp_path / "library")

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", choose_after_selecting_more)
    with qtbot.waitSignal(panel.work_finished, timeout=2000):
        panel.move_action.move_button.click()
    assert sorted(path.name for path in (tmp_path / "library").iterdir()) == ["A.mp3", "B.mp3"]


def test_rows_inside_symlinked_opened_folder_stay_listed(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    (tmp_path / "real").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "real")
    panel = make_panel(qtbot)
    make_files(tmp_path / "real", "A.mp3")
    open_folder(panel, tmp_path / "link", monkeypatch)
    select_rows(panel, 0)
    start_move(qtbot, panel, tmp_path / "real/sorted", monkeypatch)
    assert get_names(panel) == ["A.mp3"]


def test_renames_are_refused_while_moving(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    release = threading.Event()

    def relocate_slowly(source: Path, target: Path) -> RelocationOutcome:
        release.wait(5)
        return RelocationOutcome(source, target)

    monkeypatch.setattr(move_job, "relocate_file", relocate_slowly)
    panel = make_panel(qtbot)
    [_, other] = add_session_files(panel, tmp_path, "A.mp3", "B.mp3")
    select_rows(panel, 0)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", choose(str(tmp_path / "dest")))
    try:
        panel.move_action.move_button.click()
        panel.rename_bar.rename_single_file(other, "New")
        panel.rename_bar.apply_rename()
        assert other.exists()
    finally:
        with qtbot.waitSignal(panel.work_finished, timeout=2000):
            release.set()


def test_symlinked_files_stay_listed_after_relocation(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "elsewhere/Linked.mp3").touch()
    (tmp_path / "library").mkdir()
    (tmp_path / "library/Linked.mp3").symlink_to(tmp_path / "elsewhere/Linked.mp3")
    make_files(tmp_path / "library", "Song.mp3")
    panel = make_panel(qtbot)
    open_folder(panel, tmp_path / "library", monkeypatch)
    select_rows(panel, 1)
    start_move(qtbot, panel, tmp_path / "library/sorted", monkeypatch)
    assert get_names(panel) == ["Linked.mp3", "Song.mp3"]


def test_download_protection_follows_download_state(tmp_path: Path):
    downloading = [False]
    is_protected = make_download_protection(tmp_path, lambda: downloading[0])
    assert is_protected(tmp_path)
    assert not is_protected(tmp_path / "list")
    downloading[0] = True
    assert is_protected(tmp_path / "list")
