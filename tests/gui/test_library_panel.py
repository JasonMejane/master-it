from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog, QLineEdit
from pytestqt.qtbot import QtBot

from masterit.gui.library_panel import LibraryPanel
from masterit.library.rename_rules import AddPrefix, AddSuffix, RemoveText

from .library_helpers import choose, get_names, make_files, make_panel, open_folder, select_rows


def get_previews(panel: LibraryPanel) -> list[object]:
    model = panel.table_model
    return [model.data(model.index(row, 1)) for row in range(model.rowCount())]


def set_rule(panel: LibraryPanel, rule: type, text: str) -> None:
    panel.operation_input.setCurrentIndex(panel.operation_input.findData(rule))
    panel.rename_text_input.setText(text)


def test_starts_with_empty_session(qtbot: QtBot):
    panel = make_panel(qtbot)
    assert panel.table_model.rowCount() == 0
    assert panel.source_label.text() == "This session's downloads"
    assert not panel.apply_button.isEnabled()


def test_downloaded_files_are_added_to_session(qtbot: QtBot, tmp_path: Path):
    panel = make_panel(qtbot)
    [song] = make_files(tmp_path, "Song.mp3")
    panel.add_downloaded_file(song)
    assert get_names(panel) == ["Song.mp3"]


def test_open_folder_lists_its_audio_files(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    panel = make_panel(qtbot)
    make_files(tmp_path, "b.mp3", "list/a.flac", "cover.jpg")
    open_folder(panel, tmp_path, monkeypatch)
    assert get_names(panel) == ["b.mp3", "a.flac"]
    assert panel.source_label.text() == f"Folder: {tmp_path}"


def test_cancelled_folder_choice_keeps_list(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    panel = make_panel(qtbot)
    panel.add_downloaded_file(make_files(tmp_path, "Song.mp3")[0])
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", choose(""))
    panel.open_folder_button.click()
    assert get_names(panel) == ["Song.mp3"]


def test_downloads_while_folder_open_go_to_session_only(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    panel = make_panel(qtbot)
    (tmp_path / "folder").mkdir()
    open_folder(panel, tmp_path / "folder", monkeypatch)
    panel.add_downloaded_file(make_files(tmp_path, "Song.mp3")[0])
    assert get_names(panel) == []
    panel.session_button.click()
    assert get_names(panel) == ["Song.mp3"]
    assert panel.source_label.text() == "This session's downloads"


def test_preview_follows_selection_and_rule(qtbot: QtBot, tmp_path: Path):
    panel = make_panel(qtbot)
    for path in make_files(tmp_path, "A (Official Video).mp3", "B (Official Video).mp3"):
        panel.add_downloaded_file(path)
    set_rule(panel, RemoveText, "Official Video")
    assert get_previews(panel) == ["", ""]
    select_rows(panel, 1)
    assert get_previews(panel) == ["", "B.mp3"]
    assert panel.apply_button.isEnabled()
    set_rule(panel, AddSuffix, " (Live)")
    assert get_previews(panel) == ["", "B (Official Video) (Live).mp3"]


def test_apply_renames_selected_files_and_reports(qtbot: QtBot, tmp_path: Path):
    panel = make_panel(qtbot)
    for path in make_files(tmp_path, "A.mp3", "B.mp3", "X B.mp3"):
        panel.add_downloaded_file(path)
    select_rows(panel, 0, 1)
    set_rule(panel, AddPrefix, "X ")
    panel.apply_button.click()
    assert get_names(panel) == ["X A.mp3", "B.mp3", "X B.mp3"]
    assert (tmp_path / "X A.mp3").exists()
    assert panel.status_label.text() == "1 renamed, 1 skipped, 0 failed."
    assert panel.rename_text_input.text() == ""
    assert not panel.apply_button.isEnabled()


def test_apply_in_folder_updates_rows_in_place(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    panel = make_panel(qtbot)
    make_files(tmp_path, "B.mp3", "C.mp3")
    open_folder(panel, tmp_path, monkeypatch)
    select_rows(panel, 1)
    set_rule(panel, AddPrefix, "A ")
    panel.apply_button.click()
    assert get_names(panel) == ["B.mp3", "A C.mp3"]


def test_renamed_session_file_keeps_new_path_in_session(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    panel = make_panel(qtbot)
    [song] = make_files(tmp_path, "Song.mp3")
    panel.add_downloaded_file(song)
    open_folder(panel, tmp_path, monkeypatch)
    select_rows(panel, 0)
    set_rule(panel, AddPrefix, "X ")
    panel.apply_button.click()
    panel.session_button.click()
    assert get_names(panel) == ["X Song.mp3"]


def test_failed_rename_shows_error(qtbot: QtBot, tmp_path: Path):
    panel = make_panel(qtbot)
    [song] = make_files(tmp_path, "Song.mp3")
    panel.add_downloaded_file(song)
    select_rows(panel, 0)
    set_rule(panel, AddPrefix, "X ")
    song.unlink()
    panel.apply_button.click()
    assert panel.status_label.text().startswith("0 renamed, 0 skipped, 1 failed. Song.mp3: ")


def edit_name(qtbot: QtBot, panel: LibraryPanel, row: int, name: str) -> None:
    view = panel.table_view
    view.edit(panel.table_model.index(row, 0))
    editor = view.viewport().findChild(QLineEdit)
    assert editor is not None
    editor.setText(name)
    QTest.keyClick(editor, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: panel.status_label.text() != "", timeout=1000)


def test_editing_name_renames_single_file(qtbot: QtBot, tmp_path: Path):
    panel = make_panel(qtbot)
    panel.show()
    [song] = make_files(tmp_path, "Song.mp3")
    panel.add_downloaded_file(song)
    edit_name(qtbot, panel, 0, "New")
    assert get_names(panel) == ["New.mp3"]
    assert panel.status_label.text() == "1 renamed, 0 skipped, 0 failed."
    assert panel.table_view.viewport().findChildren(QLineEdit) == []


def test_editing_name_with_extension_keeps_single_extension(qtbot: QtBot, tmp_path: Path):
    panel = make_panel(qtbot)
    panel.show()
    panel.add_downloaded_file(make_files(tmp_path, "Song.mp3")[0])
    edit_name(qtbot, panel, 0, "New.MP3")
    assert get_names(panel) == ["New.mp3"]


def test_editing_name_to_taken_name_shows_problem(qtbot: QtBot, tmp_path: Path):
    panel = make_panel(qtbot)
    for path in make_files(tmp_path, "Song.mp3", "Other.mp3"):
        panel.add_downloaded_file(path)
    panel.show()
    edit_name(qtbot, panel, 0, "Other")
    assert get_names(panel) == ["Song.mp3", "Other.mp3"]
    assert panel.status_label.text() == "A file with this name already exists"


def test_editing_name_unchanged_does_nothing(qtbot: QtBot, tmp_path: Path):
    panel = make_panel(qtbot)
    panel.add_downloaded_file(make_files(tmp_path, "Song.mp3")[0])
    panel.rename_single_file(panel.table_model.get_path(0), "Song")
    assert panel.status_label.text() == ""


def test_same_download_twice_is_listed_once(qtbot: QtBot, tmp_path: Path):
    panel = make_panel(qtbot)
    [song] = make_files(tmp_path, "Song.mp3")
    panel.add_downloaded_file(song)
    panel.add_downloaded_file(song)
    assert get_names(panel) == ["Song.mp3"]
