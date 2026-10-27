from pathlib import Path

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QColor
from pytestqt.qtbot import QtBot

from masterit.download.events import ItemCompleted, ItemFailed, ItemProgress, ItemRef
from masterit.gui.download_table_model import DownloadTableModel

SONG = ItemRef("id1", "Song")


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
