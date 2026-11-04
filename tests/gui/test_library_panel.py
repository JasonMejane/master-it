from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog, QLabel, QLineEdit, QPushButton
from pytestqt.qtbot import QtBot

from masterit.gui.library_panel import LibraryPanel
from masterit.tags.fields import TagField

from ..tags.fakes import FakeTagStore
from .library_helpers import choose, get_names, make_files, make_panel, open_folder, select_rows


def get_previews(panel: LibraryPanel) -> list[object]:
    model = panel.table_model
    return [model.data(model.index(row, 1)) for row in range(model.rowCount())]


def set_rule(panel: LibraryPanel, label: str, text: str) -> None:
    panel.rename_bar.operation_input.setCurrentText(label)
    panel.rename_bar.rename_text_input.setText(text)


def test_starts_with_empty_session(qtbot: QtBot):
    panel = make_panel(qtbot)
    assert panel.table_model.rowCount() == 0
    assert panel.source_bar.source_label.text() == "This session's downloads"
    assert not panel.rename_bar.apply_button.isEnabled()


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
    assert panel.source_bar.source_label.text() == f"Folder: {tmp_path}"


def test_cancelled_folder_choice_keeps_list(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    panel = make_panel(qtbot)
    panel.add_downloaded_file(make_files(tmp_path, "Song.mp3")[0])
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", choose(""))
    panel.source_bar.open_folder_button.click()
    assert get_names(panel) == ["Song.mp3"]


def test_downloads_while_folder_open_go_to_session_only(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    panel = make_panel(qtbot)
    (tmp_path / "folder").mkdir()
    open_folder(panel, tmp_path / "folder", monkeypatch)
    panel.add_downloaded_file(make_files(tmp_path, "Song.mp3")[0])
    assert get_names(panel) == []
    panel.source_bar.session_button.click()
    assert get_names(panel) == ["Song.mp3"]
    assert panel.source_bar.source_label.text() == "This session's downloads"


def test_preview_follows_selection_and_rule(qtbot: QtBot, tmp_path: Path):
    panel = make_panel(qtbot)
    for path in make_files(tmp_path, "A (Official Video).mp3", "B (Official Video).mp3"):
        panel.add_downloaded_file(path)
    set_rule(panel, "Remove text", "Official Video")
    assert get_previews(panel) == ["", ""]
    select_rows(panel, 1)
    assert get_previews(panel) == ["", "B.mp3"]
    assert panel.rename_bar.apply_button.isEnabled()
    set_rule(panel, "Add suffix", " (Live)")
    assert get_previews(panel) == ["", "B (Official Video) (Live).mp3"]


def test_apply_renames_selected_files_and_reports(qtbot: QtBot, tmp_path: Path):
    panel = make_panel(qtbot)
    for path in make_files(tmp_path, "A.mp3", "B.mp3", "X B.mp3"):
        panel.add_downloaded_file(path)
    select_rows(panel, 0, 1)
    set_rule(panel, "Add prefix", "X ")
    panel.rename_bar.apply_button.click()
    assert get_names(panel) == ["X A.mp3", "B.mp3", "X B.mp3"]
    assert (tmp_path / "X A.mp3").exists()
    assert panel.status_label.text() == "1 renamed, 1 skipped, 0 failed."
    assert panel.rename_bar.rename_text_input.text() == ""
    assert not panel.rename_bar.apply_button.isEnabled()


def test_apply_in_folder_updates_rows_in_place(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    panel = make_panel(qtbot)
    make_files(tmp_path, "B.mp3", "C.mp3")
    open_folder(panel, tmp_path, monkeypatch)
    select_rows(panel, 1)
    set_rule(panel, "Add prefix", "A ")
    panel.rename_bar.apply_button.click()
    assert get_names(panel) == ["B.mp3", "A C.mp3"]


def test_renamed_session_file_keeps_new_path_in_session(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    panel = make_panel(qtbot)
    [song] = make_files(tmp_path, "Song.mp3")
    panel.add_downloaded_file(song)
    open_folder(panel, tmp_path, monkeypatch)
    select_rows(panel, 0)
    set_rule(panel, "Add prefix", "X ")
    panel.rename_bar.apply_button.click()
    panel.source_bar.session_button.click()
    assert get_names(panel) == ["X Song.mp3"]


def test_failed_rename_shows_error(qtbot: QtBot, tmp_path: Path):
    panel = make_panel(qtbot)
    [song] = make_files(tmp_path, "Song.mp3")
    panel.add_downloaded_file(song)
    select_rows(panel, 0)
    set_rule(panel, "Add prefix", "X ")
    song.unlink()
    panel.rename_bar.apply_button.click()
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
    panel.rename_bar.rename_single_file(panel.table_model.get_path(0), "Song")
    assert panel.status_label.text() == ""


def test_same_download_twice_is_listed_once(qtbot: QtBot, tmp_path: Path):
    panel = make_panel(qtbot)
    [song] = make_files(tmp_path, "Song.mp3")
    panel.add_downloaded_file(song)
    panel.add_downloaded_file(song)
    assert get_names(panel) == ["Song.mp3"]


def test_table_and_side_panel_share_a_splitter(qtbot: QtBot):
    panel = make_panel(qtbot)
    splitter = panel.content_splitter
    table_part, side_panel = splitter.widget(0), splitter.widget(1)
    assert table_part is not None
    assert table_part.isAncestorOf(panel.table_view)
    assert side_panel is not None
    assert side_panel.isAncestorOf(panel.tag_form)
    assert side_panel.isAncestorOf(panel.cover_view)
    assert not splitter.childrenCollapsible()


def test_side_panel_takes_about_a_third_by_default(qtbot: QtBot):
    panel = make_panel(qtbot)
    panel.resize(1500, 800)
    panel.show()
    table_width, side_width = panel.content_splitter.sizes()
    assert side_width / (table_width + side_width) == pytest.approx(0.3, abs=0.05)


def make_tagged_files_panel(qtbot: QtBot, tmp_path: Path) -> LibraryPanel:
    tagged, untitled = make_files(tmp_path, "x.mp3", "y.mp3")
    store = FakeTagStore(
        {
            tagged: {TagField.ARTIST: "Queen", TagField.TITLE: "Jazz"},
            untitled: {TagField.ARTIST: "Queen"},
        }
    )
    panel = make_panel(qtbot, tag_store=store)
    for path in (tagged, untitled):
        panel.add_downloaded_file(path)
    return panel


def test_name_from_tags_previews_names_in_the_rename_bar(qtbot: QtBot, tmp_path: Path):
    panel = make_tagged_files_panel(qtbot, tmp_path)
    select_rows(panel, 0, 1)
    panel.tag_form.name_from_tags_button.click()
    assert panel.rename_bar.operation_input.currentText() == "Name from tags"
    assert not panel.rename_bar.rename_text_input.isEnabled()
    assert get_previews(panel) == ["Queen - Jazz.mp3", "⚠ No title tag"]
    assert panel.rename_bar.apply_button.isEnabled()


def test_name_from_tags_renames_on_apply(qtbot: QtBot, tmp_path: Path):
    panel = make_tagged_files_panel(qtbot, tmp_path)
    select_rows(panel, 0, 1)
    panel.tag_form.name_from_tags_button.click()
    panel.rename_bar.apply_button.click()
    assert get_names(panel) == ["Queen - Jazz.mp3", "y.mp3"]
    assert (tmp_path / "Queen - Jazz.mp3").exists()
    assert panel.status_label.text() == "1 renamed, 1 skipped, 0 failed."


def test_text_operations_use_the_text_again(qtbot: QtBot, tmp_path: Path):
    panel = make_tagged_files_panel(qtbot, tmp_path)
    select_rows(panel, 0)
    panel.tag_form.name_from_tags_button.click()
    set_rule(panel, "Add prefix", "A ")
    assert panel.rename_bar.rename_text_input.isEnabled()
    assert get_previews(panel)[0] == "A x.mp3"


def test_overwritten_download_refreshes_the_name_from_tags_preview(qtbot: QtBot, tmp_path: Path):
    [song] = make_files(tmp_path, "x.mp3")
    store = FakeTagStore({song: {TagField.ARTIST: "Queen", TagField.TITLE: "Jazz"}})
    panel = make_panel(qtbot, tag_store=store)
    panel.add_downloaded_file(song)
    select_rows(panel, 0)
    panel.tag_form.name_from_tags_button.click()
    store.tags[song] = {TagField.ARTIST: "Queen", TagField.TITLE: "Mustapha"}
    panel.add_downloaded_file(song)
    assert get_previews(panel) == ["Queen - Mustapha.mp3"]


NO_MATCH_HINT = "No selected file name (without extension) contains this text."


def make_song_panel(qtbot: QtBot, tmp_path: Path, *names: str) -> LibraryPanel:
    panel = make_panel(qtbot)
    for path in make_files(tmp_path, *names):
        panel.add_downloaded_file(path)
    return panel


def get_hint(panel: LibraryPanel) -> str:
    return panel.rename_bar.hint_label.text()


def test_unmatched_removal_says_so(qtbot: QtBot, tmp_path: Path):
    panel = make_song_panel(qtbot, tmp_path, "Song.mp3")
    select_rows(panel, 0)
    set_rule(panel, "Remove text", "Video")
    assert get_hint(panel) == NO_MATCH_HINT
    assert not panel.rename_bar.apply_button.isEnabled()


def test_hint_clears_once_the_text_matches(qtbot: QtBot, tmp_path: Path):
    panel = make_song_panel(qtbot, tmp_path, "Song Video.mp3")
    select_rows(panel, 0)
    set_rule(panel, "Remove text", "Videx")
    set_rule(panel, "Remove text", "Video")
    assert get_hint(panel) == ""


def test_hint_follows_the_selection(qtbot: QtBot, tmp_path: Path):
    panel = make_song_panel(qtbot, tmp_path, "Song.mp3", "Song Video.mp3")
    set_rule(panel, "Remove text", "Video")
    assert get_hint(panel) == ""
    select_rows(panel, 0)
    assert get_hint(panel) == NO_MATCH_HINT
    panel.table_view.clearSelection()
    select_rows(panel, 1)
    assert get_hint(panel) == ""


@pytest.mark.parametrize(
    ("label", "text"), [("Remove text", ""), ("Remove text", "   "), ("Add prefix", "X ")]
)
def test_no_hint_without_text_or_for_other_rules(
    qtbot: QtBot, tmp_path: Path, label: str, text: str
):
    panel = make_song_panel(qtbot, tmp_path, "Song.mp3")
    select_rows(panel, 0)
    set_rule(panel, label, text)
    assert get_hint(panel) == ""


def test_hint_leaves_the_status_alone(qtbot: QtBot, tmp_path: Path):
    panel = make_song_panel(qtbot, tmp_path, "Song.mp3")
    select_rows(panel, 0)
    panel.show_status("2 tagged, 0 failed.")
    set_rule(panel, "Remove text", "Video")
    assert panel.status_label.text() == "2 tagged, 0 failed."


def test_name_from_tags_with_names_already_right_gives_no_hint(qtbot: QtBot, tmp_path: Path):
    [song] = make_files(tmp_path, "Queen - Jazz.mp3")
    store = FakeTagStore({song: {TagField.ARTIST: "Queen", TagField.TITLE: "Jazz"}})
    panel = make_panel(qtbot, tag_store=store)
    panel.add_downloaded_file(song)
    select_rows(panel, 0)
    set_rule(panel, "Remove text", "x")
    panel.tag_form.name_from_tags_button.click()
    assert get_hint(panel) == ""


def test_hint_does_not_move_the_rename_bar(qtbot: QtBot, tmp_path: Path):
    panel = make_song_panel(qtbot, tmp_path, "Song.mp3")
    panel.resize(900, 600)
    panel.show()
    select_rows(panel, 0)
    set_rule(panel, "Remove text", "Song")
    sizes = (panel.rename_bar.rename_text_input.size(), panel.minimumSizeHint())
    set_rule(panel, "Remove text", "Video")
    qtbot.wait(10)
    assert get_hint(panel) == NO_MATCH_HINT
    assert (panel.rename_bar.rename_text_input.size(), panel.minimumSizeHint()) == sizes


def test_panel_is_split_into_titled_sections(qtbot: QtBot):
    panel = make_panel(qtbot)
    titles = sorted(label.text() for label in panel.findChildren(QLabel, "sectionTitle"))
    assert titles == ["Files", "Tag editor"]


def test_rename_bar_sits_with_the_files(qtbot: QtBot):
    panel = make_panel(qtbot)
    files_part = panel.content_splitter.widget(0)
    assert files_part is not None
    assert files_part.isAncestorOf(panel.rename_bar)


def test_main_actions_are_primary_and_buttons_have_icons(qtbot: QtBot):
    panel = make_panel(qtbot)
    primary = [panel.tag_form.apply_button, panel.rename_bar.apply_button]
    primary.append(panel.auto_tag_action.auto_tag_button)
    assert all(button.property("role") == "primary" for button in primary)
    assert all(not button.icon().isNull() for button in panel.findChildren(QPushButton))
    assert panel.status_label.property("muted") is True


def test_files_are_striped_without_row_numbers(qtbot: QtBot):
    panel = make_panel(qtbot)
    assert panel.table_view.alternatingRowColors()
    assert panel.table_view.verticalHeader().isHidden()


def test_path_labels_shrink_instead_of_widening_the_panel(qtbot: QtBot):
    panel = make_panel(qtbot)
    width = panel.minimumSizeHint().width()
    long_path = "/music/" + "long-folder/" * 30
    panel.source_bar.source_label.setText(long_path)
    panel.auto_tag_action.root_label.setText(long_path)
    assert panel.minimumSizeHint().width() == width
