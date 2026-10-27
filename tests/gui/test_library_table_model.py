from pathlib import Path

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QColor
from pytestqt.qtbot import QtBot

from masterit.gui.library_table_model import LibraryTableModel
from masterit.library.rename_plan import RenameEntry, RenamePlan, RenameProblem

ROOT = Path("/music")
SONG = ROOT / "list" / "Song.mp3"
OTHER = ROOT / "Other.mp3"


def make_model(root: Path | None = ROOT) -> LibraryTableModel:
    model = LibraryTableModel()
    model.set_files([SONG, OTHER], root)
    return model


def get_row_texts(model: LibraryTableModel, row: int) -> list[object]:
    return [model.data(model.index(row, column)) for column in range(model.columnCount())]


def test_headers():
    model = LibraryTableModel()
    headers = [model.headerData(column, Qt.Orientation.Horizontal) for column in range(3)]
    assert headers == ["Name", "New name", "Folder"]
    assert model.headerData(0, Qt.Orientation.Vertical) is None


def test_rows_show_name_and_folder_relative_to_root():
    model = make_model()
    assert get_row_texts(model, 0) == ["Song.mp3", "", "list"]
    assert get_row_texts(model, 1) == ["Other.mp3", "", ""]


def test_folder_is_full_path_without_root():
    assert get_row_texts(make_model(None), 0)[2] == "/music/list"


def test_get_path_returns_row_file():
    assert make_model().get_path(1) == OTHER


def test_append_file_inserts_row(qtbot: QtBot):
    model = make_model()
    with qtbot.waitSignal(model.rowsInserted):
        model.append_file(ROOT / "New.mp3")
    assert model.rowCount() == 3


def test_preview_shows_new_names_and_problems(qtbot: QtBot):
    model = make_model()
    plan = RenamePlan(
        (
            RenameEntry(SONG, ROOT / "list" / "X Song.mp3"),
            RenameEntry(OTHER, ROOT / "X.mp3", RenameProblem.TARGET_EXISTS),
        )
    )
    with qtbot.waitSignal(model.dataChanged):
        model.set_preview(plan)
    assert model.data(model.index(0, 1)) == "X Song.mp3"
    assert model.data(model.index(1, 1)) == "⚠ A file with this name already exists"
    role = Qt.ItemDataRole.ForegroundRole
    assert model.data(model.index(1, 1), role) == QColor(Qt.GlobalColor.red)
    assert model.data(model.index(0, 1), role) is None


def test_only_name_column_is_editable_with_stem():
    model = make_model()
    assert model.flags(model.index(0, 0)) & Qt.ItemFlag.ItemIsEditable
    assert not model.flags(model.index(0, 1)) & Qt.ItemFlag.ItemIsEditable
    assert model.data(model.index(0, 0), Qt.ItemDataRole.EditRole) == "Song"


def test_editing_name_requests_rename_without_changing_model():
    model = make_model()
    requests: list[tuple[Path, str]] = []

    def record_request(path: Path, name: str) -> None:
        requests.append((path, name))

    model.rename_requested.connect(record_request)
    assert not model.setData(model.index(0, 0), "New", Qt.ItemDataRole.EditRole)
    assert requests == [(SONG, "New")]
    assert model.data(model.index(0, 0)) == "Song.mp3"


def test_editing_other_columns_or_roles_is_ignored(qtbot: QtBot):
    model = make_model()
    with qtbot.assertNotEmitted(model.rename_requested):
        assert not model.setData(model.index(0, 1), "New", Qt.ItemDataRole.EditRole)
        assert not model.setData(model.index(0, 0), "New", Qt.ItemDataRole.DisplayRole)


def test_invalid_index_and_child_counts():
    model = make_model()
    assert model.data(QModelIndex()) is None
    assert model.data(model.index(0, 0), Qt.ItemDataRole.DecorationRole) is None
    assert model.rowCount(model.index(0, 0)) == 0
    assert model.columnCount(model.index(0, 0)) == 0
    assert model.flags(QModelIndex()) == Qt.ItemFlag.NoItemFlags


def test_preview_on_empty_model_emits_nothing(qtbot: QtBot):
    model = LibraryTableModel()
    with qtbot.assertNotEmitted(model.dataChanged):
        model.set_preview(RenamePlan(()))


def test_get_files_returns_listed_files():
    assert make_model().get_files() == [SONG, OTHER]
