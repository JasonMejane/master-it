from pathlib import Path

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QColor
from pytestqt.qtbot import QtBot

from masterit.download.events import (
    ItemCompleted,
    ItemFailed,
    ItemProgress,
    ItemQueued,
    ItemRef,
    ItemSkipped,
    LinkStarted,
)
from masterit.download.skip_list import SkipList
from masterit.gui.download_table_model import DownloadTableModel

SONG = ItemRef("id1", "Song")
CHECK_ROLE = Qt.ItemDataRole.CheckStateRole


def record_insertions(model: DownloadTableModel) -> list[tuple[int, int]]:
    insertions: list[tuple[int, int]] = []

    def record(parent: QModelIndex, first: int, last: int) -> None:
        insertions.append((first, last))

    model.rowsInserted.connect(record)
    return insertions


def get_text(model: DownloadTableModel, row: int, column: int) -> object:
    return model.data(model.index(row, column + 1))


def get_check(model: DownloadTableModel, row: int) -> object:
    return model.data(model.index(row, 0), CHECK_ROLE)


def set_check(model: DownloadTableModel, row: int, state: Qt.CheckState) -> bool:
    return model.setData(model.index(row, 0), state.value, CHECK_ROLE)


def test_model_has_check_title_status_and_details_columns():
    model = DownloadTableModel()
    headers = [
        model.headerData(column, Qt.Orientation.Horizontal) for column in range(model.columnCount())
    ]
    assert headers == ["", "Title", "Status", "Details"]


def test_vertical_header_is_default():
    assert DownloadTableModel().headerData(0, Qt.Orientation.Vertical) is None


def test_new_item_inserts_row(qtbot: QtBot):
    model = DownloadTableModel()
    with qtbot.waitSignal(model.rowsInserted):
        model.apply_event(ItemProgress("a", SONG, 42.4))
    assert [get_text(model, 0, column) for column in range(3)] == ["Song", "Downloading 42%", ""]


def test_known_item_updates_row(qtbot: QtBot):
    model = DownloadTableModel()
    model.apply_event(ItemProgress("a", SONG, 10.0))
    with qtbot.waitSignal(model.dataChanged):
        model.apply_event(ItemCompleted("a", SONG, Path("/music/Song.mp3")))
    assert model.rowCount() == 1
    assert get_text(model, 0, 1) == "Done"


def test_status_labels():
    model = DownloadTableModel()
    model.apply_event(ItemCompleted("a", SONG, Path("/x.mp3"), ("no cover",)))
    model.apply_event(ItemFailed("b", None, "boom"))
    assert [get_text(model, row, 1) for row in range(2)] == ["Done with warnings", "Failed"]


def test_details_are_also_tooltips():
    model = DownloadTableModel()
    model.apply_event(ItemFailed("b", None, "boom"))
    assert model.data(model.index(0, 3), Qt.ItemDataRole.ToolTipRole) == "boom"


def test_failed_rows_are_red_and_others_default():
    model = DownloadTableModel()
    model.apply_event(ItemFailed("b", None, "boom"))
    model.apply_event(ItemProgress("a", SONG, 1.0))
    role = Qt.ItemDataRole.ForegroundRole
    assert model.data(model.index(0, 0), role) == QColor(Qt.GlobalColor.red)
    assert model.data(model.index(1, 0), role) is None


def test_unhandled_role_and_invalid_index_return_none():
    model = DownloadTableModel()
    model.apply_event(ItemProgress("a", SONG, 1.0))
    assert model.data(model.index(0, 0), Qt.ItemDataRole.DecorationRole) is None
    assert model.data(QModelIndex()) is None


def test_child_indexes_have_no_rows():
    model = DownloadTableModel()
    model.apply_event(ItemProgress("a", SONG, 1.0))
    assert model.rowCount(model.index(0, 0)) == 0
    assert model.columnCount(model.index(0, 0)) == 0


def test_clear_resets_model(qtbot: QtBot):
    model = DownloadTableModel()
    model.apply_event(ItemProgress("a", SONG, 1.0))
    with qtbot.waitSignal(model.modelReset):
        model.clear()
    assert model.rowCount() == 0


def test_summary_comes_from_rows():
    model = DownloadTableModel()
    model.apply_event(ItemFailed("b", None, "boom"))
    assert model.get_summary().failed == 1


def test_cancelling_unfinished_rows_updates_view(qtbot: QtBot):
    model = DownloadTableModel()
    model.apply_event(ItemProgress("a", SONG, 40.0))
    with qtbot.waitSignal(model.dataChanged):
        model.mark_unfinished_cancelled()
    assert get_text(model, 0, 1) == "Cancelled"


def test_cancelling_empty_model_emits_nothing(qtbot: QtBot):
    model = DownloadTableModel()
    with qtbot.assertNotEmitted(model.dataChanged):
        model.mark_unfinished_cancelled()


def test_links_are_inserted_as_pending_rows(qtbot: QtBot):
    model = DownloadTableModel()
    insertions = record_insertions(model)
    model.add_links(["a", "b"])
    assert insertions == [(0, 1)]
    assert [get_text(model, row, 1) for row in range(2)] == ["Pending", "Pending"]
    role = Qt.ItemDataRole.ForegroundRole
    assert model.data(model.index(0, 0), role) == QColor(Qt.GlobalColor.gray)


def test_no_links_insert_nothing(qtbot: QtBot):
    model = DownloadTableModel()
    with qtbot.assertNotEmitted(model.rowsInserted):
        model.add_links([])


def test_playlist_entries_are_inserted_after_their_link(qtbot: QtBot):
    model = DownloadTableModel()
    model.add_links(["a", "b"])
    model.apply_event(ItemQueued("a", SONG))
    insertions = record_insertions(model)
    model.apply_event(ItemQueued("a", ItemRef("id2", "Other")))
    assert insertions == [(1, 1)]
    assert [get_text(model, row, 0) for row in range(3)] == ["Song", "Other", "b"]


def test_pending_rows_left_at_the_end_fail(qtbot: QtBot):
    model = DownloadTableModel()
    model.add_links(["a"])
    with qtbot.waitSignal(model.dataChanged):
        model.mark_pending_failed()
    assert get_text(model, 0, 1) == "Failed"
    assert get_text(model, 0, 2) == "Not downloaded"


def test_failing_pending_rows_of_empty_model_emits_nothing(qtbot: QtBot):
    model = DownloadTableModel()
    with qtbot.assertNotEmitted(model.dataChanged):
        model.mark_pending_failed()


def test_skip_labels():
    model = DownloadTableModel()
    model.add_links(["a", "b"])
    model.set_skip_list(SkipList())
    set_check(model, 0, Qt.CheckState.Unchecked)
    model.apply_event(ItemSkipped("b", None))
    assert [get_text(model, row, 1) for row in range(2)] == ["Will skip", "Skipped"]


def test_pending_rows_have_no_checkbox_without_skip_list():
    model = DownloadTableModel()
    model.add_links(["a"])
    assert get_check(model, 0) is None
    assert not model.flags(model.index(0, 0)) & Qt.ItemFlag.ItemIsUserCheckable
    assert not set_check(model, 0, Qt.CheckState.Unchecked)
    assert get_text(model, 0, 1) == "Pending"


def test_pending_rows_are_checked_and_checkable_during_download(qtbot: QtBot):
    model = DownloadTableModel()
    model.add_links(["a"])
    with qtbot.waitSignal(model.dataChanged):
        model.set_skip_list(SkipList())
    assert get_check(model, 0) == Qt.CheckState.Checked
    assert model.flags(model.index(0, 0)) & Qt.ItemFlag.ItemIsUserCheckable


def test_only_check_column_is_checkable():
    model = DownloadTableModel()
    model.add_links(["a"])
    model.set_skip_list(SkipList())
    assert model.data(model.index(0, 1), CHECK_ROLE) is None
    assert not model.flags(model.index(0, 1)) & Qt.ItemFlag.ItemIsUserCheckable
    assert not model.setData(model.index(0, 1), Qt.CheckState.Unchecked.value, CHECK_ROLE)


def test_unchecking_requests_skip_and_checking_cancels_it(qtbot: QtBot):
    model = DownloadTableModel()
    model.add_links(["a"])
    skip_list = SkipList()
    model.set_skip_list(skip_list)
    with qtbot.waitSignal(model.dataChanged):
        assert set_check(model, 0, Qt.CheckState.Unchecked)
    assert (get_check(model, 0), get_text(model, 0, 1)) == (Qt.CheckState.Unchecked, "Will skip")
    assert skip_list.is_skipped("a", None)
    assert set_check(model, 0, Qt.CheckState.Checked)
    assert get_text(model, 0, 1) == "Pending"
    assert not skip_list.is_skipped("a", None)


def test_setting_current_check_state_changes_nothing(qtbot: QtBot):
    model = DownloadTableModel()
    model.add_links(["a"])
    model.set_skip_list(SkipList())
    with qtbot.assertNotEmitted(model.dataChanged):
        assert set_check(model, 0, Qt.CheckState.Checked)
    assert get_text(model, 0, 1) == "Pending"


def test_downloading_rows_have_no_checkbox():
    model = DownloadTableModel()
    model.set_skip_list(SkipList())
    model.apply_event(ItemProgress("b", SONG, 1.0))
    assert get_check(model, 0) is None
    assert not set_check(model, 0, Qt.CheckState.Unchecked)


def test_removing_skip_list_hides_checkboxes():
    model = DownloadTableModel()
    model.add_links(["a"])
    model.set_skip_list(SkipList())
    model.set_skip_list(None)
    assert get_check(model, 0) is None


def test_started_link_label():
    model = DownloadTableModel()
    model.add_links(["a"])
    model.apply_event(LinkStarted("a"))
    assert get_text(model, 0, 1) == "Starting"


def test_check_change_by_user_is_announced(qtbot: QtBot):
    model = DownloadTableModel()
    model.add_links(["a"])
    model.set_skip_list(SkipList())
    announced: list[tuple[int, bool]] = []

    def record(row: int, checked: bool) -> None:
        announced.append((row, checked))

    model.check_changed.connect(record)
    set_check(model, 0, Qt.CheckState.Unchecked)
    assert announced == [(0, False)]


def test_unchanged_check_is_not_announced(qtbot: QtBot):
    model = DownloadTableModel()
    model.add_links(["a"])
    model.set_skip_list(SkipList())
    with qtbot.assertNotEmitted(model.check_changed):
        set_check(model, 0, Qt.CheckState.Checked)


def test_rows_are_checked_together_without_announcing(qtbot: QtBot):
    model = DownloadTableModel()
    model.add_links(["a", "b", "c"])
    model.apply_event(ItemProgress("c", SONG, 1.0))
    model.set_skip_list(SkipList())
    set_check(model, 1, Qt.CheckState.Unchecked)
    with qtbot.assertNotEmitted(model.check_changed):
        model.set_rows_checked([0, 1, 2], checked=False)
    assert [get_text(model, row, 1) for row in range(3)] == [
        "Will skip",
        "Will skip",
        "Downloading 1%",
    ]
