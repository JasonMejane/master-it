from pathlib import Path

import pytest
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QColor
from pytestqt.qtbot import QtBot

from masterit.gui.library_table_model import LibraryTableModel
from masterit.library.relocation import Relocation, RelocationPlan, RelocationProblem
from masterit.tags.fields import TagField
from masterit.tags.tag_cache import TagCache

from ..tags.fakes import FakeTagStore

ROOT = Path("/music")
SONG = ROOT / "list" / "Song.mp3"
OTHER = ROOT / "Other.mp3"


def make_model(root: Path | None = ROOT, store: FakeTagStore | None = None) -> LibraryTableModel:
    model = LibraryTableModel(TagCache(store or FakeTagStore()))
    model.set_files([SONG, OTHER], root)
    return model


def get_row_texts(model: LibraryTableModel, row: int) -> list[object]:
    return [model.data(model.index(row, column)) for column in range(3)]


def get_tag_texts(model: LibraryTableModel, row: int) -> list[object]:
    return [model.data(model.index(row, column)) for column in range(3, model.columnCount())]


def test_headers():
    model = LibraryTableModel(TagCache(FakeTagStore()))
    columns = range(model.columnCount())
    headers = [model.headerData(column, Qt.Orientation.Horizontal) for column in columns]
    assert headers == [
        "Name",
        "New name",
        "Folder",
        "Title",
        "Artist",
        "Album",
        "Album artist",
        "Year",
        "Genre",
        "Track",
    ]
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
    plan = RelocationPlan(
        (
            Relocation(SONG, ROOT / "list" / "X Song.mp3"),
            Relocation(OTHER, ROOT / "X.mp3", RelocationProblem.TARGET_EXISTS),
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
    model = LibraryTableModel(TagCache(FakeTagStore()))
    with qtbot.assertNotEmitted(model.dataChanged):
        model.set_preview(RelocationPlan(()))


def test_get_files_returns_listed_files():
    assert make_model().get_files() == [SONG, OTHER]


def test_folder_is_relative_through_symlinked_root(tmp_path: Path):
    (tmp_path / "real/list").mkdir(parents=True)
    (tmp_path / "link").symlink_to(tmp_path / "real")
    model = LibraryTableModel(TagCache(FakeTagStore()))
    model.set_files([tmp_path / "real/list/Song.mp3"], tmp_path / "link")
    assert model.data(model.index(0, 2)) == "list"


def test_folder_text_is_computed_once_not_on_every_paint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    model = LibraryTableModel(TagCache(FakeTagStore()))
    model.set_files([tmp_path / "list/Song.mp3"], tmp_path)
    model.append_file(tmp_path / "Other.mp3")

    def fail_resolve(self: Path, strict: bool = False) -> Path:
        raise AssertionError("resolve called while painting")

    monkeypatch.setattr(Path, "resolve", fail_resolve)
    assert [model.data(model.index(row, 2)) for row in range(2)] == ["list", ""]


TAGGED_STORE_TAGS = {SONG: {TagField.TITLE: "Song", TagField.ARTIST: "Artist", TagField.TRACK: "3"}}


def test_tag_columns_show_file_tags():
    model = make_model(store=FakeTagStore(TAGGED_STORE_TAGS))
    assert get_tag_texts(model, 0) == ["Song", "Artist", "", "", "", "", "3"]
    assert get_tag_texts(model, 1) == [""] * 7


def test_tag_preview_shows_edits_highlighted_on_given_files_only(qtbot: QtBot):
    model = make_model(store=FakeTagStore(TAGGED_STORE_TAGS))
    with qtbot.waitSignal(model.dataChanged):
        model.set_tag_preview([SONG], {TagField.ARTIST: "New", TagField.TRACK: ""})
    assert get_tag_texts(model, 0) == ["Song", "New", "", "", "", "", ""]
    assert get_tag_texts(model, 1) == [""] * 7
    role = Qt.ItemDataRole.ForegroundRole
    assert model.data(model.index(0, 4), role) == QColor(Qt.GlobalColor.blue)
    assert model.data(model.index(0, 3), role) is None
    assert model.data(model.index(1, 4), role) is None


def test_tag_preview_is_cleared_by_new_files():
    model = make_model()
    model.set_tag_preview([SONG], {TagField.ARTIST: "New"})
    model.set_files([SONG], ROOT)
    assert get_tag_texts(model, 0)[1] == ""


def test_refresh_tags_reads_files_again(qtbot: QtBot):
    store = FakeTagStore(TAGGED_STORE_TAGS)
    model = make_model(store=store)
    get_tag_texts(model, 0)
    store.tags[SONG] = {TagField.TITLE: "Changed"}
    with qtbot.waitSignal(model.dataChanged):
        model.refresh_tags([SONG])
    assert get_tag_texts(model, 0)[0] == "Changed"


def test_new_files_read_tags_again():
    store = FakeTagStore(TAGGED_STORE_TAGS)
    model = make_model(store=store)
    get_tag_texts(model, 0)
    model.set_files([SONG], ROOT)
    get_tag_texts(model, 0)
    assert store.reads.count(SONG) == 2


def test_tag_columns_are_not_editable():
    model = make_model()
    assert not model.flags(model.index(0, 3)) & Qt.ItemFlag.ItemIsEditable


def test_tags_of_a_file_are_shared_for_selection():
    model = make_model(store=FakeTagStore(TAGGED_STORE_TAGS))
    assert model.get_tags(SONG) == TAGGED_STORE_TAGS[SONG]
