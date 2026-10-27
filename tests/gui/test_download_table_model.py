from pathlib import Path

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QColor
from pytestqt.qtbot import QtBot

from masterit.download.events import ItemCompleted, ItemFailed, ItemProgress, ItemQueued, ItemRef
from masterit.gui.download_table_model import DownloadTableModel

SONG = ItemRef("id1", "Song")


def record_insertions(model: DownloadTableModel) -> list[tuple[int, int]]:
    insertions: list[tuple[int, int]] = []

    def record(parent: QModelIndex, first: int, last: int) -> None:
        insertions.append((first, last))

    model.rowsInserted.connect(record)
    return insertions


def get_text(model: DownloadTableModel, row: int, column: int) -> object:
    return model.data(model.index(row, column))


def test_model_has_title_status_and_details_columns():
    model = DownloadTableModel()
    headers = [
        model.headerData(column, Qt.Orientation.Horizontal) for column in range(model.columnCount())
    ]
    assert headers == ["Title", "Status", "Details"]


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
    assert model.data(model.index(0, 2), Qt.ItemDataRole.ToolTipRole) == "boom"


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
