import threading
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from pytestqt.qtbot import QtBot

from masterit.gui import tag_job
from masterit.gui.library_panel import LibraryPanel
from masterit.tags.fields import TagField, Tags
from masterit.tags.tag_edits import TagOutcome
from masterit.tags.tag_store import TagStore

from ..tags.fakes import FakeTagStore
from .library_helpers import make_panel, select_rows

SONG_A = Path("/music/a.mp3")
SONG_B = Path("/music/b.mp3")
STORED_TAGS = {
    SONG_A: {TagField.ARTIST: "Artist", TagField.TITLE: "One", TagField.YEAR: "2020"},
    SONG_B: {TagField.ARTIST: "Artist", TagField.TITLE: "Two"},
}
TITLE_COLUMN = 3
ARTIST_COLUMN = 4
GENRE_COLUMN = 8
COMMENT_COLUMN = 10


def make_tag_panel(qtbot: QtBot, store: FakeTagStore | None = None) -> LibraryPanel:
    panel = make_panel(qtbot, tag_store=store or FakeTagStore(STORED_TAGS))
    panel.add_downloaded_file(SONG_A)
    panel.add_downloaded_file(SONG_B)
    return panel


def get_input_text(panel: LibraryPanel, field: TagField) -> str:
    return panel.tag_form.field_inputs[field].text()


def type_tag(panel: LibraryPanel, field: TagField, text: str) -> None:
    line = panel.tag_form.field_inputs[field]
    line.selectAll()
    QTest.keyClick(line, Qt.Key.Key_Delete)
    QTest.keyClicks(line, text)


def get_cell(panel: LibraryPanel, row: int, column: int, role: int = 0) -> object:
    return panel.table_model.data(panel.table_model.index(row, column), role)


def apply_tags(qtbot: QtBot, panel: LibraryPanel) -> None:
    with qtbot.waitSignal(panel.work_finished, timeout=2000):
        panel.tag_form.apply_button.click()


def test_form_is_disabled_without_selection(qtbot: QtBot):
    panel = make_tag_panel(qtbot)
    assert not panel.tag_form.field_inputs[TagField.TITLE].isEnabled()
    assert not panel.tag_form.apply_button.isEnabled()


def test_selecting_one_file_loads_its_tags(qtbot: QtBot):
    panel = make_tag_panel(qtbot)
    select_rows(panel, 0)
    assert get_input_text(panel, TagField.TITLE) == "One"
    assert get_input_text(panel, TagField.YEAR) == "2020"
    assert get_input_text(panel, TagField.GENRE) == ""
    assert panel.tag_form.field_inputs[TagField.TITLE].isEnabled()


def test_selecting_several_files_shows_shared_values_only(qtbot: QtBot):
    panel = make_tag_panel(qtbot)
    select_rows(panel, 0, 1)
    title_input = panel.tag_form.field_inputs[TagField.TITLE]
    assert get_input_text(panel, TagField.ARTIST) == "Artist"
    assert title_input.text() == ""
    assert title_input.placeholderText() == "<multiple values>"
    assert panel.tag_form.field_inputs[TagField.ARTIST].placeholderText() == ""


def test_edits_are_previewed_on_selected_rows(qtbot: QtBot):
    panel = make_tag_panel(qtbot)
    select_rows(panel, 0)
    type_tag(panel, TagField.GENRE, "Rock")
    assert get_cell(panel, 0, GENRE_COLUMN) == "Rock"
    assert get_cell(panel, 1, GENRE_COLUMN) == ""
    role = Qt.ItemDataRole.ForegroundRole
    assert get_cell(panel, 0, GENRE_COLUMN, role) == QColor(Qt.GlobalColor.blue)
    assert panel.tag_form.apply_button.isEnabled()


def test_invalid_value_is_refused(qtbot: QtBot):
    panel = make_tag_panel(qtbot)
    select_rows(panel, 0)
    type_tag(panel, TagField.YEAR, "20")
    assert not panel.tag_form.apply_button.isEnabled()
    assert panel.tag_form.problem_label.text() == "Year must look like 2024 or 2024-05-17."
    type_tag(panel, TagField.YEAR, "2021")
    assert panel.tag_form.apply_button.isEnabled()
    assert panel.tag_form.problem_label.text() == ""


def test_apply_writes_only_edited_fields_to_selected_files(qtbot: QtBot):
    store = FakeTagStore(STORED_TAGS)
    panel = make_tag_panel(qtbot, store)
    select_rows(panel, 0, 1)
    type_tag(panel, TagField.GENRE, "Rock")
    apply_tags(qtbot, panel)
    assert store.tags[SONG_A] == {**STORED_TAGS[SONG_A], TagField.GENRE: "Rock"}
    assert store.tags[SONG_B] == {**STORED_TAGS[SONG_B], TagField.GENRE: "Rock"}
    assert panel.status_label.text() == "2 tagged, 0 failed."
    assert get_cell(panel, 1, TITLE_COLUMN) == "Two"
    assert get_cell(panel, 1, GENRE_COLUMN, Qt.ItemDataRole.ForegroundRole) is None
    assert get_input_text(panel, TagField.GENRE) == "Rock"
    assert not panel.tag_form.apply_button.isEnabled()


def test_clearing_a_field_removes_the_tag(qtbot: QtBot):
    store = FakeTagStore(STORED_TAGS)
    panel = make_tag_panel(qtbot, store)
    select_rows(panel, 0)
    type_tag(panel, TagField.YEAR, "")
    apply_tags(qtbot, panel)
    assert store.tags[SONG_A][TagField.YEAR] == ""
    assert get_cell(panel, 0, 7) == ""


def test_failures_are_reported(qtbot: QtBot):
    panel = make_tag_panel(qtbot, FakeTagStore(STORED_TAGS, failing={SONG_A}))
    select_rows(panel, 0, 1)
    type_tag(panel, TagField.GENRE, "Rock")
    apply_tags(qtbot, panel)
    assert panel.status_label.text() == "1 tagged, 1 failed. a.mp3: read-only"


def test_reset_discards_edits(qtbot: QtBot):
    panel = make_tag_panel(qtbot)
    select_rows(panel, 0)
    type_tag(panel, TagField.TITLE, "New")
    panel.tag_form.reset_button.click()
    assert get_input_text(panel, TagField.TITLE) == "One"
    assert get_cell(panel, 0, TITLE_COLUMN) == "One"
    assert not panel.tag_form.apply_button.isEnabled()
    assert not panel.tag_form.reset_button.isEnabled()


def test_selection_change_discards_edits(qtbot: QtBot):
    panel = make_tag_panel(qtbot)
    select_rows(panel, 0)
    type_tag(panel, TagField.TITLE, "New")
    select_rows(panel, 1)
    assert get_input_text(panel, TagField.TITLE) == ""
    assert get_cell(panel, 0, TITLE_COLUMN) == "One"


def test_actions_are_locked_while_tagging(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch):
    release = threading.Event()

    def write_slowly(path: Path, edits: Tags, store: TagStore) -> TagOutcome:
        release.wait(5)
        return TagOutcome(path)

    monkeypatch.setattr(tag_job, "write_tag_edits", write_slowly)
    panel = make_tag_panel(qtbot)
    select_rows(panel, 0)
    type_tag(panel, TagField.GENRE, "Rock")
    panel.tag_form.apply_button.click()
    try:
        assert panel.is_busy
        assert panel.status_label.text() == "Tagging 0/1…"
        assert not panel.tag_form.isEnabled()
        assert not panel.move_action.isEnabled()
        assert not panel.table_view.isEnabled()
        panel.tag_form.apply_tags()
        panel.rename_bar.rename_single_file(SONG_A, "x")
        assert panel.status_label.text() == "Busy: rename ignored."
    finally:
        with qtbot.waitSignal(panel.work_finished, timeout=2000):
            release.set()
    assert not panel.is_busy
    assert panel.tag_form.isEnabled()
    assert panel.table_model.get_path(0) == SONG_A


def test_unexpected_error_is_reported(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch):
    def crash(path: Path, edits: Tags, store: TagStore) -> TagOutcome:
        raise RuntimeError("boom")

    monkeypatch.setattr(tag_job, "write_tag_edits", crash)
    panel = make_tag_panel(qtbot)
    select_rows(panel, 0)
    type_tag(panel, TagField.GENRE, "Rock")
    apply_tags(qtbot, panel)
    assert panel.status_label.text() == "Tagging stopped by an unexpected error: boom"


def test_emptied_mixed_field_is_not_an_edit(qtbot: QtBot):
    panel = make_tag_panel(qtbot)
    select_rows(panel, 0, 1)
    type_tag(panel, TagField.TITLE, "Z")
    type_tag(panel, TagField.TITLE, "")
    assert not panel.tag_form.apply_button.isEnabled()
    assert get_cell(panel, 0, TITLE_COLUMN) == "One"


def test_field_back_to_loaded_value_is_not_an_edit(qtbot: QtBot):
    panel = make_tag_panel(qtbot)
    select_rows(panel, 0)
    type_tag(panel, TagField.TITLE, "Onex")
    type_tag(panel, TagField.TITLE, "One")
    assert not panel.tag_form.apply_button.isEnabled()
    assert not panel.tag_form.reset_button.isEnabled()


def test_clear_action_is_offered_for_fields_with_a_value(qtbot: QtBot):
    panel = make_tag_panel(qtbot)
    select_rows(panel, 0, 1)
    assert panel.tag_form.clear_actions[TagField.TITLE].isVisible()
    assert panel.tag_form.clear_actions[TagField.ARTIST].isVisible()
    assert not panel.tag_form.clear_actions[TagField.GENRE].isVisible()


def test_clear_action_removes_shared_comment(qtbot: QtBot):
    store = FakeTagStore({SONG_A: {TagField.COMMENT: "https://youtu.be/x"}})
    panel = make_tag_panel(qtbot, store)
    select_rows(panel, 0)
    panel.tag_form.clear_actions[TagField.COMMENT].trigger()
    comment_input = panel.tag_form.field_inputs[TagField.COMMENT]
    assert comment_input.text() == ""
    assert comment_input.placeholderText() == "<removed>"
    assert get_cell(panel, 0, COMMENT_COLUMN) == ""
    apply_tags(qtbot, panel)
    assert store.tags[SONG_A][TagField.COMMENT] == ""


def test_clear_action_removes_mixed_field_from_all_selected(qtbot: QtBot):
    store = FakeTagStore(STORED_TAGS)
    panel = make_tag_panel(qtbot, store)
    select_rows(panel, 0, 1)
    panel.tag_form.clear_actions[TagField.TITLE].trigger()
    title_input = panel.tag_form.field_inputs[TagField.TITLE]
    assert title_input.placeholderText() == "<removed>"
    assert get_cell(panel, 1, TITLE_COLUMN) == ""
    apply_tags(qtbot, panel)
    assert store.tags[SONG_A][TagField.TITLE] == ""
    assert store.tags[SONG_B][TagField.TITLE] == ""


def test_typing_after_clear_replaces_removal(qtbot: QtBot):
    panel = make_tag_panel(qtbot)
    select_rows(panel, 0, 1)
    panel.tag_form.clear_actions[TagField.TITLE].trigger()
    type_tag(panel, TagField.TITLE, "Z")
    assert get_cell(panel, 0, TITLE_COLUMN) == "Z"


def test_problem_is_cleared_on_selection_change(qtbot: QtBot):
    panel = make_tag_panel(qtbot)
    select_rows(panel, 0)
    type_tag(panel, TagField.YEAR, "20")
    select_rows(panel, 1)
    assert panel.tag_form.problem_label.text() == ""


def test_valid_typing_keeps_previous_status(qtbot: QtBot):
    panel = make_tag_panel(qtbot)
    select_rows(panel, 0)
    panel.show_status("2 moved, 0 skipped, 0 failed.")
    type_tag(panel, TagField.YEAR, "20")
    type_tag(panel, TagField.YEAR, "2021")
    assert panel.status_label.text() == "2 moved, 0 skipped, 0 failed."


def test_crash_refreshes_tags_of_every_file_of_the_job(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
):
    store = FakeTagStore(STORED_TAGS)

    def write_then_crash(path: Path, edits: Tags, tag_store: TagStore) -> TagOutcome:
        store.write(path, edits)
        raise RuntimeError("boom")

    monkeypatch.setattr(tag_job, "write_tag_edits", write_then_crash)
    panel = make_tag_panel(qtbot, store)
    select_rows(panel, 0)
    get_cell(panel, 0, GENRE_COLUMN)
    type_tag(panel, TagField.GENRE, "Rock")
    apply_tags(qtbot, panel)
    assert get_cell(panel, 0, GENRE_COLUMN, Qt.ItemDataRole.ForegroundRole) is None
    assert get_cell(panel, 0, GENRE_COLUMN) == "Rock"


def test_cleared_field_stays_removed_after_typing_and_deleting(qtbot: QtBot):
    panel = make_tag_panel(qtbot)
    select_rows(panel, 0, 1)
    panel.tag_form.clear_actions[TagField.TITLE].trigger()
    type_tag(panel, TagField.TITLE, "Z")
    type_tag(panel, TagField.TITLE, "")
    assert panel.tag_form.field_inputs[TagField.TITLE].placeholderText() == "<removed>"
    assert panel.tag_form.apply_button.isEnabled()


def test_finished_download_keeps_pending_edits(qtbot: QtBot):
    store = FakeTagStore(STORED_TAGS)
    panel = make_tag_panel(qtbot, store)
    select_rows(panel, 0)
    type_tag(panel, TagField.GENRE, "Rock")
    store.tags[SONG_B] = {TagField.TITLE: "New"}
    panel.add_downloaded_file(SONG_B)
    assert get_input_text(panel, TagField.GENRE) == "Rock"
    assert get_cell(panel, 1, TITLE_COLUMN) == "New"


QUEEN = Path("/music/Queen - Jazz.mp3")
FREDDIE = Path("/music/Freddie - Mustapha.mp3")
UNNAMED = Path("/music/untitled.mp3")


def make_named_panel(qtbot: QtBot, store: FakeTagStore | None = None) -> LibraryPanel:
    panel = make_panel(qtbot, tag_store=store or FakeTagStore())
    for path in (QUEEN, FREDDIE, UNNAMED):
        panel.add_downloaded_file(path)
    return panel


def get_artist_and_title(panel: LibraryPanel, row: int) -> tuple[object, object]:
    return get_cell(panel, row, ARTIST_COLUMN), get_cell(panel, row, TITLE_COLUMN)


def test_tags_from_name_previews_each_file_own_values(qtbot: QtBot):
    panel = make_named_panel(qtbot)
    select_rows(panel, 0, 1)
    panel.tag_form.tags_from_name_button.click()
    assert get_artist_and_title(panel, 0) == ("Queen", "Jazz")
    assert get_artist_and_title(panel, 1) == ("Freddie", "Mustapha")
    artist_input = panel.tag_form.field_inputs[TagField.ARTIST]
    assert artist_input.text() == ""
    assert artist_input.placeholderText() == "<from file names>"
    assert panel.tag_form.apply_button.isEnabled()
    assert panel.tag_form.reset_button.isEnabled()


def test_tags_from_name_are_written_per_file(qtbot: QtBot):
    store = FakeTagStore({QUEEN: {TagField.GENRE: "Rock"}})
    panel = make_named_panel(qtbot, store)
    select_rows(panel, 0, 1)
    panel.tag_form.tags_from_name_button.click()
    apply_tags(qtbot, panel)
    assert store.tags[QUEEN] == {
        TagField.GENRE: "Rock",
        TagField.ARTIST: "Queen",
        TagField.TITLE: "Jazz",
    }
    assert store.tags[FREDDIE] == {TagField.ARTIST: "Freddie", TagField.TITLE: "Mustapha"}
    assert panel.status_label.text() == "2 tagged, 0 failed."


def test_tags_from_name_of_one_file_fill_the_fields(qtbot: QtBot):
    panel = make_named_panel(qtbot)
    select_rows(panel, 0)
    panel.tag_form.tags_from_name_button.click()
    assert get_input_text(panel, TagField.ARTIST) == "Queen"
    assert get_input_text(panel, TagField.TITLE) == "Jazz"


def test_tags_from_name_leave_out_files_without_artist_and_title(qtbot: QtBot):
    store = FakeTagStore()
    panel = make_named_panel(qtbot, store)
    select_rows(panel, 0, 2)
    panel.tag_form.tags_from_name_button.click()
    assert panel.status_label.text() == '1 left out: name is not "Artist - Title".'
    assert get_input_text(panel, TagField.ARTIST) == ""
    assert get_artist_and_title(panel, 2) == ("", "")
    apply_tags(qtbot, panel)
    assert UNNAMED not in store.tags
    assert panel.status_label.text() == "1 tagged, 0 failed."


def test_tags_from_name_without_any_match_is_not_an_edit(qtbot: QtBot):
    panel = make_named_panel(qtbot)
    select_rows(panel, 2)
    panel.tag_form.tags_from_name_button.click()
    assert not panel.tag_form.apply_button.isEnabled()
    assert panel.tag_form.field_inputs[TagField.ARTIST].placeholderText() == ""


def test_typed_field_overrides_tags_from_name(qtbot: QtBot):
    panel = make_named_panel(qtbot)
    select_rows(panel, 0, 1)
    panel.tag_form.tags_from_name_button.click()
    type_tag(panel, TagField.ARTIST, "Band")
    assert get_artist_and_title(panel, 0) == ("Band", "Jazz")
    assert get_artist_and_title(panel, 1) == ("Band", "Mustapha")
    assert panel.tag_form.field_inputs[TagField.TITLE].placeholderText() == "<from file names>"


def test_reset_drops_tags_from_name(qtbot: QtBot):
    panel = make_named_panel(qtbot)
    select_rows(panel, 0, 1)
    panel.tag_form.tags_from_name_button.click()
    panel.tag_form.reset_button.click()
    assert get_artist_and_title(panel, 0) == ("", "")
    assert not panel.tag_form.apply_button.isEnabled()


def test_name_buttons_need_a_selection(qtbot: QtBot):
    panel = make_named_panel(qtbot)
    assert not panel.tag_form.tags_from_name_button.isEnabled()
    assert not panel.tag_form.name_from_tags_button.isEnabled()
    select_rows(panel, 0)
    assert panel.tag_form.tags_from_name_button.isEnabled()
    assert panel.tag_form.name_from_tags_button.isEnabled()


OLD_ARTIST = {TagField.ARTIST: "Old"}


@pytest.mark.parametrize("rows", [(0,), (0, 1)])
def test_typing_the_original_value_overrides_tags_from_name(qtbot: QtBot, rows: tuple[int, ...]):
    store = FakeTagStore({QUEEN: OLD_ARTIST, FREDDIE: OLD_ARTIST})
    panel = make_named_panel(qtbot, store)
    select_rows(panel, *rows)
    panel.tag_form.tags_from_name_button.click()
    type_tag(panel, TagField.ARTIST, "Old")
    assert {get_cell(panel, row, ARTIST_COLUMN) for row in rows} == {"Old"}


def test_erasing_a_typed_field_goes_back_to_tags_from_name(qtbot: QtBot):
    store = FakeTagStore({QUEEN: OLD_ARTIST, FREDDIE: OLD_ARTIST})
    panel = make_named_panel(qtbot, store)
    select_rows(panel, 0, 1)
    panel.tag_form.tags_from_name_button.click()
    type_tag(panel, TagField.ARTIST, "X")
    type_tag(panel, TagField.ARTIST, "")
    artist_input = panel.tag_form.field_inputs[TagField.ARTIST]
    assert artist_input.placeholderText() == "<from file names>"
    assert get_artist_and_title(panel, 0) == ("Queen", "Jazz")


def test_clear_action_drops_one_field_from_names(qtbot: QtBot):
    store = FakeTagStore()
    panel = make_named_panel(qtbot, store)
    select_rows(panel, 0)
    panel.tag_form.tags_from_name_button.click()
    assert panel.tag_form.clear_actions[TagField.ARTIST].isVisible()
    panel.tag_form.clear_actions[TagField.ARTIST].trigger()
    assert get_artist_and_title(panel, 0) == ("", "Jazz")


def test_tags_from_name_skip_values_already_tagged(qtbot: QtBot):
    store = FakeTagStore({QUEEN: {TagField.ARTIST: "Queen", TagField.TITLE: "Jazz"}})
    panel = make_named_panel(qtbot, store)
    select_rows(panel, 0)
    panel.tag_form.tags_from_name_button.click()
    assert get_input_text(panel, TagField.ARTIST) == "Queen"
    assert not panel.tag_form.apply_button.isEnabled()
    assert panel.status_label.text() == ""


def test_tags_from_name_keep_fields_without_name_values(qtbot: QtBot):
    panel = make_named_panel(qtbot, FakeTagStore({UNNAMED: OLD_ARTIST}))
    select_rows(panel, 2)
    type_tag(panel, TagField.GENRE, "Rock")
    panel.tag_form.tags_from_name_button.click()
    assert get_input_text(panel, TagField.ARTIST) == "Old"
    type_tag(panel, TagField.ARTIST, "X")
    type_tag(panel, TagField.ARTIST, "Old")
    assert get_cell(panel, 2, ARTIST_COLUMN, Qt.ItemDataRole.ForegroundRole) is None


def test_clearing_a_missing_tag_writes_nothing(qtbot: QtBot):
    store = FakeTagStore()
    panel = make_named_panel(qtbot, store)
    select_rows(panel, 0, 2)
    panel.tag_form.tags_from_name_button.click()
    panel.tag_form.clear_actions[TagField.ARTIST].trigger()
    apply_tags(qtbot, panel)
    assert UNNAMED not in store.tags
    assert panel.status_label.text() == "1 tagged, 0 failed."


def test_typing_the_current_value_is_not_written(qtbot: QtBot):
    store = FakeTagStore({QUEEN: {TagField.ARTIST: "Old", TagField.TITLE: "Jazz"}})
    panel = make_named_panel(qtbot, store)
    select_rows(panel, 0)
    panel.tag_form.tags_from_name_button.click()
    type_tag(panel, TagField.ARTIST, "Old")
    assert not panel.tag_form.apply_button.isEnabled()
